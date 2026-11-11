"""Cliente de la API de Open-Meteo (lluvia pasada y prevista)."""
import requests

from .errors import ExternalAPIError

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 10
PAST_DAYS = 3
FORECAST_DAYS = 3


def fetch_precipitation(lat, lon):
    """Devuelve {"past_mm", "forecast_mm", "daily"} para el punto (lat, lon).

    `daily` es la lista de días con su lluvia: {"date": "AAAA-MM-DD" o None, "mm": float,
    "forecast": bool}; `forecast` es True para los días previstos (hoy incluido).

    Se piden PAST_DAYS días pasados y FORECAST_DAYS de pronóstico (el pronóstico
    incluye el día de hoy). Open-Meteo devuelve un valor por día, así que los
    primeros PAST_DAYS son lluvia ya caída y los siguientes son lluvia prevista.

    Lanza ExternalAPIError si el servicio no responde o la respuesta es inválida.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",
    }
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        daily_data = response.json()["daily"]
        raw_values = daily_data["precipitation_sum"]
        dates = daily_data.get("time") or []
        if all(value is None for value in raw_values):
            # Sin ningún dato no se puede decir "no llueve": se avisa en vez de inventar ceros
            raise ExternalAPIError("Open-Meteo no devolvió datos de lluvia para este lugar.")
        # Algunos días sueltos pueden venir como None (sin dato); se cuentan como 0 mm
        values = [float(value or 0.0) for value in raw_values]
        if len(values) < PAST_DAYS + FORECAST_DAYS:
            raise ExternalAPIError("Open-Meteo devolvió menos días de los esperados.")
        daily = [
            {
                "date": dates[index] if index < len(dates) else None,
                "mm": round(value, 1),
                "forecast": index >= PAST_DAYS,
            }
            for index, value in enumerate(values[:PAST_DAYS + FORECAST_DAYS])
        ]
        return {
            "past_mm": round(sum(values[:PAST_DAYS]), 1),
            "forecast_mm": round(sum(values[PAST_DAYS:PAST_DAYS + FORECAST_DAYS]), 1),
            "daily": daily,
        }
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise ExternalAPIError(f"Error consultando Open-Meteo: {exc}") from exc
