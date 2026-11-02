"""Pruebas del cliente de la API externa: valores, fechas, caché y fallos."""
import io
from unittest.mock import patch

from django.test import SimpleTestCase

from economia import indicadores
from economia.indicadores import FuenteNoDisponible

from .ayudas import PruebaConFuenteFalsa, cargar


def por_codigo(resultado):
    return {i["codigo"]: i for i in resultado["indicadores"]}


class ValoresTests(PruebaConFuenteFalsa):
    def test_trae_los_diez_indicadores_con_los_valores_reales(self):
        r = indicadores.listar_actuales()
        ind = por_codigo(r)
        self.assertEqual(len(r["indicadores"]), 10)
        self.assertEqual(r["no_entregados_por_la_fuente"], [])
        self.assertEqual(ind["uf"]["valor"], 41215.77)
        self.assertEqual(ind["dolar"]["valor"], 986.58)
        self.assertEqual(ind["tpm"]["valor"], 4.5)

    def test_valores_formateados_al_estilo_chileno_con_su_unidad(self):
        ind = por_codigo(indicadores.listar_actuales())
        self.assertEqual(ind["uf"]["valor_formateado"], "$41.215,77")
        self.assertEqual(ind["dolar"]["valor_formateado"], "$986,58")
        self.assertEqual(ind["utm"]["valor_formateado"], "$72.151")
        self.assertEqual(ind["tpm"]["valor_formateado"], "4,5 %")
        self.assertEqual(ind["bitcoin"]["valor_formateado"], "US$80.771,9")

    def test_lectura_simple(self):
        ind = por_codigo(indicadores.listar_actuales())
        self.assertEqual(ind["uf"]["lectura_simple"], "1 UF vale $41.215,77")
        self.assertEqual(ind["tpm"]["lectura_simple"], "La TPM está en 4,5 %")
        self.assertEqual(ind["ipc"]["lectura_simple"], "Los precios variaron -0,2 % en el mes")

    def test_cada_indicador_explica_que_es_y_con_que_conceptos_se_relaciona(self):
        for i in indicadores.listar_actuales()["indicadores"]:
            self.assertTrue(i["que_es"] and i["por_que_importa"])
            self.assertTrue(i["conceptos_relacionados"])
            for c in i["conceptos_relacionados"]:
                self.assertTrue(c["slug"] and c["nombre"])

    def test_indicador_que_la_fuente_no_entrega_se_informa_como_faltante(self):
        resumen = cargar("mindicador_resumen.json")
        del resumen["euro"]
        self.fuente.respuestas_fijas[""] = resumen
        r = indicadores.listar_actuales()
        self.assertEqual(r["no_entregados_por_la_fuente"], ["euro"])
        self.assertEqual(len(r["indicadores"]), 9)
        with self.assertRaisesMessage(FuenteNoDisponible, "euro"):
            indicadores.tasas_de_cambio()


class FrescuraTests(PruebaConFuenteFalsa):
    """Hoy es 25-oct-2026. El IPC que entrega la fuente es de dic-2025: debe marcarse atrasado."""

    def test_dias_desde_el_dato(self):
        ind = por_codigo(indicadores.listar_actuales())
        self.assertEqual(ind["uf"]["fecha_dato"], "2026-10-25")
        self.assertEqual(ind["uf"]["dias_desde_el_dato"], 0)
        self.assertEqual(ind["dolar"]["dias_desde_el_dato"], 2)  # dato del viernes 23
        self.assertEqual(ind["utm"]["dias_desde_el_dato"], 24)
        self.assertEqual(ind["imacec"]["dias_desde_el_dato"], 85)
        self.assertEqual(ind["ipc"]["dias_desde_el_dato"], 328)

    def test_solo_el_ipc_esta_atrasado(self):
        ind = por_codigo(indicadores.listar_actuales())
        atrasados = [c for c, i in ind.items() if i["dato_atrasado"]]
        self.assertEqual(atrasados, ["ipc"])


