"""Cliente de la API de sismos del USGS (United States Geological Survey)."""
from datetime import datetime, timedelta, timezone

import requests

from .errors import ExternalAPIError

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
TIMEOUT_SECONDS = 10


def fetch_quakes(lat, lon, radius_km, days):
    """Devuelve los sismos ocurridos en los últimos `days` días dentro de
    `radius_km` kilómetros del punto (lat, lon), del más reciente al más antiguo.

    Cada sismo es un diccionario con las claves:
    id, magnitude, place, latitude, longitude, depth_km, time (datetime en UTC).

    Lanza ExternalAPIError si el servicio no responde o la respuesta es inválida.
    """
    # Ventana exacta de `days` días terminando ahora (en UTC), la misma que luego se muestra en el detalle
    now = datetime.now(timezone.utc)
    params = {
        "format": "geojson",
        "latitude": lat,
        "longitude": lon,
        "maxradiuskm": radius_km,
        "starttime": (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "orderby": "time",
    }
    try:
        response = requests.get(USGS_URL, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        features = response.json()["features"]
        return [_parse_feature(feature) for feature in features]
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise ExternalAPIError(f"Error consultando USGS: {exc}") from exc


def _parse_feature(feature):
    """Convierte un sismo en formato GeoJSON a un diccionario simple."""
    properties = feature["properties"]
    # GeoJSON guarda las coordenadas como [longitud, latitud, profundidad_km]
    longitude, latitude, depth_km = feature["geometry"]["coordinates"][:3]
    return {
        "id": feature["id"],
        # La magnitud puede venir vacía (None) en eventos sin calcular
        "magnitude": properties.get("mag"),
        "place": properties.get("place") or "Sin descripción",
        "latitude": latitude,
        "longitude": longitude,
        "depth_km": depth_km,
        # El tiempo llega en milisegundos desde 1970
        "time": datetime.fromtimestamp(properties["time"] / 1000, tz=timezone.utc),
    }
