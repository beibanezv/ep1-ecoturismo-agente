"""Clima real via Open-Meteo (sin API key). Si la fecha esta fuera del rango
de pronostico (~16 dias) responde disponible=False: nunca inventa datos."""
import requests

COORDENADAS_REGION = {
    "Los Lagos": (-41.47, -72.94),
    "Magallanes": (-53.16, -70.91),
    "Araucanía": (-38.74, -73.25),
    "Los Ríos": (-39.81, -73.25),
    "Aysén": (-45.57, -72.07),
}

NOMBRE_FUENTE = "open-meteo.com"
PRECIPITACION_MAX_MM = 10.0
VIENTO_MAX_KMH = 50.0
TEMP_MINIMA_C = -2.0


def pronostico(region: str, fecha_iso: str, obtener=requests.get) -> dict:
    base = {"disponible": False, "region": region, "fecha": fecha_iso, "fuente": NOMBRE_FUENTE}
    if region not in COORDENADAS_REGION:
        return {**base, "motivo": f"Region sin coordenadas: {region}"}
    lat, lon = COORDENADAS_REGION[region]
    try:
        r = obtener(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weathercode",
                "start_date": fecha_iso,
                "end_date": fecha_iso,
                "timezone": "America/Santiago",
            },
            timeout=15,
        )
        r.raise_for_status()
        diario = r.json().get("daily", {})
    except Exception as e:
        return {**base, "motivo": f"Error consultando Open-Meteo: {e}"}
    if not diario or not diario.get("time"):
        return {**base, "motivo": "Fecha fuera del rango de pronostico (Open-Meteo cubre ~16 dias hacia adelante)"}
    return {
        **base,
        "disponible": True,
        "temp_max_c": diario["temperature_2m_max"][0],
        "temp_min_c": diario["temperature_2m_min"][0],
        "precipitacion_mm": diario["precipitation_sum"][0],
        "viento_max_kmh": diario["wind_speed_10m_max"][0],
        "codigo_clima": diario["weathercode"][0],
    }


def es_conflicto_climatico(p: dict) -> tuple[bool, str]:
    if not p.get("disponible"):
        return False, "sin datos climaticos"
    motivos = []
    if (p.get("precipitacion_mm") or 0) >= PRECIPITACION_MAX_MM:
        motivos.append(f"precipitacion {p['precipitacion_mm']} mm >= {PRECIPITACION_MAX_MM} mm")
    if (p.get("viento_max_kmh") or 0) >= VIENTO_MAX_KMH:
        motivos.append(f"viento {p['viento_max_kmh']} km/h >= {VIENTO_MAX_KMH} km/h")
    if (p.get("temp_min_c") if p.get("temp_min_c") is not None else 99) <= TEMP_MINIMA_C:
        motivos.append(f"temperatura minima {p['temp_min_c']} C <= {TEMP_MINIMA_C} C")
    return (True, "; ".join(motivos)) if motivos else (False, "condiciones aptas")


def describir_pronostico(p: dict) -> str:
    if not p.get("disponible"):
        return f"Clima no disponible para {p['region']} el {p['fecha']}: {p.get('motivo')}."
    return (
        f"Pronostico {p['region']} {p['fecha']} ({NOMBRE_FUENTE}): "
        f"temp max {p['temp_max_c']} C, min {p['temp_min_c']} C, "
        f"precipitacion {p['precipitacion_mm']} mm, viento max {p['viento_max_kmh']} km/h."
    )
