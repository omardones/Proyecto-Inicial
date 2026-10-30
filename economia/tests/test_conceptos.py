"""Pruebas de los datos del PDF y de la lógica de prerrequisitos / ruta de aprendizaje."""
import json

from django.test import SimpleTestCase

from economia import conceptos, indicadores

from .ayudas import FIXTURES


class DatosDelPdfTests(SimpleTestCase):
    def test_hay_38_conceptos_con_slugs_unicos(self):
        slugs = [c["slug"] for c in conceptos.todos()]
        self.assertEqual(len(slugs), 38)
        self.assertEqual(len(set(slugs)), 38)

    def test_cantidades_por_nivel_como_en_el_pdf(self):
        por_nivel = {n: len(conceptos.buscar(nivel=n)) for n in conceptos.NIVELES}
        self.assertEqual(por_nivel, {"basico": 10, "intermedio": 18, "avanzado": 10})

    def test_prerrequisitos_existen_y_no_hay_ciclos(self):
        slugs = {c["slug"] for c in conceptos.todos()}
        for c in conceptos.todos():
            for p in c["prerrequisitos"]:
                self.assertIn(p, slugs, f"{c['slug']} pide un prerrequisito que no existe: {p}")
            self.assertNotIn(c["slug"], conceptos.clausura(c["slug"]), f"Ciclo en {c['slug']}")

    def test_un_concepto_nunca_depende_de_uno_de_nivel_mas_alto(self):
        orden = list(conceptos.NIVELES)
        for c in conceptos.todos():
            for p in c["prerrequisitos"]:
                self.assertLessEqual(
                    orden.index(conceptos.obtener(p)["nivel"]), orden.index(c["nivel"]),
                    f"{c['slug']} ({c['nivel']}) depende de {p}",
                )

    def test_antes_aprende_del_pdf_coincide_con_los_prerrequisitos_encadenados(self):
        """Las 38 listas 'Antes aprende' de las fichas deben salir de encadenar los prerrequisitos directos."""
        esperado = json.loads((FIXTURES / "antes_aprende_pdf.json").read_text(encoding="utf-8"))
        self.assertEqual(len(esperado), 38)
        for slug, previos in esperado.items():
            self.assertEqual(conceptos.clausura(slug), set(previos), slug)

    def test_fuentes_y_estados_son_coherentes(self):
        catalogo = {f["id"] for f in conceptos.fuentes()}
        for c in conceptos.todos():
            estado = c["verificacion"]["estado"]
            self.assertIn(estado, conceptos.ESTADOS)
            for f in c["fuentes"]:
                self.assertIn(f, catalogo, f"{c['slug']} cita una fuente desconocida: {f}")
            if estado in ("A", "B"):  # "verificado" o "parcial" exige al menos una fuente oficial
                oficiales = [f for f in c["fuentes"] if f != "mankiw"]
                self.assertTrue(oficiales, f"{c['slug']} es {estado} pero no cita fuente oficial")

    def test_el_pdf_trae_9_conceptos_A_14_B_y_15_C(self):
        conteo = {e: len(conceptos.buscar(estado=e)) for e in conceptos.ESTADOS}
        self.assertEqual(conteo, {"A": 9, "B": 14, "C": 15})


class RutaDeAprendizajeTests(SimpleTestCase):
    def test_la_ruta_completa_incluye_todo_y_respeta_prerrequisitos(self):
        ruta = conceptos.ruta_aprendizaje()
        self.assertEqual(len(ruta), 38)
        self.assertEqual(set(ruta), {c["slug"] for c in conceptos.todos()})
        for i, slug in enumerate(ruta):
            for p in conceptos.obtener(slug)["prerrequisitos"]:
                self.assertLess(ruta.index(p), i, f"{p} debe ir antes que {slug}")

    def test_es_determinista_y_empieza_por_los_basicos(self):
        self.assertEqual(conceptos.ruta_aprendizaje(), conceptos.ruta_aprendizaje())
        self.assertEqual(conceptos.ruta_aprendizaje()[0], "dinero")

    def test_ruta_hasta_un_concepto_trae_solo_lo_necesario(self):
        ruta = conceptos.ruta_aprendizaje("credito-hipotecario")
        self.assertEqual(ruta[-1], "credito-hipotecario")
        self.assertEqual(set(ruta), conceptos.clausura("credito-hipotecario") | {"credito-hipotecario"})
        self.assertLess(ruta.index("cae"), ruta.index("credito-hipotecario"))
        self.assertLess(ruta.index("uf"), ruta.index("credito-hipotecario"))
        self.assertNotIn("bono", ruta)

    def test_un_concepto_sin_prerrequisitos_se_estudia_solo(self):
        self.assertEqual(conceptos.ruta_aprendizaje("dinero"), ["dinero"])


class BusquedaTests(SimpleTestCase):
    def test_filtros_por_nivel_categoria_y_estado(self):
        self.assertEqual(len(conceptos.buscar(nivel="basico")), 10)
        self.assertEqual(len(conceptos.buscar(categoria="macroeconomia")), 9)
        self.assertEqual(len(conceptos.buscar(categoria="deudas-y-creditos")), 5)

    def test_busqueda_de_texto_ignora_tildes_y_mayusculas(self):
        for texto in ("inflacion", "INFLACIÓN", "Inflación"):
            slugs = [c["slug"] for c in conceptos.buscar(q=texto)]
            self.assertIn("inflacion", slugs, texto)

    def test_filtros_se_combinan(self):
        resultado = conceptos.buscar(nivel="avanzado", estado="A")
        self.assertEqual({c["slug"] for c in resultado}, {"criptomonedas", "riesgo-y-rentabilidad"})

    def test_sin_resultados(self):
        self.assertEqual(conceptos.buscar(q="zzzxxx"), [])


class CatalogoDeIndicadoresTests(SimpleTestCase):
    def test_cada_indicador_apunta_a_conceptos_que_existen(self):
        for ind in indicadores.CATALOGO:
            for slug in ind.conceptos:
                self.assertIsNotNone(conceptos.obtener(slug), f"{ind.codigo} -> {slug}")

    def test_codigos_unicos(self):
        codigos = [i.codigo for i in indicadores.CATALOGO]
        self.assertEqual(len(codigos), len(set(codigos)))

    def test_las_monedas_del_conversor_existen_en_el_catalogo(self):
        for codigo in indicadores.MONEDAS.values():
            if codigo:
                self.assertIn(codigo, indicadores.POR_CODIGO)
