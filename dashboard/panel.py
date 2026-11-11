"""Datos del panel: lluvia por día, sismos, mapa de calor por zona y estado de las fuentes."""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from events.services import quakes_near
from risk.models import SourceCheck
from risk.services import level_for

HEATMAP_DAYS = 7
EVOLUTION_LIMIT = 30
SOURCE_WINDOW = 20  # cuántas consultas recientes cuentan para el % de éxito


def _local_date(moment):
    return timezone.localtime(moment).date()


def rain_series(assessment):
    """Barras de lluvia diaria de una evaluación (vacío si es anterior a que se guardara el detalle)."""
    labels, values, forecast = [], [], []
    for index, day in enumerate(assessment.rain_daily or []):
        label = day.get("date")
        labels.append(f"{label[8:10]}/{label[5:7]}" if label else f"Día {index + 1}")
        values.append(day["mm"])
        forecast.append(bool(day.get("forecast")))
    return {"labels": labels, "values": values, "forecast": forecast}


def evolution(zone):
    """Puntajes de las últimas evaluaciones de la zona, de la más antigua a la más reciente."""
    items = list(zone.assessments.all()[:EVOLUTION_LIMIT])[::-1]
    return {
        "labels": [timezone.localtime(a.created_at).strftime("%d/%m %H:%M") for a in items],
        "scores": [a.score for a in items],
    }


def quake_points(assessment):
    """Sismos de la ventana de la evaluación como puntos (días antes de evaluar, magnitud)."""
    quakes = quakes_near(
        assessment.latitude, assessment.longitude, assessment.radius_km, assessment.days,
        until=assessment.created_at,
    )
    points = []
    for quake in quakes:
        if quake.magnitude is None:
            continue
        days_ago = (assessment.created_at - quake.time).total_seconds() / 86400
        points.append({"x": round(-days_ago, 2), "y": quake.magnitude, "place": quake.place})
    return {"points": points, "omitted": len(quakes) - len(points), "window": assessment.days}


def heatmap(zones, days=HEATMAP_DAYS):
    """Mapa de calor: por cada zona y día, el mayor puntaje evaluado ese día (None si no se evaluó)."""
    today = timezone.localdate()
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    rows = []
    for zone in zones:
        best = defaultdict(int)
        seen = set()
        for assessment in zone.assessments.filter(created_at__gte=timezone.now() - timedelta(days=days + 1)):
            day = _local_date(assessment.created_at)
            seen.add(day)
            best[day] = max(best[day], assessment.score)
        cells = []
        for day in dates:
            score = best[day] if day in seen else None
            cells.append({"score": score, "level": level_for(score).value if score is not None else None})
        rows.append({"zone": zone, "cells": cells})
    return {"dates": dates, "rows": rows}


def source_status():
    """Estado de cada fuente: última consulta y porcentaje de éxito reciente."""
    result = []
    for value, label in SourceCheck.Source.choices:
        recent = list(SourceCheck.objects.filter(source=value)[:SOURCE_WINDOW])
        last = recent[0] if recent else None
        ok_count = sum(1 for check in recent if check.ok)
        result.append(
            {
                "label": label,
                "last": last,
                "ok_percent": round(100 * ok_count / len(recent)) if recent else None,
                "checks": len(recent),
            }
        )
    return result
