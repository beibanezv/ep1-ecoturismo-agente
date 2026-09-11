"""
app.py - Demo Streamlit EP1 Ecoturismo (ISY0101).

UI simple espejo de veterinaria: pedido -> itinerario justificado.
Ejecuta: uv run streamlit run app.py
"""
import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

from agent.llm_client import ClienteFalso, ClienteLangChain
from agent.observabilidad import init_langsmith
from agent.reasoning_loop import AgentePlanificador
from agent.trace import Trazador

init_langsmith()

CASO_SIN_CONFLICTO = {
    "consulta": "kayak suave para principiantes en Chiloe",
    "fecha": "2026-12-08",
}
CASO_REPLAN = {
    "consulta": "trekking exigente en Torres del Paine",
    "fecha": "2026-12-15",
}

st.set_page_config(page_title="Ecoturismo - Itinerarios", page_icon="🌿", layout="wide")
st.title("🌿 Agencia boutique — Itinerarios de ecoturismo")
st.caption("ISY0101 EP1 · LangChain (ChatGroq) + Chroma + loop propio · Replanifica ante conflicto, cita cada decisión · Tracing en LangSmith (proyecto ep1-ecoturismo)")

with st.sidebar:
    st.header("Configuración")
    modo_falso = st.checkbox("Modo demo determinista (sin API key)", value=True,
                             help="Usa ClienteFalso: reproducible, sin cuota Groq.")
    ver_trace = st.checkbox("Mostrar trazabilidad del caso", value=True)
    st.divider()
    st.markdown("**Fuentes:**")
    st.markdown("- `data/internal/paquetes/` 9 paquetes (PAQ-001..009)\n- `data/external/trail_status.json` 14 senderos (simulada)\n- Clima real Open-Meteo (sin key; fuera de rango ~16 días = no disponible)")

st.subheader("Casos de demostración")
c1, c2 = st.columns(2)
if c1.button("✅ Caso 1: sin conflicto (PAQ-001 Chiloé)", use_container_width=True):
    st.session_state.update(CASO_SIN_CONFLICTO)
if c2.button("🔁 Caso 2: replanifica (PAQ-002 → PAQ-009)", use_container_width=True):
    st.session_state.update(CASO_REPLAN)

consulta = st.text_area("Pedido del cliente",
                        value=st.session_state.get("consulta", CASO_SIN_CONFLICTO["consulta"]),
                        height=80, placeholder="Ej: kayak suave para principiantes en Chiloe")
fecha = st.text_input("Fecha del viaje (ISO)", value=st.session_state.get("fecha", CASO_SIN_CONFLICTO["fecha"]),
                      placeholder="2026-12-08")

if st.button("🔍 Planificar itinerario", type="primary", use_container_width=True):
    if not modo_falso and not os.getenv("GROQ_API_KEY"):
        st.error("Falta GROQ_API_KEY en .env (o activa el modo demo determinista).")
        st.stop()
    archivo_trace = RAIZ / "logs" / "trace.jsonl"
    lineas_previas = len(archivo_trace.read_text(encoding="utf-8").strip().split("\n")) if archivo_trace.exists() else 0
    with st.spinner("Recuperando paquetes, verificando senderos/clima/guía..."):
        try:
            llm = ClienteFalso() if modo_falso else ClienteLangChain()
            agente = AgentePlanificador(llm=llm, trazador=Trazador(None))
            r = agente.planificar(consulta, fecha=fecha or None)
            st.subheader("Itinerario")
            st.markdown(r.texto)
            st.divider()
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Paquete original", r.paquete_original_id or "-")
                st.metric("Paquete final", r.paquete_id or "(sin alternativa)")
            with m2:
                st.metric("Replanificado", "sí" if r.replanificado else "no")
                st.write(f"**Conflicto:** {r.detalle_conflicto or 'ninguno'}")
            with m3:
                st.markdown("**Fuentes citadas:**")
                st.write(", ".join(r.fuentes_citadas) if r.fuentes_citadas else "(ninguna)")
            if ver_trace and r.archivo_trace:
                with st.expander("Trazabilidad del caso (trace.jsonl)"):
                    try:
                        lineas = Path(r.archivo_trace).read_text(encoding="utf-8").strip().split("\n")
                        for linea in lineas[lineas_previas:]:
                            e = json.loads(linea)
                            st.code(f"[{e['paso']:02d}] {e['tipo']} | " + " | ".join(
                                f"{k}={v}" for k, v in e.items() if k not in ("paso", "tipo", "hora_utc")))
                    except FileNotFoundError:
                        st.info("Aún no hay trace para esta corrida.")
            st.caption(f"LLM: {type(llm).__name__} · Original: {r.paquete_original_id or '-'} · Final: {r.paquete_id or '-'}")
        except Exception as e:
            st.error(f"Error: {e}")
            st.exception(e)

st.divider()
st.caption("Fuentes externas: Open-Meteo real + trail_status.json simulada (CONAF sin API pública). Uso de IA declarado en el informe.")
