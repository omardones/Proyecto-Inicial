"""
Piezas compartidas por las pruebas.

Las pruebas NUNCA llaman a Internet: reemplazan indicadores._descargar
por una fuente falsa que responde con los JSON de tests/fixtures/.

Fuentes simuladas:
- indicadores_resumen.json: resumen de indicadores.cl.
- indicadores_uf_simulada.json: historial simulado de UF.
- indicadores_tpm_simulada.json: historial simulado de TPM.
- coingecko_bitcoin_actual.json: precio actual simulado de Bitcoin.
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
    """Simula indicadores.cl y CoinGecko sin realizar llamadas a Internet."""

    ARCHIVOS = {
        "/hoy.json": "indicadores_resumen.json",
        "/uf.json": "indicadores_uf_simulada.json",
        "/tpm.json": "indicadores_tpm_simulada.json",
    }

    ARCHIVO_BITCOIN = "coingecko_bitcoin_actual.json"

    def __init__(self):
        self.llamadas = []
        self.caida = False
        self.caida_coingecko = False
        self.respuestas_fijas = {}

    def __call__(self, url):
        self.llamadas.append(url)

        if self.caida:
            raise FuenteNoDisponible("simulado: sin conexión")

        if url.startswith(indicadores.url_fuente()):
            ruta = url[len(indicadores.url_fuente()):]
            archivo = self.ARCHIVOS.get(ruta)
        elif url.startswith("https://api.coingecko.com/api/v3/simple/price"):
            if self.caida_coingecko:
                raise FuenteNoDisponible("simulado: CoinGecko sin conexión")
            ruta = "bitcoin_actual"
            archivo = self.ARCHIVO_BITCOIN
        else:
            raise FuenteNoDisponible(f"simulado: URL desconocida '{url}'")

        if ruta in self.respuestas_fijas:
            return self.respuestas_fijas[ruta]

        if archivo is None:
            raise FuenteNoDisponible(
                f"simulado: no hay fixture para '{ruta}'"
            )

        return cargar(archivo)


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
