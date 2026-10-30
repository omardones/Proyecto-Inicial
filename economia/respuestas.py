"""
Utilidades para responder siempre en JSON, incluso cuando hay errores.

Todas las respuestas de error tienen la misma forma, para que quien haga el
frontend pueda tratarlas igual:

    {"error": {"codigo": "no_encontrado", "mensaje": "Texto legible", ...extras}}
"""
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# ensure_ascii=False  -> las tildes y la ñ salen como "ñ" y no como "ñ"
# indent=2            -> el JSON se lee bien en el navegador (útil para demostrar)
_JSON_OPCIONES = {"ensure_ascii": False, "indent": 2}


def ok(datos, status=200):
    return JsonResponse(datos, status=status, json_dumps_params=_JSON_OPCIONES)


def error(codigo, mensaje, status, **extra):
    cuerpo = {"error": {"codigo": codigo, "mensaje": mensaje, **extra}}
    return JsonResponse(cuerpo, status=status, json_dumps_params=_JSON_OPCIONES)


def solo_lectura(vista):
    """
    Decorador: la API solo acepta GET (y HEAD). Cualquier otro método recibe 405 en JSON.

    Va junto con csrf_exempt: la protección CSRF de Django existe para peticiones que
    MODIFICAN datos; aquí no hay ninguna, y sin esto un POST recibiría una página HTML
    de "403 CSRF" en vez del 405 en JSON.
    """

    @csrf_exempt
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if request.method not in ("GET", "HEAD"):
            respuesta = error(
                "metodo_no_permitido",
                "Esta API es de solo lectura: usa el método GET.",
                405,
            )
            respuesta["Allow"] = "GET, HEAD, OPTIONS"
            return respuesta
        return vista(request, *args, **kwargs)

    return envoltura
