"""Pruebas de los clientes externos con datos simulados (no usan internet)."""
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from .errors import ExternalAPIError
from .open_meteo import fetch_precipitation
from .usgs import fetch_quakes


def fake_response(payload):
    """Crea una respuesta falsa de `requests` que devuelve `payload` como JSON."""
    return Mock(json=lambda: payload, raise_for_status=lambda: None)


SAMPLE_USGS = {
    "features": [
        {
            "id": "us1234",
            "properties": {"mag": 4.6, "place": "30 km N de Riohacha", "time": 1700000000000},
            "geometry": {"coordinates": [-72.9, 11.8, 25.0]},
        },
        {
            "id": "us5678",
            "properties": {"mag": None, "place": None, "time": 1700003600000},
            "geometry": {"coordinates": [-73.0, 11.7, 10.0]},
        },
    ]
}


class FetchQuakesTests(TestCase):
    @patch("integrations.usgs.requests.get")
    def test_convierte_los_sismos_a_diccionarios(self, get):
        get.return_value = fake_response(SAMPLE_USGS)
        quakes = fetch_quakes(11.54, -72.91, 300, 30)
        self.assertEqual(len(quakes), 2)
        first = quakes[0]
        self.assertEqual(first["id"], "us1234")
        self.assertEqual(first["magnitude"], 4.6)
        self.assertEqual(first["latitude"], 11.8)
        self.assertEqual(first["longitude"], -72.9)
        self.assertEqual(first["depth_km"], 25.0)
        self.assertEqual(
            first["time"], datetime.fromtimestamp(1700000000, tz=timezone.utc)
        )

    @patch("integrations.usgs.requests.get")
    def test_acepta_magnitud_y_lugar_vacios(self, get):
        get.return_value = fake_response(SAMPLE_USGS)
        second = fetch_quakes(11.54, -72.91, 300, 30)[1]
        self.assertIsNone(second["magnitude"])
        self.assertEqual(second["place"], "Sin descripción")

    @patch("integrations.usgs.requests.get")
    def test_zona_sin_sismos_devuelve_lista_vacia(self, get):
        get.return_value = fake_response({"features": []})
        self.assertEqual(fetch_quakes(0, 0, 100, 7), [])

    @patch("integrations.usgs.requests.get", side_effect=requests.ConnectionError("sin red"))
    def test_error_de_red_lanza_external_api_error(self, _get):
        with self.assertRaises(ExternalAPIError):
            fetch_quakes(0, 0, 100, 7)

    @patch("integrations.usgs.requests.get")
    def test_respuesta_incompleta_lanza_external_api_error(self, get):
        get.return_value = fake_response({"sin_features": True})
        with self.assertRaises(ExternalAPIError):
            fetch_quakes(0, 0, 100, 7)


class FetchPrecipitationTests(TestCase):
    @patch("integrations.open_meteo.requests.get")
    def test_separa_lluvia_pasada_y_prevista(self, get):
        get.return_value = fake_response({"daily": {"precipitation_sum": [1, 2, 3, 4, 5, 6]}})
        self.assertEqual(
            fetch_precipitation(11.54, -72.91), {"past_mm": 6.0, "forecast_mm": 15.0}
        )

    @patch("integrations.open_meteo.requests.get")
    def test_valores_none_cuentan_como_cero(self, get):
        get.return_value = fake_response(
            {"daily": {"precipitation_sum": [None, 2, 3, 4, None, 6]}}
        )
        self.assertEqual(
            fetch_precipitation(0, 0), {"past_mm": 5.0, "forecast_mm": 10.0}
        )

    @patch("integrations.open_meteo.requests.get", side_effect=requests.Timeout("lento"))
    def test_error_de_red_lanza_external_api_error(self, _get):
        with self.assertRaises(ExternalAPIError):
            fetch_precipitation(0, 0)

    @patch("integrations.open_meteo.requests.get")
    def test_respuesta_incompleta_lanza_external_api_error(self, get):
        get.return_value = fake_response({"daily": {}})
        with self.assertRaises(ExternalAPIError):
            fetch_precipitation(0, 0)

    @patch("integrations.open_meteo.requests.get")
    def test_pocos_dias_lanza_external_api_error(self, get):
        get.return_value = fake_response({"daily": {"precipitation_sum": [1, 2, 3]}})
        with self.assertRaises(ExternalAPIError):
            fetch_precipitation(0, 0)
