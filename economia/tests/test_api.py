"""Pruebas de punta a punta: se hacen peticiones HTTP reales contra las rutas /api/..."""
from django.test import Client

from .ayudas import PruebaConFuenteFalsa


class ApiBase(PruebaConFuenteFalsa):
    def get(self, ruta, **kwargs):
        return self.client.get(ruta, **kwargs)

    def json(self, ruta, status=200):
        r = self.get(ruta)
        self.assertEqual(r.status_code, status, r.content.decode())
        self.assertTrue(r["Content-Type"].startswith("application/json"))
        return r.json()

    def assertError(self, ruta, status, codigo):
        cuerpo = self.json(ruta, status)
        self.assertEqual(cuerpo["error"]["codigo"], codigo)
        self.assertTrue(cuerpo["error"]["mensaje"])
        return cuerpo["error"]


class GeneralTests(ApiBase):
    def test_indice_describe_la_api(self):
        d = self.json("/api/")
        self.assertEqual(set(d["endpoints"]), {"conceptos", "datos_en_vivo", "herramientas", "sistema"})
        rutas = [e["ruta"] for grupo in d["endpoints"].values() for e in grupo]
        self.assertIn("/api/indicadores/", rutas)
        self.assertTrue(d["endpoints"]["conceptos"][0]["ejemplo"].startswith("http://testserver/api/"))

    def test_json_con_tildes_y_enes_sin_escapar(self):
        texto = self.get("/api/conceptos/inflacion/").content.decode("utf-8")
        self.assertIn("Inflación", texto)
        self.assertNotIn("\\u00f3", texto)

    def test_salud(self):
        d = self.json("/api/salud/")
        self.assertEqual(d["estado"], "ok")
        self.assertEqual(d["conceptos_cargados"], 38)
        self.assertNotIn("fuente_externa", d)
        self.assertEqual(self.fuente.llamadas, [])  # por defecto no llama a internet

    def test_salud_probando_la_fuente(self):
        self.assertTrue(self.json("/api/salud/?probar_fuente=1")["fuente_externa"]["disponible"])
        self.fuente.caida = True
        d = self.json("/api/salud/?probar_fuente=1")  # el servidor sigue "ok" aunque la fuente falle
        self.assertEqual(d["estado"], "ok")
        self.assertFalse(d["fuente_externa"]["disponible"])

    def test_la_raiz_muestra_la_pagina_basica(self):
        r = self.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r["Content-Type"])
        html = r.content.decode()
        self.assertIn("Economía para jóvenes", html)
        # La página consume rutas reales de la API
        for ruta in ("/api/indicadores/", "/api/conceptos/", "/api/ruta-aprendizaje/", "/api/herramientas/convertir/"):
            self.assertIn(ruta, html)

    def test_ruta_inexistente_devuelve_404_en_json(self):
        self.assertError("/api/no-existe/", 404, "no_encontrado")

    def test_falta_la_barra_final_se_redirige_conservando_los_parametros(self):
        r = self.get("/api/conceptos?nivel=basico")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r["Location"], "/api/conceptos/?nivel=basico")

    def test_solo_lectura_post_da_405_en_json_incluso_con_proteccion_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        r = cliente.post("/api/conceptos/")
        self.assertEqual(r.status_code, 405)
        self.assertEqual(r.json()["error"]["codigo"], "metodo_no_permitido")
        self.assertIn("GET", r["Allow"])

    def test_head_funciona(self):
        self.assertEqual(self.client.head("/api/conceptos/").status_code, 200)

    def test_cors_en_la_api_pero_no_fuera_de_ella(self):
        self.assertEqual(self.get("/api/conceptos/")["Access-Control-Allow-Origin"], "*")
        pre = self.client.options("/api/conceptos/")
        self.assertEqual(pre.status_code, 204)
        self.assertIn("GET", pre["Access-Control-Allow-Methods"])
        self.assertNotIn("Access-Control-Allow-Origin", self.get("/otra-cosa/"))

    def test_cors_se_puede_restringir_desde_settings(self):
        with self.settings(ECONOMIA_CORS_ORIGEN="https://mi-frontend.cl"):
            self.assertEqual(self.get("/api/conceptos/")["Access-Control-Allow-Origin"], "https://mi-frontend.cl")


