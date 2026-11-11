from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.errors import ExternalAPIError
from risk.models import RiskAssessment

from .forms import MAX_ZONES
from .models import Zone
from .services import evaluate_zone, summary, zones_ranked

User = get_user_model()
PASSWORD = "clave-segura-2026"


def make_assessment(lat=11.54, lon=-72.91, score=30, level="medio", zone=None):
    return RiskAssessment.objects.create(
        latitude=lat, longitude=lon, radius_km=300, days=30,
        rain_past_mm=10, rain_forecast_mm=5, quake_count=0, max_magnitude=None,
        rain_score=score, quake_score=0, score=score, level=level,
        explanation="Explicación.", zone=zone,
    )


class AuthTests(TestCase):
    def test_registro_crea_usuario_y_abre_sesion(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"username": "ana", "password1": PASSWORD, "password2": PASSWORD},
        )
        self.assertRedirects(response, reverse("accounts:zones"))
        self.assertTrue(User.objects.filter(username="ana").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_registro_rechaza_contrasenas_distintas(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"username": "ana", "password1": PASSWORD, "password2": "otra-clave-2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="ana").exists())

    def test_registro_rechaza_contrasena_numerica(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"username": "ana", "password1": "12345678", "password2": "12345678"},
        )
        self.assertFalse(User.objects.filter(username="ana").exists())
        self.assertIn("password2", response.context["form"].errors)

    def test_login_correcto_y_incorrecto(self):
        User.objects.create_user("ana", password=PASSWORD)
        bad = self.client.post(reverse("accounts:login"), {"username": "ana", "password": "mala"})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "alert")
        ok = self.client.post(reverse("accounts:login"), {"username": "ana", "password": PASSWORD})
        self.assertRedirects(ok, reverse("accounts:zones"))

    def test_logout_solo_por_post(self):
        user = User.objects.create_user("ana", password=PASSWORD)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_zonas_exige_sesion(self):
        response = self.client.get(reverse("accounts:zones"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:zones')}")


class ZoneTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password=PASSWORD)
        self.other = User.objects.create_user("beto", password=PASSWORD)
        self.client.force_login(self.user)

    def post_zone(self, **overrides):
        data = {"name": "Casa", "latitude": "11.54", "longitude": "-72.91", "radius_km": "300", **overrides}
        return self.client.post(reverse("accounts:zones"), data)

    def test_crear_zona_valida(self):
        response = self.post_zone()
        self.assertRedirects(response, reverse("accounts:zones"))
        zone = Zone.objects.get()
        self.assertEqual((zone.user, zone.name, zone.latitude), (self.user, "Casa", 11.54))

    def test_coordenadas_invalidas_no_crean_zona(self):
        response = self.post_zone(latitude="120")
        self.assertEqual(response.status_code, 200)
        self.assertIn("latitude", response.context["form"].errors)
        self.assertEqual(Zone.objects.count(), 0)

    def test_nombre_duplicado_se_rechaza_sin_importar_mayusculas(self):
        Zone.objects.create(user=self.user, name="Casa", latitude=1, longitude=1)
        response = self.post_zone(name="casa")
        self.assertIn("name", response.context["form"].errors)
        self.assertEqual(Zone.objects.count(), 1)

    def test_otro_usuario_puede_usar_el_mismo_nombre(self):
        Zone.objects.create(user=self.other, name="Casa", latitude=1, longitude=1)
        self.post_zone()
        self.assertEqual(Zone.objects.filter(user=self.user).count(), 1)

    def test_limite_de_zonas(self):
        for i in range(MAX_ZONES):
            Zone.objects.create(user=self.user, name=f"Z{i}", latitude=1, longitude=1)
        response = self.post_zone(name="Una más")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hasta")
        self.assertEqual(Zone.objects.filter(user=self.user).count(), MAX_ZONES)

    def test_la_lista_solo_muestra_zonas_propias(self):
        Zone.objects.create(user=self.user, name="Mía", latitude=1, longitude=1)
        Zone.objects.create(user=self.other, name="Ajena", latitude=1, longitude=1)
        response = self.client.get(reverse("accounts:zones"))
        self.assertContains(response, "Mía")
        self.assertNotContains(response, "Ajena")

    def test_no_se_puede_eliminar_una_zona_ajena(self):
        zone = Zone.objects.create(user=self.other, name="Ajena", latitude=1, longitude=1)
        response = self.client.post(reverse("accounts:zone_delete", args=[zone.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Zone.objects.filter(pk=zone.pk).exists())

    def test_eliminar_zona_conserva_sus_evaluaciones(self):
        zone = Zone.objects.create(user=self.user, name="Casa", latitude=1, longitude=1)
        assessment = make_assessment(zone=zone)
        self.client.post(reverse("accounts:zone_delete", args=[zone.pk]))
        assessment.refresh_from_db()
        self.assertIsNone(assessment.zone)
        self.assertEqual(Zone.objects.count(), 0)

    def test_eliminar_exige_post(self):
        zone = Zone.objects.create(user=self.user, name="Casa", latitude=1, longitude=1)
        self.assertEqual(self.client.get(reverse("accounts:zone_delete", args=[zone.pk])).status_code, 405)

    @patch("accounts.services.assess_location")
    def test_evaluar_zona_asocia_la_evaluacion_y_redirige_al_detalle(self, assess):
        zone = Zone.objects.create(user=self.user, name="Casa", latitude=11.54, longitude=-72.91, radius_km=200)
        assess.return_value = make_assessment()
        response = self.client.post(reverse("accounts:zone_evaluate", args=[zone.pk]))
        assess.assert_called_once_with(11.54, -72.91, 200)
        assessment = assess.return_value
        assessment.refresh_from_db()
        self.assertEqual(assessment.zone, zone)
        self.assertRedirects(response, reverse("dashboard:detail", args=[assessment.pk]))

    @patch("accounts.services.assess_location", side_effect=ExternalAPIError("Open-Meteo caído"))
    def test_si_falla_una_api_se_avisa_y_no_se_rompe(self, _assess):
        zone = Zone.objects.create(user=self.user, name="Casa", latitude=1, longitude=1)
        response = self.client.post(reverse("accounts:zone_evaluate", args=[zone.pk]), follow=True)
        self.assertContains(response, "No se pudo completar la evaluación")

    @patch("accounts.services.assess_location")
    def test_evaluar_todas_continua_aunque_una_falle(self, assess):
        Zone.objects.create(user=self.user, name="Buena", latitude=1, longitude=1)
        Zone.objects.create(user=self.user, name="Mala", latitude=2, longitude=2)

        def fake(lat, lon, radius):
            if lat == 2:
                raise ExternalAPIError("falló")
            return make_assessment(lat=lat, lon=lon)

        assess.side_effect = fake
        response = self.client.post(reverse("accounts:zones_evaluate_all"), follow=True)
        self.assertContains(response, "Se evaluaron 1 zona")
        self.assertContains(response, "No se pudo evaluar: Mala")

    def test_guardar_zona_desde_una_evaluacion(self):
        assessment = make_assessment()
        response = self.client.post(
            reverse("accounts:zone_save"), {"assessment_id": assessment.pk, "name": "Mi finca"}
        )
        self.assertRedirects(response, reverse("dashboard:detail", args=[assessment.pk]))
        zone = Zone.objects.get()
        self.assertEqual((zone.name, zone.latitude, zone.longitude), ("Mi finca", 11.54, -72.91))
        assessment.refresh_from_db()
        self.assertEqual(assessment.zone, zone)

    def test_guardar_zona_sin_nombre_no_crea_nada(self):
        assessment = make_assessment()
        self.client.post(reverse("accounts:zone_save"), {"assessment_id": assessment.pk, "name": "  "})
        self.assertEqual(Zone.objects.count(), 0)

    def test_el_detalle_ofrece_guardar_solo_con_sesion(self):
        assessment = make_assessment()
        url = reverse("dashboard:detail", args=[assessment.pk])
        self.assertContains(self.client.get(url), "Guardar zona")
        self.client.logout()
        anonymous = self.client.get(url)
        self.assertContains(anonymous, "Inicia sesión para guardar")
        self.assertNotContains(anonymous, "Guardar zona")

    def test_cualquiera_puede_evaluar_sin_cuenta(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 200)


class ServiceTests(TestCase):
    def test_ranking_de_mayor_a_menor_y_sin_evaluar_al_final(self):
        user = User.objects.create_user("ana", password=PASSWORD)
        low = Zone.objects.create(user=user, name="Baja", latitude=1, longitude=1)
        high = Zone.objects.create(user=user, name="Alta", latitude=2, longitude=2)
        Zone.objects.create(user=user, name="Nueva", latitude=3, longitude=3)
        make_assessment(score=20, level="bajo", zone=low)
        make_assessment(score=70, level="alto", zone=high)
        ranked = zones_ranked(Zone.objects.filter(user=user))
        self.assertEqual([z.name for z in ranked], ["Alta", "Baja", "Nueva"])
        info = summary(ranked)
        self.assertEqual((info["count"], info["evaluated"], info["average"]), (3, 2, 45))
        self.assertEqual(info["top"].name, "Alta")

    def test_resumen_sin_evaluaciones(self):
        info = summary([])
        self.assertEqual((info["count"], info["average"], info["top"]), (0, None, None))

    def test_la_ultima_evaluacion_es_la_mas_reciente(self):
        user = User.objects.create_user("ana", password=PASSWORD)
        zone = Zone.objects.create(user=user, name="Casa", latitude=1, longitude=1)
        make_assessment(score=10, level="bajo", zone=zone)
        newest = make_assessment(score=60, level="alto", zone=zone)
        self.assertEqual(zones_ranked([zone])[0].latest, newest)
