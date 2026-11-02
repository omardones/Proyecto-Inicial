from django.urls import path, re_path

from . import views

urlpatterns = [
    path("", views.indice),
    path("salud/", views.salud),
    # Conceptos
    path("conceptos/", views.conceptos_lista),
    path("conceptos/<slug:slug>/", views.concepto_detalle),
    path("ruta-aprendizaje/", views.ruta_aprendizaje),
    path("fuentes/", views.fuentes),
    # Datos en vivo
    path("indicadores/", views.indicadores_lista),
    path("indicadores/<slug:codigo>/", views.indicador_detalle),
    # Herramientas
    path("herramientas/convertir/", views.convertir),
    path("herramientas/interes-compuesto/", views.interes_compuesto),
    path("herramientas/tasa-real/", views.tasa_real),
    # Cualquier otra cosa bajo /api/ -> 404 en JSON (siempre al final)
    re_path(r"^.*$", views.no_encontrado),
]
