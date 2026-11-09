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

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"({self.latitude}, {self.longitude}) {self.level} {self.score}/100"
