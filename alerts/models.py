from django.conf import settings
from django.db import models


class AlertRule(models.Model):
    """Condición que el usuario quiere vigilar en una de sus zonas."""

    class Kind(models.TextChoices):
        SCORE = "score", "Índice de riesgo"
        RAIN = "rain", "Lluvia acumulada"
        QUAKE = "quake", "Sismo de magnitud"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alert_rules")
    zone = models.ForeignKey("accounts.Zone", on_delete=models.CASCADE, related_name="alert_rules")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    threshold = models.FloatField("umbral")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["zone__name", "kind", "threshold"]
        constraints = [
            models.UniqueConstraint(fields=["zone", "kind", "threshold"], name="unique_rule_per_zone")
        ]

    def __str__(self):
        return f"{self.zone.name}: {self.description}"

    @property
    def unit(self):
        return {"score": "/100", "rain": " mm", "quake": ""}[self.kind]

    @property
    def description(self):
        t = f"{self.threshold:g}"
        if self.kind == self.Kind.SCORE:
            return f"Índice de riesgo ≥ {t}"
        if self.kind == self.Kind.RAIN:
            return f"Lluvia (pasada + prevista) ≥ {t} mm"
        return f"Sismo de magnitud ≥ {t} en el radio de la zona"


class Alert(models.Model):
    """Aviso generado cuando una evaluación cumple una regla."""

    class Severity(models.TextChoices):
        HIGH = "alta", "Alta"
        CRITICAL = "critica", "Crítica"

    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name="alerts")
    assessment = models.ForeignKey(
        "risk.RiskAssessment", null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts"
    )
    severity = models.CharField(max_length=10, choices=Severity.choices)
    value = models.FloatField("valor medido")
    message = models.CharField(max_length=255)
    seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.message
