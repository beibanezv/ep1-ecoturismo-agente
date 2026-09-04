"""CLI de demostracion (D9): pedido del cliente -> itinerario justificado.

Uso:
    python main.py "kayak suave para principiantes en Chiloe" --fecha 2026-12-08
    python main.py "trekking exigente en Torres del Paine" --fecha 2026-12-15 --pasos
    python main.py "kayak en Chiloe" --fecha 2026-12-08 --falso

Con --falso usa ClienteFalso (determinista, sin cuota Groq) para probar el
pipeline completo; sin esa bandera usa ClienteGroq (openai/gpt-oss-120b).
"""
import argparse
import json
import sys
from pathlib import Path

from agent.llm_client import ClienteFalso, ClienteGroq
from agent.reasoning_loop import AgentePlanificador

RAIZ = Path(__file__).resolve().parent


def mostrar_trace(archivo: str, omitir: int = 0) -> None:
    if not archivo:
        return
    lineas = Path(archivo).read_text(encoding="utf-8").strip().split("\n")
    print("\n--- TRAZABILIDAD (trace.jsonl) ---")
    for linea in lineas[omitir:]:
        e = json.loads(linea)
        partes = [f"[{e['paso']:02d}] {e['tipo']}"]
        for clave, valor in e.items():
            if clave in ("paso", "tipo", "hora_utc"):
                continue
            partes.append(f"{clave}={valor}")
        print(" | ".join(partes))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agente de planificacion de ecoturismo: pedido -> itinerario justificado con citas.",
        epilog='Ejemplo: python main.py "observacion de ballenas en Los Lagos" --fecha 2026-12-05 --pasos',
    )
    parser.add_argument("consulta", help="pedido del cliente (entre comillas)")
    parser.add_argument("--fecha", default=None, help="fecha del viaje en formato ISO (ej: 2026-12-08)")
    parser.add_argument("--pasos", action="store_true", help="mostrar cada paso del loop (trace.jsonl)")
    parser.add_argument("--falso", action="store_true", help="usar ClienteFalso determinista (sin cuota Groq)")
    args = parser.parse_args()

    llm = ClienteFalso() if args.falso else ClienteGroq()
    agente = AgentePlanificador(llm=llm)

    archivo_trace = RAIZ / "logs" / "trace.jsonl"
    lineas_previas = len(archivo_trace.read_text(encoding="utf-8").strip().split("\n")) if archivo_trace.exists() else 0

    print(f"Consulta: {args.consulta}")
    if args.fecha:
        print(f"Fecha del viaje: {args.fecha}")
    print(f"LLM: {type(llm).__name__}\n")

    r = agente.planificar(args.consulta, fecha=args.fecha)

    print("--- RESPUESTA ---")
    print(r.texto)
    print()
    if r.paquete_original_id:
        print(f"Paquete original:  {r.paquete_original_id}")
    print(f"Paquete final:     {r.paquete_id or '(ninguno: conflicto irresoluble)'}")
    print(f"Replanificado:     {'si' if r.replanificado else 'no'}")
    print(f"Conflictos:        {r.detalle_conflicto}")
    print(f"Fuentes citadas:   {', '.join(r.fuentes_citadas) if r.fuentes_citadas else '(ninguna)'}")
    print(f"Trace:             {r.archivo_trace}")

    if args.pasos:
        mostrar_trace(r.archivo_trace, omitir=lineas_previas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
