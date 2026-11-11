"""Reglas de alerta: se revisan cada vez que una zona se evalúa con datos nuevos."""
from .models import Alert, AlertRule

MAX_RULES = 20

# Rango razonable del umbral para cada tipo de regla (también se usa en el formulario)
LIMITS = {
    AlertRule.Kind.SCORE: (1, 100),
    AlertRule.Kind.RAIN: (1, 1000),
    AlertRule.Kind.QUAKE: (1, 10),
}


def measured_value(kind, assessment):
    """Valor de la evaluación que corresponde a cada tipo de regla (None si no hay dato)."""
    if kind == AlertRule.Kind.SCORE:
        return float(assessment.score)
    if kind == AlertRule.Kind.RAIN:
        return round(assessment.rain_past_mm + assessment.rain_forecast_mm, 1)
    return assessment.max_magnitude  # puede ser None si no hubo sismos


def severity_for(rule, value):
    """Crítica si el valor supera el umbral por un margen amplio; si no, alta."""
    if rule.kind == AlertRule.Kind.SCORE:
        return Alert.Severity.CRITICAL if value >= 75 else Alert.Severity.HIGH
    if rule.kind == AlertRule.Kind.QUAKE:
        return Alert.Severity.CRITICAL if value >= rule.threshold + 1 else Alert.Severity.HIGH
    return Alert.Severity.CRITICAL if value >= rule.threshold * 1.5 else Alert.Severity.HIGH


def build_message(rule, value):
    zone = rule.zone.name
    if rule.kind == AlertRule.Kind.SCORE:
        return f"{zone}: el índice de riesgo llegó a {value:g}/100 (tu umbral es {rule.threshold:g})."
    if rule.kind == AlertRule.Kind.RAIN:
        return f"{zone}: se acumulan {value:g} mm de lluvia entre lo caído y lo previsto (tu umbral es {rule.threshold:g} mm)."
    return f"{zone}: hubo un sismo de magnitud {value:g} cerca de la zona (tu umbral es {rule.threshold:g})."


def check_rules(assessment):
    """Revisa las reglas activas de la zona de la evaluación y crea las alertas que correspondan.

    No repite una alerta mientras la anterior de la misma regla siga sin marcarse como vista,
    salvo que la situación empeore a crítica: entonces se actualiza esa alerta.
    Devuelve la lista de alertas nuevas o actualizadas.
    """
    zone = assessment.zone
    if zone is None:
        return []
    created = []
    for rule in zone.alert_rules.filter(active=True).select_related("zone"):
        value = measured_value(rule.kind, assessment)
        if value is None or value < rule.threshold:
            continue
        severity = severity_for(rule, value)
        pending = rule.alerts.filter(seen=False).first()
        if pending:
            # Ya hay un aviso sin ver: no se repite, salvo que la situación haya empeorado
            if severity == Alert.Severity.CRITICAL and pending.severity != Alert.Severity.CRITICAL:
                pending.severity = severity
                pending.value = value
                pending.assessment = assessment
                pending.message = build_message(rule, value)
                pending.save(update_fields=["severity", "value", "assessment", "message"])
                created.append(pending)
            continue
        created.append(
            Alert.objects.create(
                rule=rule, assessment=assessment, severity=severity, value=value,
                message=build_message(rule, value),
            )
        )
    return created


def would_trigger(kind, threshold, zone):
    """Cuántas evaluaciones ya guardadas de la zona habrían activado una regla así."""
    count = 0
    for assessment in zone.assessments.all():
        value = measured_value(kind, assessment)
        if value is not None and value >= threshold:
            count += 1
    return count
