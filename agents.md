# agents.md — Memoria de decisiones y avance del semestre

**Proyecto:** ep1-ecoturismo-agente
**Curso:** ISY0101 Ingeniería de Soluciones con IA — Evaluación Parcial 1 (30%)
**GitHub:** https://github.com/beibanezv
**Última actualización:** 2026-09-03

> Memoria técnica del proyecto. Se actualiza en cada sesión para preservar
> decisiones, tradeoffs y avance entre entregas. Sirve de bitácora para el
> docente (IE7/IE8: justificar decisiones) y para el equipo.

## 1. Contexto del semestre

- EP1 = 1 caso organizacional + informe de 5 páginas APA (IE1–IE9, pauta en
  `../EP1_ISY0101_Estudiante.pdf`). Se desarrolla en parejas, 5 semanas.
- Estrategia del equipo: construir DOS prototipos con arquitectura base común
  (este y `../ep1-veterinaria-agente`), elegir el mejor como entregable
  único; el otro se descarta o se menciona en la presentación explicando por
  qué se eligió uno sobre el otro.
- Regla del stack: **≥50% con tecnologías vistas en clase es concepto guía,
  no requisito literal.** El profesor alienta la exploración. Toda tecnología
  fuera del curso debe quedar justificada aquí y en el informe.

## 2. Decisiones cerradas

| # | Decisión | Elección | Justificación | Alternativa descartada |
|---|---|---|---|---|
| D1 | Proveedor LLM | Groq: `openai/gpt-oss-120b` (respuesta final) / `gpt-oss-20b` (loops y dev), detrás de `agent/llm_client.py` intercambiable | Único proveedor del curso (CLAUDE.md del repo de materiales); cuota gratis 200k tokens/día | Stub sin proveedor por defecto |
| D2 | Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` local (384d) | Contenido en español; convención del curso; costo 0 y privado | `all-MiniLM-L6-v2` (enfoque inglés, propuesto inicialmente) |
| D3 | Vector store | **ChromaDB** persistente en `chroma_db/` | Filtro nativo por metadata (`region`, `tipo_actividad`, `dificultad`); API simple. Exploración alentada por el profesor | FAISS (lo que enseña RA1/IL1.3). Tradeoff para el informe: curso usa FAISS por velocidad en índices pequeños; Chroma gana en filtrado por metadata |
| D4 | Chunking | `RecursiveCharacterTextSplitter`-style 500/50 | Visto en RA1/IL1.3 (`2-text-chunking.py`); paquetes son documentos cortos | Sin chunking |
| D5 | Gestor de deps | uv + Python 3.13 | Convención del curso (uv.lock en repo materiales) | pip |
| D6 | Repos | Dos repos independientes | Superficie común ~100 líneas (`llm_client` + logger); entrega académica es por repo | Paquete `shared/`, monorepo |
| D7 | Nombres | `ep1-ecoturismo-agente` | Distintivo en GitHub beibanezv (decenas de archivos similares); describe la función (replanificador) | `EP1-Turismo` |
| D8 | Orquestación | Loop razonamiento-acción propio (sin LangGraph/CrewAI) | Control total del logging de trazabilidad (requisito del encargo); la pauta pide mostrar el loop explícito | LangGraph (visto en curso; capa extra innecesaria para 1 agente) |
| D9 | Interfaz demo | CLI (`main.py`) + notebook `notebooks/demo.ipynb` | La pauta no exige UI; Streamlit solo aparece en RA1 como app de demostración de las IL (IL1.3/IL1.4), no como requisito. Menos trabajo y menos cuota | Mini-UI Streamlit (estilo proyecto Oxford) |

## 3. Requisitos funcionales (encargo)

Agencia boutique de ecoturismo en el sur de Chile arma itinerarios
personalizados y debe replanificar cuando cambian las condiciones (sendero
cerrado, mal clima, guía no disponible). Dado un pedido de cliente (fechas,
tipo de actividad, nivel de experiencia):

1. RAG: recuperar paquetes/itinerarios internos que calcen con el perfil.
2. Verificar fuentes externas: clima real vía Open-Meteo (sin API key) y
   estado de senderos (`data/external/trail_status.json`, simulada).
3. Si hay conflicto: replanificar eligiendo una alternativa (no solo informar).
4. Entregar itinerario final justificando y citando la fuente de cada decisión.
5. Logging de cada paso (qué recuperó, qué tool llamó, por qué replanificó).

## 4. Estructura

```
ep1-ecoturismo-agente/
├── data/
│   ├── internal/paquetes/     (8-10 itinerarios .json)
│   ├── internal/guias_roster.json (4-5 guías con disponibilidad)
│   └── external/trail_status.json (simulada, limitación documentada)
├── ingestion/ingest.py        carga → chunk → embed → Chroma
├── agent/
│   ├── llm_client.py          interfaz intercambiable, Groq default
│   ├── reasoning_loop.py      loop razonamiento-acción (máx N pasos)
│   ├── prompts.py
│   └── trace.py               log JSONL de trazabilidad
├── tools/
│   ├── weather.py             Open-Meteo (real, sin key)
│   ├── trail_status.py        lee trail_status.json como fuente externa
│   └── replanner.py           elige alternativa ante conflicto
├── main.py                    CLI: pedido cliente → itinerario justificado
├── tests/
│   ├── eval_dataset.json      12-15 consultas con resultado esperado
│   └── eval_agent.py          corre evals y reporta % de aciertos
└── docs/                      informe y diagramas (Fase 6)
```

## 5. Plan de fases

- [x] Fase 0 — Scaffold: uv, pyproject, .env.example, verify_groq.py, git init
- [x] Fase 1 — Datos simulados (8-10 paquetes + 4-5 guías) + ingesta + índice Chroma
- [x] Fase 2 — llm_client.py + prompts + respuesta base con citas
- [ ] Fase 3 — Tools clima/senderos + loop razonamiento-acción + trace.jsonl
- [ ] Fase 4 — Replanificación automática
- [ ] Fase 5 — Evals: 12-15 casos, tests/eval_agent.py, meta ≥85% aciertos
- [ ] Fase 6 — README completo + diagrama Mermaid + docs/informe

## 6. Limitaciones conocidas

- Estado de senderos: CONAF no ofrece API pública → `trail_status.json` se
  consulta como fuente externa simulada. Documentado en README/informe.
- Cuota Groq (200k tokens/día): usar `GROQ_MODEL_FAST` (20b) en dev y evals.

## 7. Historial de decisiones

- **2026-09-03** — Plan aprobado por el equipo (estructura, fases, stack).
  ChromaDB elegido sobre FAISS (D3) tras relajar la regla del 50% a concepto
  guía. Scaffold completado (Fase 0).
- **2026-09-03** — Fase 1 completada: 9 paquetes + 5 guías + 14 senderos,
  índice Chroma con 24 docs, 5/5 verificaciones semánticas OK.
- **2026-09-03** — Fase 2 completada: `agent/llm_client.py` (ClienteGroq +
  ClienteFalso determinista para dev/tests sin cuota), `agent/prompts.py`
  (regla de citas [F#] + negativa honesta), `agent/retriever.py`,
  `agent/agent.py`. Flujo probado end-to-end con ClienteFalso. Decisión D9:
  demo será CLI + notebook (Streamlit descartado, ver tabla).
