"""
Los 38 conceptos del PDF "Conceptos financieros: prerrequisitos y fuentes".

Los datos viven en economia/data/conceptos.json y economia/data/fuentes.json
(se generaron leyendo el PDF y verificando que todo calce). Este módulo los
carga una sola vez y ofrece funciones para consultarlos.

Idea central: cada concepto lista sus PRERREQUISITOS DIRECTOS. Con eso se
calculan dos cosas útiles para quien aprende desde cero:
  - la "ruta de aprendizaje": en qué orden estudiar los conceptos.
  - "desbloquea": qué conceptos se vuelven fáciles una vez que dominas este.
"""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

NIVELES = {
    "basico": "Básico",
    "intermedio": "Intermedio",
    "avanzado": "Avanzado",
}
_ORDEN_NIVEL = {slug: i for i, slug in enumerate(NIVELES)}

CATEGORIAS = {
    "fundamentos": "Fundamentos",
    "ahorro-e-inversion": "Ahorro e inversión",
    "deudas-y-creditos": "Deudas y créditos",
    "macroeconomia": "Macroeconomía",
}

# Leyenda de verificación (viene del PDF). "para_el_lector" es una frase simple
# pensada para mostrarse tal cual a quien lee la página.
ESTADOS = {
    "A": {
        "etiqueta": "VERIFICADO en fuente oficial",
        "para_el_lector": "Esta definición está respaldada por una fuente oficial.",
    },
    "B": {
        "etiqueta": "PARCIAL: parte verificada en fuente oficial",
        "para_el_lector": "Una parte está respaldada por una fuente oficial; el resto viene de un libro de texto.",
    },
    "C": {
        "etiqueta": "BIBLIOGRAFÍA: sin fuente oficial consultada",
        "para_el_lector": "Esta definición viene de un libro de texto y aún no se contrasta con una fuente oficial.",
    },
}


def normalizar(texto):
    """'Inflación' -> 'inflacion' (para buscar sin importar tildes ni mayúsculas)."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


@lru_cache(maxsize=1)
def _cargar():
    conceptos = json.loads((DATA / "conceptos.json").read_text(encoding="utf-8"))
    fuentes = json.loads((DATA / "fuentes.json").read_text(encoding="utf-8"))
    por_slug = {c["slug"]: c for c in conceptos}
    desbloquea = {slug: [] for slug in por_slug}
    for c in conceptos:
        for previo in c["prerrequisitos"]:
            desbloquea[previo].append(c["slug"])
    return conceptos, por_slug, desbloquea, {f["id"]: f for f in fuentes}


# ---------------------------------------------------------------------------
# Consultas básicas
# ---------------------------------------------------------------------------
def todos():
    return _cargar()[0]


def obtener(slug):
    return _cargar()[1].get(slug)


def fuentes():
    return list(_cargar()[3].values())


def _referencia(slug):
    c = obtener(slug)
    return {"slug": c["slug"], "nombre": c["nombre"]}


def buscar(nivel=None, categoria=None, estado=None, q=None):
    """Filtra la lista de conceptos. Todos los filtros son opcionales y se combinan (Y)."""
    texto = normalizar(q) if q else None
    resultado = []
    for c in todos():
        if nivel and c["nivel"] != nivel:
            continue
        if categoria and c["categoria"] != categoria:
            continue
        if estado and c["verificacion"]["estado"] != estado:
            continue
        if texto:
            pajar = normalizar(f"{c['nombre']} {c['definicion']} {c['ejemplo']}")
            if texto not in pajar:
                continue
        resultado.append(c)
    return resultado


# ---------------------------------------------------------------------------
# Prerrequisitos y ruta de aprendizaje
# ---------------------------------------------------------------------------
def clausura(slug):
    """Todos los prerrequisitos de un concepto, directos e indirectos (sin repetir)."""
    por_slug = _cargar()[1]
    vistos = set()
    pendientes = list(por_slug[slug]["prerrequisitos"])
    while pendientes:
        actual = pendientes.pop()
        if actual not in vistos:
            vistos.add(actual)
            pendientes.extend(por_slug[actual]["prerrequisitos"])
    return vistos


def ruta_aprendizaje(hasta=None):
    """
    Orden recomendado para estudiar. Si se indica `hasta`, solo lo necesario para
    llegar a ese concepto (incluido al final).

    Algoritmo (orden topológico): en cada paso se elige, entre los conceptos cuyos
    prerrequisitos ya están estudiados, el de nivel más bajo (y por nombre si empatan).
    Así el resultado siempre es el mismo y nunca aparece un concepto antes de lo que necesita.
    """
    por_slug = _cargar()[1]
    if hasta is None:
        faltan = set(por_slug)
    else:
        faltan = clausura(hasta) | {hasta}

    ruta = []
    estudiados = set()
    while faltan:
        disponibles = [
            s for s in faltan if all(p in estudiados for p in por_slug[s]["prerrequisitos"])
        ]
        siguiente = min(
            disponibles,
            key=lambda s: (_ORDEN_NIVEL[por_slug[s]["nivel"]], normalizar(por_slug[s]["nombre"])),
        )
        ruta.append(siguiente)
        estudiados.add(siguiente)
        faltan.remove(siguiente)
    return ruta


# ---------------------------------------------------------------------------
# Formatos de salida (lo que ve quien consume la API)
# ---------------------------------------------------------------------------
def _etiquetado(clave, mapa):
    return {"slug": clave, "nombre": mapa[clave]}


def resumen(c):
    """Versión corta: para listados."""
    return {
        "slug": c["slug"],
        "nombre": c["nombre"],
        "categoria": _etiquetado(c["categoria"], CATEGORIAS),
        "nivel": _etiquetado(c["nivel"], NIVELES),
        "definicion": c["definicion"],
        "estado_verificacion": c["verificacion"]["estado"],
    }


def ficha(c):
    """Versión completa de un concepto."""
    _, por_slug, desbloquea, catalogo = _cargar()
    previos_en_orden = [s for s in ruta_aprendizaje(hasta=c["slug"]) if s != c["slug"]]
    estado = c["verificacion"]["estado"]
    return {
        "slug": c["slug"],
        "nombre": c["nombre"],
        "categoria": _etiquetado(c["categoria"], CATEGORIAS),
        "nivel": _etiquetado(c["nivel"], NIVELES),
        "definicion": c["definicion"],
        "ejemplo": c["ejemplo"],
        "verificacion": {
            "estado": estado,
            "etiqueta": c["verificacion"]["etiqueta"],
            "para_el_lector": ESTADOS[estado]["para_el_lector"],
            "nota": c["verificacion"]["nota"],
        },
        "prerrequisitos_directos": [_referencia(s) for s in c["prerrequisitos"]],
        "antes_de_aprender": [
            {**_referencia(s), "nivel": _etiquetado(por_slug[s]["nivel"], NIVELES)}
            for s in previos_en_orden
        ],
        "desbloquea": [_referencia(s) for s in desbloquea[c["slug"]]],
        "fuentes": [catalogo[f] for f in c["fuentes"]],
    }
