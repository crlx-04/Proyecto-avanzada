"""Pruebas del buscador de lugares, del nombre guardado con la evaluación y de las páginas de error."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from integrations.errors import ExternalAPIError
from risk.models import RiskAssessment

from .tests import VALID_FORM, make_assessment, remember

PLACES = [{"name": "Lima", "detail": "Perú", "latitude": -12.0432, "longitude": -77.0282}]


class PlaceSearchViewTests(TestCase):
    @patch("dashboard.views.geocoding.search_places", return_value=PLACES)
    def test_devuelve_los_lugares_en_json(self, search):
        response = self.client.get(reverse("dashboard:place_search"), {"q": "  lima "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": PLACES})
        search.assert_called_once_with("lima")  # se quitan los espacios sobrantes

    @patch("dashboard.views.geocoding.search_places")
    def test_texto_muy_corto_no_consulta_la_api(self, search):
        response = self.client.get(reverse("dashboard:place_search"), {"q": "a"})
        self.assertEqual(response.json(), {"results": []})
        search.assert_not_called()

    @patch("dashboard.views.geocoding.search_places", return_value=[])
    def test_el_texto_se_recorta_a_80_caracteres(self, search):
        self.client.get(reverse("dashboard:place_search"), {"q": "x" * 500})
        self.assertEqual(len(search.call_args.args[0]), 80)

    @patch("dashboard.views.geocoding.search_places", side_effect=ExternalAPIError("No se pudo conectar."))
    def test_si_la_api_falla_responde_503_con_mensaje(self, _search):
        response = self.client.get(reverse("dashboard:place_search"), {"q": "lima"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "No se pudo conectar.")


class PlaceNameTests(TestCase):
    def test_la_pagina_principal_tiene_el_buscador(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, 'id="place-query"')
        self.assertContains(response, 'name="place_name"')

    @patch("dashboard.views.assess_location")
    def test_el_nombre_elegido_llega_a_la_evaluacion(self, assess):
        assess.return_value = make_assessment()
        self.client.post(reverse("dashboard:home"), {**VALID_FORM, "place_name": " Lima, Perú "})
        self.assertEqual(assess.call_args.kwargs["place_name"], "Lima, Perú")

    def test_nombre_demasiado_largo_no_se_acepta(self):
        response = self.client.post(reverse("dashboard:home"), {**VALID_FORM, "place_name": "x" * 81})
        self.assertEqual(response.status_code, 200)  # vuelve al formulario, no evalúa
        self.assertEqual(RiskAssessment.objects.count(), 0)

    def test_el_detalle_y_el_historial_muestran_el_nombre_guardado(self):
        assessment = make_assessment(lat=-12.04, lon=-77.03)
        assessment.place_name = "Lima, Perú"
        assessment.save()
        remember(self.client, assessment)
        self.assertContains(self.client.get(reverse("dashboard:detail", args=[assessment.pk])), "Lima, Perú")
        self.assertContains(self.client.get(reverse("dashboard:history")), "Lima, Perú")

    def test_sin_nombre_guardado_se_usa_el_lugar_conocido_mas_cercano(self):
        assessment = make_assessment()  # coordenadas de Riohacha
        remember(self.client, assessment)
        self.assertContains(self.client.get(reverse("dashboard:history")), "Riohacha")

    def test_un_nombre_con_html_se_muestra_como_texto(self):
        assessment = make_assessment()
        assessment.place_name = "<script>alert(1)</script>"
        assessment.save()
        remember(self.client, assessment)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")


class HomeErrorMessageTests(TestCase):
    @patch("dashboard.views.assess_location", side_effect=ExternalAPIError("No se pudo conectar con USGS."))
    def test_el_error_se_muestra_en_lenguaje_claro(self, _assess):
        response = self.client.post(reverse("dashboard:home"), VALID_FORM)
        self.assertContains(response, "No se pudo completar la evaluación. No se pudo conectar con USGS.")


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_pagina_404_propia(self):
        response = self.client.get("/esta-pagina-no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "No encontramos esa página", status_code=404)
        self.assertContains(response, "Volver al inicio", status_code=404)

    def test_evaluacion_ajena_muestra_la_404_propia(self):
        assessment = make_assessment()  # nadie la "recuerda" en esta sesión
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, "No encontramos esa página", status_code=404)

    def test_pagina_500_propia(self):
        self.client.raise_request_exception = False  # que responda 500 en vez de lanzar el error en la prueba
        with patch("dashboard.views.visible_to", side_effect=RuntimeError("fallo inesperado")):
            response = self.client.get(reverse("dashboard:history"))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Algo salió mal", status_code=500)
