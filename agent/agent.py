"""Agente base RAG con citas (Fase 2): recuperar -> prompt -> LLM -> extraer fuentes citadas."""
import re
from dataclasses import dataclass

from agent.llm_client import ClienteGroq, ClienteLLM, RespuestaLLM
from agent.prompts import SISTEMA_BASE, armar_usuario
from agent.retriever import Fragmento, Recuperador

REGEX_CITA = re.compile(r"\[F(\d+)\]")


@dataclass
class RespuestaAgente:
    texto: str
    fuentes_citadas: list[str]
    fragmentos: list[Fragmento]
    llm: RespuestaLLM


class AgenteItinerario:
    def __init__(self, llm: ClienteLLM | None = None, k: int = 4):
        self.llm = llm or ClienteGroq()
        self.recuperador = Recuperador()
        self.k = k

    def responder(self, consulta: str, filtro: dict | None = None) -> RespuestaAgente:
        fragmentos = self.recuperador.buscar(consulta, k=self.k, filtro=filtro)
        usuario = armar_usuario(consulta, fragmentos)
        respuesta = self.llm.completar(SISTEMA_BASE, usuario)

        indices = sorted({int(n) for n in REGEX_CITA.findall(respuesta.texto)})
        fuentes: list[str] = []
        for n in indices:
            if 1 <= n <= len(fragmentos):
                fuente = fragmentos[n - 1].fuente
                if fuente not in fuentes:
                    fuentes.append(fuente)

        return RespuestaAgente(
            texto=respuesta.texto,
            fuentes_citadas=fuentes,
            fragmentos=fragmentos,
            llm=respuesta,
        )
