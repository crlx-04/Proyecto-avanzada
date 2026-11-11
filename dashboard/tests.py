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


def remember(client, *assessments):
    """Hace que el navegador de prueba sea el autor de estas evaluaciones (así puede verlas)."""
    session = client.session
    session["ndip_assessments"] = [a.pk for a in assessments]
    session.save()


class DetailViewTests(TestCase):
    def test_muestra_explicacion_lugar_y_sismos_de_la_zona(self):
        assessment = make_assessment()
        remember(self.client, assessment)
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
        remember(self.client, assessment)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, "Conviene estar atento")

    def test_nivel_alto_muestra_alerta_y_recomendaciones(self):
        assessment = make_assessment(level="alto", score=60)
        remember(self.client, assessment)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, "¡Alerta!")
        self.assertContains(response, "Revisa tu plan y tu ruta de evacuación.")

    def test_nivel_bajo_no_muestra_alerta(self):
        assessment = make_assessment(level="bajo", score=10)
        remember(self.client, assessment)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, "Sin alertas por ahora")
        self.assertNotContains(response, "¡Alerta!")

    def test_el_boton_evaluar_de_nuevo_envia_decimales_con_punto(self):
        assessment = make_assessment()
        remember(self.client, assessment)
        response = self.client.get(reverse("dashboard:detail", args=[assessment.pk]))
        self.assertContains(response, 'name="latitude" value="11.54"')
        self.assertContains(response, 'name="longitude" value="-72.91"')

    def test_evaluacion_inexistente_da_404(self):
        response = self.client.get(reverse("dashboard:detail", args=[9999]))
        self.assertEqual(response.status_code, 404)


class HistoryViewTests(TestCase):
    def test_lista_las_evaluaciones_con_el_nombre_del_lugar(self):
        remember(self.client, make_assessment(score=32))
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


