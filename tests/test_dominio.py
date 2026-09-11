"""D11: puerta fuera-de-dominio. Sin LLM ni tools ante consultas ajenas al ambito."""
import json
from pathlib import Path

from agent.llm_client import ClienteFalso
from agent.reasoning_loop import AgentePlanificador
from agent.trace import Trazador


class ClienteContador(ClienteFalso):
    def __init__(self):
        super().__init__()
        self.llamadas = 0

    def completar(self, sistema, usuario):
        self.llamadas += 1
        return super().completar(sistema, usuario)


def test_off_topic_redirige_sin_llamar_tools_ni_llm(tmp_path):
    llm = ClienteContador()
    trazador = Trazador(tmp_path / "trace.jsonl")
    agente = AgentePlanificador(llm=llm, trazador=trazador)
    r = agente.planificar("que prefieres perritos o gatitos", fecha="2026-12-24")
    assert r.paquete_id is None
    assert r.replanificado is False
    assert r.detalle_conflicto == "fuera_de_dominio"
    assert "ecoturismo" in r.texto and "kayak" in r.texto
    assert llm.llamadas == 0
    tipos = [json.loads(l)["tipo"] for l in Path(r.archivo_trace).read_text(encoding="utf-8").strip().split("\n")]
    assert "fuera_de_dominio" in tipos
    assert "herramienta" not in tipos
    assert "respuesta_final" not in tipos


def test_off_topic_variado_tambien_redirige(tmp_path):
    for q in ("receta de torta de chocolate", "como cambio la rueda de mi auto"):
        trazador = Trazador(tmp_path / "trace.jsonl")
        agente = AgentePlanificador(llm=ClienteFalso(), trazador=trazador)
        r = agente.planificar(q)
        assert r.paquete_id is None
        assert r.detalle_conflicto == "fuera_de_dominio"


def test_in_domain_pasa_la_puerta(tmp_path):
    # Caso borde valido: debe seguir recomendando PAQ-001 sin redirigir.
    trazador = Trazador(tmp_path / "trace.jsonl")
    agente = AgentePlanificador(llm=ClienteFalso(), trazador=trazador)
    r = agente.planificar("kayak suave para principiantes en Chiloe", fecha="2026-12-08")
    assert r.paquete_id == "PAQ-001"
    assert r.detalle_conflicto != "fuera_de_dominio"
