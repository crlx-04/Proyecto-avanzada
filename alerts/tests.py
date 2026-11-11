from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Zone
from accounts.services import evaluate_zone
from risk.models import RiskAssessment

from .forms import RuleForm
from .models import Alert, AlertRule
from .services import MAX_RULES, check_rules, would_trigger

User = get_user_model()
PASSWORD = "clave-segura-2026"


def assessment(zone, score=60, past=20, forecast=40, mag=5.2):
    return RiskAssessment.objects.create(
        latitude=zone.latitude, longitude=zone.longitude, radius_km=300, days=30,
        rain_past_mm=past, rain_forecast_mm=forecast, quake_count=1, max_magnitude=mag,
        rain_score=50, quake_score=40, score=score, level="alto", explanation="x", zone=zone,
    )


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password=PASSWORD)
        self.zone = Zone.objects.create(user=self.user, name="Casa", latitude=11.5, longitude=-72.9)
        self.client.login(username="ana", password=PASSWORD)

    def rule(self, kind="score", threshold=50, **kw):
        return AlertRule.objects.create(user=self.user, zone=self.zone, kind=kind, threshold=threshold, **kw)


class CheckRulesTests(Base):
    def test_regla_cumplida_crea_alerta(self):
        self.rule("score", 50)
        created = check_rules(assessment(self.zone, score=60))
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].severity, "alta")
        self.assertIn("Casa", created[0].message)

    def test_regla_no_cumplida_no_crea_alerta(self):
        self.rule("score", 80)
        self.assertEqual(check_rules(assessment(self.zone, score=60)), [])

    def test_score_75_o_mas_es_critica(self):
        self.rule("score", 50)
        self.assertEqual(check_rules(assessment(self.zone, score=80))[0].severity, "critica")

    def test_lluvia_suma_pasada_y_prevista(self):
        self.rule("rain", 55)
        created = check_rules(assessment(self.zone, past=20, forecast=40))
        self.assertEqual(created[0].value, 60)

    def test_sismo_sin_datos_no_alerta(self):
        self.rule("quake", 4)
        self.assertEqual(check_rules(assessment(self.zone, mag=None)), [])

    def test_sismo_sobre_umbral_alerta(self):
        self.rule("quake", 5)
        self.assertEqual(len(check_rules(assessment(self.zone, mag=5.2))), 1)

    def test_regla_inactiva_se_ignora(self):
        self.rule("score", 10, active=False)
        self.assertEqual(check_rules(assessment(self.zone)), [])

    def test_no_repite_alerta_sin_ver(self):
        self.rule("score", 50)
        check_rules(assessment(self.zone))
        self.assertEqual(check_rules(assessment(self.zone)), [])
        self.assertEqual(Alert.objects.count(), 1)

    def test_vuelve_a_alertar_si_la_anterior_ya_fue_vista(self):
        self.rule("score", 50)
        check_rules(assessment(self.zone)); Alert.objects.update(seen=True)
        self.assertEqual(len(check_rules(assessment(self.zone))), 1)

    def test_evaluacion_sin_zona_no_alerta(self):
        a = assessment(self.zone); a.zone = None
        self.assertEqual(check_rules(a), [])

    def test_evaluate_zone_dispara_reglas(self):
        self.rule("score", 50)
        fake = assessment(self.zone, score=70); fake.zone = None; fake.save()
        with patch("accounts.services.assess_location", return_value=fake):
            result = evaluate_zone(self.zone)
        self.assertEqual(len(result.new_alerts), 1)

    def test_would_trigger_cuenta_evaluaciones_previas(self):
        assessment(self.zone, score=60); assessment(self.zone, score=20)
        self.assertEqual(would_trigger("score", 50, self.zone), 1)


