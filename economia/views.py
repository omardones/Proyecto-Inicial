"""
Vistas de la API. Cada función recibe una petición HTTP y devuelve JSON.
La lógica de verdad vive en conceptos.py, indicadores.py y herramientas.py;
aquí solo se leen y validan parámetros y se arma la respuesta.
"""
import re
from decimal import Decimal

from django.http import HttpResponsePermanentRedirect
from django.urls import Resolver404, resolve

from . import conceptos, herramientas, indicadores
from .indicadores import FuenteNoDisponible
from .respuestas import error, ok, solo_lectura

VERSION = "1.0"


# ---------------------------------------------------------------------------
# Lectura y validación de parámetros (?clave=valor)
# ---------------------------------------------------------------------------
class ParametroInvalido(Exception):
    pass


_NUMERO = re.compile(r"-?\d+(\.\d+)?")
# "100.000" o "1.234.567": en Chile el punto separa miles, pero aquí significaría 100 y 1,234567.
_PARECE_PUNTO_DE_MILES = re.compile(r"-?[1-9]\d{0,2}(\.\d{3})+")


def _numero(request, nombre, minimo, maximo, ejemplo):
    """
    Número decimal obligatorio. Se pide con punto decimal y sin separador de miles
    (1000000.50, no 1.000.000,50). Como "100.000" es un error muy fácil de cometer en Chile
    (y valdría 100, sin avisar), los números que parecen escritos con puntos de miles se rechazan.
    """
    crudo = request.GET.get(nombre, "").strip()
    if not crudo:
        raise ParametroInvalido(f"Falta el parámetro '{nombre}'. Ejemplo: {nombre}={ejemplo}")
    if _PARECE_PUNTO_DE_MILES.fullmatch(crudo):  # va primero: "1.000.000" tampoco es un decimal válido
        raise ParametroInvalido(
            f"'{nombre}' parece escrito con punto de miles (como en 1.000.000). Escríbelo sin separadores, "
            f"por ejemplo {nombre}=1000000; el punto solo se usa para decimales (por ejemplo 1.5)."
        )
    if len(crudo) > 30 or not _NUMERO.fullmatch(crudo):
        raise ParametroInvalido(
            f"'{nombre}' debe ser un número con punto decimal y sin separador de miles "
            f"(ejemplo: {nombre}={ejemplo})."
        )
    valor = Decimal(crudo)
    if not (minimo <= valor <= maximo):
        raise ParametroInvalido(f"'{nombre}' debe estar entre {minimo} y {maximo}.")
    return valor


def _entero(request, nombre, minimo, maximo, defecto=None):
    crudo = request.GET.get(nombre, "").strip()
    if not crudo:
        if defecto is None:
            raise ParametroInvalido(f"Falta el parámetro '{nombre}' (entero entre {minimo} y {maximo}).")
        return defecto
    if not re.fullmatch(r"\d{1,6}", crudo) or not (minimo <= int(crudo) <= maximo):
        raise ParametroInvalido(f"'{nombre}' debe ser un número entero entre {minimo} y {maximo}.")
    return int(crudo)


def _opcion(request, nombre, validas, transformar=lambda s: s):
    """Parámetro opcional que debe ser uno de `validas`. Devuelve None si no viene."""
    crudo = request.GET.get(nombre, "").strip()
    if not crudo:
        return None
    valor = transformar(crudo)
    if valor not in validas:
        raise ParametroInvalido(f"'{nombre}' debe ser uno de: {', '.join(validas)}.")
    return valor


def _parametro_invalido(e):
    return error("parametro_invalido", str(e), 400)


def _sin_fuente(e):
    return error(
        "fuente_no_disponible",
        "No pudimos obtener los datos económicos en vivo en este momento. Intenta de nuevo en unos minutos.",
        503,
        detalle=str(e),
    )


def _url(request, ruta):
    return request.build_absolute_uri(ruta)


