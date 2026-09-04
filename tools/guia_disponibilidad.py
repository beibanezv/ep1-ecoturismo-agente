"""Disponibilidad de guias: verificacion del roster interno (guias_roster.json).

Se modela como tool [T#] porque la consulta de agenda es una verificacion con
salida estructurada, distinta a la recomendacion del RAG.
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVO_ROSTER = RAIZ / "data" / "internal" / "guias_roster.json"
NOMBRE_FUENTE = "guias_roster.json (interno)"

CACHE_ROSTER: dict | None = None


def cargar_roster() -> dict[str, dict]:
    global CACHE_ROSTER
    if CACHE_ROSTER is None:
        datos = json.loads(ARCHIVO_ROSTER.read_text(encoding="utf-8"))
        CACHE_ROSTER = {g["id"]: g for g in datos["guias"]}
    return CACHE_ROSTER


def consultar_guia(guia_id: str, fecha_iso: str) -> dict:
    """Devuelve {disponible, motivo, fuente}. Nunca inventa: si la fecha no
    esta en el roster del guia, no esta disponible."""
    guia = cargar_roster().get(guia_id)
    if guia is None:
        return {
            "guia_id": guia_id, "fecha": fecha_iso, "disponible": False,
            "motivo": f"Guia inexistente en roster: {guia_id}", "fuente": NOMBRE_FUENTE,
        }
    fechas = {d for lista in guia["disponibilidad"].values() for d in lista}
    disponible = fecha_iso in fechas
    return {
        "guia_id": guia_id,
        "nombre": guia["nombre"],
        "fecha": fecha_iso,
        "disponible": disponible,
        "motivo": None if disponible else f"{guia['nombre']} sin agenda para {fecha_iso}",
        "fuente": NOMBRE_FUENTE,
    }


def describir_disponibilidad(r: dict) -> str:
    if r["disponible"]:
        return f"Guia {r['guia_id']} ({r['nombre']}): DISPONIBLE el {r['fecha']}."
    return f"Guia {r['guia_id']}: NO disponible el {r['fecha']}. {r.get('motivo') or ''}"
