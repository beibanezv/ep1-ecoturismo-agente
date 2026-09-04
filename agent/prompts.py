"""Prompts del agente (apartado B / IE2): instruccion de sistema + plantilla de consulta con citas."""

SISTEMA_BASE = """\
Eres el agente de planificacion de una agencia boutique de ecoturismo en el sur de Chile.

Reglas:
1. Responde SOLO con informacion del CONTEXTO RECUPERADO. No inventes paquetes, precios, fechas, senderos ni guias.
2. Cita cada afirmacion factual con el marcador del fragmento fuente, en formato [F1], [F2], etc. Sin cita = sin afirmacion.
3. Si el contexto no basta para responder, di exactamente: "No tengo informacion suficiente en la base de conocimiento interna" y explica que dato falta.
4. Escribe en espanol, tono profesional y cercano, maximo 200 palabras.
5. Si el pedido menciona un mes, revisa que este dentro de la temporada del paquete antes de recomendarlo.
"""

PLANTILLA_USUARIO = """\
CONTEXTO RECUPERADO:
{bloque_contexto}

PEDIDO DEL CLIENTE:
{consulta}

Tu tarea: proponer el paquete mas adecuado (o responder la pregunta) citando los fragmentos que fundamenten cada decision. Si ningun fragmento calza, aplica la regla 3.
"""


def armar_usuario(consulta: str, fragmentos: list) -> str:
    lineas = []
    for i, f in enumerate(fragmentos, start=1):
        lineas.append(f"[F{i}] (fuente: {f.fuente}, tipo: {f.tipo})\n{f.texto}")
    bloque = "\n\n".join(lineas) if lineas else "(sin fragmentos recuperados)"
    return PLANTILLA_USUARIO.format(bloque_contexto=bloque, consulta=consulta)
