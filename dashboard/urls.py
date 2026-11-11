from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("evaluacion/<int:pk>/", views.detail, name="detail"),
    path("historial/", views.history, name="history"),
]
