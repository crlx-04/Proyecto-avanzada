from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from events.services import quakes_near
from integrations.errors import ExternalAPIError
from risk.access import as_int, claim, visible_to
from risk.models import RiskAssessment
from risk.services import DISCLAIMER, assess_location, level_for

from accounts.models import Zone
from accounts.services import zones_ranked

from . import demo as demo_data
from . import export as export_data
from . import panel as panel_data
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
            messages.error(
                request,
                f"No se pudo completar la evaluación. {exc} Si no tienes conexión, puedes abrir la demostración desde el menú.",
            )
        else:
            claim(request, assessment)
            return redirect("dashboard:detail", pk=assessment.pk)

    return render(
        request,
        "dashboard/home.html",
        {
            "form": form,
            "places": PLACES,
            "recent": _with_labels(visible_to(request)[:6]),
            "disclaimer": DISCLAIMER,
        },
    )


def _detail_context(assessment, quakes, history_points, demo=False):
    """Datos que usa la pantalla de resultado. `history_points` son (momento, puntaje)."""
    return {
        "assessment": assessment,
        "demo": demo,
        "rain_level": _level_info(assessment.rain_score),
        "quake_level": _level_info(assessment.quake_score),
        "advice": ADVICE[assessment.level],
        "recommendations": RECOMMENDATIONS[assessment.level],
        "official_note": OFFICIAL_NOTE,
        "quake_rows": [
            {
                "magnitude": quake.magnitude,
                "place": quake.place,
                "time": _local(quake.time, "%d/%m/%Y %H:%M"),
                "depth_km": quake.depth_km,
                "css": _mag_class(quake.magnitude),
            }
            for quake in quakes
        ],
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
            "labels": [_local(moment, "%d/%m %H:%M") for moment, _score in history_points],
            "scores": [score for _moment, score in history_points],
        },
        "history_count": len(history_points),
        "disclaimer": DISCLAIMER,
    }


def detail(request, pk):
    """Resultado de una evaluación: nivel, explicación, mapa, sismos y gráfico del historial."""
    assessment = get_object_or_404(visible_to(request), pk=pk)
    assessment.place_label = label_for(assessment.latitude, assessment.longitude)

    # Sismos de la ventana que se usó al evaluar (hasta el momento de la evaluación)
    quakes = quakes_near(
        assessment.latitude,
        assessment.longitude,
        assessment.radius_km,
        assessment.days,
        until=assessment.created_at,
    )
    history_points = [
        (item.created_at, item.score) for item in zone_history(assessment, queryset=visible_to(request))
    ]
    return render(request, "dashboard/detail.html", _detail_context(assessment, quakes, history_points))


def demo(request):
    """Evaluación de ejemplo con datos fijos: funciona aunque no haya internet."""
    assessment, quakes, history_points = demo_data.build()
    quake_objects = [SimpleNamespace(**quake) for quake in quakes]
    return render(
        request,
        "dashboard/detail.html",
        _detail_context(assessment, quake_objects, history_points, demo=True),
    )


def history(request):
    """Tabla con las últimas evaluaciones guardadas."""
    return render(
        request,
        "dashboard/history.html",
        {
            "assessments": _with_labels(visible_to(request)[:100]),
            "disclaimer": DISCLAIMER,
        },
    )


@login_required
def panel(request):
    """Panel de una zona guardada: lluvia por día, sismos, evolución, mapa de calor y fuentes."""
    zones = zones_ranked(Zone.objects.filter(user=request.user))
    selected = None
    if zones:
        selected = next((z for z in zones if str(z.pk) == request.GET.get("zona")), zones[0])
    latest = selected.latest if selected else None
    context = {
        "zones": zones,
        "selected": selected,
        "latest": latest,
        "heatmap": panel_data.heatmap(zones),
        "sources": panel_data.source_status(),
        "disclaimer": DISCLAIMER,
    }
    if latest:
        rain = panel_data.rain_series(latest)
        context.update(
            {
                "rain": rain,
                "has_rain": bool(rain["values"]),
                "rain_total": round(sum(rain["values"]), 1),
                "quakes": panel_data.quake_points(latest),
                "evolution": panel_data.evolution(selected),
            }
        )
    return render(request, "dashboard/panel.html", context)


@login_required
def export_csv(request):
    """Descarga las evaluaciones de las zonas del usuario (o de una zona con ?zona=ID) en CSV."""
    zone = None
    if request.GET.get("zona"):
        zone = get_object_or_404(Zone, pk=as_int(request.GET["zona"]), user=request.user)
    name = f"evaluaciones-{zone.name.lower().replace(' ', '-')}" if zone else "evaluaciones"
    response = HttpResponse(export_data.build_csv(request.user, zone), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{name}-{timezone.localdate()}.csv"'
    return response
