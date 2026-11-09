# Natural Disaster Intelligence Platform (NDIP)

>Proyecto final de **Programación Avanzada A1** — Universidad de La Guajira, periodo 2026-2.

Aplicación web en Django que **estima el nivel de riesgo de una ubicación** combinando la lluvia reciente y prevista con la actividad sísmica de la zona, y explica el resultado en lenguaje simple.

> **Aviso importante:** el resultado es una *estimación basada en datos recientes y reglas simples*, no una predicción. En sismos solo refleja la **actividad reciente** de la zona: los terremotos no se pueden predecir.

## Estado del proyecto

| Fase | Contenido | Estado |
|------|-----------|--------|
| 0 | Estructura del proyecto, entorno y repositorio | Hecha |
| 1 | `integrations`: clientes de USGS y Open-Meteo, errores controlados, pruebas | Hecha |
| 2 | `events` + `risk`: modelos, historial de sismos e índice de riesgo | Hecha |
| 3 | `dashboard`: consulta por ubicación, mapa (Leaflet), gráficos, avisos de incertidumbre | Pendiente |
| 4 | `accounts` + `alerts`: usuarios, zonas guardadas y alertas | Pendiente |
| 5 | Pruebas finales, documentación y ensayo de sustentación | Pendiente |

Por ahora el proyecto funciona desde la consola de Django (`python manage.py shell`) y el panel de administración. La interfaz web llega en la fase 3.

## Problema que resuelve

Las personas no tienen una forma simple de saber, a partir de su ubicación, qué tan expuestas están a lluvias intensas y a actividad sísmica reciente. NDIP reúne datos abiertos, los guarda para formar un historial propio y los resume en un nivel de riesgo (bajo, medio, alto o crítico) con una explicación comprensible.

## Cómo funciona

```
assess_location(lat, lon)
   │
   ├─ integrations.open_meteo.fetch_precipitation → lluvia de los últimos 3 días y prevista
   ├─ events.services.refresh_quakes              → consulta USGS y guarda los sismos (sin duplicar)
   ├─ risk.services.compute_risk                  → puntajes, nivel y explicación
   └─ RiskAssessment.objects.create               → guarda la evaluación
```

Si alguna API externa falla, se lanza `ExternalAPIError` y **no se guarda nada**, para que la interfaz pueda mostrar un mensaje claro en lugar de romperse.

### Cómo se calcula el riesgo

Cada factor produce un puntaje de 0 a 100, y el **puntaje general es el más alto de los dos**.

- **Lluvia:** `lluvia de los últimos 3 días × 0.8 + lluvia prevista × 1.2` (máximo 100).
- **Sismos:** puntos por la mayor magnitud (desde M3, 20 puntos por grado, máximo 60) más 2 puntos por cada sismo (máximo 40).

| Puntaje | Nivel |
|---------|-------|
| 0 – 24 | Bajo |
| 25 – 49 | Medio |
| 50 – 74 | Alto |
| 75 – 100 | Crítico |

Los pesos y umbrales son una elección razonable y sencilla, no una verdad científica; se pueden ajustar en `risk/services.py`.

## Fuentes de datos

- **Sismos:** [USGS Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/)
- **Lluvia y pronóstico:** [Open-Meteo](https://open-meteo.com/)

No requieren clave de API.

## Estructura del proyecto

| App | Responsabilidad |
|-----|-----------------|
| `integrations` | Clientes de USGS y Open-Meteo. Sin modelos ni vistas. Define `ExternalAPIError`. |
| `events` | Modelo `Quake`, guardado del historial de sismos y búsqueda por cercanía. |
| `risk` | Modelo `RiskAssessment` y cálculo del índice de riesgo. |
| `dashboard` | Interfaz web *(fase 3)*. |
| `accounts` | Usuarios *(fase 4)*. |
| `alerts` | Zonas guardadas y alertas *(fase 4)*. |

## Instalación y ejecución

Requiere Python 3.10 o superior y Git. Los comandos son para Git Bash en Windows; en Linux o macOS cambia solo la activación del entorno (`source .venv/bin/activate`).

```bash
git clone https://github.com/crlx-04/Proyecto-avanzada.git
cd Proyecto-avanzada
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
``

## Limitaciones conocidas

- El índice es una heurística simple; no es un modelo científico validado.
- En sismos mide actividad reciente, no la probabilidad de que ocurra un terremoto.
- La búsqueda por cercanía no contempla el cruce del meridiano 180°.
- Depende de que USGS y Open-Meteo estén disponibles.

## Uso de IA

- **Claude (Anthropic):** apoyo en el diseño de la arquitectura y el plan por fases.