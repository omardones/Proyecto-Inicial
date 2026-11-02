from django.urls import path
from . import views

urlpatterns = [
    path('', views.mi_pagina, name='index'),
    path('concepto/<int:concepto_id>/', views.detalle_concepto, name='detalle_concepto'),
]