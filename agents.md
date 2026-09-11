# agents.md — Memoria de decisiones y avance del semestre

**Proyecto:** ep1-ecoturismo-agente
**Curso:** ISY0101 Ingeniería de Soluciones con IA — Evaluación Parcial 1 (30%)
**GitHub:** https://github.com/beibanezv
**Última actualización:** 2026-09-10

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
| D9 | Interfaz demo | CLI + notebook + Streamlit `app.py` (solo demo) | La pauta no exige UI; Streamlit es formulario delgado sobre `planificar()` con los 2 casos del guion (PAQ-001 sin conflicto, PAQ-002→PAQ-009), modo `--falso` por defecto | Solo CLI |
| D10 | LangChain / LangSmith | `ClienteLangChain` (ChatGroq vía langchain-groq) por defecto + `agent/observabilidad.py` activo | Mismo contrato `completar()`; `planificar()` con `@traceable`; tracing al proyecto `ep1-ecoturismo` si hay `LANGSMITH_API_KEY` en `.env`, si no es no-op; tests/evals con tracing apagado | LangGraph / tracing obligatorio |

Convencion de commits: mensajes simples y en espanol durante todo el semestre.

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
│   ├── internal/paquetes/     (9 itinerarios .json: PAQ-001..009)
│   ├── internal/guias_roster.json (5 guías GUI-001..005 con disponibilidad)
│   └── external/trail_status.json (14 senderos, simulada, limitación documentada)
├── ingestion/ingest.py        carga → chunk → embed → Chroma (24 docs)
├── agent/
│   ├── llm_client.py          ClienteGroq + ClienteFalso + ClienteLangChain
│   ├── reasoning_loop.py      loop razonamiento-acción (máx N pasos)
│   ├── prompts.py
│   ├── retriever.py           lee EMBEDDING_MODEL del .env, error amable si falta colección
│   ├── observabilidad.py      init_langsmith opt-in + decorador traceable no-op
│   └── trace.py               log JSONL de trazabilidad
├── tools/
│   ├── weather.py             Open-Meteo (real, sin key)
│   ├── trail_status.py        lee trail_status.json como fuente externa
│   ├── guia_disponibilidad.py roster interno como tool [T#]
│   └── replanner.py           elige alternativa ante conflicto
├── main.py                    CLI: pedido cliente → itinerario justificado
├── app.py                     Streamlit demo (2 casos del guion, modo falso por defecto)
├── tests/
│   ├── eval_dataset.json      12 consultas con resultado esperado
│   └── eval_agent.py          corre evals y reporta % de aciertos
└── docs/                      informe y diagramas (Fase 6)
```

## 5. Plan de fases

- [x] Fase 0 — Scaffold: uv, pyproject, .env.example, verify_groq.py, git init
- [x] Fase 1 — Datos simulados (8-10 paquetes + 4-5 guías) + ingesta + índice Chroma
- [x] Fase 2 — llm_client.py + prompts + respuesta base con citas
- [x] Fase 3 — Tools clima/senderos + loop razonamiento-acción + trace.jsonl
- [x] Fase 4 — Replanificación automática (`tools/replanner.py` + `tools/guia_disponibilidad.py` + `SISTEMA_REPLAN`; suite 13/13: 10/10 al cerrar la fase, +3 tests en la revisión)
- [x] Fase 5 — Evals: 12 casos en `tests/eval_dataset.json`, 12/12 (100%) ≥ meta 85%
- [x] Fase 6 — README completo + diagrama Mermaid + CLI + notebook demo

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
  demo será CLI + notebook (Streamlit se agrega después como espejo de
  demo, ver D9 y la entrada del 2026-09-10).
- **2026-09-04** — Fase 3 completada: `agent/trace.py` (JSONL por paso),
  `tools/trail_status.py` (fuente simulada), `tools/weather.py` (Open-Meteo
  real; fuera de rango devuelve disponible=False sin inventar; umbrales de
  conflicto: lluvia ≥10 mm, viento ≥50 km/h, mínima ≤-2 °C),
  `agent/reasoning_loop.py` (detecta e informa conflictos, no replanifica),
  citas extendidas a [T#] para herramientas. `tests/test_fase3.py`: 5/5 OK.
  Open-Meteo verificado en vivo (Magallanes 2026-09-06).
- **2026-09-04** — Fase 4 completada: `tools/guia_disponibilidad.py` (roster
  interno verificado como tool [T#]; nunca inventa disponibilidad) y
  `tools/replanner.py` (reconsulta RAG con k=8, excluye el paquete
  conflictado, evalúa temporada/senderos/clima/guía y elige el primer viable).
  `agent/prompts.py` agrega `SISTEMA_REPLAN`; `reasoning_loop.py` integra la
  verificación de guía como tercer tipo de conflicto y el flujo de
  replanificación. Contrato de resultado: si replanifica, `paquete_id` es el
  alternativo y `paquete_original_id` conserva el original; si no hay
  alternativa viable, `paquete_id=None` con respuesta honesta; `conflicto` y
  `detalle_conflicto` se mantienen siempre. `tests/test_fase4.py`: 5/5 OK
  (suite total 10/10).
- **2026-09-04** — Fase 5 completada: `tests/eval_dataset.json` con 12 casos
  (sin conflicto, replanificación por sendero/clima/guía/temporada, casos sin
  alternativa y verificación de citas). Expectativas escritas tras sondear el
  comportamiento real del agente (script probe), no teóricas. Evals: 12/12
  (100%) ≥ meta 85%, con `ClienteFalso` (reproducible y sin cuota).
- **2026-09-04** — Fase 6 completada: `main.py` (CLI con `--fecha`, `--pasos`
  para ver el trace de la corrida y `--falso` para ClienteFalso),
  `notebooks/demo.ipynb` (5 casos incluyendo replanificación y replan
  fallida), README con diagrama Mermaid del pipeline. El prototipo
  veterinario (`../ep1-veterinaria-agente`, Fases 0-6, evals 14/14) se
  construyó con la misma arquitectura base (D1-D8) y validó la reutilización
  de la superficie común.

- **2026-09-05** — Guion de demo para la presentación (probado en desarrollo).
  Todo con `--falso` (ClienteFalso determinista, sin cuota ni API key):
  1. `& ".venv\Scripts\python.exe" main.py "kayak suave para principiantes en Chiloe" --fecha 2026-12-08 --pasos --falso` → PAQ-001 sin conflicto.
  2. `& ".venv\Scripts\python.exe" main.py "trekking exigente en Torres del Paine" --fecha 2026-12-15 --pasos --falso` → replanifica PAQ-002 → PAQ-009 (senda-base-torres cerrado).
  3. `& ".venv\Scripts\python.exe" main.py "observacion de ballenas y fauna marina en Los Lagos" --fecha 2026-12-05 --pasos --falso` → replanifica PAQ-005 → PAQ-003 (fuera de temporada + guía sin agenda).
  4. `& ".venv\Scripts\python.exe" main.py "trekking exigente en Torres del Paine" --fecha 2026-12-04 --pasos --falso` → respuesta honesta sin alternativa (paquete: None).
  Evidencia cuantitativa: `& ".venv\Scripts\python.exe" -m pytest -q` → 10/10 y
  `& ".venv\Scripts\python.exe" -m tests.eval_agent` → 12/12 (100%).
  `--pasos` muestra el trace de la corrida (trazabilidad en vivo). Caso opcional
  con LLM real: quitar `--falso` en el caso 1 (requiere GROQ_API_KEY en .env).
  Caveat: fechas de dic 2026 quedan fuera del rango de Open-Meteo (~16 días) →
  clima no disponible, no es conflicto (limitación documentada). Los casos del
  prototipo veterinario están en el agents.md del repo gemelo.
- **2026-09-10** — Corrección pre-entrega: `retriever.py` lee
  `EMBEDDING_MODEL` del `.env` (antes hardcodeado) con error amable que pide
  re-correr ingesta; Streamlit `app.py` agregado como espejo simple del
  veterinario (2 casos del guion, D9 actualizada); `agent/observabilidad.py`
  (LangSmith opt-in, no-op sin key) + `ClienteLangChain` alternativo en
  `llm_client.py` (D10). Re-verificado: pytest 10/10, evals 12/12.
- **2026-09-10 (2)** — Revisión externa + fixes: `tools/weather.py` traduce el
  HTTP 400 de Open-Meteo (fecha fuera de rango) a un motivo claro en vez de
  exponer el error crudo; `tools/replanner.mes_de_fecha` valida el formato ISO
  (antes `int(fecha[5:7])` lanzaba excepción sin captura) y `main.py` la
  reporta con código de salida 2; un sendero sin estado conocido ya no se
  trata como viable (se marca conflicto en el loop y en el replanificador);
  `tests/metricas_rag.py` agrega Precision@1 y MRR y explicita que
  Faithfulness/Answer Relevancy son circulares. Tests nuevos: 13/13.
  Evals 12/12.
- **2026-09-11** — Cableado LangSmith: `ClienteLangChain` por defecto en
  `main.py`/`app.py` (`--falso` y `--groq-directo` como escapes),
  `@traceable("planificar")` en el loop, `init_langsmith()` al inicio;
  tracing apagado en tests/evals (conftest + scripts). Primera corrida real
  trazada al proyecto `ep1-ecoturismo`. Tabla 4 + Figura 2 del informe con
  Precision@1 y MRR (1,00/1,00). Re-verificado: pytest 13/13, evals 12/12.

- **2026-09-11 (2)** — Puerta fuera-de-dominio (D11): Fragmento.score con distancias de Chroma; si el top-1 > 0,55 se redirige al ambito sin quemar tools ni LLM (evento fuera_de_dominio en trace). Calibrado: 12 validas <= 0,38, 6 ajenas >= 0,72. Regla 7 de respaldo en el prompt. main.py con stdout UTF-8 (Windows). Tests nuevos (test_dominio.py): 16/16. Evals 12/12.
