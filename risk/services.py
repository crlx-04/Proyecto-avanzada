"""Cálculo del índice de riesgo.

IMPORTANTE: el índice es una estimación basada en reglas simples sobre datos
recientes. No predice terremotos ni inundaciones. En sismos mide *actividad
reciente* de la zona, no la probabilidad de que ocurra uno.
"""
import time
from dataclasses import dataclass

from events.services import refresh_quakes
from integrations import open_meteo
from integrations.errors import ExternalAPIError

from .models import RiskAssessment, SourceCheck

# --- Lluvia: cada milímetro pesa más si es previsto que si ya cayó ---
PAST_RAIN_WEIGHT = 0.8
FORECAST_RAIN_WEIGHT = 1.2

# --- Sismos: puntos por la mayor magnitud + puntos por la cantidad ---
MIN_RELEVANT_MAGNITUDE = 3.0   # por debajo de esto no suma puntos de magnitud
POINTS_PER_MAGNITUDE = 20      # puntos por cada grado sobre el mínimo
MAX_MAGNITUDE_POINTS = 60
POINTS_PER_QUAKE = 2
MAX_COUNT_POINTS = 40

DISCLAIMER = (
    "Esta es una estimación basada en datos recientes, no una predicción. "
    "En sismos solo refleja la actividad reciente de la zona; los terremotos no se pueden predecir."
)


@dataclass(frozen=True)
class RiskResult:
    score: int
    level: str
    rain_score: int
    quake_score: int
    explanation: str


def level_for(score):
    """Convierte un puntaje 0-100 en un nivel de riesgo."""
    if score < 25:
        return RiskAssessment.Level.LOW
    if score < 50:
        return RiskAssessment.Level.MEDIUM
    if score < 75:
        return RiskAssessment.Level.HIGH
    return RiskAssessment.Level.CRITICAL


def rain_score_for(past_mm, forecast_mm):
    raw = past_mm * PAST_RAIN_WEIGHT + forecast_mm * FORECAST_RAIN_WEIGHT
    return round(min(100, raw))


def quake_score_for(magnitudes):
    """`magnitudes` es la lista de magnitudes de los sismos (puede contener None)."""
    known = [m for m in magnitudes if m is not None]
    magnitude_points = 0
    if known:
        magnitude_points = (max(known) - MIN_RELEVANT_MAGNITUDE) * POINTS_PER_MAGNITUDE
        magnitude_points = min(MAX_MAGNITUDE_POINTS, max(0, magnitude_points))
    count_points = min(MAX_COUNT_POINTS, len(magnitudes) * POINTS_PER_QUAKE)
    return round(min(100, magnitude_points + count_points))


def _label(level):
    return RiskAssessment.Level(level).label


def compute_risk(past_mm, forecast_mm, magnitudes, radius_km, days):
    """Calcula el riesgo a partir de lluvia y sismos. No toca la red ni la base de datos."""
    rain_score = rain_score_for(past_mm, forecast_mm)
    quake_score = quake_score_for(magnitudes)
    # El nivel general lo manda el factor más alto
    score = max(rain_score, quake_score)
    level = level_for(score)

    parts = [
        f"En los últimos {open_meteo.PAST_DAYS} días cayeron {past_mm} mm de lluvia y se prevén "
        f"{forecast_mm} mm en los próximos días. "
        f"Riesgo por lluvia: {_label(level_for(rain_score))} ({rain_score}/100)."
    ]
    if not magnitudes:
        parts.append(
            f"No hubo sismos registrados en los últimos {days} días dentro de {radius_km} km. "
            f"Actividad sísmica reciente: {_label(level_for(quake_score))} ({quake_score}/100)."
        )
    else:
        known = [m for m in magnitudes if m is not None]
        biggest = f", el mayor de magnitud {max(known)}" if known else ""
        parts.append(
            f"Hubo {len(magnitudes)} sismo(s) en los últimos {days} días dentro de {radius_km} km"
            f"{biggest}. Actividad sísmica reciente: "
            f"{_label(level_for(quake_score))} ({quake_score}/100)."
        )
    parts.append(f"El nivel general ({_label(level)}) corresponde al factor más alto.")

    return RiskResult(
        score=score,
        level=level,
        rain_score=rain_score,
        quake_score=quake_score,
        explanation=" ".join(parts),
    )


def _checked(source, function, *args):
    """Llama a una fuente externa y deja registrado si respondió bien y cuánto tardó."""
    started = time.monotonic()
    try:
        result = function(*args)
    except ExternalAPIError as exc:
        SourceCheck.objects.create(
            source=source, ok=False, detail=str(exc)[:255], duration_ms=int((time.monotonic() - started) * 1000)
        )
        raise
    SourceCheck.objects.create(source=source, ok=True, duration_ms=int((time.monotonic() - started) * 1000))
    return result


def assess_location(lat, lon, radius_km=300, days=30):
    """Consulta lluvia y sismos, calcula el riesgo y guarda la evaluación.

    Lanza ExternalAPIError si falla alguna de las dos APIs (no guarda nada en ese caso).
    """
    rain = _checked(SourceCheck.Source.OPEN_METEO, open_meteo.fetch_precipitation, lat, lon)
    quakes = _checked(SourceCheck.Source.USGS, refresh_quakes, lat, lon, radius_km, days)
    magnitudes = [quake.magnitude for quake in quakes]
    result = compute_risk(rain["past_mm"], rain["forecast_mm"], magnitudes, radius_km, days)

    known = [m for m in magnitudes if m is not None]
    return RiskAssessment.objects.create(
        latitude=lat,
        longitude=lon,
        radius_km=radius_km,
        days=days,
        rain_past_mm=rain["past_mm"],
        rain_forecast_mm=rain["forecast_mm"],
        quake_count=len(quakes),
        max_magnitude=max(known) if known else None,
        rain_score=result.rain_score,
        quake_score=result.quake_score,
        score=result.score,
        level=result.level,
        explanation=result.explanation,
        rain_daily=rain.get("daily", []),
    )
