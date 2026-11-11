"""Quién puede ver cada evaluación.

- Con sesión iniciada: las que hizo (owner) y las de sus zonas guardadas.
- Sin sesión: solo las que hizo ese mismo navegador (se recuerdan en la sesión).
Nadie ve las evaluaciones de otra persona, aunque conozca su número.
"""
from django.db.models import Q
from django.http import Http404

from .models import RiskAssessment

SESSION_KEY = "ndip_assessments"
MAX_REMEMBERED = 100


def as_int(value):
    """Convierte un identificador recibido por la URL o el formulario; si no es un número, responde 404."""
    try:
        return int(value)
    except (TypeError, ValueError):
        raise Http404("Identificador no válido.")


def claim(request, assessment):
    """Deja la evaluación a nombre de quien la acaba de hacer (usuario o navegador anónimo)."""
    if request.user.is_authenticated and assessment.owner_id != request.user.pk:
        assessment.owner = request.user
        assessment.save(update_fields=["owner"])
    remembered = request.session.get(SESSION_KEY, [])
    if assessment.pk not in remembered:
        remembered = (remembered + [assessment.pk])[-MAX_REMEMBERED:]
        request.session[SESSION_KEY] = remembered


def visible_to(request):
    """Evaluaciones que esta persona puede ver, de la más reciente a la más antigua."""
    condition = Q(pk__in=request.session.get(SESSION_KEY, []))
    if request.user.is_authenticated:
        condition |= Q(owner=request.user) | Q(zone__user=request.user)
    return RiskAssessment.objects.filter(condition).distinct()
