from django.shortcuts import render
from django.urls import reverse

from .models import Concepto


def lista(request):
    q = request.GET.get('q', '')
    conceptos = Concepto.objects.filter(nombre__icontains=q).order_by('nombre')
    return render(request, 'conceptos/lista.html', {'conceptos': conceptos, 'q': q})


def arbol(request):
    datos = [
        {
            'slug': str(c.pk),
            'nombre': c.nombre,
            'cat': c.categoria,
            'catnombre': c.get_categoria_display(),
            'url': reverse('conceptos:lista') + '?q=' + c.nombre,
            'pre': [str(p.pk) for p in c.prerrequisitos.all()],
        }
        for c in Concepto.objects.prefetch_related('prerrequisitos')
    ]
    return render(request, 'conceptos/arbol.html', {'datos': datos})
    