from django.db import models


class Quake(models.Model):
    """Sismo traído de USGS. Se guarda para ir formando el historial propio."""

    usgs_id = models.CharField(max_length=50, unique=True)
    # La magnitud puede venir vacía en eventos que USGS aún no calcula
    magnitude = models.FloatField(null=True, blank=True)
    place = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    depth_km = models.FloatField()
    time = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-time"]

    def __str__(self):
        return f"M{self.magnitude} - {self.place}"
