"""
Mini quiz de un concepto.

Las preguntas se ARMAN con el contenido que ya está en data/conceptos.json (definiciones,
ejemplos y prerrequisitos que vienen del PDF). No se inventa información nueva: lo único
que cambia es el orden y qué otros conceptos se usan como alternativas incorrectas.

Con la misma `semilla` el quiz sale siempre igual (útil para las pruebas); con otra semilla
cambian las alternativas, para poder "intentar de nuevo".
"""
import random
import re

from . import conceptos

LETRAS = "abcd"


def _terminos(c):
    """Formas en que puede aparecer el nombre: 'UF (Unidad de Fomento)' -> UF, Unidad de Fomento."""
    nombre = c["nombre"]
    partes = [nombre, re.sub(r"\s*\(.*?\)", "", nombre)] + re.findall(r"\((.*?)\)", nombre)
    return sorted({p.strip() for p in partes if len(p.strip()) >= 2}, key=len, reverse=True)


def _ocultar(texto, c):
    """Reemplaza el nombre del concepto por '___' para que la pregunta no se responda sola."""
    for termino in _terminos(c):
        texto = re.sub(r"(?<!\w)" + re.escape(termino) + r"(?!\w)", "___", texto, flags=re.IGNORECASE)
    return texto


def _distractores(rng, correcto, candidatos, cantidad=3):
    """Elige `cantidad` conceptos distintos de `correcto`, prefiriendo los de su misma categoría."""
    otros = [c for c in candidatos if c["slug"] != correcto["slug"]]
    misma = [c for c in otros if c["categoria"] == correcto["categoria"]]
    resto = [c for c in otros if c["categoria"] != correcto["categoria"]]
    rng.shuffle(misma)
    rng.shuffle(resto)
    return (misma + resto)[:cantidad]


def _pregunta(rng, numero, enunciado, correcta, incorrectas, explicacion, contexto=None):
    textos = [correcta] + incorrectas
    rng.shuffle(textos)
    opciones = [{"id": LETRAS[i], "texto": t} for i, t in enumerate(textos)]
    pregunta = {
        "numero": numero,
        "pregunta": enunciado,
        "opciones": opciones,
        "correcta": LETRAS[textos.index(correcta)],
        "explicacion": explicacion,
    }
    if contexto:
        pregunta["contexto"] = contexto
    return pregunta


def _descendientes(slug):
    """Conceptos que necesitan (directa o indirectamente) a `slug`."""
    return {c["slug"] for c in conceptos.todos() if slug in conceptos.clausura(c["slug"])}


def generar(slug, semilla=0):
    c = conceptos.obtener(slug)
    if c is None:
        return None
    rng = random.Random(f"{slug}:{semilla}")
    todos = conceptos.todos()
    preguntas = []

    # 1) ¿Qué significa?
    otros = _distractores(rng, c, todos)
    preguntas.append(_pregunta(
        rng, 1,
        f"¿Qué significa «{c['nombre']}»?",
        _ocultar(c["definicion"], c),
        [_ocultar(o["definicion"], o) for o in otros],
        c["definicion"],
    ))

    # 2) ¿Qué concepto muestra este ejemplo?
    if c["ejemplo"]:
        otros = _distractores(rng, c, todos)
        preguntas.append(_pregunta(
            rng, 2,
            "¿Qué concepto se ve en este ejemplo?",
            c["nombre"],
            [o["nombre"] for o in otros],
            f"El ejemplo corresponde a «{c['nombre']}».",
            contexto=_ocultar(c["ejemplo"], c),
        ))

    # 3) Antes / después: usa los prerrequisitos del PDF
    antes = conceptos.clausura(slug)
    despues = _descendientes(slug)
    if c["prerrequisitos"]:
        correcto = conceptos.obtener(rng.choice(sorted(c["prerrequisitos"])))
        # alternativas incorrectas: conceptos que NO hacen falta antes (ni el mismo concepto)
        candidatos = [o for o in todos if o["slug"] not in antes and o["slug"] != slug]
        otros = _distractores(rng, correcto, candidatos)
        preguntas.append(_pregunta(
            rng, len(preguntas) + 1,
            f"¿Cuál de estos conceptos conviene entender ANTES de «{c['nombre']}»?",
            correcto["nombre"],
            [o["nombre"] for o in otros],
            f"«{correcto['nombre']}» es un prerrequisito directo de «{c['nombre']}».",
        ))
    elif despues:
        correcto = conceptos.obtener(rng.choice(sorted(despues)))
        candidatos = [o for o in todos if o["slug"] not in despues and o["slug"] != slug]
        otros = _distractores(rng, correcto, candidatos)
        preguntas.append(_pregunta(
            rng, len(preguntas) + 1,
            f"¿Cuál de estos conceptos se apoya en «{c['nombre']}»?",
            correcto["nombre"],
            [o["nombre"] for o in otros],
            f"Para entender «{correcto['nombre']}» conviene saber antes «{c['nombre']}».",
        ))

    return {
        "concepto": {"slug": c["slug"], "nombre": c["nombre"]},
        "semilla": semilla,
        "total_preguntas": len(preguntas),
        "minimo_para_aprobar": max(1, len(preguntas) - 1),
        "preguntas": preguntas,
        "nota": "Las preguntas se arman con las definiciones, ejemplos y prerrequisitos del PDF.",
    }
