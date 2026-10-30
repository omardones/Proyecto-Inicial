"""
Piezas compartidas por las pruebas.

Las pruebas NUNCA llaman a internet: reemplazan indicadores._descargar por una
"fuente falsa" que responde con los JSON de tests/fixtures/.
  - mindicador_resumen.json      -> respuesta REAL de https://mindicador.cl/api (25-oct-2026)
  - mindicador_uf_simulada.json  -> serie inventada, solo con la forma real
  - mindicador_tpm_simulada.json -> idem
"""
import json
import logging
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from economia import indicadores
from economia.indicadores import FuenteNoDisponible

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HOY = date(2026, 10, 25)  # el día en que se capturó la respuesta real


def cargar(nombre):
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


class FuenteFalsa:
    """Hace de API externa: devuelve los fixtures, cuenta las llamadas y puede 'caerse'."""

    ARCHIVOS = {
        "": "mindicador_resumen.json",
        "/uf": "mindicador_uf_simulada.json",
        "/tpm": "mindicador_tpm_simulada.json",
    }

    def __init__(self):
        self.llamadas = []
        self.caida = False
        self.respuestas_fijas = {}  # ruta -> JSON a devolver (pisa al fixture)

    def __call__(self, url):
        self.llamadas.append(url)
        if self.caida:
            raise FuenteNoDisponible("simulado: sin conexión")
        ruta = url[len(indicadores.url_fuente()):]
        if ruta in self.respuestas_fijas:
            return self.respuestas_fijas[ruta]
        if ruta not in self.ARCHIVOS:
            raise FuenteNoDisponible(f"simulado: no hay fixture para '{ruta}'")
        return cargar(self.ARCHIVOS[ruta])


class PruebaConFuenteFalsa(SimpleTestCase):
    """Base: caché limpia, fecha de 'hoy' fija y fuente externa simulada."""

    def setUp(self):
        cache.clear()
        logging.disable(logging.CRITICAL)  # los fallos simulados no ensucian la salida de las pruebas
        self.addCleanup(logging.disable, logging.NOTSET)
        self.fuente = FuenteFalsa()
        for parche in (
            patch("economia.indicadores._descargar", self.fuente),
            patch("economia.indicadores.hoy_chile", return_value=HOY),
        ):
            parche.start()
            self.addCleanup(parche.stop)
