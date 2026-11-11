from .models import Alert


def unread_alerts(request):
    """Cantidad de alertas sin ver, para el contador del menú."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"unread_alerts": Alert.objects.filter(rule__user=user, seen=False).count()}