class ConceptosApiTests(ApiBase):
    def test_lista_completa_con_filtros_disponibles(self):
        d = self.json("/api/conceptos/")
        self.assertEqual(d["total"], 38)
        self.assertEqual(len(d["conceptos"]), 38)
        self.assertEqual(len(d["niveles_disponibles"]), 3)
        self.assertEqual(len(d["categorias_disponibles"]), 4)
        primero = d["conceptos"][0]
        self.assertEqual(set(primero), {"slug", "nombre", "categoria", "nivel", "definicion", "estado_verificacion"})

    def test_filtros(self):
        self.assertEqual(self.json("/api/conceptos/?nivel=basico")["total"], 10)
        self.assertEqual(self.json("/api/conceptos/?nivel=BASICO")["total"], 10)  # mayúsculas da igual
        self.assertEqual(self.json("/api/conceptos/?estado=a")["total"], 9)
        self.assertEqual(self.json("/api/conceptos/?categoria=macroeconomia&nivel=intermedio")["total"], 8)
        self.assertEqual(self.json("/api/conceptos/?q=dólar")["total"], self.json("/api/conceptos/?q=dolar")["total"])

    def test_filtro_invalido_da_400_explicando_las_opciones(self):
        error = self.assertError("/api/conceptos/?nivel=experto", 400, "parametro_invalido")
        self.assertIn("basico", error["mensaje"])
        self.assertError("/api/conceptos/?estado=Z", 400, "parametro_invalido")
        self.assertError("/api/conceptos/?q=" + "x" * 101, 400, "parametro_invalido")

    def test_ficha_completa(self):
        c = self.json("/api/conceptos/credito-hipotecario/?en_vivo=0")["concepto"]
        self.assertEqual(c["nombre"], "Crédito hipotecario")
        self.assertEqual(c["nivel"], {"slug": "avanzado", "nombre": "Avanzado"})
        self.assertEqual(c["verificacion"]["estado"], "B")
        self.assertTrue(c["verificacion"]["para_el_lector"])
        self.assertEqual([p["slug"] for p in c["prerrequisitos_directos"]], ["cae", "uf"])
        previos = [p["slug"] for p in c["antes_de_aprender"]]
        self.assertLess(previos.index("deuda"), previos.index("cae"))  # en orden de estudio
        self.assertNotIn("credito-hipotecario", previos)
        self.assertEqual(c["fuentes"][0]["id"], "bcch-metodologia-uf")
        self.assertEqual(c["desbloquea"], [])

    def test_desbloquea(self):
        c = self.json("/api/conceptos/dinero/?en_vivo=0")["concepto"]
        slugs = {x["slug"] for x in c["desbloquea"]}
        self.assertTrue({"inflacion", "interes", "pib", "tipo-de-cambio"} <= slugs)
        self.assertEqual(c["antes_de_aprender"], [])

    def test_ficha_incluye_datos_en_vivo_relacionados(self):
        d = self.json("/api/conceptos/uf/")["concepto"]
        self.assertTrue(d["en_vivo"]["disponible"])
        self.assertEqual([i["codigo"] for i in d["en_vivo"]["indicadores"]], ["uf"])
        self.assertEqual(d["en_vivo"]["indicadores"][0]["valor"], 41215.77)
        self.assertEqual(d["indicadores_relacionados"][0]["url"], "http://testserver/api/indicadores/uf/")

    def test_en_vivo_0_no_llama_a_la_fuente(self):
        d = self.json("/api/conceptos/uf/?en_vivo=0")["concepto"]
        self.assertIsNone(d["en_vivo"])
        self.assertEqual(self.fuente.llamadas, [])

    def test_concepto_sin_indicadores_no_llama_a_la_fuente(self):
        d = self.json("/api/conceptos/escasez/")["concepto"]
        self.assertIsNone(d["en_vivo"])
        self.assertEqual(d["indicadores_relacionados"], [])
        self.assertEqual(self.fuente.llamadas, [])

    def test_si_la_fuente_falla_la_ficha_igual_se_entrega(self):
        self.fuente.caida = True
        d = self.json("/api/conceptos/tipo-de-cambio/")["concepto"]  # 200, no 503
        self.assertEqual(d["nombre"], "Tipo de cambio")
        self.assertFalse(d["en_vivo"]["disponible"])
        self.assertIn("mensaje", d["en_vivo"])

    def test_concepto_inexistente(self):
        self.assertError("/api/conceptos/xyz/", 404, "no_encontrado")

    def test_ruta_de_aprendizaje(self):
        d = self.json("/api/ruta-aprendizaje/")
        self.assertEqual(d["total_pasos"], 38)
        self.assertEqual([p["paso"] for p in d["pasos"]], list(range(1, 39)))
        self.assertIsNone(d["hasta"])
        d = self.json("/api/ruta-aprendizaje/?hasta=uf")
        self.assertEqual([p["slug"] for p in d["pasos"]], ["dinero", "inflacion", "uf"])
        self.assertError("/api/ruta-aprendizaje/?hasta=xyz", 404, "no_encontrado")

    def test_fuentes_y_leyenda(self):
        d = self.json("/api/fuentes/")
        self.assertEqual([x["estado"] for x in d["leyenda_verificacion"]], ["A", "B", "C"])
        self.assertEqual(d["total_fuentes"], 17)
        for f in d["fuentes"]:
            self.assertTrue(f["usada_en"], f"{f['id']} no la usa ningún concepto")
        mankiw = next(f for f in d["fuentes"] if f["id"] == "mankiw")
        self.assertIsNone(mankiw["url"])
        self.assertFalse(mankiw["consultada_en_linea"])


