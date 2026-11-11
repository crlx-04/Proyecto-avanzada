"""Consultas y datos de apoyo para las vistas del dashboard."""
from events.geo import distance_km
from risk.models import RiskAssessment

# Dos evaluaciones se consideran "de la misma zona" si están a menos de esta distancia
SAME_ZONE_KM = 5
# Cuántas evaluaciones recientes se revisan al buscar el historial de una zona
CANDIDATES_LIMIT = 500

# Lugares de ejemplo: llenan el formulario con un clic y sirven para ponerle nombre a las coordenadas
PLACES = [
    {"name": "Riohacha", "lat": 11.5444, "lon": -72.9072},
    {"name": "Maicao", "lat": 11.3778, "lon": -72.2392},
    {"name": "Medellín", "lat": 6.2518, "lon": -75.5636},
    {"name": "Bogotá", "lat": 4.7110, "lon": -74.0721},
    {"name": "Cartagena", "lat": 10.3910, "lon": -75.4794},
    {"name": "Cali", "lat": 3.4516, "lon": -76.5320},
]
PLACE_MATCH_KM = 30

# Recomendaciones generales por nivel (informativas, no reemplazan los avisos oficiales)
ADVICE = {
    "bajo": "Condiciones tranquilas por ahora. No hace falta tomar medidas especiales; "
            "vuelve a evaluar si cambia el pronóstico.",
    "medio": "Hay señales a vigilar. Consulta el pronóstico oficial, ten a mano un plan básico "
             "de emergencia y los números de las autoridades locales.",
    "alto": "Conviene estar atento. Evita zonas cercanas a cauces y laderas durante lluvias "
            "fuertes, revisa tu plan de emergencia y sigue las indicaciones de las autoridades locales.",
    "critico": "Situación para tomar muy en serio. Sigue las alertas oficiales, evita las zonas "
               "de riesgo y ten listo tu plan de emergencia.",
}
# Lista corta de acciones por nivel (para el panel de alertas)
RECOMMENDATIONS = {
    "bajo": ["Mantente informado del pronóstico.", "Vuelve a evaluar si cambian las condiciones."],
    "medio": ["Consulta el pronóstico oficial del IDEAM.", "Ten a mano un plan básico de emergencia.",
              "Guarda los números de las autoridades locales."],
    "alto": ["Evita zonas cercanas a cauces y laderas.", "Revisa tu plan y tu ruta de evacuación.",
             "Sigue las indicaciones de las autoridades locales."],
    "critico": ["Sigue las alertas oficiales de inmediato.", "Evita las zonas de riesgo y cauces de agua.",
                "Ten listo tu plan y tus documentos de emergencia."],
}
OFFICIAL_NOTE = (
    "Esta herramienta es informativa y no reemplaza los avisos oficiales. Para clima consulta al "
    "IDEAM y para sismos al Servicio Geológico Colombiano."
)


def label_for(lat, lon):
    """Nombre del lugar de ejemplo más cercano (a menos de PLACE_MATCH_KM), o None."""
    nearest = min(PLACES, key=lambda p: distance_km(lat, lon, p["lat"], p["lon"]))
    if distance_km(lat, lon, nearest["lat"], nearest["lon"]) <= PLACE_MATCH_KM:
        return nearest["name"]
    return None


def zone_history(assessment, max_km=SAME_ZONE_KM, limit=30):
    """Evaluaciones de la misma zona (incluida `assessment`), de la más antigua a la más reciente."""
    recent = RiskAssessment.objects.all()[:CANDIDATES_LIMIT]  # ya vienen de la más nueva a la más vieja
    same_zone = [
        item
        for item in recent
        if distance_km(assessment.latitude, assessment.longitude, item.latitude, item.longitude)
        <= max_km
    ]
    return list(reversed(same_zone[:limit]))
