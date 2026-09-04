"""Fase 3: el loop detecta conflictos de sendero y clima, y deja trace.jsonl."""
import json
from pathlib import Path

from agent.llm_client import ClienteFalso
from agent.reasoning_loop import AgentePlanificador
from agent.trace import Trazador
from tools.weather import es_conflicto_climatico


def planificar_en_tmp(tmp_path, consulta, fecha=None, clima=None):
    trazador = Trazador(tmp_path / "trace.jsonl")
    agente = AgentePlanificador(llm=ClienteFalso(), trazador=trazador, proveedor_clima=clima) if clima else AgentePlanificador(llm=ClienteFalso(), trazador=trazador)
    return agente.planificar(consulta, fecha=fecha)


def test_detecta_sendero_cerrado(tmp_path):
    # PAQ-002 usa senda-base-torres (cerrada en trail_status.json). Dic 2026 esta
    # fuera del rango de Open-Meteo -> clima sin datos, no debe marcar conflicto.
    r = planificar_en_tmp(tmp_path, "trekking exigente en Torres del Paine", fecha="2026-12-15")
    assert r.paquete_id == "PAQ-002"
    assert r.conflicto is True
    assert "senda-base-torres" in r.detalle_conflicto
    assert "trail_status.json (simulada)" in r.fuentes_citadas


def test_sin_conflicto_en_chiloe(tmp_path):
    # PAQ-001 solo usa senda-costa-lemuy (abierta).
    r = planificar_en_tmp(tmp_path, "kayak suave para principiantes en Chiloe", fecha="2026-12-05")
    assert r.paquete_id == "PAQ-001"
    assert r.conflicto is False
    assert r.detalle_conflicto == "sin conflictos"


def test_conflicto_climatico_con_stub(tmp_path):
    def clima_adverso(region, fecha):
        return {
            "disponible": True, "region": region, "fecha": fecha,
            "temp_max_c": 5.0, "temp_min_c": -4.0, "precipitacion_mm": 25.0,
            "viento_max_kmh": 70.0, "codigo_clima": 80, "fuente": "stub-clima",
        }

    r = planificar_en_tmp(
        tmp_path, "kayak suave para principiantes en Chiloe", fecha="2026-12-05", clima=clima_adverso
    )
    assert r.conflicto is True
    assert "precipitacion 25.0 mm" in r.detalle_conflicto
    assert "stub-clima" in r.fuentes_citadas


def test_trace_registra_todos_los_pasos(tmp_path):
    r = planificar_en_tmp(tmp_path, "trekking exigente en Torres del Paine", fecha="2026-12-15")
    lineas = Path(r.archivo_trace).read_text(encoding="utf-8").strip().split("\n")
    tipos = [json.loads(l)["tipo"] for l in lineas]
    assert tipos[0] == "consulta"
    assert tipos[1] == "recuperacion"
    assert tipos[-1] == "respuesta_final"
    assert "herramienta" in tipos
    pasos = [json.loads(l)["paso"] for l in lineas]
    assert pasos == list(range(1, len(lineas) + 1))


def test_umbrales_climaticos():
    base = {"disponible": True, "precipitacion_mm": 2.0, "viento_max_kmh": 20.0, "temp_min_c": 3.0}
    assert es_conflicto_climatico(base) == (False, "condiciones aptas")
    assert es_conflicto_climatico({**base, "precipitacion_mm": 12.0})[0] is True
    assert es_conflicto_climatico({"disponible": False}) == (False, "sin datos climaticos")
