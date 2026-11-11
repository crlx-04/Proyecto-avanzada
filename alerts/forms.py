from django import forms

from .models import AlertRule
from .services import LIMITS, MAX_RULES


class RuleForm(forms.Form):
    zone = forms.ModelChoiceField(queryset=None, label="Zona", empty_label=None)
    kind = forms.ChoiceField(choices=AlertRule.Kind.choices, label="Qué vigilar")
    threshold = forms.FloatField(label="Umbral")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["zone"].queryset = user.zones.all()

    def clean(self):
        data = super().clean()
        kind, threshold, zone = data.get("kind"), data.get("threshold"), data.get("zone")
        if kind and threshold is not None:
            low, high = LIMITS[AlertRule.Kind(kind)]
            if not low <= threshold <= high:
                self.add_error("threshold", f"El umbral debe estar entre {low} y {high}.")
        if self.user.alert_rules.count() >= MAX_RULES:
            raise forms.ValidationError(f"Puedes tener hasta {MAX_RULES} reglas. Elimina alguna para crear otra.")
        if zone and kind and threshold is not None and AlertRule.objects.filter(
            zone=zone, kind=kind, threshold=threshold
        ).exists():
            raise forms.ValidationError("Ya tienes una regla igual para esa zona.")
        return data
