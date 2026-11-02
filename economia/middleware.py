"""
CORS mínimo para la API.

¿Por qué existe? El frontend (hecho por otra persona del equipo) normalmente
corre en otro puerto, por ejemplo http://localhost:5173. Sin estas cabeceras el
navegador bloquea sus llamadas a este backend ("CORS error").

Es seguro dejarlo abierto (*) porque la API es pública, de solo lectura y no
maneja datos de usuarios. Si algún día se publica, se puede restringir con:

    ECONOMIA_CORS_ORIGEN = "https://mi-frontend.cl"      # en settings.py
"""
from django.conf import settings
from django.http import HttpResponse


class CorsSimpleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        if request.method == "OPTIONS":  # "preflight" del navegador
            respuesta = HttpResponse(status=204)
        else:
            respuesta = self.get_response(request)

        respuesta["Access-Control-Allow-Origin"] = getattr(settings, "ECONOMIA_CORS_ORIGEN", "*")
        respuesta["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        respuesta["Access-Control-Allow-Headers"] = "Content-Type"
        respuesta["Access-Control-Max-Age"] = "86400"
        return respuesta