class ViewTests(Base):
    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("alerts:list")).status_code, 302)

    def test_lista_muestra_alertas_y_reglas(self):
        self.rule("score", 50); check_rules(assessment(self.zone))
        html = self.client.get(reverse("alerts:list")).content.decode()
        self.assertIn("Alertas activas", html)
        self.assertIn("Índice de riesgo ≥ 50", html)

    def test_crear_regla(self):
        r = self.client.post(reverse("alerts:rule_create"), {"zone": self.zone.pk, "kind": "rain", "threshold": "120"})
        self.assertRedirects(r, reverse("alerts:list"))
        self.assertEqual(AlertRule.objects.get().threshold, 120)

    def test_umbral_fuera_de_rango_se_rechaza(self):
        self.client.post(reverse("alerts:rule_create"), {"zone": self.zone.pk, "kind": "score", "threshold": "500"})
        self.assertEqual(AlertRule.objects.count(), 0)

    def test_regla_duplicada_se_rechaza(self):
        self.rule("score", 50)
        self.client.post(reverse("alerts:rule_create"), {"zone": self.zone.pk, "kind": "score", "threshold": "50"})
        self.assertEqual(AlertRule.objects.count(), 1)

    def test_no_se_puede_usar_zona_ajena(self):
        other = User.objects.create_user("beto", password=PASSWORD)
        z = Zone.objects.create(user=other, name="Ajena", latitude=1, longitude=1)
        self.client.post(reverse("alerts:rule_create"), {"zone": z.pk, "kind": "score", "threshold": "50"})
        self.assertEqual(AlertRule.objects.count(), 0)

    def test_limite_de_reglas(self):
        for i in range(MAX_RULES):
            self.rule("score", i + 1)
        form = RuleForm({"zone": self.zone.pk, "kind": "rain", "threshold": 10}, user=self.user)
        self.assertFalse(form.is_valid())

    def test_alternar_y_eliminar_regla(self):
        r = self.rule()
        self.client.post(reverse("alerts:rule_toggle", args=[r.pk]))
        r.refresh_from_db(); self.assertFalse(r.active)
        self.client.post(reverse("alerts:rule_delete", args=[r.pk]))
        self.assertEqual(AlertRule.objects.count(), 0)

    def test_marcar_vista_y_todas(self):
        r = self.rule(); check_rules(assessment(self.zone))
        a = Alert.objects.get()
        self.client.post(reverse("alerts:seen", args=[a.pk]))
        a.refresh_from_db(); self.assertTrue(a.seen)
        Alert.objects.update(seen=False)
        self.client.post(reverse("alerts:seen_all"))
        self.assertFalse(Alert.objects.filter(seen=False).exists())

    def test_acciones_solo_con_post(self):
        r = self.rule()
        self.assertEqual(self.client.get(reverse("alerts:rule_toggle", args=[r.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("alerts:rule_delete", args=[r.pk])).status_code, 405)

    def test_no_toca_reglas_ni_alertas_ajenas(self):
        r = self.rule(); check_rules(assessment(self.zone)); a = Alert.objects.get()
        self.client.logout()
        User.objects.create_user("beto", password=PASSWORD); self.client.login(username="beto", password=PASSWORD)
        self.assertEqual(self.client.post(reverse("alerts:rule_toggle", args=[r.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("alerts:rule_delete", args=[r.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("alerts:seen", args=[a.pk])).status_code, 404)

    def test_contador_en_menu(self):
        self.rule(); check_rules(assessment(self.zone))
        html = self.client.get(reverse("accounts:zones")).content.decode()
        self.assertIn('class="nbadge"', html)


class EscalationTests(Base):
    def test_si_empeora_a_critica_se_actualiza_la_alerta_pendiente(self):
        self.rule("score", 50)
        check_rules(assessment(self.zone, score=60))          # alta
        updated = check_rules(assessment(self.zone, score=90))  # crítica, aún sin ver la anterior
        self.assertEqual(len(updated), 1)
        self.assertEqual(Alert.objects.count(), 1)
        alert = Alert.objects.get()
        self.assertEqual((alert.severity, alert.value), ("critica", 90))

    def test_si_sigue_igual_no_se_toca_la_alerta_pendiente(self):
        self.rule("score", 50)
        check_rules(assessment(self.zone, score=90))
        self.assertEqual(check_rules(assessment(self.zone, score=95)), [])
        self.assertEqual(Alert.objects.get().value, 90)


class CsrfTests(Base):
    def test_post_sin_token_csrf_es_rechazado(self):
        from django.test import Client
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="ana", password=PASSWORD)
        r = strict.post(reverse("alerts:rule_create"), {"zone": self.zone.pk, "kind": "score", "threshold": "50"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(AlertRule.objects.count(), 0)
