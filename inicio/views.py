from django.shortcuts import render, get_object_or_404
from .models import Concepto

def mi_pagina(request):
    # Capturamos lo que el usuario escribió en la barra de búsqueda
    query = request.GET.get('q', '')
    resultado = None
    conceptos_sugeridos = Concepto.objects.all()[:5] # Muestra algunos conceptos rápidos

    if query:
        # Buscamos en la base de datos si el título o definición coincide con lo buscado
        # (usamos icontigens para que no importe si escriben mayúsculas o minúsculas)
        resultado = Concepto.objects.filter(titulo__icontains=query).first()

    contexto = {
        'query': query,
        'resultado': resultado,
        'conceptos_sugeridos': conceptos_sugeridos
    }
    return render(request, 'inicio/index.html', contexto)

def detalle_concepto(request, concepto_id):
    # Vista para cuando seleccionen un concepto específico
    concepto = get_object_or_404(Concepto, id=concepto_id)
    return render(request, 'inicio/detalle.html', {'concepto': concepto})