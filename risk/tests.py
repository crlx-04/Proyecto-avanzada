from datetime import timedelta
from unittest import TestCase as PlainTestCase
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from events.models import Quake
from integrations.errors import ExternalAPIError

from .models import RiskAssessment
from .services import (
    assess_location,
    compute_risk,
    level_for,
    quake_score_for,
    rain_score_for,
)

Level = RiskAssessment.Level


class ScoreTests(PlainTestCase):
    def test_umbrales_de_nivel(self):
        self.assertEqual(level_for(24), Level.LOW)
        self.assertEqual(level_for(25), Level.MEDIUM)
        self.assertEqual(level_for(50), Level.HIGH)
        self.assertEqual(level_for(75), Level.CRITICAL)

    def test_puntaje_de_lluvia(self):
        self.assertEqual(rain_score_for(0, 0), 0)
        self.assertEqual(rain_score_for(35.7, 2.7), 32)
        self.assertEqual(rain_score_for(500, 500), 100)  # nunca pasa de 100

    def test_sin_sismos_el_puntaje_es_cero(self):
        self.assertEqual(quake_score_for([]), 0)

    def test_un_sismo_grande_pesa_mas_que_uno_pequeno(self):
        self.assertGreater(quake_score_for([6.0]), quake_score_for([3.5]))

    def test_magnitudes_vacias_no_rompen_el_calculo(self):
        # Un sismo sin magnitud solo cuenta por cantidad (2 puntos)
        self.assertEqual(quake_score_for([None]), 2)

    def test_muchos_sismos_pequenos_tienen_un_tope(self):
        self.assertEqual(quake_score_for([2.0] * 100), 40)


class ComputeRiskTests(PlainTestCase):
    def test_sin_lluvia_ni_sismos_el_riesgo_es_bajo(self):
        result = compute_risk(0, 0, [], 300, 30)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.level, Level.LOW)
        self.assertIn("No hubo sismos", result.explanation)

    def test_lluvia_extrema_es_critico(self):
        result = compute_risk(60, 50, [], 300, 30)
        self.assertEqual(result.level, Level.CRITICAL)

    def test_el_nivel_general_lo_manda_el_factor_mas_alto(self):
        result = compute_risk(0, 0, [6.0], 300, 30)
        self.assertEqual(result.score, result.quake_score)
        self.assertEqual(result.rain_score, 0)
        self.assertEqual(result.level, Level.HIGH)

    def test_la_explicacion_menciona_los_datos(self):
        result = compute_risk(35.7, 2.7, [4.6], 300, 30)
        self.assertIn("35.7 mm", result.explanation)
        self.assertIn("magnitud 4.6", result.explanation)


def quake_dict(quake_id, mag):
    return {
        "id": quake_id, "magnitude": mag, "place": "Cerca de Riohacha",
        "latitude": 11.8, "longitude": -72.9, "depth_km": 20.0,
        "time": timezone.now() - timedelta(days=1),
    }


class AssessLocationTests(TestCase):
    @patch("integrations.usgs.fetch_quakes")
    @patch("integrations.open_meteo.fetch_precipitation")
    def test_guarda_la_evaluacion_y_los_sismos(self, rain, quakes):
        rain.return_value = {"past_mm": 35.7, "forecast_mm": 2.7}
        quakes.return_value = [quake_dict("a", 4.6)]
        assessment = assess_location(11.54, -72.91)
        self.assertEqual(RiskAssessment.objects.count(), 1)
        self.assertEqual(Quake.objects.count(), 1)
        self.assertEqual(assessment.quake_count, 1)
        self.assertEqual(assessment.max_magnitude, 4.6)
        self.assertEqual(assessment.rain_score, 32)

    @patch("integrations.usgs.fetch_quakes", return_value=[])
    @patch("integrations.open_meteo.fetch_precipitation")
    def test_zona_sin_sismos(self, rain, _quakes):
        rain.return_value = {"past_mm": 0.0, "forecast_mm": 0.0}
        assessment = assess_location(11.54, -72.91)
        self.assertEqual(assessment.quake_count, 0)
        self.assertIsNone(assessment.max_magnitude)
        self.assertEqual(assessment.level, Level.LOW)

    @patch("integrations.usgs.fetch_quakes", side_effect=ExternalAPIError("USGS caído"))
    @patch("integrations.open_meteo.fetch_precipitation")
    def test_si_falla_una_api_no_se_guarda_nada(self, rain, _quakes):
        rain.return_value = {"past_mm": 1.0, "forecast_mm": 1.0}
        with self.assertRaises(ExternalAPIError):
            assess_location(11.54, -72.91)
        self.assertEqual(RiskAssessment.objects.count(), 0)


class SourceCheckTests(TestCase):
    @patch("integrations.usgs.fetch_quakes", return_value=[])
    @patch("integrations.open_meteo.fetch_precipitation")
    def test_registra_consultas_exitosas_y_guarda_lluvia_diaria(self, rain, _quakes):
        from .models import SourceCheck
        daily = [{"date": None, "mm": 1.0, "forecast": False}]
        rain.return_value = {"past_mm": 1.0, "forecast_mm": 0.0, "daily": daily}
        assessment = assess_location(11.54, -72.91)
        self.assertEqual(assessment.rain_daily, daily)
        self.assertEqual(set(SourceCheck.objects.filter(ok=True).values_list("source", flat=True)), {"open_meteo", "usgs"})

    @patch("integrations.usgs.fetch_quakes", side_effect=ExternalAPIError("USGS caído"))
    @patch("integrations.open_meteo.fetch_precipitation")
    def test_registra_la_falla_de_una_fuente(self, rain, _quakes):
        from .models import SourceCheck
        rain.return_value = {"past_mm": 1.0, "forecast_mm": 1.0}
        with self.assertRaises(ExternalAPIError):
            assess_location(11.54, -72.91)
        failed = SourceCheck.objects.get(ok=False)
        self.assertEqual(failed.source, "usgs")
        self.assertIn("USGS caído", failed.detail)
