from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from risk.services import DISCLAIMER

from .forms import RuleForm
from .models import Alert, AlertRule
from .services import LIMITS, MAX_RULES, measured_value


def _preview_data(user):
    """Valores de las evaluaciones guardadas por zona, para la vista previa del formulario."""
    data = {}
    for zone in user.zones.all():
        data[str(zone.pk)] = {
            kind.value: [v for v in (measured_value(kind, a) for a in zone.assessments.all()) if v is not None]
            for kind in AlertRule.Kind
        }
    return data


@login_required
def alert_list(request):
    alerts = Alert.objects.filter(rule__user=request.user).select_related("rule__zone")
    active = [a for a in alerts if not a.seen]
    history = [a for a in alerts if a.seen][:30]
    rules = list(AlertRule.objects.filter(user=request.user).select_related("zone"))
    since = timezone.now() - timedelta(days=30)
    return render(
        request,
        "alerts/list.html",
        {
            "active": active,
            "history": history,
            "rules": rules,
            "stats": {
                "active": len(active),
                "critical": sum(1 for a in active if a.severity == Alert.Severity.CRITICAL),
                "high": sum(1 for a in active if a.severity == Alert.Severity.HIGH),
                "rules_on": sum(1 for r in rules if r.active),
                "rules": len(rules),
                "month": alerts.filter(created_at__gte=since).count(),
            },
            "form": RuleForm(user=request.user),
            "zones": request.user.zones.all(),
            "preview": _preview_data(request.user),
            "limits": {k.value: v for k, v in LIMITS.items()},
            "max_rules": MAX_RULES,
            "disclaimer": DISCLAIMER,
        },
    )


@login_required
@require_POST
def rule_create(request):
    form = RuleForm(request.POST, user=request.user)
    if form.is_valid():
        rule = AlertRule.objects.create(user=request.user, **form.cleaned_data)
        messages.success(request, f"Regla creada: {rule.description}. Se revisará cuando evalúes «{rule.zone.name}».")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("alerts:list")


@login_required
@require_POST
def rule_toggle(request, pk):
    rule = get_object_or_404(AlertRule, pk=pk, user=request.user)
    rule.active = not rule.active
    rule.save(update_fields=["active"])
    return redirect("alerts:list")


@login_required
@require_POST
def rule_delete(request, pk):
    rule = get_object_or_404(AlertRule, pk=pk, user=request.user)
    rule.delete()
    messages.success(request, "Regla eliminada.")
    return redirect("alerts:list")


@login_required
@require_POST
def alert_seen(request, pk):
    alert = get_object_or_404(Alert, pk=pk, rule__user=request.user)
    alert.seen = True
    alert.save(update_fields=["seen"])
    return redirect("alerts:list")


@login_required
@require_POST
def alert_seen_all(request):
    Alert.objects.filter(rule__user=request.user, seen=False).update(seen=True)
    return redirect("alerts:list")
