"""Loop razonamiento-accion (D8): recuperar -> verificar senderos/guia/clima ->
replanificar si hay conflicto -> responder.

Fase 4: ante conflicto, el Replanificador busca una alternativa viable
(senderos, guia, clima, temporada); si la encuentra, responde recomendando
el cambio con SISTEMA_REPLAN; si no, responde con honestidad informativa.
Cada paso queda registrado via Trazador en logs/trace.jsonl.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from agent.llm_client import ClienteGroq, ClienteLLM
from agent.observabilidad import traceable
from agent.prompts import SISTEMA_BASE, SISTEMA_REPLAN, armar_usuario
from agent.retriever import Fragmento, Recuperador
from agent.trace import Trazador
from tools.guia_disponibilidad import NOMBRE_FUENTE as FUENTE_GUIAS
from tools.guia_disponibilidad import consultar_guia, describir_disponibilidad
from tools.replanner import Replanificador, mes_de_fecha
from tools.trail_status import NOMBRE_FUENTE as FUENTE_SENDEROS
from tools.trail_status import describir_estado, estado_sendero
from tools.weather import NOMBRE_FUENTE as FUENTE_CLIMA
from tools.weather import describir_pronostico, es_conflicto_climatico, pronostico

RAIZ = Path(__file__).resolve().parents[1]
DIR_PAQUETES = RAIZ / "data" / "internal" / "paquetes"
REGEX_CITAS = re.compile(r"\[(F|T)(\d+)\]")


@dataclass
class PlanRespuesta:
    texto: str
    paquete_id: str | None
    conflicto: bool
    detalle_conflicto: str
    fuentes_citadas: list[str] = field(default_factory=list)
    archivo_trace: str = ""
    replanificado: bool = False
    paquete_original_id: str | None = None


class AgentePlanificador:
    def __init__(
        self,
        llm: ClienteLLM | None = None,
        trazador: Trazador | None = None,
        proveedor_clima=pronostico,
        k: int = 5,
    ):
        self.llm = llm or ClienteGroq()
        self.trazador = trazador or Trazador()
        self.proveedor_clima = proveedor_clima
        self.recuperador = Recuperador()
        self.k = k

    def _cargar_paquete(self, paquete_id: str) -> dict | None:
        archivos = sorted(DIR_PAQUETES.glob(f"{paquete_id}-*.json"))
        if not archivos:
            return None
        return json.loads(archivos[0].read_text(encoding="utf-8"))

    def _verificar_guia(self, paquete: dict, fecha: str, herramientas: list, conflictos: list) -> None:
        r = consultar_guia(paquete["guia_asignado"], fecha)
        self.trazador.registrar(
            "herramienta", herramienta="consultar_guia",
            entrada=paquete["guia_asignado"], salida=r["disponible"],
        )
        herramientas.append((FUENTE_GUIAS, describir_disponibilidad(r)))
        if not r["disponible"]:
            conflictos.append(f"guia no disponible: {r.get('motivo')}")

    def _extraer_fuentes(self, respuesta: str, fragmentos: list[Fragmento], herramientas: list) -> list[str]:
        fuentes: list[str] = []
        for letra, numero in REGEX_CITAS.findall(respuesta):
            n = int(numero)
            if letra == "F" and 1 <= n <= len(fragmentos):
                fuente = fragmentos[n - 1].fuente
            elif letra == "T" and 1 <= n <= len(herramientas):
                fuente = herramientas[n - 1][0]
            else:
                continue
            if fuente not in fuentes:
                fuentes.append(fuente)
        return fuentes

    def _responder(self, sistema: str, consulta: str, fecha: str | None, fragmentos: list[Fragmento], herramientas: list, detalle: str, paquete_id: str | None, paquete_original_id: str | None, replanificado: bool) -> PlanRespuesta:
        pedido = consulta + (f" Fecha del viaje: {fecha}." if fecha else "")
        usuario = armar_usuario(pedido, fragmentos, herramientas or None)
        respuesta = self.llm.completar(sistema, usuario)
        fuentes = self._extraer_fuentes(respuesta.texto, fragmentos, herramientas)
        self.trazador.registrar(
            "respuesta_final",
            paquete_id=paquete_id,
            replanificado=replanificado,
            conflicto=bool(detalle and detalle != "sin conflictos"),
            detalle_conflicto=detalle,
            fuentes_citadas=fuentes,
            modelo=respuesta.modelo,
        )
        return PlanRespuesta(
            texto=respuesta.texto,
            paquete_id=paquete_id,
            conflicto=bool(detalle and detalle != "sin conflictos"),
            detalle_conflicto=detalle,
            fuentes_citadas=fuentes,
            archivo_trace=str(self.trazador.archivo),
            replanificado=replanificado,
            paquete_original_id=paquete_original_id,
        )

    @traceable("planificar")
    def planificar(self, consulta: str, fecha: str | None = None) -> PlanRespuesta:
        self.trazador.registrar("consulta", texto=consulta, fecha=fecha)
        if fecha:
            mes_de_fecha(fecha)  # valida formato ISO; lanza ValueError si no lo es

        fragmentos = self.recuperador.buscar(consulta, k=self.k, filtro={"tipo": "paquete"})
        self.trazador.registrar(
            "recuperacion",
            paquete_ids=[f.fuente for f in fragmentos],
            n_fragmentos=len(fragmentos),
        )

        paquete = None
        paquete_id = fragmentos[0].fuente if fragmentos else None
        if paquete_id:
            paquete = self._cargar_paquete(paquete_id)

        herramientas: list[tuple[str, str]] = []
        conflictos: list[str] = []

        if paquete:
            senderos = sorted({d["sendero"] for d in paquete["itinerario"] if d.get("sendero")})
            for sid in senderos:
                est = estado_sendero(sid)
                if est is None:
                    # Sin estado conocido no se puede validar la seguridad del plan.
                    self.trazador.registrar(
                        "herramienta", herramienta="estado_sendero", entrada=sid, salida="desconocido"
                    )
                    herramientas.append((FUENTE_SENDEROS, f"Senda {sid}: estado desconocido."))
                    conflictos.append(f"sendero sin estado conocido: {sid}")
                    continue
                self.trazador.registrar(
                    "herramienta", herramienta="estado_sendero", entrada=sid, salida=est["estado"]
                )
                herramientas.append((FUENTE_SENDEROS, describir_estado(est)))
                if est["estado"] == "cerrado":
                    conflictos.append(f"sendero cerrado: {sid} ({est['motivo']})")

        if paquete and fecha:
            mes = mes_de_fecha(fecha)
            if mes not in paquete["temporada"]:
                conflictos.append(f"fuera de temporada: {mes} no esta en {', '.join(paquete['temporada'])}")

            clima = self.proveedor_clima(paquete["region"], fecha)
            self.trazador.registrar(
                "herramienta",
                herramienta="pronostico_clima",
                entrada={"region": paquete["region"], "fecha": fecha},
                salida="disponible" if clima.get("disponible") else f"no disponible: {clima.get('motivo')}",
            )
            herramientas.append((clima.get("fuente") or FUENTE_CLIMA, describir_pronostico(clima)))
            hay_conflicto, motivo = es_conflicto_climatico(clima)
            if hay_conflicto:
                conflictos.append(f"clima adverso en {paquete['region']}: {motivo}")

            self._verificar_guia(paquete, fecha, herramientas, conflictos)

        detalle = "sin conflictos" if not conflictos else " | ".join(conflictos)

        if conflictos and paquete_id:
            replan = Replanificador(
                recuperador=self.recuperador,
                trazador=self.trazador,
                proveedor_clima=self.proveedor_clima,
                cargar_paquete=self._cargar_paquete,
            )
            resultado = replan.buscar_alternativa(
                consulta=consulta,
                fecha=fecha,
                paquete_conflictado_id=paquete_id,
                motivo_conflicto=detalle,
                fragmentos_previos=fragmentos,
            )
            if resultado.viable:
                ctx_fragmentos = [resultado.fragmento]
                ctx_herramientas = resultado.herramientas
                self.trazador.registrar(
                    "seleccion_final",
                    paquete_id=resultado.paquete["id"],
                    conflictos_resueltos=detalle,
                )
                return self._responder(
                    sistema=SISTEMA_BASE + SISTEMA_REPLAN,
                    consulta=consulta,
                    fecha=fecha,
                    fragmentos=ctx_fragmentos,
                    herramientas=ctx_herramientas,
                    detalle=detalle,
                    paquete_id=resultado.paquete["id"],
                    paquete_original_id=paquete_id,
                    replanificado=True,
                )
            self.trazador.registrar(
                "seleccion_final",
                paquete_id=None,
                conflicto_irresoluble=detalle,
            )
            return self._responder(
                sistema=SISTEMA_BASE,
                consulta=consulta,
                fecha=fecha,
                fragmentos=[f for f in fragmentos if f.fuente == paquete_id] or fragmentos[:1],
                herramientas=herramientas,
                detalle=detalle,
                paquete_id=None,
                paquete_original_id=paquete_id,
                replanificado=False,
            )

        pedido_herramientas = herramientas
        usuario = consulta
        pedido = usuario + (f" Fecha del viaje: {fecha}." if fecha else "")
        usr = armar_usuario(pedido, fragmentos, pedido_herramientas or None)
        respuesta = self.llm.completar(SISTEMA_BASE, usr)
        fuentes = self._extraer_fuentes(respuesta.texto, fragmentos, herramientas)
        self.trazador.registrar(
            "respuesta_final",
            paquete_id=paquete_id,
            replanificado=False,
            conflicto=bool(conflictos),
            detalle_conflicto=detalle,
            fuentes_citadas=fuentes,
            modelo=respuesta.modelo,
        )
        return PlanRespuesta(
            texto=respuesta.texto,
            paquete_id=paquete_id,
            conflicto=bool(conflictos),
            detalle_conflicto=detalle,
            fuentes_citadas=fuentes,
            archivo_trace=str(self.trazador.archivo),
            replanificado=False,
        )
