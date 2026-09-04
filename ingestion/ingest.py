"""Ingesta RAG: paquetes internos + roster de guias -> ChromaDB persistente."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
DIR_PAQUETES = RAIZ / "data" / "internal" / "paquetes"
ARCHIVO_GUIAS = RAIZ / "data" / "internal" / "guias_roster.json"
DIR_CHROMA = RAIZ / "chroma_db"

MAX_CHARS = 500
OVERLAP = 50


def cargar_paquetes() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR_PAQUETES.glob("*.json"))]


def cargar_guias() -> list[dict]:
    return json.loads(ARCHIVO_GUIAS.read_text(encoding="utf-8"))["guias"]


def texto_paquete(p: dict) -> str:
    partes = [
        f"Paquete: {p['nombre']} (id {p['id']}).",
        f"Region: {p['region']}. Actividad: {p['tipo_actividad']}. Dificultad: {p['dificultad']}.",
        f"Duracion: {p['dias']} dias. Temporada: {', '.join(p['temporada'])}.",
        f"Guia asignado: {p['guia_asignado']}. Capacidad maxima: {p['capacidad_max']} personas.",
        f"Resumen: {p['resumen']}",
        "Itinerario:",
    ]
    for dia in p["itinerario"]:
        linea = f"Dia {dia['dia']} - {dia['lugar']}: {dia['actividad']}"
        if dia.get("sendero"):
            linea += f" (sendero: {dia['sendero']})"
        partes.append(linea)
    return "\n".join(partes)


def texto_guia(g: dict) -> str:
    meses = ", ".join(g["disponibilidad"].keys())
    return (
        f"Guia: {g['nombre']} (id {g['id']}). "
        f"Especialidades: {', '.join(g['especialidades'])}. "
        f"Regiones: {', '.join(g['regiones'])}. "
        f"Certificaciones: {', '.join(g['certificaciones'])}. "
        f"Disponibilidad para la temporada {temporada_2026_2027()}: {meses}."
    )


def temporada_2026_2027() -> str:
    return "octubre 2026 - abril 2027"


def chunk_texto(texto: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    parrafos = [p.strip() for p in texto.split("\n") if p.strip()]
    chunks: list[str] = []
    actual = ""
    for p in parrafos:
        while len(p) > max_chars:
            if actual:
                chunks.append(actual)
                actual = ""
            chunks.append(p[:max_chars])
            p = p[max_chars - overlap:]
        if not actual:
            actual = p
        elif len(actual) + 1 + len(p) <= max_chars:
            actual = f"{actual}\n{p}"
        else:
            chunks.append(actual)
            actual = p
    if actual:
        chunks.append(actual)
    return chunks


def construir_indice() -> tuple[int, int]:
    from chromadb import PersistentClient
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    modelo = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    ef = SentenceTransformerEmbeddingFunction(model_name=modelo)
    cliente = PersistentClient(path=str(DIR_CHROMA))
    try:
        cliente.delete_collection("conocimiento")
    except Exception:
        pass
    col = cliente.get_or_create_collection("conocimiento", embedding_function=ef)

    ids: list[str] = []
    documentos: list[str] = []
    metadatas: list[dict] = []

    for p in cargar_paquetes():
        for i, chunk in enumerate(chunk_texto(texto_paquete(p))):
            ids.append(f"{p['id']}::c{i}")
            documentos.append(chunk)
            metadatas.append({
                "tipo": "paquete",
                "paquete_id": p["id"],
                "nombre": p["nombre"],
                "region": p["region"],
                "tipo_actividad": p["tipo_actividad"],
                "dificultad": p["dificultad"],
                "dias": p["dias"],
                "temporada": ", ".join(p["temporada"]),
                "guia_id": p["guia_asignado"],
                "chunk_index": i,
            })

    for g in cargar_guias():
        for i, chunk in enumerate(chunk_texto(texto_guia(g))):
            ids.append(f"{g['id']}::c{i}")
            documentos.append(chunk)
            metadatas.append({
                "tipo": "guia",
                "guia_id": g["id"],
                "nombre": g["nombre"],
                "regiones": ", ".join(g["regiones"]),
                "especialidades": ", ".join(g["especialidades"]),
                "chunk_index": i,
            })

    col.add(ids=ids, documents=documentos, metadatas=metadatas)
    return len(documentos), col.count()


def verificar() -> bool:
    from chromadb import PersistentClient
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    ef = SentenceTransformerEmbeddingFunction(model_name=os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ))
    col = PersistentClient(path=str(DIR_CHROMA)).get_collection("conocimiento", embedding_function=ef)

    casos = [
        ("kayak suave para principiantes en Chiloe", {"tipo": "paquete"}, {"PAQ-001"}),
        ("trekking exigente entre volcanes de altura", {"tipo": "paquete"}, {"PAQ-002", "PAQ-008"}),
        ("ver pinguinos en su habitat natural", {"tipo": "paquete"}, {"PAQ-003"}),
        ("bicicleta de montana para empezar", {"tipo": "paquete"}, {"PAQ-004", "PAQ-009"}),
        ("expedicion de kayak de varios dias para expertos", {"$and": [{"tipo_actividad": "kayak"}, {"dificultad": "avanzado"}]}, {"PAQ-007"}),
    ]
    ok = True
    for consulta, filtro, esperados in casos:
        r = col.query(query_texts=[consulta], n_results=1, where=filtro)
        paquete_id = r["metadatas"][0][0].get("paquete_id", "?")
        paso = paquete_id in esperados
        ok = ok and paso
        print(f"{'MATCH ' if paso else 'MISS  '} '{consulta}' -> {paquete_id} (esperado: {sorted(esperados)})")
    return ok


if __name__ == "__main__":
    load_dotenv()
    chunks, total = construir_indice()
    print(f"Ingesta OK: {chunks} documentos indexados (total en coleccion: {total})")
    raise SystemExit(0 if verificar() else 1)
