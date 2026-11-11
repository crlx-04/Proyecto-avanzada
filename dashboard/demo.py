"""Evaluación de ejemplo para mostrar la plataforma sin conexión a internet.

Los datos son fijos: no se consultan APIs ni se guarda nada en la base de datos.
Sirve como plan B en una presentación si no hay internet.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from risk.models import RiskAssessment
from risk.services import compute_risk

PLACE = "Riohacha, La Guajira (ejemplo)"
LAT, LON, RADIUS_KM, DAYS = 11.5444, -72.9072, 300, 30
# Momento fijo de la evaluación de ejemplo (hora de Colombia, UTC-5)
EVALUATED_AT = datetime(2026, 11, 10, 8, 0, tzinfo=dt_timezone(timedelta(hours=-5)))
RAIN_PAST_MM, RAIN_FORECAST_MM = 38.0, 46.5

# (días antes de la evaluación, magnitud, lugar, lat, lon, profundidad km)
_QUAKES = [
    (1, 4.8, "38 km NE de Santa Marta, Colombia", 11.62, -73.88, 22.0),
    (3, 3.9, "52 km S de Riohacha, Colombia", 11.04, -72.95, 14.5),
    (6, 4.3, "70 km O de Maracaibo, Venezuela", 10.72, -72.10, 9.0),
    (9, 3.4, "25 km N de Valledupar, Colombia", 10.64, -73.25, 18.0),
    (14, 4.1, "44 km SO de Riohacha, Colombia", 11.18, -73.15, 31.0),
    (21, 3.2, "61 km E de Uribia, Colombia", 11.72, -72.05, 12.0),
]
# Evaluaciones previas de la misma zona (días antes, puntaje) para el gráfico de evolución
_HISTORY = [(13, 21), (11, 28), (9, 35), (7, 33), (5, 41), (3, 52), (2, 58), (1, 66)]


def _quakes():
    return [
        {
            "time": EVALUATED_AT - timedelta(days=d, hours=2 + i),
            "magnitude": mag, "place": place, "latitude": la, "longitude": lo, "depth_km": depth,
        }
        for i, (d, mag, place, la, lo, depth) in enumerate(_QUAKES)
    ]


def build():
    """Devuelve (evaluación sin guardar, sismos, historial de puntajes) de la demostración."""
    quakes = _quakes()
    magnitudes = [q["magnitude"] for q in quakes]
    result = compute_risk(RAIN_PAST_MM, RAIN_FORECAST_MM, magnitudes, RADIUS_KM, DAYS)
    assessment = RiskAssessment(
        latitude=LAT, longitude=LON, radius_km=RADIUS_KM, days=DAYS,
        rain_past_mm=RAIN_PAST_MM, rain_forecast_mm=RAIN_FORECAST_MM,
        quake_count=len(quakes), max_magnitude=max(magnitudes),
        rain_score=result.rain_score, quake_score=result.quake_score,
        score=result.score, level=result.level, explanation=result.explanation,
        created_at=EVALUATED_AT,
    )
    assessment.place_label = PLACE
    history = [(EVALUATED_AT - timedelta(days=d), score) for d, score in _HISTORY]
    history.append((EVALUATED_AT, assessment.score))
    return assessment, quakes, history
