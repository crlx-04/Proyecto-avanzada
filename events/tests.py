from datetime import timedelta
from unittest import TestCase as PlainTestCase
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .geo import distance_km
from .models import Quake
from .services import quakes_near, refresh_quakes


def make_item(quake_id, lat=11.8, lon=-72.9, mag=4.5):
    return {
        "id": quake_id,
        "magnitude": mag,
        "place": "Cerca de Riohacha",
        "latitude": lat,
        "longitude": lon,
        "depth_km": 20.0,
        "time": timezone.now() - timedelta(days=1),
    }


class DistanceTests(PlainTestCase):
    def test_un_grado_de_longitud_en_el_ecuador_son_unos_111_km(self):
        self.assertAlmostEqual(distance_km(0, 0, 0, 1), 111.19, delta=0.5)

    def test_mismo_punto_distancia_cero(self):
        self.assertEqual(distance_km(11.5, -72.9, 11.5, -72.9), 0)


class RefreshQuakesTests(TestCase):
    @patch("integrations.usgs.fetch_quakes")
    def test_guarda_los_sismos(self, fetch):
        fetch.return_value = [make_item("a"), make_item("b")]
        result = refresh_quakes(11.54, -72.91, 300, 30)
        self.assertEqual(len(result), 2)
        self.assertEqual(Quake.objects.count(), 2)

    @patch("integrations.usgs.fetch_quakes")
    def test_repetir_la_consulta_no_duplica(self, fetch):
        fetch.return_value = [make_item("a")]
        refresh_quakes(11.54, -72.91, 300, 30)
        fetch.return_value = [make_item("a", mag=5.0)]
        refresh_quakes(11.54, -72.91, 300, 30)
        self.assertEqual(Quake.objects.count(), 1)
        self.assertEqual(Quake.objects.get().magnitude, 5.0)


class QuakesNearTests(TestCase):
    def setUp(self):
        base = {"place": "x", "depth_km": 10.0, "time": timezone.now() - timedelta(days=2)}
        Quake.objects.create(usgs_id="cerca", latitude=11.6, longitude=-72.9, magnitude=4.0, **base)
        Quake.objects.create(usgs_id="lejos", latitude=6.25, longitude=-75.57, magnitude=4.0, **base)
        Quake.objects.create(
            usgs_id="viejo", latitude=11.6, longitude=-72.9, magnitude=4.0,
            place="x", depth_km=10.0, time=timezone.now() - timedelta(days=60),
        )

    def test_solo_devuelve_sismos_cercanos_y_recientes(self):
        found = quakes_near(11.54, -72.91, 300, 30)
        self.assertEqual([q.usgs_id for q in found], ["cerca"])

    def test_la_ventana_puede_terminar_en_el_pasado(self):
        # "viejo" tiene 60 días: cae en la ventana de 30 días que terminó hace 50
        until = timezone.now() - timedelta(days=50)
        found = quakes_near(11.54, -72.91, 300, 30, until=until)
        self.assertEqual([q.usgs_id for q in found], ["viejo"])
