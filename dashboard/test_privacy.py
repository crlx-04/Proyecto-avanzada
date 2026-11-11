"""Privacidad: cada persona solo ve y usa sus propias evaluaciones."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Zone
from accounts.services import evaluate_zone
from risk.models import RiskAssessment

User = get_user_model()
PASSWORD = "clave-segura-2026"


def make(zone=None, owner=None, lat=11.5, lon=-72.9):
    return RiskAssessment.objects.create(
        latitude=lat, longitude=lon, radius_km=300, days=30, rain_past_mm=1, rain_forecast_mm=1,
        quake_count=0, rain_score=5, quake_score=0, score=5, level="bajo", explanation="x",
        zone=zone, owner=owner,
    )


class PrivacyTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", password=PASSWORD)
        self.beto = User.objects.create_user("beto", password=PASSWORD)
        self.zone_ana = Zone.objects.create(user=self.ana, name="Casa de Ana", latitude=11.5, longitude=-72.9)
        self.secret = make(zone=self.zone_ana, owner=self.ana)

    def test_visitante_anonimo_no_ve_evaluacion_ajena(self):
        self.assertEqual(self.client.get(reverse("dashboard:detail", args=[self.secret.pk])).status_code, 404)

    def test_otro_usuario_no_ve_evaluacion_ajena(self):
        self.client.login(username="beto", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("dashboard:detail", args=[self.secret.pk])).status_code, 404)

    def test_el_dueno_si_la_ve(self):
        self.client.login(username="ana", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("dashboard:detail", args=[self.secret.pk])).status_code, 200)

    def test_historial_e_inicio_no_filtran_evaluaciones_ajenas(self):
        for url in ("dashboard:history", "dashboard:home"):
            html = self.client.get(reverse(url)).content.decode()
            self.assertNotIn("11,5", html)
            self.assertNotIn(str(self.secret.latitude).replace(".", ","), html)
        self.client.login(username="beto", password=PASSWORD)
        self.assertEqual(len(self.client.get(reverse("dashboard:history")).context["assessments"]), 0)

    def test_historial_del_dueno_incluye_sus_evaluaciones(self):
        self.client.login(username="ana", password=PASSWORD)
        self.assertEqual(len(self.client.get(reverse("dashboard:history")).context["assessments"]), 1)

    def test_evaluacion_anonima_solo_la_ve_quien_la_hizo(self):
        fake = make()
        with patch("dashboard.views.assess_location", return_value=fake):
            response = self.client.post(reverse("dashboard:home"),
                                        {"latitude": "11.5", "longitude": "-72.9", "radius_km": "300", "days": "30"})
        self.assertRedirects(response, reverse("dashboard:detail", args=[fake.pk]))
        self.assertEqual(self.client.get(reverse("dashboard:detail", args=[fake.pk])).status_code, 200)
        otro = self.client_class()
        self.assertEqual(otro.get(reverse("dashboard:detail", args=[fake.pk])).status_code, 404)

    def test_historial_de_zona_no_mezcla_evaluaciones_de_otros(self):
        from dashboard.views import detail  # noqa: F401  (asegura que la vista existe)
        make(owner=self.ana)
        beto_eval = make(owner=self.beto)
        self.client.login(username="beto", password=PASSWORD)
        response = self.client.get(reverse("dashboard:detail", args=[beto_eval.pk]))
        self.assertEqual(response.context["history_count"], 1)

    def test_guardar_zona_no_permite_apropiarse_de_evaluacion_ajena(self):
        self.client.login(username="beto", password=PASSWORD)
        self.client.post(reverse("accounts:zone_save"), {"assessment_id": self.secret.pk, "name": "Robada"})
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.zone, self.zone_ana)
        self.assertFalse(Zone.objects.filter(user=self.beto).exists())

    def test_guardar_zona_con_id_malformado_responde_404(self):
        self.client.login(username="beto", password=PASSWORD)
        self.assertEqual(self.client.post(reverse("accounts:zone_save"), {"assessment_id": "abc", "name": "X"}).status_code, 404)

    def test_evaluar_zona_deja_la_evaluacion_a_nombre_del_usuario(self):
        fake = make()
        with patch("accounts.services.assess_location", return_value=fake):
            evaluate_zone(self.zone_ana)
        fake.refresh_from_db()
        self.assertEqual(fake.owner, self.ana)

    def test_exportar_con_zona_malformada_responde_404(self):
        self.client.login(username="ana", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("dashboard:export_csv"), {"zona": "abc"}).status_code, 404)
