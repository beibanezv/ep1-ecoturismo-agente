"""Evals del agente: corre el dataset y reporta la meta de aciertos.

Uso:  python -m tests.eval_agent
"""
import os
import sys
from dataclasses import dataclass
import json
from pathlib import Path

# Evals deterministas con ClienteFalso: sin tracing LangSmith.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from agent.reasoning_loop import AgentePlanificador  # noqa: E402
from agent.llm_client import ClienteFalso  # noqa: E402
from agent.trace import Trazador  # noqa: E402

DATASET = RAIZ / "tests" / "eval_dataset.json"
TRACE_EVALS = RAIZ / "logs" / "trace_evals.jsonl"

CLIMA_BUENO = {
    "disponible": True,
    "temp_max_c": 18.0,
    "temp_min_c": 8.0,
    "precipitacion_mm": 1.0,
    "viento_max_kmh": 15.0,
    "codigo_clima": "parcialmente_nublado",
    "fuente": "stub-clima",
}


def clima_bueno(region, fecha):
    c = dict(CLIMA_BUENO)
    c["region"] = region
    c["fecha"] = fecha
    return c


def clima_adverso_los_lagos(region, fecha):
    c = clima_bueno(region, fecha)
    if region == "Los Lagos":
        c.update(
            temp_max_c=11.0,
            temp_min_c=4.0,
            precipitacion_mm=18.0,
            viento_max_kmh=52.0,
            codigo_clima="lluvia_intensa",
        )
    return c


@dataclass
class Veredicto:
    id: str
    ok: bool
    fallos: list[str]


def _registrar_fallo(fallos, campo, esperado, obtenido):
    fallos.append(f"{campo}: esperado={esperado!r} obtenido={obtenido!r}")


def _revisar_caso(caso, respuesta):
    fallos = []
    esp = caso.get("esperado", {})
    if "paquete_id" in esp and respuesta.paquete_id != esp["paquete_id"]:
        _registrar_fallo(fallos, "paquete_id", esp["paquete_id"], respuesta.paquete_id)
    if "conflicto" in esp and respuesta.conflicto != esp["conflicto"]:
        _registrar_fallo(fallos, "conflicto", esp["conflicto"], respuesta.conflicto)
    if "replanificado" in esp and respuesta.replanificado != esp["replanificado"]:
        _registrar_fallo(fallos, "replanificado", esp["replanificado"], respuesta.replanificado)
    if "paquete_original_id" in esp and respuesta.paquete_original_id != esp["paquete_original_id"]:
        _registrar_fallo(fallos, "paquete_original_id", esp["paquete_original_id"], respuesta.paquete_original_id)
    if "detalle_conflicto_contiene" in esp:
        sub = esp["detalle_conflicto_contiene"]
        if sub not in (respuesta.detalle_conflicto or ""):
            _registrar_fallo(fallos, "detalle_conflicto_contiene", sub, respuesta.detalle_conflicto)
    for sub in esp.get("citas_contiene", []):
        if sub not in (respuesta.fuentes_citadas or []):
            _registrar_fallo(fallos, "citas_contiene", sub, respuesta.fuentes_citadas)
    return Veredicto(caso["id"], not fallos, fallos)


def main() -> int:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    meta = dataset.get("meta", 0.85)
    trazador = Trazador(TRACE_EVALS)
    proveedores = {"bueno": clima_bueno, "adverso_los_lagos": clima_adverso_los_lagos}
    agente = AgentePlanificador(llm=ClienteFalso(), trazador=trazador, proveedor_clima=proveedores["bueno"])

    aciertos = 0
    veredictos = []
    for caso in dataset["casos"]:
        agente.proveedor_clima = proveedores.get(caso.get("clima", "bueno"), clima_bueno)
        respuesta = agente.planificar(caso["consulta"], fecha=caso.get("fecha"))
        v = _revisar_caso(caso, respuesta)
        veredictos.append(v)
        aciertos += 1 if v.ok else 0

    total = len(veredictos)
    tasa = aciertos / total if total else 0.0
    print(f"Evals: {aciertos}/{total} casos OK ({tasa:.0%}) | meta >= {meta:.0%}")
    for v in veredictos:
        marca = "OK  " if v.ok else "FALLA"
        print(f"  [{marca}] {v.id}")
        for f in v.fallos:
            print(f"         {f}")
    if tasa < meta:
        print("Por debajo de la meta.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
