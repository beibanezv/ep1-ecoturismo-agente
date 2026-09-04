"""Prompts del agente (apartado B / IE2): instruccion de sistema + plantilla de consulta con citas."""

SISTEMA_BASE = """\
Eres el agente de planificacion de una agencia boutique de ecoturismo en el sur de Chile.

Reglas:
1. Responde SOLO con informacion del CONTEXTO RECUPERADO. No inventes paquetes, precios, fechas, senderos ni guias.
2. Cita cada afirmacion factual con el marcador del fragmento fuente, en formato [F1], [F2], etc. Sin cita = sin afirmacion.
3. Si el contexto no basta para responder, di exactamente: "No tengo informacion suficiente en la base de conocimiento interna" y explica que dato falta.
4. Escribe en espanol, tono profesional y cercano, maximo 200 palabras.
5. Si el pedido menciona un mes, revisa que este dentro de la temporada del paquete antes de recomendarlo.
6. Si hay RESULTADOS DE HERRAMIENTAS EXTERNAS ([T1], [T2], etc.), usalos para validar la recomendacion: informa conflictos de sendero o clima citando la fuente, pero no cambies de paquete por tu cuenta.
"""

PLANTILLA_USUARIO = """\
CONTEXTO RECUPERADO:
{bloque_contexto}
{bloque_herramientas}
PEDIDO DEL CLIENTE:
{consulta}

Tu tarea: proponer el paquete mas adecuado (o responder la pregunta) citando los fragmentos que fundamenten cada decision. Si ningun fragmento calza, aplica la regla 3.
"""


def armar_usuario(consulta: str, fragmentos: list, resultados_tools: list | None = None) -> str:
    lineas = []
    for i, f in enumerate(fragmentos, start=1):
        lineas.append(f"[F{i}] (fuente: {f.fuente}, tipo: {f.tipo})\n{f.texto}")
    bloque = "\n\n".join(lineas) if lineas else "(sin fragmentos recuperados)"
    bloque_tools = ""
    if resultados_tools:
        partes = [
            f"[T{i}] (fuente: {fuente})\n{texto}"
            for i, (fuente, texto) in enumerate(resultados_tools, start=1)
        ]
        bloque_tools = "RESULTADOS DE HERRAMIENTAS EXTERNAS:\n" + "\n\n".join(partes) + "\n"
    return PLANTILLA_USUARIO.format(
        bloque_contexto=bloque, bloque_herramientas=bloque_tools, consulta=consulta
    )
