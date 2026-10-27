from django.urls import path
from . import views

app_name = 'conceptos'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('arbol/', views.arbol, name='arbol'),
]