# ---------------------------------------------------------------------------
# Información general
# ---------------------------------------------------------------------------
@solo_lectura
def indice(request):
    """GET /api/  ->  mapa de la API (se explica sola)."""
    def e(ruta, descripcion, ejemplo=None, parametros=None):
        return {
            "metodo": "GET",
            "ruta": ruta,
            "descripcion": descripcion,
            "parametros": parametros or {},
            "ejemplo": _url(request, ejemplo or ruta),
        }

    return ok({
        "nombre": "API de Economía para jóvenes",
        "version": VERSION,
        "descripcion": (
            "Explica conceptos de economía y finanzas personales en lenguaje simple y los conecta "
            "con datos económicos de Chile en vivo."
        ),
        "endpoints": {
            "conceptos": [
                e("/api/conceptos/", "Lista de los 38 conceptos, con filtros.",
                  "/api/conceptos/?nivel=basico",
                  {"nivel": "basico | intermedio | avanzado", "categoria": "fundamentos | ahorro-e-inversion | deudas-y-creditos | macroeconomia",
                   "estado": "A | B | C (qué tan respaldado está)", "q": "texto a buscar"}),
                e("/api/conceptos/{slug}/", "Ficha completa: definición, ejemplo, prerrequisitos, fuentes y datos en vivo relacionados.",
                  "/api/conceptos/uf/", {"en_vivo": "0 para no incluir datos en vivo (por defecto 1)"}),
                e("/api/ruta-aprendizaje/", "En qué orden estudiar los conceptos (todos, o solo lo necesario para llegar a uno).",
                  "/api/ruta-aprendizaje/?hasta=credito-hipotecario", {"hasta": "slug del concepto al que quieres llegar"}),
                e("/api/fuentes/", "Fuentes consultadas y significado de los estados de verificación A, B y C."),
            ],
            "datos_en_vivo": [
                e("/api/indicadores/", "Último valor de UF, dólar, euro, TPM, IPC, Imacec, desempleo, UTM, bitcoin y cobre."),
                e("/api/indicadores/{codigo}/", "Un indicador con su variación y sus valores anteriores.",
                  "/api/indicadores/dolar/", {"ultimos": "cuántos valores anteriores mostrar, 1 a 366 (por defecto 30)"}),
            ],
            "herramientas": [
                e("/api/herramientas/convertir/", "Convierte entre pesos (clp), UF (uf), dólares (usd) y euros (eur) con valores en vivo.",
                  "/api/herramientas/convertir/?de=usd&a=clp&monto=100",
                  {"de": "clp | uf | usd | eur", "a": "clp | uf | usd | eur", "monto": "número (punto decimal)"}),
                e("/api/herramientas/interes-compuesto/", "Cuánto crece un ahorro con interés compuesto, año por año.",
                  "/api/herramientas/interes-compuesto/?capital=100000&tasa=10&anios=2",
                  {"capital": "pesos", "tasa": "% anual", "anios": "entero"}),
                e("/api/herramientas/tasa-real/", "Cuánto crece de verdad tu poder de compra: tasa nominal vs. inflación.",
                  "/api/herramientas/tasa-real/?nominal=5&inflacion=4", {"nominal": "% anual", "inflacion": "% anual"}),
            ],
            "sistema": [
                e("/api/salud/", "¿El servidor está funcionando?", "/api/salud/?probar_fuente=1",
                  {"probar_fuente": "1 para comprobar también la API externa de indicadores"}),
            ],
        },
    })


@solo_lectura
def salud(request):
    """GET /api/salud/  ->  estado del servidor. Con ?probar_fuente=1 prueba además la API externa."""
    respuesta = {
        "estado": "ok",
        "version": VERSION,
        "conceptos_cargados": len(conceptos.todos()),
        "hora_servidor": indicadores.ahora_chile().isoformat(timespec="seconds"),
    }
    if request.GET.get("probar_fuente") == "1":
        disponible, detalle = indicadores.probar_fuente()
        respuesta["fuente_externa"] = {
            "url": indicadores.url_fuente(), "disponible": disponible, "detalle": detalle,
        }
    return ok(respuesta)


# ---------------------------------------------------------------------------
# Conceptos
# ---------------------------------------------------------------------------
@solo_lectura
def conceptos_lista(request):
    try:
        nivel = _opcion(request, "nivel", list(conceptos.NIVELES), str.lower)
        categoria = _opcion(request, "categoria", list(conceptos.CATEGORIAS), str.lower)
        estado = _opcion(request, "estado", list(conceptos.ESTADOS), str.upper)
        q = request.GET.get("q", "").strip() or None
        if q and len(q) > 100:
            raise ParametroInvalido("'q' admite hasta 100 caracteres.")
    except ParametroInvalido as e:
        return _parametro_invalido(e)

    encontrados = conceptos.buscar(nivel=nivel, categoria=categoria, estado=estado, q=q)
    return ok({
        "total": len(encontrados),
        "filtros_aplicados": {"nivel": nivel, "categoria": categoria, "estado": estado, "q": q},
        "conceptos": [conceptos.resumen(c) for c in encontrados],
        "niveles_disponibles": [{"slug": s, "nombre": n} for s, n in conceptos.NIVELES.items()],
        "categorias_disponibles": [{"slug": s, "nombre": n} for s, n in conceptos.CATEGORIAS.items()],
    })


@solo_lectura
def concepto_detalle(request, slug):
    c = conceptos.obtener(slug)
    if c is None:
        return error(
            "no_encontrado", f"No existe el concepto '{slug}'. Mira /api/conceptos/ para ver todos.", 404,
        )

    relacionados = indicadores.indicadores_de_concepto(slug)
    ficha = conceptos.ficha(c)
    ficha["indicadores_relacionados"] = [
        {"codigo": i.codigo, "nombre": i.nombre, "url": _url(request, f"/api/indicadores/{i.codigo}/")}
        for i in relacionados
    ]

    # Datos en vivo: si la fuente externa falla, la ficha igual se entrega (sin romperse).
    ficha["en_vivo"] = None
    if relacionados and request.GET.get("en_vivo", "1") != "0":
        try:
            actuales = indicadores.listar_actuales()
            codigos = {i.codigo for i in relacionados}
            ficha["en_vivo"] = {
                "disponible": True,
                "indicadores": [i for i in actuales["indicadores"] if i["codigo"] in codigos],
                "meta": actuales["meta"],
            }
        except FuenteNoDisponible as e:
            ficha["en_vivo"] = {
                "disponible": False,
                "mensaje": "Los datos en vivo no están disponibles en este momento.",
                "detalle": str(e),
            }
    return ok({"concepto": ficha})


