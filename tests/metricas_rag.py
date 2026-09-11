"""Metricas RAG para el informe (IE4/IE9, Tabla 4 + Figura 2).

Mide, con ClienteFalso determinista (sin cuota Groq), sobre los 12 casos de
tests/eval_dataset.json:
- Context Precision: fragmentos recuperados que son paquetes pertinentes
  (paquete final esperado u original) / total recuperados.
- Context Recall: paquetes esperados (final + original) cubiertos por la
  recuperacion / total esperados.
- Faithfulness: citas [F#] de la respuesta que resuelven a un fragmento
  realmente recuperado (el guardarraíl _extraer_fuentes descarta marcadores
  fuera de rango) / total citas a paquetes.
- Answer Relevancy: tasa de veredictos OK del harness (tests/eval_agent.py).
- Precision@1 y MRR: posición del primer paquete pertinente en el ranking
  recuperado (métricas rank-aware que no dependen de cuántos vecinos traiga k).

Nota metodológica: con ClienteFalso, Faithfulness es 1,00 por construcción
(_extraer_fuentes solo devuelve citas que resuelven) y Answer Relevancy es la
tasa de acierto del propio harness, no una métrica de relevancia semántica.
Se reportan Precision@1 y MRR para compensar esa circularidad.

Uso:  python -m tests.metricas_rag
"""
import json
import os
import sys
import tempfile
from pathlib import Path

# Metricas deterministas con ClienteFalso: sin tracing LangSmith.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from agent.reasoning_loop import AgentePlanificador  # noqa: E402
from agent.llm_client import ClienteFalso  # noqa: E402
from agent.trace import Trazador  # noqa: E402
from tests.eval_agent import (  # noqa: E402
    _revisar_caso,
    clima_adverso_los_lagos,
    clima_bueno,
)

DATASET = RAIZ / "tests" / "eval_dataset.json"
SALIDA_JSON = RAIZ / "tests" / "metricas_rag.json"


def _leer_recuperados(archivo: Path) -> list[str]:
    """Union ordenada de paquete_ids de todos los eventos 'recuperacion'
    (consulta inicial k=5 + reconsulta de replan k=8)."""
    recuperados: list[str] = []
    for linea in archivo.read_text(encoding="utf-8").strip().split("\n"):
        e = json.loads(linea)
        if e.get("tipo") == "recuperacion":
            for pid in e.get("paquete_ids", []):
                if pid not in recuperados:
                    recuperados.append(pid)
    return recuperados


def main() -> int:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    proveedores = {"bueno": clima_bueno, "adverso_los_lagos": clima_adverso_los_lagos}
    filas = []
    with tempfile.TemporaryDirectory() as tmp:
        for caso in dataset["casos"]:
            trace_tmp = Path(tmp) / f"trace_{caso['id']}.jsonl"
            agente = AgentePlanificador(
                llm=ClienteFalso(),
                trazador=Trazador(trace_tmp),
                proveedor_clima=proveedores.get(caso.get("clima", "bueno"), clima_bueno),
            )
            r = agente.planificar(caso["consulta"], fecha=caso.get("fecha"))
            recuperados = _leer_recuperados(trace_tmp)
            esp = caso.get("esperado", {})
            esperados = {x for x in (esp.get("paquete_id"), esp.get("paquete_original_id")) if x}
            pertinentes = [p for p in recuperados if p in esperados]
            precision = len(pertinentes) / len(recuperados) if recuperados else 0.0
            recall = len(esperados & set(recuperados)) / len(esperados) if esperados else 1.0
            citados_paq = [c for c in (r.fuentes_citadas or []) if c.startswith("PAQ-")]
            faith = (
                len([c for c in citados_paq if c in recuperados]) / len(citados_paq)
                if citados_paq
                else 1.0
            )
            rank = next(
                (i + 1 for i, p in enumerate(recuperados) if p in esperados), None
            )
            v = _revisar_caso(caso, r)
            filas.append(
                {
                    "id": caso["id"],
                    "n_recuperados": len(recuperados),
                    "precision": round(precision, 2),
                    "recall": round(recall, 2),
                    "faithfulness": round(faith, 2),
                    "precision_at_1": 1.0 if rank == 1 else 0.0,
                    "mrr": round(1.0 / rank, 2) if rank else 0.0,
                    "veredicto_ok": v.ok,
                }
            )
    n = len(filas)
    ag = {
        "n_casos": n,
        "context_precision": round(sum(f["precision"] for f in filas) / n, 2),
        "context_recall": round(sum(f["recall"] for f in filas) / n, 2),
        "faithfulness": round(sum(f["faithfulness"] for f in filas) / n, 2),
        "answer_relevancy": round(sum(1 for f in filas if f["veredicto_ok"]) / n, 2),
        "precision_at_1": round(sum(f["precision_at_1"] for f in filas) / n, 2),
        "mrr": round(sum(f["mrr"] for f in filas) / n, 2),
    }
    SALIDA_JSON.write_text(
        json.dumps({"agregado": ag, "casos": filas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Tabla 4 - Metricas RAG (n=12, ClienteFalso determinista)")
    print(" caso | rec | Prec | Rec  | Faith | P@1  | MRR  | veredicto")
    for f in filas:
        marca = "OK" if f["veredicto_ok"] else "FALLA"
        print(
            f" {f['id']:4s} | {f['n_recuperados']:3d} | {f['precision']:.2f} "
            f"| {f['recall']:.2f} | {f['faithfulness']:.2f} | {f['precision_at_1']:.2f} "
            f"| {f['mrr']:.2f} | {marca}"
        )
    print(
        f"Context Precision={ag['context_precision']:.2f} | "
        f"Context Recall={ag['context_recall']:.2f} | "
        f"Faithfulness={ag['faithfulness']:.2f} | "
        f"Answer Relevancy={ag['answer_relevancy']:.2f} | "
        f"Precision@1={ag['precision_at_1']:.2f} | MRR={ag['mrr']:.2f}"
    )
    print(f"JSON: {SALIDA_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
