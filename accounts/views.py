from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from dashboard.services import PLACES
from integrations.errors import ExternalAPIError
from risk.access import as_int, visible_to
from risk.services import DISCLAIMER

from .forms import MAX_ZONES, RegisterForm, ZoneForm
from .models import Zone
from .services import evaluate_zone, summary, zones_ranked

ERROR_PREFIX = "No se pudo completar la evaluación. Revisa tu conexión e inténtalo de nuevo."


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:zones")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)  # entra directamente después de registrarse
        messages.success(request, f"Cuenta creada. Bienvenido, {user.username}.")
        return redirect("accounts:zones")
    return render(request, "accounts/register.html", {"form": form, "disclaimer": DISCLAIMER})


@login_required
def zones(request):
    """Lista las zonas del usuario ordenadas por riesgo y permite agregar una nueva."""
    if request.method == "POST":
        form = ZoneForm(request.POST, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            Zone.objects.create(user=request.user, **data)
            messages.success(request, f"Zona «{data['name']}» guardada. Evalúala para ver su riesgo.")
            return redirect("accounts:zones")
    else:
        form = ZoneForm(user=request.user)

    ranked = zones_ranked(Zone.objects.filter(user=request.user))
    return render(
        request,
        "accounts/zones.html",
        {
            "form": form,
            "zones": ranked,
            "summary": summary(ranked),
            "zones_map": [
                {
                    "name": z.name,
                    "lat": z.latitude,
                    "lon": z.longitude,
                    "radius_km": z.radius_km,
                    "score": z.latest.score if z.latest else None,
                    "level": z.latest.level if z.latest else None,
                    "label": z.latest.get_level_display() if z.latest else "Sin evaluar",
                }
                for z in ranked
            ],
            "places": PLACES,
            "max_zones": MAX_ZONES,
            "disclaimer": DISCLAIMER,
        },
    )


@login_required
@require_POST
def zone_delete(request, pk):
    zone = get_object_or_404(Zone, pk=pk, user=request.user)  # solo se pueden borrar las propias
    name = zone.name
    zone.delete()  # sus evaluaciones se conservan en el historial (zone queda en NULL)
    messages.success(request, f"Zona «{name}» eliminada.")
    return redirect("accounts:zones")


@login_required
@require_POST
def zone_evaluate(request, pk):
    zone = get_object_or_404(Zone, pk=pk, user=request.user)
    try:
        assessment = evaluate_zone(zone)
    except ExternalAPIError as error:
        messages.error(request, f"{ERROR_PREFIX} ({error})")
        return redirect("accounts:zones")
    if assessment.new_alerts:
        messages.warning(request, f"Se activó {len(assessment.new_alerts)} alerta(s). Revísalas en Alertas.")
    return redirect("dashboard:detail", pk=assessment.pk)


@login_required
@require_POST
def zones_evaluate_all(request):
    """Evalúa todas las zonas. Si una falla, sigue con las demás y avisa al final."""
    done, failed, new_alerts = 0, [], 0
    for zone in Zone.objects.filter(user=request.user):
        try:
            new_alerts += len(evaluate_zone(zone).new_alerts)
            done += 1
        except ExternalAPIError:
            failed.append(zone.name)
    if done:
        messages.success(request, f"Se evaluaron {done} zona(s).")
    if new_alerts:
        messages.warning(request, f"Se activaron {new_alerts} alerta(s). Revísalas en Alertas.")
    if failed:
        messages.error(request, "No se pudo evaluar: " + ", ".join(failed) + ". Inténtalo de nuevo.")
    return redirect("accounts:zones")


@login_required
@require_POST
def zone_save(request):
    """Guarda como zona el lugar de una evaluación que la persona acaba de ver (y es suya)."""
    assessment = get_object_or_404(visible_to(request), pk=as_int(request.POST.get("assessment_id")))
    if assessment.zone_id is not None:
        messages.error(request, "Esa evaluación ya pertenece a una zona guardada.")
        return redirect("dashboard:detail", pk=assessment.pk)
    # Las coordenadas salen de la evaluación guardada, no del formulario
    data = {
        "name": request.POST.get("name", ""),
        "latitude": assessment.latitude,
        "longitude": assessment.longitude,
        "radius_km": assessment.radius_km,
    }
    form = ZoneForm(data, user=request.user)
    if form.is_valid():
        zone = Zone.objects.create(user=request.user, **form.cleaned_data)
        assessment.zone = zone
        assessment.owner = request.user
        assessment.save(update_fields=["zone", "owner"])
        messages.success(request, f"Zona «{zone.name}» guardada en tu lista.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("dashboard:detail", pk=assessment.pk)
