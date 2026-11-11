from django import forms


class LocationForm(forms.Form):
    """Datos que el usuario escribe para evaluar una ubicación."""

    latitude = forms.FloatField(
        label="Latitud",
        min_value=-90,
        max_value=90,
        widget=forms.NumberInput(attrs={"step": "any", "placeholder": "Ej. 11.5444"}),
    )
    longitude = forms.FloatField(
        label="Longitud",
        min_value=-180,
        max_value=180,
        widget=forms.NumberInput(attrs={"step": "any", "placeholder": "Ej. -72.9072"}),
    )
    radius_km = forms.IntegerField(
        label="Radio para buscar sismos (km)", min_value=10, max_value=1000, initial=300
    )
    days = forms.IntegerField(
        label="Días de historial de sismos", min_value=1, max_value=365, initial=30
    )
