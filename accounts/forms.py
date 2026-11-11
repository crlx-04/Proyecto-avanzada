from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Zone

MAX_ZONES = 10  # cada evaluación consulta dos APIs externas, así que se limita


class RegisterForm(UserCreationForm):
    """Registro con usuario y contraseña (las reglas de contraseña son las de Django)."""

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)
        labels = {"username": "Usuario"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"


class ZoneForm(forms.Form):
    """Datos de una zona nueva. Recibe el usuario para validar duplicados y el límite."""

    name = forms.CharField(label="Nombre", max_length=60)
    latitude = forms.FloatField(label="Latitud", min_value=-90, max_value=90)
    longitude = forms.FloatField(label="Longitud", min_value=-180, max_value=180)
    radius_km = forms.IntegerField(label="Radio de sismos (km)", min_value=10, max_value=1000, initial=300)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Escribe un nombre para la zona.")
        if Zone.objects.filter(user=self.user, name__iexact=name).exists():
            raise forms.ValidationError("Ya tienes una zona con ese nombre.")
        return name

    def clean(self):
        cleaned = super().clean()
        if Zone.objects.filter(user=self.user).count() >= MAX_ZONES:
            raise forms.ValidationError(f"Puedes guardar hasta {MAX_ZONES} zonas. Elimina una para agregar otra.")
        return cleaned
