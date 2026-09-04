# EP1 — Agente Replanificador de Itinerarios de Ecoturismo

**ISY0101 · Ingeniería de Soluciones con IA · Evaluación Parcial 1 (30%)**

Agente LLM + RAG que genera itinerarios de ecoturismo personalizados (sur de
Chile) y los **replanifica automáticamente** cuando el clima o el estado de los
senderos invalidan el plan, entregando el itinerario final con la fuente que
respalda cada decisión.

> **Estado:** Fase 0 (scaffold). Decisiones técnicas y avance del semestre en
> [`agents.md`](agents.md).

## Cómo correr

```bash
uv sync
cp .env.example .env   # pegar GROQ_API_KEY (gratis) de https://console.groq.com
uv run python scripts/verify_groq.py
```

Documentación completa (arquitectura, fuentes internas/externas, evaluación,
limitaciones) se completa en la Fase 6 del plan.
