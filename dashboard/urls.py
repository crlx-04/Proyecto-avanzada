from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("evaluacion/<int:pk>/", views.detail, name="detail"),
    path("exportar/evaluaciones.csv", views.export_csv, name="export_csv"),
    path("panel/", views.panel, name="panel"),
    path("demo/", views.demo, name="demo"),
    path("historial/", views.history, name="history"),
]
