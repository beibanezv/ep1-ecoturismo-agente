"""Replanificador (Fase 4): ante conflicto, busca y valida una alternativa.

Criterios de viabilidad de un paquete candidato (todos duros, verificables):
1. Diferente al paquete conflictado.
2. Temporada: el mes de la fecha debe estar en "temporada" del paquete.
3. Senderos: ninguno de sus senderos en estado "cerrado".
4. Guia: el guia asignado debe tener agenda para la fecha.
5. Clima: sin conflicto climatico en su region (si hay datos).

El primer candidato viable por ranking semantico gana; cada verificacion
queda en trace.jsonl y se entrega como (fuente, texto) para citar como [T#].
"""
from dataclasses import dataclass, field

from agent.retriever import Fragmento, Recuperador
from agent.trace import Trazador
from tools.guia_disponibilidad import NOMBRE_FUENTE as FUENTE_GUIAS
from tools.guia_disponibilidad import consultar_guia, describir_disponibilidad
from tools.trail_status import NOMBRE_FUENTE as FUENTE_SENDEROS
from tools.trail_status import estado_sendero
from tools.weather import describir_pronostico, es_conflicto_climatico

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


@dataclass
class ResultadoReplan:
    viable: bool
    paquete: dict | None = None
    fragmento: Fragmento | None = None
    herramientas: list[tuple[str, str]] = field(default_factory=list)
    motivo_conflicto: str = ""
    descartes: list[str] = field(default_factory=list)


class Replanificador:
    def __init__(
        self,
        recuperador: Recuperador,
        trazador: Trazador,
        proveedor_clima,
        cargar_paquete,
        k: int = 8,
    ):
        self.recuperador = recuperador
        self.trazador = trazador
        self.proveedor_clima = proveedor_clima
        self.cargar_paquete = cargar_paquete
        self.k = k

    def _evaluar(self, paquete: dict, fragmento: Fragmento, fecha: str | None) -> tuple[bool, list[tuple[str, str]], list[str]]:
        """Devuelve (viable, herramientas, conflictos) del candidato."""
        herramientas: list[tuple[str, str]] = []
        conflictos: list[str] = []

        if fecha:
            mes = MESES[int(fecha[5:7]) - 1]
            if mes not in paquete["temporada"]:
                conflictos.append(f"fuera de temporada ({mes} no esta en {', '.join(paquete['temporada'])})")
                return False, herramientas, conflictos

        for sid in sorted({d["sendero"] for d in paquete["itinerario"] if d.get("sendero")}):
            est = estado_sendero(sid)
            if est is None:
                continue
            self.trazador.registrar("herramienta", herramienta="estado_sendero", entrada=sid, salida=est["estado"], contexto="replan")
            herramientas.append((FUENTE_SENDEROS, f"[{paquete['id']}] {est['sendero_id']}: {est['estado']}"))
            if est["estado"] == "cerrado":
                conflictos.append(f"sendero cerrado: {sid}")

        if fecha:
            r_guia = consultar_guia(paquete["guia_asignado"], fecha)
            self.trazador.registrar("herramienta", herramienta="consultar_guia", entrada=paquete["guia_asignado"], salida=r_guia["disponible"], contexto="replan")
            herramientas.append((FUENTE_GUIAS, f"[{paquete['id']}] {describir_disponibilidad(r_guia)}"))
            if not r_guia["disponible"]:
                conflictos.append(f"guia no disponible: {r_guia.get('motivo')}")

            if self.proveedor_clima:
                clima = self.proveedor_clima(paquete["region"], fecha)
                self.trazador.registrar("herramienta", herramienta="pronostico_clima", entrada={"region": paquete["region"], "fecha": fecha}, salida="disponible" if clima.get("disponible") else f"no disponible: {clima.get('motivo')}", contexto="replan")
                herramientas.append((clima.get("fuente") or "clima", f"[{paquete['id']}] {describir_pronostico(clima)}"))
                hay, motivo = es_conflicto_climatico(clima)
                if hay:
                    conflictos.append(f"clima adverso en {paquete['region']}: {motivo}")

        return not conflictos, herramientas, conflictos

    def buscar_alternativa(
        self,
        consulta: str,
        fecha: str | None,
        paquete_conflictado_id: str,
        motivo_conflicto: str,
        fragmentos_previos: list[Fragmento],
    ) -> ResultadoReplan:
        self.trazador.registrar(
            "replan_inicio",
            origen=paquete_conflictado_id,
            motivo=motivo_conflicto,
            k=self.k,
        )

        nuevos = self.recuperador.buscar(consulta, k=self.k, filtro={"tipo": "paquete"})
        self.trazador.registrar(
            "recuperacion",
            paquete_ids=[f.fuente for f in nuevos],
            n_fragmentos=len(nuevos),
            contexto="replan",
        )

        # Orden: primero los ya rankeados en la consulta original, luego los nuevos.
        vistos: set[str] = set()
        orden: list[Fragmento] = []
        for f in [*fragmentos_previos, *nuevos]:
            if f.fuente not in vistos and f.tipo == "paquete":
                vistos.add(f.fuente)
                orden.append(f)

        descartes: list[str] = []
        for fragmento in orden:
            if fragmento.fuente == paquete_conflictado_id:
                continue
            paquete = self.cargar_paquete(fragmento.fuente)
            if paquete is None:
                continue
            viable, herramientas, conflictos = self._evaluar(paquete, fragmento, fecha)
            if viable:
                self.trazador.registrar(
                    "replanificacion",
                    origen=paquete_conflictado_id,
                    destino=paquete["id"],
                    motivo=motivo_conflicto,
                    criterio=f"candidato viable en evaluacion {len(descartes) + 1} de {len(orden) - 1}",
                )
                return ResultadoReplan(
                    viable=True,
                    paquete=paquete,
                    fragmento=fragmento,
                    herramientas=herramientas,
                    motivo_conflicto=motivo_conflicto,
                )
            descartes.append(f"{paquete['id']}: {'; '.join(conflictos)}")

        self.trazador.registrar(
            "replanificacion_fallida",
            origen=paquete_conflictado_id,
            motivo=motivo_conflicto,
            descartes=descartes,
        )
        return ResultadoReplan(viable=False, motivo_conflicto=motivo_conflicto, descartes=descartes)
