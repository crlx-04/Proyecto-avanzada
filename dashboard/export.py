"""Exportación de evaluaciones a CSV (se abre directo en Excel)."""
import csv
from io import StringIO

from django.utils import timezone

from risk.models import RiskAssessment

# Excel en español usa ";" como separador y "," como decimal
DELIMITER = ";"
HEADER = [
    "Zona", "Fecha", "Latitud", "Longitud", "Radio (km)",
    "Lluvia últimos 3 días (mm)", "Lluvia prevista (mm)",
    "Sismos", "Mayor magnitud",
    "Puntaje lluvia", "Puntaje sismos", "Índice de riesgo", "Nivel",
]


def _num(value):
    """Número con coma decimal; vacío si no hay dato."""
    if value is None:
        return ""
    return str(value).replace(".", ",")


def rows(user, zone=None):
    """Evaluaciones de las zonas del usuario (de una sola zona si se indica), de la más reciente a la más antigua."""
    queryset = RiskAssessment.objects.filter(zone__user=user).select_related("zone")
    if zone is not None:
        queryset = queryset.filter(zone=zone)
    for item in queryset:
        yield [
            item.zone.name,
            timezone.localtime(item.created_at).strftime("%Y-%m-%d %H:%M"),
            _num(item.latitude), _num(item.longitude), item.radius_km,
            _num(item.rain_past_mm), _num(item.rain_forecast_mm),
            item.quake_count, _num(item.max_magnitude),
            item.rain_score, item.quake_score, item.score, item.get_level_display(),
        ]


def build_csv(user, zone=None):
    """Texto CSV con BOM UTF-8 para que Excel muestre bien las tildes."""
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=DELIMITER)
    writer.writerow(HEADER)
    writer.writerows(rows(user, zone))
    return "﻿" + buffer.getvalue()
