"""Lógica de las zonas guardadas: ordenarlas por riesgo y evaluarlas."""
from alerts.services import check_rules
from risk.services import assess_location


def zones_ranked(zones):
    """Devuelve las zonas con su última evaluación (zone.latest), de mayor a menor riesgo.

    Las zonas que aún no se han evaluado quedan al final.
    """
    zones = list(zones)
    for zone in zones:
        zone.latest = zone.assessments.first()  # RiskAssessment ordena por fecha descendente
    zones.sort(key=lambda z: (z.latest is None, -(z.latest.score if z.latest else 0), z.name.lower()))
    return zones


def summary(zones):
    """Cifras para las tarjetas de arriba: cantidad, promedio y zona más afectada."""
    evaluated = [z for z in zones if z.latest]
    average = round(sum(z.latest.score for z in evaluated) / len(evaluated)) if evaluated else None
    top = max(evaluated, key=lambda z: z.latest.score) if evaluated else None
    return {"count": len(zones), "evaluated": len(evaluated), "average": average, "top": top}


def evaluate_zone(zone):
    """Evalúa la zona con datos actuales y deja la evaluación asociada a ella.

    Puede lanzar ExternalAPIError si USGS u Open-Meteo no responden.
    """
    assessment = assess_location(zone.latitude, zone.longitude, zone.radius_km)
    assessment.zone = zone
    assessment.owner = zone.user
    assessment.save(update_fields=["zone", "owner"])
    assessment.new_alerts = check_rules(assessment)  # revisa las reglas del usuario con estos datos
    return assessment
