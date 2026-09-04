"""Loop razonamiento-accion (D8): recuperar -> verificar senderos -> verificar clima -> responder.

Fase 3: detecta e informa conflictos, sin replanificar (la replanificacion automatica es Fase 4).
Cada paso queda registrado via Trazador en logs/trace.jsonl.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from agent.llm_client import ClienteGroq, ClienteLLM
from agent.prompts import SISTEMA_BASE, armar_usuario
from agent.retriever import Fragmento, Recuperador
from agent.trace import Trazador
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

    def planificar(self, consulta: str, fecha: str | None = None) -> PlanRespuesta:
        self.trazador.registrar("consulta", texto=consulta, fecha=fecha)

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
                    self.trazador.registrar(
                        "herramienta", herramienta="estado_sendero", entrada=sid, salida="desconocido"
                    )
                    continue
                self.trazador.registrar(
                    "herramienta", herramienta="estado_sendero", entrada=sid, salida=est["estado"]
                )
                herramientas.append((FUENTE_SENDEROS, describir_estado(est)))
                if est["estado"] == "cerrado":
                    conflictos.append(f"sendero cerrado: {sid} ({est['motivo']})")

        if paquete and fecha:
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

        detalle = "sin conflictos" if not conflictos else " | ".join(conflictos)
        pedido = consulta + (f" Fecha del viaje: {fecha}." if fecha else "")
        usuario = armar_usuario(pedido, fragmentos, herramientas or None)
        respuesta = self.llm.completar(SISTEMA_BASE, usuario)

        fuentes: list[str] = []
        for letra, numero in REGEX_CITAS.findall(respuesta.texto):
            n = int(numero)
            if letra == "F" and 1 <= n <= len(fragmentos):
                fuente = fragmentos[n - 1].fuente
            elif letra == "T" and 1 <= n <= len(herramientas):
                fuente = herramientas[n - 1][0]
            else:
                continue
            if fuente not in fuentes:
                fuentes.append(fuente)

        self.trazador.registrar(
            "respuesta_final",
            paquete_id=paquete_id,
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
        )
