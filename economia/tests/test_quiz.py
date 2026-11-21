"""Pruebas del mini quiz: se arma solo con el contenido del PDF y no se responde solo."""
from django.test import SimpleTestCase

from economia import conceptos, quiz


class QuizTests(SimpleTestCase):
    def test_todos_los_conceptos_tienen_quiz_valido(self):
        for c in conceptos.todos():
            q = quiz.generar(c["slug"])
            self.assertGreaterEqual(q["total_preguntas"], 2, c["slug"])
            for p in q["preguntas"]:
                ids = [o["id"] for o in p["opciones"]]
                textos = [o["texto"] for o in p["opciones"]]
                self.assertEqual(len(ids), 4, c["slug"])
                self.assertEqual(len(set(textos)), 4, f"{c['slug']}: alternativas repetidas")
                self.assertIn(p["correcta"], ids)

    def test_la_definicion_correcta_es_la_del_concepto(self):
        c = conceptos.obtener("inflacion")
        p = quiz.generar("inflacion")["preguntas"][0]
        correcta = next(o["texto"] for o in p["opciones"] if o["id"] == p["correcta"])
        self.assertEqual(correcta, c["definicion"])

    def test_el_nombre_se_oculta_para_que_no_se_responda_solo(self):
        p = quiz.generar("uf")["preguntas"]
        correcta = next(o["texto"] for o in p[0]["opciones"] if o["id"] == p[0]["correcta"])
        self.assertNotIn("Unidad de Fomento", correcta)
        self.assertNotIn("UF", p[1]["contexto"])

    def test_pregunta_de_prerrequisito_usa_uno_directo_y_ninguna_alternativa_es_previa(self):
        c = conceptos.obtener("credito-hipotecario")
        p = quiz.generar("credito-hipotecario")["preguntas"][-1]
        nombres = {conceptos.obtener(s)["nombre"]: s for s in conceptos.clausura("credito-hipotecario")}
        correcta = next(o["texto"] for o in p["opciones"] if o["id"] == p["correcta"])
        self.assertIn(nombres[correcta], c["prerrequisitos"])
        incorrectas = [o["texto"] for o in p["opciones"] if o["id"] != p["correcta"]]
        self.assertFalse(set(incorrectas) & set(nombres))

    def test_misma_semilla_mismo_quiz_y_otra_semilla_lo_cambia(self):
        self.assertEqual(quiz.generar("ahorro", 1), quiz.generar("ahorro", 1))
        distintos = {str(quiz.generar("ahorro", s)["preguntas"]) for s in range(5)}
        self.assertGreater(len(distintos), 1)

    def test_concepto_inexistente(self):
        self.assertIsNone(quiz.generar("no-existe"))
