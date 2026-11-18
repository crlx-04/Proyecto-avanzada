"""Buscador de lugares por nombre (API de geocodificación de Open-Meteo, sin clave)."""
import logging

import requests

from .errors import ExternalAPIError

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT_SECONDS = 8
MAX_RESULTS = 6


def search_places(query, limit=MAX_RESULTS):
    """Devuelve hasta `limit` lugares que coinciden con `query`.

    Cada lugar es un diccionario con: name (ciudad o pueblo), detail (región y país),
    latitude y longitude. Si no hay coincidencias devuelve una lista vacía.

    Lanza ExternalAPIError si el servicio no responde o la respuesta es inválida.
    """
    params = {"name": query, "count": limit, "language": "es", "format": "json"}
    try:
        response = requests.get(GEOCODING_URL, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        # Cuando no hay coincidencias la API no incluye la clave "results"
        results = response.json().get("results") or []
        return [_parse_place(item) for item in results[:limit]]
    except requests.RequestException as exc:
        logger.warning("El buscador de lugares no respondió: %s", exc)
        raise ExternalAPIError(
            "No se pudo conectar con el buscador de lugares. Revisa tu conexión o elige el punto en el mapa."
        ) from exc
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Respuesta inesperada del buscador de lugares: %r", exc)
        raise ExternalAPIError("El buscador de lugares devolvió una respuesta que no se pudo interpretar.") from exc


def _parse_place(item):
    """Convierte un resultado de la API en un diccionario simple."""
    name = str(item["name"])
    # admin1 es el departamento, estado o provincia; puede no venir o repetir el nombre (Lima, Lima)
    region = item.get("admin1")
    if region == name:
        region = None
    detail = ", ".join(part for part in (region, item.get("country")) if part)
    return {
        "name": name,
        "detail": detail,
        "latitude": round(float(item["latitude"]), 4),
        "longitude": round(float(item["longitude"]), 4),
    }
