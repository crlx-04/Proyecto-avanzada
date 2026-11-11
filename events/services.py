"""Lógica de sismos: guardar lo que trae USGS y consultar el historial guardado."""
from datetime import timedelta
from math import cos, radians

from django.utils import timezone

from integrations import usgs

from .geo import distance_km
from .models import Quake

KM_PER_DEGREE = 111.0


def refresh_quakes(lat, lon, radius_km, days):
    """Consulta USGS, guarda los sismos (sin duplicarlos) y devuelve los de esa consulta.

    Lanza ExternalAPIError (de `integrations`) si USGS no responde.
    """
    saved = []
    for item in usgs.fetch_quakes(lat, lon, radius_km, days):
        quake, _created = Quake.objects.update_or_create(
            usgs_id=item["id"],
            defaults={
                "magnitude": item["magnitude"],
                "place": item["place"],
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "depth_km": item["depth_km"],
                "time": item["time"],
            },
        )
        saved.append(quake)
    return saved


def quakes_near(lat, lon, radius_km, days, until=None):
    """Sismos ya guardados en la base de datos dentro de `radius_km` de un punto.

    La ventana de tiempo son los `days` días que terminan en `until` (por defecto, ahora).
    Primero filtra con un cuadro aproximado (rápido, lo hace la base de datos)
    y luego con la distancia exacta. No cubre el cruce del meridiano 180°.
    """
    end = until or timezone.now()
    start = end - timedelta(days=days)
    lat_margin = radius_km / KM_PER_DEGREE
    lon_margin = radius_km / (KM_PER_DEGREE * max(cos(radians(lat)), 0.01))
    candidates = Quake.objects.filter(
        time__gte=start,
        time__lte=end,
        latitude__range=(lat - lat_margin, lat + lat_margin),
        longitude__range=(lon - lon_margin, lon + lon_margin),
    )
    return [q for q in candidates if distance_km(lat, lon, q.latitude, q.longitude) <= radius_km]
