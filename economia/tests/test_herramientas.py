"""Pruebas de las calculadoras. Los casos principales son los ejemplos del propio PDF."""
from decimal import Decimal as D

from django.test import SimpleTestCase

from economia import herramientas
from economia.formato import formato_cl


class FormatoTests(SimpleTestCase):
    def test_formato_chileno(self):
        self.assertEqual(formato_cl(41215.77), "41.215,77")
        self.assertEqual(formato_cl(72151), "72.151")
        self.assertEqual(formato_cl(4.5), "4,5")
        self.assertEqual(formato_cl(-0.2), "-0,2")
        self.assertEqual(formato_cl(0), "0")
        self.assertEqual(formato_cl(100000), "100.000")
        self.assertEqual(formato_cl(1234567.891), "1.234.567,89")


class InteresCompuestoTests(SimpleTestCase):
    def test_ejemplo_del_pdf_100000_al_10_por_ciento(self):
        r = herramientas.interes_compuesto(D(100000), D(10), 2)
        self.assertEqual([f["saldo"] for f in r["detalle_por_anio"]], [110000.0, 121000.0])
        self.assertEqual(r["saldo_final"], 121000.0)
        self.assertEqual(r["ganancia_total"], 21000.0)

    def test_se_compara_con_interes_simple(self):
        r = herramientas.interes_compuesto(D(100000), D(10), 2)
        self.assertEqual(r["saldo_con_interes_simple"], 120000.0)
        self.assertEqual(r["ventaja_del_interes_compuesto"], 1000.0)

    def test_tasa_cero_no_gana_nada(self):
        r = herramientas.interes_compuesto(D(50000), D(0), 5)
        self.assertEqual(r["saldo_final"], 50000.0)
        self.assertEqual(r["ventaja_del_interes_compuesto"], 0.0)

    def test_un_anio_va_en_singular(self):
        self.assertIn("durante 1 año ", herramientas.interes_compuesto(D(1000), D(5), 1)["lectura_simple"])

    def test_no_acumula_errores_de_redondeo(self):
        # 0.1 + 0.2 en float no es 0.3; con Decimal el capital se conserva exacto
        r = herramientas.interes_compuesto(D("0.10"), D(0), 3)
        self.assertEqual(r["saldo_final"], 0.1)

    def test_texto_legible(self):
        t = herramientas.interes_compuesto(D(100000), D(10), 2)["lectura_simple"]
        self.assertIn("$100.000", t)
        self.assertIn("$121.000", t)
        self.assertIn("$120.000", t)


class TasaRealTests(SimpleTestCase):
    def test_ejemplo_del_pdf_5_y_4_ronda_1_por_ciento(self):
        r = herramientas.tasa_real(D(5), D(4))
        self.assertEqual(r["tasa_real_aproximada_pct"], 1.0)
        self.assertAlmostEqual(r["tasa_real_exacta_pct"], 0.9615, places=4)
        self.assertIn("poder de compra crece", r["lectura_simple"])

    def test_tasa_real_negativa_pierdes_poder_de_compra(self):
        r = herramientas.tasa_real(D(2), D(5))
        self.assertLess(r["tasa_real_exacta_pct"], 0)
        self.assertIn("Pierdes poder de compra", r["lectura_simple"])

    def test_misma_tasa_que_inflacion_es_cero(self):
        r = herramientas.tasa_real(D(3), D(3))
        self.assertEqual(r["tasa_real_exacta_pct"], 0.0)
        self.assertIn("se mantiene", r["lectura_simple"])


class ConvertirTests(SimpleTestCase):
    TASAS = {
        "clp": {"pesos": 1},
        "uf": {"pesos": 40000},
        "usd": {"pesos": 1000},
        "eur": {"pesos": 1100},
    }

    def convertir(self, monto, de, a):
        return herramientas.convertir(D(monto), de, a, self.TASAS)["resultado"]

    def test_a_pesos(self):
        self.assertEqual(self.convertir(1, "uf", "clp"), 40000.0)
        self.assertEqual(self.convertir(100, "usd", "clp"), 100000.0)

    def test_desde_pesos(self):
        self.assertEqual(self.convertir(40000, "clp", "uf"), 1.0)
        self.assertEqual(self.convertir(1100, "clp", "usd"), 1.1)

    def test_entre_monedas_extranjeras(self):
        self.assertEqual(self.convertir(110, "usd", "eur"), 100.0)

    def test_misma_moneda(self):
        self.assertEqual(self.convertir(123, "usd", "usd"), 123.0)

    def test_texto_legible(self):
        t = herramientas.convertir(D(100), "usd", "clp", self.TASAS)["lectura_simple"]
        self.assertEqual(t, "100 USD = 100.000 CLP")
