"""Fase 4: el agente replanifica ante conflicto (sendero/clima/guia/temporada)
o responde con honestidad si no hay alternativa viable."""
import json
from pathlib import Path

from agent.llm_client import ClienteFalso
from agent.reasoning_loop import AgentePlanificador
from agent.trace import Trazador
from agent.retriever import Fragmento
from tools.guia_disponibilidad import consultar_guia
from tools.replanner import Replanificador


def clima_por_region(adverso_region):
    def _clima(region, fecha):
        if region == adverso_region:
            return {
                "disponible": True, "region": region, "fecha": fecha,
                "temp_max_c": 5.0, "temp_min_c": -4.0, "precipitacion_mm": 25.0,
                "viento_max_kmh": 70.0, "codigo_clima": 80, "fuente": "stub-clima",
            }
        return {
            "disponible": True, "region": region, "fecha": fecha,
            "temp_max_c": 18.0, "temp_min_c": 8.0, "precipitacion_mm": 1.0,
            "viento_max_kmh": 15.0, "codigo_clima": 1, "fuente": "stub-clima",
        }
    return _clima


def clima_bueno(region, fecha):
    return {
        "disponible": True, "region": region, "fecha": fecha,
        "temp_max_c": 18.0, "temp_min_c": 8.0, "precipitacion_mm": 1.0,
        "viento_max_kmh": 15.0, "codigo_clima": 1, "fuente": "stub-clima",
    }


def planificar(tmp_path, consulta, fecha, clima):
    trazador = Trazador(tmp_path / "trace.jsonl")
    agente = AgentePlanificador(llm=ClienteFalso(), trazador=trazador, proveedor_clima=clima)
    return agente.planificar(consulta, fecha=fecha)


def test_guia_disponible_en_roster():
    assert consultar_guia("GUI-003", "2026-12-05")["disponible"] is True
    assert consultar_guia("GUI-003", "2026-12-07")["disponible"] is False
    assert consultar_guia("GUI-999", "2026-12-05")["disponible"] is False


def test_replanifica_por_clima_adverso(tmp_path):
    # PAQ-001 (kayak Chiloe, Los Lagos) con clima adverso en Los Lagos.
    # 2026-12-08: GUI-001 y GUI-004 tienen agenda; los candidatos de Los Lagos
    # caen por clima, y el replanificador debe encontrar viable en otra region.
    r = planificar(tmp_path, "kayak suave para principiantes en Chiloe", "2026-12-08", clima_por_region("Los Lagos"))
    assert r.conflicto is True
    assert "clima adverso" in r.detalle_conflicto
    assert r.replanificado is True
    assert r.paquete_original_id == "PAQ-001"
    assert r.paquete_id and r.paquete_id != "PAQ-001"


def test_replanifica_por_guia_no_disponible(tmp_path):
    # PAQ-005 (ballenas Corcovado, GUI-005 con agenda solo 2027): el 2027-01-09
    # su guia no tiene agenda -> conflicto de guia -> replanifica (PAQ-003 es
    # viable: GUI-003 tiene agenda ese dia y temporada OK).
    r = planificar(tmp_path, "observacion de ballenas en el corcovado con guia biologo", "2027-01-09", clima_bueno)
    assert r.conflicto is True
    assert "guia no disponible" in r.detalle_conflicto
    assert r.replanificado is True
    assert r.paquete_original_id == "PAQ-005"
    assert r.paquete_id != "PAQ-005"


def test_sin_alternativa_viable_responde_honesto(tmp_path):
    # 2026-12-04: ningun guia tiene agenda ese dia (roster 2026 no lo cubre) y
    # PAQ-002 tiene su sendero cerrado -> replan fallido -> respuesta honesta.
    r = planificar(tmp_path, "trekking exigente en Torres del Paine", "2026-12-04", clima_bueno)
    assert r.conflicto is True
    assert r.replanificado is False
    assert r.paquete_id is None
    assert r.paquete_original_id == "PAQ-002"
    assert "senda-base-torres" in r.detalle_conflicto


def test_sendero_desconocido_no_es_viable(tmp_path):
    """Un paquete con un sendero sin estado conocido no debe considerarse viable."""
    replan = Replanificador(
        recuperador=None,
        trazador=Trazador(tmp_path / "trace.jsonl"),
        proveedor_clima=clima_bueno,
        cargar_paquete=lambda pid: None,
    )
    paquete = {
        "id": "PAQ-XUS",
        "region": "Araucanía",
        "temporada": ["diciembre"],
        "guia_asignado": "GUI-004",
        "itinerario": [{"dia": 1, "sendero": "senda-inexistente"}],
    }
    fragmento = Fragmento(id="PAQ-XUS::c0", texto="x", tipo="paquete", fuente="PAQ-XUS")
    viable, _, conflictos = replan._evaluar(paquete, fragmento, fecha=None)
    assert viable is False
    assert any("sendero sin estado conocido" in c for c in conflictos)


def test_trace_registra_pasos_replan(tmp_path):
    r = planificar(tmp_path, "kayak suave para principiantes en Chiloe", "2026-12-08", clima_por_region("Los Lagos"))
    lineas = Path(r.archivo_trace).read_text(encoding="utf-8").strip().split("\n")
    eventos = [json.loads(l) for l in lineas]
    tipos = [e["tipo"] for e in eventos]
    assert "replan_inicio" in tipos
    assert "replanificacion" in tipos
    assert "seleccion_final" in tipos
    assert tipos[-1] == "respuesta_final"
    pasos = [e["paso"] for e in eventos]
    assert pasos == list(range(1, len(eventos) + 1))
    assert eventos[-1]["replanificado"] is True
    assert eventos[-1]["paquete_id"] == r.paquete_id