class IndicadoresApiTests(ApiBase):
    def test_lista_de_indicadores(self):
        d = self.json("/api/indicadores/")
        self.assertEqual(len(d["indicadores"]), 10)
        self.assertEqual(d["meta"]["fuente"]["nombre"], "mindicador.cl")
        uf = d["indicadores"][0]
        self.assertEqual((uf["codigo"], uf["valor"], uf["valor_formateado"]), ("uf", 41215.77, "$41.215,77"))

    def test_detalle_de_un_indicador(self):
        d = self.json("/api/indicadores/uf/?ultimos=2")["indicador"]
        self.assertEqual(len(d["serie"]), 2)
        self.assertEqual(d["variacion"]["absoluta"], 3.77)

    def test_indicador_inexistente_lista_los_disponibles(self):
        error = self.assertError("/api/indicadores/oro/", 404, "no_encontrado")
        self.assertIn("uf", error["disponibles"])
        self.assertIn("tasa_desempleo", error["disponibles"])

    def test_parametro_ultimos_invalido(self):
        for malo in ("0", "-1", "abc", "367", "2.5"):
            self.assertError(f"/api/indicadores/uf/?ultimos={malo}", 400, "parametro_invalido")

    def test_fuente_caida_sin_cache_da_503_en_json(self):
        self.fuente.caida = True
        self.assertError("/api/indicadores/", 503, "fuente_no_disponible")
        self.assertError("/api/indicadores/uf/", 503, "fuente_no_disponible")

    def test_fuente_caida_con_cache_sigue_respondiendo(self):
        self.json("/api/indicadores/")
        self.fuente.caida = True
        with self.settings(ECONOMIA_CACHE_SEGUNDOS=0):  # fuerza a intentar de nuevo la fuente
            d = self.json("/api/indicadores/")
        self.assertTrue(d["meta"]["cache"]["obsoleta"])
        self.assertIn("aviso", d["meta"])