@solo_lectura
def ruta_aprendizaje(request):
    hasta = request.GET.get("hasta", "").strip() or None
    if hasta is not None and conceptos.obtener(hasta) is None:
        return error("no_encontrado", f"No existe el concepto '{hasta}'. Mira /api/conceptos/ para ver todos.", 404)

    pasos = []
    for numero, slug in enumerate(conceptos.ruta_aprendizaje(hasta), start=1):
        resumen = conceptos.resumen(conceptos.obtener(slug))
        pasos.append({
            "paso": numero,
            "slug": slug,
            "nombre": resumen["nombre"],
            "nivel": resumen["nivel"],
            "categoria": resumen["categoria"],
            "prerrequisitos_directos": conceptos.obtener(slug)["prerrequisitos"],
        })
    return ok({"hasta": hasta, "total_pasos": len(pasos), "pasos": pasos})


@solo_lectura
def fuentes(request):
    usadas_en = {}
    for c in conceptos.todos():
        for f in c["fuentes"]:
            usadas_en.setdefault(f, []).append(c["slug"])
    return ok({
        "leyenda_verificacion": [
            {"estado": letra, **datos} for letra, datos in conceptos.ESTADOS.items()
        ],
        "total_fuentes": len(conceptos.fuentes()),
        "fuentes": [{**f, "usada_en": usadas_en.get(f["id"], [])} for f in conceptos.fuentes()],
    })


# ---------------------------------------------------------------------------
# Datos en vivo
# ---------------------------------------------------------------------------
@solo_lectura
def indicadores_lista(request):
    try:
        return ok(indicadores.listar_actuales())
    except FuenteNoDisponible as e:
        return _sin_fuente(e)


@solo_lectura
def indicador_detalle(request, codigo):
    if codigo not in indicadores.POR_CODIGO:
        return error(
            "no_encontrado", f"No existe el indicador '{codigo}'.", 404,
            disponibles=list(indicadores.POR_CODIGO),
        )
    try:
        ultimos = _entero(request, "ultimos", 1, 366, defecto=30)
    except ParametroInvalido as e:
        return _parametro_invalido(e)
    try:
        return ok(indicadores.detalle(codigo, ultimos))
    except FuenteNoDisponible as e:
        return _sin_fuente(e)


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------
@solo_lectura
def convertir(request):
    try:
        de = _opcion(request, "de", list(indicadores.MONEDAS), str.lower)
        a = _opcion(request, "a", list(indicadores.MONEDAS), str.lower)
        if de is None or a is None:
            raise ParametroInvalido(
                f"Faltan 'de' y 'a' (monedas: {', '.join(indicadores.MONEDAS)}). "
                "Ejemplo: de=usd&a=clp&monto=100"
            )
        monto = _numero(request, "monto", Decimal(0), Decimal("1000000000000000"), "100")
    except ParametroInvalido as e:
        return _parametro_invalido(e)

    try:
        tasas, meta = indicadores.tasas_de_cambio()
    except FuenteNoDisponible as e:
        return _sin_fuente(e)
    return ok({
        "conversion": herramientas.convertir(monto, de, a, tasas),
        "valores_usados_en_pesos": tasas,
        "meta": meta,
    })


@solo_lectura
def interes_compuesto(request):
    try:
        capital = _numero(request, "capital", Decimal("0.01"), Decimal("1000000000000"), "100000")
        tasa = _numero(request, "tasa", Decimal(0), Decimal(100), "10")
        anios = _entero(request, "anios", 1, 80)
    except ParametroInvalido as e:
        return _parametro_invalido(e)
    return ok({"interes_compuesto": herramientas.interes_compuesto(capital, tasa, anios)})


@solo_lectura
def tasa_real(request):
    try:
        nominal = _numero(request, "nominal", Decimal(-99), Decimal(1000), "5")
        inflacion = _numero(request, "inflacion", Decimal(-99), Decimal(1000), "4")
    except ParametroInvalido as e:
        return _parametro_invalido(e)
    return ok({"tasa_real": herramientas.tasa_real(nominal, inflacion)})


# ---------------------------------------------------------------------------
# Cualquier otra ruta bajo /api/
# ---------------------------------------------------------------------------
@solo_lectura
def no_encontrado(request, ruta=""):
    # Si olvidaron la "/" final (/api/conceptos) pero la ruta con "/" existe, se redirige.
    if not request.path.endswith("/"):
        try:
            if resolve(request.path_info + "/").func is not no_encontrado:
                destino = request.path + "/"
                if request.META.get("QUERY_STRING"):
                    destino += "?" + request.META["QUERY_STRING"]
                return HttpResponsePermanentRedirect(destino)
        except Resolver404:
            pass
    return error(
        "no_encontrado", "Esa ruta no existe. Mira /api/ para ver todo lo que ofrece la API.", 404,
    )