class DemoModeTests(TestCase):
    """La demostración funciona sin internet y sin datos previos."""

    def test_demo_abre_sin_datos_ni_red(self):
        with patch("risk.services.open_meteo.fetch_precipitation", side_effect=AssertionError("no debe usar la red")), \
             patch("events.services.usgs.fetch_quakes", side_effect=AssertionError("no debe usar la red")):
            response = self.client.get(reverse("dashboard:demo"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modo demostración")
        self.assertContains(response, "Riohacha")

    def test_demo_no_guarda_nada(self):
        from risk.models import RiskAssessment
        from events.models import Quake
        self.client.get(reverse("dashboard:demo"))
        self.assertEqual(RiskAssessment.objects.count(), 0)
        self.assertEqual(Quake.objects.count(), 0)

    def test_demo_es_coherente(self):
        from . import demo
        assessment, quakes, history = demo.build()
        self.assertEqual(assessment.score, max(assessment.rain_score, assessment.quake_score))
        self.assertEqual(assessment.quake_count, len(quakes))
        self.assertEqual(history[-1][1], assessment.score)

    def test_demo_no_ofrece_reevaluar_ni_guardar(self):
        response = self.client.get(reverse("dashboard:demo"))
        self.assertNotContains(response, "Evaluar de nuevo")
        self.assertNotContains(response, "Guardar zona")

    def test_demo_enlazada_desde_inicio(self):
        self.assertContains(self.client.get(reverse("dashboard:home")), reverse("dashboard:demo"))


class PanelTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import Zone
        self.user = get_user_model().objects.create_user("ana", password="clave-segura-2026")
        self.zone = Zone.objects.create(user=self.user, name="Casa", latitude=11.5, longitude=-72.9)
        self.client.login(username="ana", password="clave-segura-2026")

    def assessment(self, score=60, zone=None, daily=None, created=None):
        item = RiskAssessment.objects.create(
            latitude=11.5, longitude=-72.9, radius_km=300, days=30,
            rain_past_mm=10, rain_forecast_mm=5, quake_count=1, max_magnitude=4.5,
            rain_score=score, quake_score=10, score=score, level="alto", explanation="x",
            zone=zone or self.zone, rain_daily=daily or [],
        )
        if created:
            RiskAssessment.objects.filter(pk=item.pk).update(created_at=created)
            item.refresh_from_db()
        return item

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard:panel")).status_code, 302)

    def test_sin_zonas_muestra_mensaje(self):
        from accounts.models import Zone
        Zone.objects.all().delete()
        self.assertContains(self.client.get(reverse("dashboard:panel")), "Aún no tienes zonas guardadas")

    def test_zona_sin_evaluar(self):
        self.assertContains(self.client.get(reverse("dashboard:panel")), "aún no se ha evaluado")

    def test_muestra_lluvia_diaria_y_sismos(self):
        daily = [{"date": f"2026-11-{8 + i:02d}", "mm": float(i), "forecast": i >= 3} for i in range(6)]
        item = self.assessment(daily=daily)
        Quake.objects.create(usgs_id="q1", magnitude=4.5, place="Cerca", latitude=11.6, longitude=-72.9,
                             depth_km=10, time=item.created_at - timedelta(days=2))
        response = self.client.get(reverse("dashboard:panel"))
        self.assertEqual(response.context["rain"]["values"], [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(response.context["rain_total"], 15.0)
        self.assertEqual(len(response.context["quakes"]["points"]), 1)
        self.assertAlmostEqual(response.context["quakes"]["points"][0]["x"], -2, places=1)

    def test_evaluacion_antigua_sin_detalle_diario(self):
        self.assessment()
        response = self.client.get(reverse("dashboard:panel"))
        self.assertFalse(response.context["has_rain"])
        self.assertContains(response, "sin el detalle diario")

    def test_selecciona_zona_y_no_ve_ajenas(self):
        from django.contrib.auth import get_user_model
        from accounts.models import Zone
        other = get_user_model().objects.create_user("beto", password="clave-segura-2026")
        foreign = Zone.objects.create(user=other, name="Ajena", latitude=1, longitude=1)
        mine = Zone.objects.create(user=self.user, name="Finca", latitude=10, longitude=-73)
        response = self.client.get(reverse("dashboard:panel"), {"zona": foreign.pk})
        self.assertNotEqual(response.context["selected"], foreign)
        self.assertNotContains(response, "Ajena")
        self.assertEqual(self.client.get(reverse("dashboard:panel"), {"zona": mine.pk}).context["selected"], mine)

    def test_mapa_de_calor_toma_el_mayor_puntaje_del_dia(self):
        self.assessment(score=30); self.assessment(score=70)
        row = self.client.get(reverse("dashboard:panel")).context["heatmap"]["rows"][0]
        self.assertEqual(row["cells"][-1]["score"], 70)
        self.assertEqual(row["cells"][-1]["level"], "alto")
        self.assertIsNone(row["cells"][0]["score"])

    def test_estado_de_fuentes(self):
        from risk.models import SourceCheck
        SourceCheck.objects.create(source="usgs", ok=True, duration_ms=300)
        SourceCheck.objects.create(source="usgs", ok=False, detail="caído")
        self.assessment()
        sources = {s["label"]: s for s in self.client.get(reverse("dashboard:panel")).context["sources"]}
        self.assertEqual(sources["USGS (sismos)"]["ok_percent"], 50)
        self.assertIsNone(sources["Open-Meteo (lluvia)"]["last"])


class ExportCsvTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import Zone
        User = get_user_model()
        self.user = User.objects.create_user("ana", password="clave-segura-2026")
        self.zone = Zone.objects.create(user=self.user, name="Casa Norte", latitude=11.5, longitude=-72.9)
        self.other_zone = Zone.objects.create(user=self.user, name="Finca", latitude=10.1, longitude=-73.2)
        for zone, score in [(self.zone, 60), (self.other_zone, 20)]:
            RiskAssessment.objects.create(
                latitude=11.5, longitude=-72.9, radius_km=300, days=30, rain_past_mm=10.5, rain_forecast_mm=5,
                quake_count=0, max_magnitude=None, rain_score=score, quake_score=0, score=score,
                level="alto", explanation="x", zone=zone,
            )
        self.client.login(username="ana", password="clave-segura-2026")

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard:export_csv")).status_code, 302)

    def test_descarga_todas_las_zonas(self):
        response = self.client.get(reverse("dashboard:export_csv"))
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", response["Content-Disposition"])
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith("﻿Zona;Fecha"))
        self.assertEqual(len(text.strip().splitlines()), 3)  # encabezado + 2 evaluaciones
        self.assertIn("Casa Norte", text)
        self.assertIn("10,5", text)  # coma decimal para Excel en español

    def test_filtra_por_zona(self):
        text = self.client.get(reverse("dashboard:export_csv"), {"zona": self.zone.pk}).content.decode("utf-8")
        self.assertIn("Casa Norte", text)
        self.assertNotIn("Finca", text)

    def test_no_exporta_datos_ajenos(self):
        from django.contrib.auth import get_user_model
        from accounts.models import Zone
        other = get_user_model().objects.create_user("beto", password="clave-segura-2026")
        foreign = Zone.objects.create(user=other, name="Secreta", latitude=1, longitude=1)
        RiskAssessment.objects.create(
            latitude=1, longitude=1, radius_km=300, days=30, rain_past_mm=0, rain_forecast_mm=0, quake_count=0,
            rain_score=0, quake_score=0, score=0, level="bajo", explanation="x", zone=foreign)
        self.assertNotIn("Secreta", self.client.get(reverse("dashboard:export_csv")).content.decode("utf-8"))
        self.assertEqual(self.client.get(reverse("dashboard:export_csv"), {"zona": foreign.pk}).status_code, 404)

    def test_celdas_sin_dato_quedan_vacias(self):
        text = self.client.get(reverse("dashboard:export_csv")).content.decode("utf-8")
        self.assertIn(";0;;", text)  # 0 sismos y magnitud vacía


class ThemeToggleTests(TestCase):
    def test_boton_de_tema_y_sin_recuadro_de_fuentes(self):
        html = self.client.get(reverse("dashboard:home")).content.decode("utf-8")
        self.assertIn('id="theme-toggle"', html)
        self.assertIn("data-theme", html)
        self.assertNotIn("Fuentes de datos", html)
