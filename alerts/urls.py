from django.urls import path

from . import views

app_name = "alerts"

urlpatterns = [
    path("alertas/", views.alert_list, name="list"),
    path("alertas/reglas/nueva/", views.rule_create, name="rule_create"),
    path("alertas/reglas/<int:pk>/alternar/", views.rule_toggle, name="rule_toggle"),
    path("alertas/reglas/<int:pk>/eliminar/", views.rule_delete, name="rule_delete"),
    path("alertas/<int:pk>/vista/", views.alert_seen, name="seen"),
    path("alertas/marcar-todas/", views.alert_seen_all, name="seen_all"),
]
