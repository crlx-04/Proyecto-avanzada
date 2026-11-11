from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from events.services import quakes_near
from integrations.errors import ExternalAPIError
from risk.models import RiskAssessment
from risk.services import DISCLAIMER, assess_location, level_for

from .forms import LocationForm
from .services import ADVICE, OFFICIAL_NOTE, PLACES, RECOMMENDATIONS, label_for, zone_history


def _local(moment, fmt):
    """Formatea una fecha en la hora local del proyecto (America/Bogota)."""
    return timezone.localtime(moment).strftime(fmt)


def _with_labels(assessments):
    """Agrega a cada evaluación el nombre del lugar conocido más cercano (si hay uno)."""
    items = list(assessments)
    for item in items:
        item.place_label = label_for(item.latitude, item.longitude)
    return items


def _level_info(score):
    level = level_for(score)
    return {"value": level.value, "label": level.label}


def _mag_class(magnitude):
    if magnitude is None:
        return "mag-na"
    if magnitude >= 5:
        return "mag-high"
    if magnitude >= 4:
        return "mag-mid"
    return "mag-low"


def home(request):
    """Formulario para evaluar una ubicación + últimas evaluaciones."""
    # Permite llegar con valores precargados: /?latitude=11.5&longitude=-72.9
    initial = {
        key: request.GET[key]
        for key in ("latitude", "longitude", "radius_km", "days")
        if key in request.GET
    }
    form = LocationForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            assessment = assess_location(
                data["latitude"], data["longitude"], data["radius_km"], data["days"]
            )
        except ExternalAPIError as exc:
            messages.error(request, f"No se pudo completar la evaluación. {exc}")
        else:
            return redirect("dashboard:detail", pk=assessment.pk)

    return render(
        request,
        "dashboard/home.html",
        {
            "form": form,
            "places": PLACES,
            "recent": _with_labels(RiskAssessment.objects.all()[:6]),
            "disclaimer": DISCLAIMER,
        },
    )


def detail(request, pk):
    """Resultado de una evaluación: nivel, explicación, mapa, sismos y gráfico del historial."""
    assessment = get_object_or_404(RiskAssessment, pk=pk)
    assessment.place_label = label_for(assessment.latitude, assessment.longitude)

    # Sismos de la ventana que se usó al evaluar (hasta el momento de la evaluación)
    quakes = quakes_near(
        assessment.latitude,
        assessment.longitude,
        assessment.radius_km,
        assessment.days,
        until=assessment.created_at,
    )
    quake_rows = [
        {
            "magnitude": quake.magnitude,
            "place": quake.place,
            "time": _local(quake.time, "%d/%m/%Y %H:%M"),
            "depth_km": quake.depth_km,
            "css": _mag_class(quake.magnitude),
        }
        for quake in quakes
    ]
    history = zone_history(assessment)

    return render(
        request,
        "dashboard/detail.html",
        {
            "assessment": assessment,
            "rain_level": _level_info(assessment.rain_score),
            "quake_level": _level_info(assessment.quake_score),
            "advice": ADVICE[assessment.level],
            "recommendations": RECOMMENDATIONS[assessment.level],
            "official_note": OFFICIAL_NOTE,
            "quake_rows": quake_rows,
            "map_data": {
                "lat": assessment.latitude,
                "lon": assessment.longitude,
                "radius_km": assessment.radius_km,
            },
            "quakes_data": [
                {
                    "lat": quake.latitude,
                    "lon": quake.longitude,
                    "mag": quake.magnitude,
                    "place": quake.place,
                    "time": _local(quake.time, "%d/%m/%Y %H:%M"),
                }
                for quake in quakes
            ],
            "chart_data": {
                "labels": [_local(item.created_at, "%d/%m %H:%M") for item in history],
                "scores": [item.score for item in history],
            },
            "history_count": len(history),
            "disclaimer": DISCLAIMER,
        },
    )


def history(request):
    """Tabla con las últimas evaluaciones guardadas."""
    return render(
        request,
        "dashboard/history.html",
        {
            "assessments": _with_labels(RiskAssessment.objects.all()[:100]),
            "disclaimer": DISCLAIMER,
        },
    )
