"""Utilidades geográficas sencillas."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1, lon1, lat2, lon2):
    """Distancia en km entre dos puntos de la Tierra (fórmula de Haversine)."""
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
