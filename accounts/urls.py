from django.contrib.auth import views as auth_views
from django.urls import path

from risk.services import DISCLAIMER

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
            extra_context={"disclaimer": DISCLAIMER},
        ),
        name="login",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),  # solo acepta POST
    path("registro/", views.register, name="register"),
    path("zonas/", views.zones, name="zones"),
    path("zonas/guardar/", views.zone_save, name="zone_save"),
    path("zonas/evaluar-todas/", views.zones_evaluate_all, name="zones_evaluate_all"),
    path("zonas/<int:pk>/eliminar/", views.zone_delete, name="zone_delete"),
    path("zonas/<int:pk>/evaluar/", views.zone_evaluate, name="zone_evaluate"),
]