class CacheTests(PruebaConFuenteFalsa):
    def llamar_en(self, t):
        with patch("economia.indicadores.time") as reloj:
            reloj.time.return_value = t
            return indicadores.listar_actuales()

    def test_segunda_consulta_usa_la_cache_y_no_llama_a_la_fuente(self):
        primera = self.llamar_en(1000.0)
        segunda = self.llamar_en(1100.0)
        self.assertEqual(len(self.fuente.llamadas), 1)
        self.assertFalse(primera["meta"]["cache"]["usada"])
        self.assertTrue(segunda["meta"]["cache"]["usada"])
        self.assertEqual(segunda["meta"]["cache"]["antiguedad_segundos"], 100)

    def test_la_cache_vence_a_los_10_minutos(self):
        self.llamar_en(1000.0)
        self.llamar_en(1000.0 + 601)
        self.assertEqual(len(self.fuente.llamadas), 2)

    def test_si_la_fuente_se_cae_se_sirve_la_cache_vieja_marcada_como_obsoleta(self):
        self.llamar_en(1000.0)
        self.fuente.caida = True
        r = self.llamar_en(1000.0 + 5000)
        self.assertEqual(len(r["indicadores"]), 10)
        self.assertTrue(r["meta"]["cache"]["obsoleta"])
        self.assertIn("aviso", r["meta"])

    def test_sin_cache_y_con_la_fuente_caida_falla_con_error_claro(self):
        self.fuente.caida = True
        with self.assertRaises(FuenteNoDisponible):
            indicadores.listar_actuales()

    def test_una_respuesta_rara_no_se_guarda_en_cache(self):
        self.fuente.respuestas_fijas[""] = {"mensaje": "mantenimiento"}
        with self.assertRaises(FuenteNoDisponible):
            indicadores.listar_actuales()
        del self.fuente.respuestas_fijas[""]
        self.assertEqual(len(indicadores.listar_actuales()["indicadores"]), 10)  # se recuperó

    def test_valores_no_numericos_se_rechazan(self):
        resumen = cargar("mindicador_resumen.json")
        for codigo in list(resumen):
            if isinstance(resumen[codigo], dict):
                resumen[codigo]["valor"] = "n/d"
        self.fuente.respuestas_fijas[""] = resumen
        with self.assertRaises(FuenteNoDisponible):
            indicadores.listar_actuales()


class DetalleTests(PruebaConFuenteFalsa):
    def test_uf_ignora_valores_futuros_y_calcula_la_variacion(self):
        d = indicadores.detalle("uf", ultimos=30)["indicador"]
        self.assertEqual(d["valor"], 41215.77)  # no el de mañana (41219.54)
        self.assertEqual(d["serie"][0], {"fecha": "2026-10-25", "valor": 41215.77})
        self.assertEqual(len(d["serie"]), 4)  # 5 puntos menos el de mañana
        self.assertEqual(d["variacion"]["respecto_de"], "2026-10-24")
        self.assertEqual(d["variacion"]["absoluta"], 3.77)
        self.assertEqual(d["variacion"]["porcentual"], 0.0091)

    def test_ultimos_limita_la_serie(self):
        d = indicadores.detalle("uf", ultimos=2)["indicador"]
        self.assertEqual([p["fecha"] for p in d["serie"]], ["2026-10-25", "2026-10-24"])

    def test_indicador_en_porcentaje_no_tiene_variacion_porcentual(self):
        d = indicadores.detalle("tpm")["indicador"]
        self.assertEqual(d["variacion"]["absoluta"], -0.25)
        self.assertIsNone(d["variacion"]["porcentual"])

    def test_tasas_de_cambio_para_el_conversor(self):
        tasas, meta = indicadores.tasas_de_cambio()
        self.assertEqual(tasas["clp"]["pesos"], 1)
        self.assertEqual(tasas["usd"]["pesos"], 986.58)
        self.assertEqual(tasas["uf"]["fecha_dato"], "2026-10-25")
        self.assertIn("fuente", meta)

    def test_probar_fuente_no_usa_la_cache(self):
        indicadores.listar_actuales()  # llena la caché
        self.fuente.caida = True
        ok, detalle = indicadores.probar_fuente()
        self.assertFalse(ok)  # una caída no queda tapada por la caché
        self.assertIn("sin conexión", detalle)


class ConexionSeguraTests(SimpleTestCase):
    """El cliente HTTPS verifica certificados y ayuda a diagnosticar si faltan."""

    def test_el_contexto_ssl_verifica_certificados(self):
        import ssl
        contexto = indicadores._contexto_ssl()
        self.assertEqual(contexto.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(contexto.check_hostname)

    def test_la_descarga_usa_ese_contexto(self):
        from unittest.mock import MagicMock, patch
        respuesta = MagicMock()
        respuesta.__enter__.return_value = io.BytesIO(b'{"ok": 1}')
        with patch("urllib.request.urlopen", return_value=respuesta) as abrir:
            self.assertEqual(indicadores._descargar("https://ejemplo.test/api"), {"ok": 1})
        self.assertIs(abrir.call_args.kwargs["context"], indicadores._contexto_ssl())

    def test_error_de_certificado_incluye_pista(self):
        import ssl
        import urllib.error
        from unittest.mock import patch
        falla = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        with patch("urllib.request.urlopen", side_effect=falla):
            with self.assertRaises(FuenteNoDisponible) as cm:
                indicadores._descargar("https://ejemplo.test/api")
        self.assertIn("pip install certifi", str(cm.exception))
