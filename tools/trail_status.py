"""Estado de senderos tratado como fuente externa simulada: CONAF no publica API."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVO_ESTADOS = RAIZ / "data" / "external" / "trail_status.json"
NOMBRE_FUENTE = "trail_status.json (simulada)"


def cargar_estados() -> dict[str, dict]:
    datos = json.loads(ARCHIVO_ESTADOS.read_text(encoding="utf-8"))
    return {s["id"]: s for s in datos["senderos"]}


def estado_sendero(sendero_id: str) -> dict | None:
    s = cargar_estados().get(sendero_id)
    if s is None:
        return None
    return {
        "sendero_id": sendero_id,
        "estado": s["estado"],
        "motivo": s.get("motivo"),
        "desde": s.get("desde"),
        "fuente": NOMBRE_FUENTE,
    }


def describir_estado(est: dict) -> str:
    texto = f"Senda {est['sendero_id']}: estado={est['estado']}."
    if est.get("motivo"):
        texto += f" Motivo: {est['motivo']}"
    if est.get("desde"):
        texto += f" (desde {est['desde']})"
    return texto
