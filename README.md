# Agente de Itinerarios — Ecoturismo Sur de Chile

**ISY0101 · Ingeniería de Soluciones con IA · Evaluación Parcial 1**

Programa que arma itinerarios de ecoturismo personalizados (sur de Chile) y
los **replanifica automáticamente** cuando algo invalida el plan: sendero
cerrado, mal clima o guía no disponible. Entrega el itinerario final indicando
la fuente que respalda cada decisión. Si ninguna alternativa sirve, lo dice
honestamente sin forzar un paquete.

## Cómo funciona

1. Busca el paquete que mejor calza con lo pedido (búsqueda semántica sobre
   base local ChromaDB).
2. Verifica el estado de los senderos, el clima (Open-Meteo, sin API key) y la
   disponibilidad del guía.
3. Si hay conflicto, busca otro paquete viable y explica el cambio.
4. Responde con el itinerario final y las citas de cada fuente.
5. Todo queda registrado en `logs/trace.jsonl` para trazabilidad.

Si la consulta no tiene relación con turismo, el programa lo indica y no arma
itinerario.

## Datos

- `data/internal/paquetes/`: 9 paquetes (región, actividad, dificultad,
  temporada, guía, itinerario con senderos).
- `data/internal/guias_roster.json`: 5 guías con fechas de disponibilidad.
- `data/external/trail_status.json`: estado de 14 senderos (dato simulado,
  a modo de fuente externa).

## Cómo ejecutarlo

Requisitos: Python 3.13, [uv](https://docs.astral.sh/uv/) y una API key
gratuita de [Groq](https://console.groq.com).

```bash
uv sync
cp .env.example .env   # pegar la GROQ_API_KEY dentro del .env

# 1. Cargar los datos a la base local
uv run python -m ingestion.ingest

# 2. Pedir un itinerario (usa el modelo de Groq)
uv run python main.py "kayak suave para principiantes en Chiloe" \
    --fecha 2026-12-08

# 3. Modo demo (respuestas fijas, sin gastar API)
uv run python main.py "trekking exigente en Torres del Paine" \
    --fecha 2026-12-15 --falso

# 4. Correr las pruebas
uv run python -m pytest -q
uv run python -m tests.eval_agent
```

Interfaz web simple para la demostración:

```bash
uv run streamlit run app.py
```

Cuaderno con ejemplos paso a paso: `notebooks/demo.ipynb`.

## Pruebas

- 16 pruebas automatizadas (`tests/`), todas pasando.
- 12 casos de evaluación (`tests/eval_dataset.json`): sin conflicto,
  replanificación por sendero/clima/guía/temporada, casos sin alternativa y
  citas. Resultado: 12/12.

## Notas

- El estado de senderos es simulado (no existe API pública) y el clima solo
  cubre fechas cercanas (~16 días); para fechas lejanas la decisión se apoya
  en las demás fuentes.
- Informe del proyecto en `docs/EP1_ISY0101_Informe.docx`.
