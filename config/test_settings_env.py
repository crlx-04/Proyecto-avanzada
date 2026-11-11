"""La configuración sensible sale del entorno (.env), no del código."""
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent


def run_settings(**env):
    """Importa config.settings en un proceso aparte con ese entorno y devuelve (código, salida)."""
    full_env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings", **env}
    code = "import config.settings as s; print(s.DEBUG, s.ALLOWED_HOSTS, s.SECRET_KEY)"
    result = subprocess.run([sys.executable, "-c", code], cwd=BASE_DIR, env=full_env, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


class SettingsEnvTests(SimpleTestCase):
    def test_sin_debug_se_exige_secret_key(self):
        code, output = run_settings(DEBUG="False", SECRET_KEY="")
        self.assertNotEqual(code, 0)
        self.assertIn("SECRET_KEY", output)

    def test_lee_valores_del_entorno(self):
        code, output = run_settings(DEBUG="False", SECRET_KEY="clave-de-prueba", ALLOWED_HOSTS="midominio.com, otro.com")
        self.assertEqual(code, 0, output)
        self.assertIn("False", output)
        self.assertIn("midominio.com", output)
        self.assertIn("clave-de-prueba", output)

    def test_el_codigo_no_contiene_la_clave_antigua(self):
        self.assertNotIn("django-insecure-", (BASE_DIR / "config" / "settings.py").read_text(encoding="utf-8"))
