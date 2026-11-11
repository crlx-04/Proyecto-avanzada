from datetime import timedelta
from unittest import TestCase as PlainTestCase
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Quake
from integrations.errors import ExternalAPIError
from risk.models import RiskAssessment

from .services import label_for, zone_history


def make_assessment(lat=11.54, lon=-72.91, score=32, level="medio"):
    return RiskAssessment.objects.create(
        latitude=lat, longitude=lon, radius_km=300, days=30,
        rain_past_mm=35.7, rain_forecast_mm=2.7, quake_count=0, max_magnitude=None,
        rain_score=score, quake_score=0, score=score, level=level,
        explanation="Explicación de prueba.",
    )


VALID_FORM = {"latitude": "11.54", "longitude": "-72.91", "radius_km": "300", "days": "30"}


class HomeViewTests(TestCase):
    def test_muestra_el_formulario_y_el_aviso_de_incertidumbre(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evaluar riesgo")
        self.assertContains(response, "Usar mi ubicación")
        self.assertContains(response, "no una predicción")

    def test_los_botones_de_ciudades_usan_punto_decimal(self):
        # Con idioma es-co Django escribiría "11,5444", que un campo numérico rechaza
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, 'data-lat="11.5444"')
        self.assertContains(response, 'data-lon="-72.9072"')
        self.assertNotContains(response, 'data-lat="11,5444"')

    def test_acepta_valores_precargados_por_url(self):
        response = self.client.get(reverse("dashboard:home"), {"latitude": "4.7", "longitude": "-74.1"})
        self.assertContains(response, 'value="4.7"')

    @patch("dashboard.views.assess_location")
    def test_evaluacion_valida_redirige_al_detalle(self, assess):
        assessment = make_assessment()
        assess.return_value = assessment
        response = self.client.post(reverse("dashboard:home"), VALID_FORM)
        self.assertRedirects(response, reverse("dashboard:detail", args=[assessment.pk]))
        assess.assert_called_once_with(11.54, -72.91, 300, 30)

    @patch("dashboard.views.assess_location")
    def test_coordenadas_invalidas_no_evaluan(self, assess):
        response = self.client.post(reverse("dashboard:home"), {**VALID_FORM, "latitude": "100"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("latitude", response.context["form"].errors)
        assess.assert_not_called()

    @patch("dashboard.views.assess_location", side_effect=ExternalAPIError("USGS caído"))
    def test_si_falla_una_api_se_muestra_un_mensaje(self, _assess):
        response = self.client.post(reverse("dashboard:home"), VALID_FORM)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No se pudo completar la evaluación")
        self.assertContains(response, "USGS caído")
        self.assertEqual(RiskAssessment.objects.count(), 0)


class DetailViewTests(TestCase):
    def test_muestra_explicacion_lugar_y_sismos_de_la_zona(self):
        assessment = make_assessment()
        Quake.objects.create(
            usgs_id="q1", magnitude=4.6, place="Cerca de Riohacha", latitude=11.8,
            longitude=-72.9, depth_km=20.0, time=timezone.now() - timedelta(days=2),
        )
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explicación de prueba.")
        self.assertContains(response, "Cerca de Riohacha")
        self.assertContains(response, "Riohacha")
        self.assertContains(response, "no una predicción")

    def test_muestra_la_recomendacion_del_nivel(self):
        assessment = make_assessment(level="alto", score=60)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, "Conviene estar atento")

    def test_nivel_alto_muestra_alerta_y_recomendaciones(self):
        assessment = make_assessment(level="alto", score=60)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, "¡Alerta!")
        self.assertContains(response, "Revisa tu plan y tu ruta de evacuación.")

    def test_nivel_bajo_no_muestra_alerta(self):
        assessment = make_assessment(level="bajo", score=10)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, "Sin alertas por ahora")
        self.assertNotContains(response, "¡Alerta!")

    def test_el_boton_evaluar_de_nuevo_envia_decimales_con_punto(self):
        assessment = make_assessment()
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, 'name="latitude" value="11.54"')
        self.assertContains(response, 'name="longitude" value="-72.91"')

    def test_evaluacion_inexistente_da_404(self):
        response = self.client.get(reverse("dashboard:detail", args=[9999]))
        self.assertEqual(response.status_code, 404)


class HistoryViewTests(TestCase):
    def test_lista_las_evaluaciones_con_el_nombre_del_lugar(self):
        make_assessment(score=32)
        response = self.client.get(reverse("dashboard:history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Medio")
        self.assertContains(response, "Riohacha")

    def test_sin_evaluaciones_muestra_mensaje(self):
        response = self.client.get(reverse("dashboard:history"))
        self.assertContains(response, "Todavía no hay evaluaciones")


class LabelTests(PlainTestCase):
    def test_reconoce_un_lugar_cercano(self):
        self.assertEqual(label_for(11.54, -72.91), "Riohacha")

    def test_lugar_desconocido_devuelve_none(self):
        self.assertIsNone(label_for(0, 0))


class ZoneHistoryTests(TestCase):
    def test_solo_incluye_la_misma_zona_de_la_mas_antigua_a_la_mas_reciente(self):
        first = make_assessment(lat=11.54, lon=-72.91)
        make_assessment(lat=6.25, lon=-75.57)  # otra ciudad
        second = make_assessment(lat=11.55, lon=-72.90)  # a ~1,5 km de la primera
        history = zone_history(second)
        self.assertEqual([item.pk for item in history], [first.pk, second.pk])
