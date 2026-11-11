from django.conf import settings
from django.db import models


class RiskAssessment(models.Model):
    """Resultado de evaluar una ubicación en un momento dado."""

    class Level(models.TextChoices):
        LOW = "bajo", "Bajo"
        MEDIUM = "medio", "Medio"
        HIGH = "alto", "Alto"
        CRITICAL = "critico", "Crítico"

    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_km = models.PositiveIntegerField("radio de búsqueda de sismos (km)")
    days = models.PositiveSmallIntegerField("días de historial de sismos")

    rain_past_mm = models.FloatField("lluvia de los últimos 3 días (mm)")
    rain_forecast_mm = models.FloatField("lluvia prevista (mm)")
    quake_count = models.PositiveIntegerField("cantidad de sismos")
    max_magnitude = models.FloatField("mayor magnitud", null=True, blank=True)

    rain_score = models.PositiveSmallIntegerField("puntaje por lluvia (0-100)")
    quake_score = models.PositiveSmallIntegerField("puntaje por actividad sísmica (0-100)")
    score = models.PositiveSmallIntegerField("puntaje general (0-100)")
    level = models.CharField(max_length=10, choices=Level.choices)
    explanation = models.TextField("explicación")
    # Lluvia día por día: [{"date": "2026-11-10", "mm": 3.2, "forecast": false}, ...]
    rain_daily = models.JSONField("lluvia diaria", default=list, blank=True)

    # Quién hizo la evaluación (vacío si el visitante no tenía sesión: entonces solo la ve su navegador)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assessments"
    )
    # Zona guardada a la que pertenece esta evaluación (vacío si el visitante no inició sesión)
    zone = models.ForeignKey(
        "accounts.Zone", null=True, blank=True, on_delete=models.SET_NULL, related_name="assessments"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"({self.latitude}, {self.longitude}) {self.level} {self.score}/100"


class SourceCheck(models.Model):
    """Registro de cada consulta a una fuente externa, para mostrar su estado en el panel."""

    class Source(models.TextChoices):
        OPEN_METEO = "open_meteo", "Open-Meteo (lluvia)"
        USGS = "usgs", "USGS (sismos)"

    source = models.CharField(max_length=20, choices=Source.choices)
    ok = models.BooleanField()
    detail = models.CharField(max_length=255, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.source} {'ok' if self.ok else 'falló'}"
