from django.conf import settings
from django.db import models


class Zone(models.Model):
    """Lugar que un usuario guarda para vigilar su riesgo (ej. «Mi casa», «Finca»)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField("nombre", max_length=60)
    latitude = models.FloatField("latitud")
    longitude = models.FloatField("longitud")
    radius_km = models.PositiveIntegerField("radio de búsqueda de sismos (km)", default=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_zone_name_per_user"),
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"