class HerramientasApiTests(ApiBase):
    def test_convertir_dolares_a_pesos_con_valor_en_vivo(self):
        d = self.json("/api/herramientas/convertir/?de=usd&a=clp&monto=100")
        self.assertEqual(d["conversion"]["resultado"], 98658.0)
        self.assertEqual(d["conversion"]["lectura_simple"], "100 USD = 98.658 CLP")
        self.assertEqual(d["valores_usados_en_pesos"]["usd"]["pesos"], 986.58)
        self.assertIn("meta", d)

    def test_convertir_uf_a_pesos_y_mayusculas(self):
        d = self.json("/api/herramientas/convertir/?de=UF&a=CLP&monto=1")
        self.assertEqual(d["conversion"]["resultado"], 41215.77)

    def test_convertir_valida_los_parametros(self):
        for query in (
            "de=usd&a=clp",  # falta monto
            "a=clp&monto=1",  # falta de
            "de=oro&a=clp&monto=1",  # moneda desconocida
            "de=usd&a=clp&monto=1.000,5",  # separador de miles / coma decimal
            "de=usd&a=clp&monto=-5",  # negativo
            "de=usd&a=clp&monto=abc",
            "de=usd&a=clp&monto=1e9",  # notación científica no se acepta
            "de=usd&a=clp&monto=NaN",
        ):
            self.assertError(f"/api/herramientas/convertir/?{query}", 400, "parametro_invalido")
        self.assertEqual(self.fuente.llamadas, [])  # con parámetros malos ni se llama a la fuente

    def test_convertir_con_fuente_caida(self):
        self.fuente.caida = True
        self.assertError("/api/herramientas/convertir/?de=usd&a=clp&monto=1", 503, "fuente_no_disponible")

    def test_interes_compuesto_ejemplo_del_pdf(self):
        d = self.json("/api/herramientas/interes-compuesto/?capital=100000&tasa=10&anios=2")["interes_compuesto"]
        self.assertEqual([f["saldo"] for f in d["detalle_por_anio"]], [110000.0, 121000.0])

    def test_interes_compuesto_valida_los_parametros(self):
        for query in (
            "tasa=10&anios=2",  # falta capital
            "capital=100000&tasa=150&anios=2",  # tasa fuera de rango
            "capital=100000&tasa=10&anios=0",
            "capital=100000&tasa=10&anios=2.5",
            "capital=100000&tasa=10&anios=81",
            "capital=0&tasa=10&anios=2",
            "capital=100.000&tasa=10&anios=2",  # punto de miles: valdría 100 sin avisar -> se rechaza
        ):
            self.assertError(f"/api/herramientas/interes-compuesto/?{query}", 400, "parametro_invalido")

    def test_punto_de_miles_se_rechaza_con_un_mensaje_que_explica_como_escribirlo(self):
        error = self.assertError("/api/herramientas/convertir/?de=usd&a=clp&monto=1.000.000", 400, "parametro_invalido")
        self.assertIn("monto=1000000", error["mensaje"])
        # pero los decimales normales sí se aceptan
        for monto in ("1.5", "0.125", "100", "1000000", "1234.56", "12.3456"):
            self.assertEqual(self.get(f"/api/herramientas/convertir/?de=usd&a=clp&monto={monto}").status_code, 200, monto)

    def test_tasa_real_ejemplo_del_pdf(self):
        d = self.json("/api/herramientas/tasa-real/?nominal=5&inflacion=4")["tasa_real"]
        self.assertEqual(d["tasa_real_aproximada_pct"], 1.0)
        self.assertAlmostEqual(d["tasa_real_exacta_pct"], 0.9615, places=4)

    def test_tasa_real_valida_los_parametros(self):
        self.assertError("/api/herramientas/tasa-real/?nominal=5", 400, "parametro_invalido")
        self.assertError("/api/herramientas/tasa-real/?nominal=5&inflacion=-100", 400, "parametro_invalido")
        self.assertError("/api/herramientas/tasa-real/?nominal=5&inflacion=x", 400, "parametro_invalido")
