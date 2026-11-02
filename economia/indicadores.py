"""
Indicadores económicos EN VIVO: UF, dólar, TPM, desempleo, etc.

Los valores vienen de una API pública gratuita, https://mindicador.cl/api, que
no necesita clave. Este módulo se encarga de tres cosas:

  1. CATÁLOGO: para cada indicador, una explicación en lenguaje simple y los
     conceptos del PDF con los que se relaciona.
  2. CLIENTE: llama a la API externa con tiempo límite y valida lo que responde.
  3. CACHÉ: guarda la respuesta unos minutos (por defecto 10) para no llamar a
     la API en cada visita. Si la API externa se cae, se sigue mostrando la
     última respuesta guardada, marcada como "obsoleta", en vez de fallar.

Cada indicador se entrega con la FECHA DEL DATO. Los indicadores mensuales
(IPC, Imacec, desempleo) se publican con retraso y algunos pueden estar
atrasados; "dato_atrasado" avisa cuando eso ocurre.
"""
import http.client
import json
import functools
import logging
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.cache import cache

from . import conceptos
from .formato import formato_cl

log = logging.getLogger("economia")


class FuenteNoDisponible(Exception):
    """La API externa no respondió, respondió con error o entregó algo inesperado."""


# ---------------------------------------------------------------------------
# Ajustes (se pueden cambiar en settings.py; ver README de la app)
# ---------------------------------------------------------------------------
def url_fuente():
    return getattr(settings, "ECONOMIA_FUENTE_URL", "https://mindicador.cl/api").rstrip("/")


def _segundos_de_cache():
    return getattr(settings, "ECONOMIA_CACHE_SEGUNDOS", 600)


def _timeout():
    return getattr(settings, "ECONOMIA_TIMEOUT_SEGUNDOS", 8)


# ---------------------------------------------------------------------------
# 1) Catálogo de indicadores
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Indicador:
    codigo: str  # el mismo código que usa mindicador.cl
    nombre: str
    unidad: str  # "pesos" | "dolares" | "porcentaje"
    frecuencia: str  # "diaria" | "mensual"  (cada cuánto cambia el dato)
    que_es: str
    por_que_importa: str
    lectura: str  # frase con {valor}; se arma con el dato real
    conceptos: tuple  # slugs de los conceptos del PDF con los que se relaciona


CATALOGO = (
    Indicador(
        "uf", "Unidad de Fomento (UF)", "pesos", "diaria",
        "Una unidad que se reajusta con la inflación y cuyo valor en pesos calcula el Banco Central "
        "cada día. No es dinero: sirve para expresar precios y deudas, como créditos hipotecarios y arriendos.",
        "Si tienes un crédito en UF, su monto en pesos aumenta cuando hay inflación.",
        "1 UF vale ${valor}",
        ("uf", "credito-hipotecario"),
    ),
    Indicador(
        "dolar", "Dólar observado", "pesos", "diaria",
        "Cuántos pesos chilenos cuesta 1 dólar estadounidense. Es el tipo de cambio de referencia en Chile.",
        "Si el dólar sube, lo que se compra en dólares (por ejemplo, productos importados) se encarece.",
        "1 dólar vale ${valor}",
        ("tipo-de-cambio",),
    ),
    Indicador(
        "euro", "Euro", "pesos", "diaria",
        "Cuántos pesos chilenos cuesta 1 euro.",
        "Funciona igual que el dólar: si el euro sube, lo que se compra en euros se encarece.",
        "1 euro vale ${valor}",
        ("tipo-de-cambio",),
    ),
    Indicador(
        "tpm", "Tasa de Política Monetaria (TPM)", "porcentaje", "diaria",
        "La tasa de interés de referencia que fija el Banco Central de Chile para cumplir su meta de inflación.",
        "Cuando el Banco Central sube la TPM, los créditos se encarecen y el consumo se enfría; "
        "así se frena la inflación.",
        "La TPM está en {valor} %",
        ("politica-monetaria-y-tpm", "banco-central", "interes"),
    ),
    Indicador(
        "ipc", "Inflación mensual (IPC)", "porcentaje", "mensual",
        "El IPC (Índice de Precios al Consumidor) mide cuánto cambian los precios de una canasta de bienes "
        "y servicios. Este valor es la variación de un mes.",
        "Si es positivo, los precios subieron ese mes y tu plata compra menos; si es negativo, bajaron.",
        "Los precios variaron {valor} % en el mes",
        ("inflacion", "tasa-nominal-y-real"),
    ),
    Indicador(
        "imacec", "Imacec (actividad económica)", "porcentaje", "mensual",
        "Indicador mensual de cuánto está produciendo la economía del país; sirve como adelanto del PIB. "
        "Se informa como variación respecto del mismo mes del año anterior.",
        "Si es positivo, la economía produjo más que hace un año; si es negativo, produjo menos.",
        "La actividad económica varió {valor} % (Imacec)",
        ("crecimiento-economico", "pib", "recesion"),
    ),
    Indicador(
        "tasa_desempleo", "Tasa de desocupación", "porcentaje", "mensual",
        "Porcentaje de personas que quieren trabajar y buscan empleo, pero no lo encuentran, "
        "respecto de todas las que forman parte de la fuerza de trabajo.",
        "Con más desempleo, menos personas tienen ingresos; por eso es una señal clave de cómo va la economía.",
        "La tasa de desocupación es {valor} %",
        ("desempleo", "recesion"),
    ),
    Indicador(
        "utm", "Unidad Tributaria Mensual (UTM)", "pesos", "mensual",
        "Una medida en pesos que se actualiza cada mes y se usa para expresar impuestos, multas y otros montos.",
        "Al fijar montos en UTM en vez de en pesos, no se desvalorizan con la inflación.",
        "1 UTM vale ${valor}",
        ("impuestos",),
    ),
    Indicador(
        "bitcoin", "Bitcoin", "dolares", "diaria",
        "El precio de 1 bitcoin, una criptomoneda, en dólares.",
        "Su precio es muy volátil: puede subir o bajar mucho en poco tiempo. La CMF advierte sobre sus riesgos.",
        "1 bitcoin vale US${valor}",
        ("criptomonedas",),
    ),
    Indicador(
        "libra_cobre", "Libra de cobre", "dolares", "diaria",
        "El precio de una libra de cobre en dólares. Chile es uno de los grandes productores de cobre "
        "del mundo y lo vende al exterior.",
        "Si el precio del cobre cambia, cambian los dólares que recibe el país, lo que puede influir en el valor del dólar.",
        "1 libra de cobre vale US${valor}",
        ("tipo-de-cambio",),
    ),
)

POR_CODIGO = {i.codigo: i for i in CATALOGO}

# Moneda de la herramienta "convertir" -> indicador que da su valor en pesos
MONEDAS = {"clp": None, "uf": "uf", "usd": "dolar", "eur": "euro"}

# Pasados estos días desde la fecha del dato, se marca como "atrasado".
# (Los datos mensuales se publican con semanas de retraso, por eso el margen es mayor.)
_DIAS_MAX = {"diaria": 10, "mensual": 110}


def indicadores_de_concepto(slug):
    return [i for i in CATALOGO if slug in i.conceptos]


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------
def _zona():
    try:
        return ZoneInfo("America/Santiago")
    except ZoneInfoNotFoundError:  # equipo sin base de zonas horarias
        return timezone(timedelta(hours=-3))


def ahora_chile():
    return datetime.now(_zona())


def hoy_chile():
    return ahora_chile().date()


def _fecha_del_dato(iso):
    """'2026-10-25T03:00:00.000Z' -> date(2026, 10, 25) (hora de Chile)."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_zona()).date()


# ---------------------------------------------------------------------------
# 2) Cliente de la API externa (+ 3) caché)
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _contexto_ssl():
    """
    Contexto HTTPS con certificados de confianza. La verificación SIEMPRE queda activa.

    Por qué existe: el Python instalado desde python.org en macOS no trae certificados
    raíz hasta que se ejecuta "Install Certificates.command", y entonces toda petición
    HTTPS falla con CERTIFICATE_VERIFY_FAILED. Orden de intentos:
      1) certifi, si está instalado (pip install certifi).
      2) Certificados del sistema que Python ya conozca.
      3) En macOS, además, los certificados raíz del propio sistema (comando "security").
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    contexto = ssl.create_default_context()
    if sys.platform == "darwin":
        try:
            pem = subprocess.run(
                ["/usr/bin/security", "find-certificate", "-a", "-p",
                 "/System/Library/Keychains/SystemRootCertificates.keychain"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout
            if pem.strip():
                contexto.load_verify_locations(cadata=pem)
        except (OSError, subprocess.SubprocessError, ssl.SSLError):
            log.warning("No se pudieron cargar los certificados raíz de macOS.")
    return contexto


def _descargar(url):
    peticion = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "economia-api/1.0 (proyecto educativo)"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=_timeout(), context=_contexto_ssl()) as respuesta:
            return json.load(respuesta)
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
        # URLError/HTTPError (sin internet, 404, 500), TimeoutError (OSError),
        # JSON mal formado (ValueError)
        motivo = getattr(e, "reason", e)
        pista = ""
        if isinstance(motivo, ssl.SSLCertVerificationError):
            pista = " Pista: en tu terminal ejecuta 'pip install certifi' y reinicia el servidor."
        raise FuenteNoDisponible(f"No se pudo leer {url}: {e}.{pista}" if pista else f"No se pudo leer {url}: {e}") from e


def _es_numero(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _punto_valido(p):
    return isinstance(p, dict) and _es_numero(p.get("valor")) and isinstance(p.get("fecha"), str)


def _validar_resumen(datos):
    if not isinstance(datos, dict) or not any(_punto_valido(datos.get(i.codigo)) for i in CATALOGO):
        raise FuenteNoDisponible("La fuente respondió algo distinto a lo esperado (resumen de indicadores).")


def _validar_serie(datos):
    serie = datos.get("serie") if isinstance(datos, dict) else None
    if not isinstance(serie, list) or not serie or not all(_punto_valido(p) for p in serie):
        raise FuenteNoDisponible("La fuente respondió algo distinto a lo esperado (serie de un indicador).")


def _consultar(ruta, validar):
    """
    Devuelve (datos, info_de_cache). Orden de preferencia:
      1. caché reciente           -> no se llama a la API
      2. API externa              -> se guarda en caché
      3. caché antigua (si la API falló) -> se marca como obsoleta
      4. nada                     -> FuenteNoDisponible
    """
    url = f"{url_fuente()}{ruta}"
    clave = f"economia:{url}"
    ahora = time.time()
    guardado = cache.get(clave)

    if guardado and ahora - guardado["t"] < _segundos_de_cache():
        return guardado["datos"], {
            "usada": True, "antiguedad_segundos": int(ahora - guardado["t"]), "obsoleta": False,
        }

    try:
        datos = _descargar(url)
        validar(datos)
    except FuenteNoDisponible as e:
        log.warning("Fuente de indicadores no disponible: %s", e)
        if guardado:
            return guardado["datos"], {
                "usada": True, "antiguedad_segundos": int(ahora - guardado["t"]), "obsoleta": True,
            }
        raise

    cache.set(clave, {"datos": datos, "t": ahora}, timeout=24 * 3600)
    return datos, {"usada": False, "antiguedad_segundos": 0, "obsoleta": False}


def _meta(info_cache):
    obtenidos = ahora_chile() - timedelta(seconds=info_cache["antiguedad_segundos"])
    meta = {
        "fuente": {"nombre": "mindicador.cl", "url": url_fuente()},
        "datos_obtenidos_en": obtenidos.isoformat(timespec="seconds"),
        "cache": info_cache,
    }
    if info_cache["obsoleta"]:
        meta["aviso"] = (
            "No se pudo contactar la fuente en este momento; "
            "se muestran los datos de una consulta anterior."
        )
    return meta


# ---------------------------------------------------------------------------
# Armado de la respuesta de cada indicador
# ---------------------------------------------------------------------------
def _con_unidad(ind, valor):
    n = formato_cl(valor)
    return {"pesos": f"${n}", "dolares": f"US${n}", "porcentaje": f"{n} %"}[ind.unidad]


def _armar(ind, punto):
    fecha = _fecha_del_dato(punto["fecha"])
    dias = (hoy_chile() - fecha).days
    return {
        "codigo": ind.codigo,
        "nombre": ind.nombre,
        "unidad": ind.unidad,
        "frecuencia": ind.frecuencia,
        "valor": punto["valor"],
        "valor_formateado": _con_unidad(ind, punto["valor"]),
        "lectura_simple": ind.lectura.format(valor=formato_cl(punto["valor"])),
        "fecha_dato": fecha.isoformat(),
        "dias_desde_el_dato": dias,
        "dato_atrasado": dias > _DIAS_MAX[ind.frecuencia],
        "que_es": ind.que_es,
        "por_que_importa": ind.por_que_importa,
        "conceptos_relacionados": [
            {"slug": s, "nombre": conceptos.obtener(s)["nombre"]} for s in ind.conceptos
        ],
    }


# ---------------------------------------------------------------------------
# API pública del módulo (la usan las vistas)
# ---------------------------------------------------------------------------
def listar_actuales():
    """Último valor de todos los indicadores del catálogo."""
    datos, info = _consultar("", _validar_resumen)
    indicadores, faltantes = [], []
    for ind in CATALOGO:
        punto = datos.get(ind.codigo)
        if _punto_valido(punto):
            indicadores.append(_armar(ind, punto))
        else:
            faltantes.append(ind.codigo)
    return {"indicadores": indicadores, "no_entregados_por_la_fuente": faltantes, "meta": _meta(info)}


def detalle(codigo, ultimos=30):
    """Último valor de un indicador + sus valores anteriores y la variación."""
    ind = POR_CODIGO[codigo]
    datos, info = _consultar(f"/{codigo}", _validar_serie)

    # más reciente primero; se descartan fechas futuras (la UF se publica por adelantado)
    puntos = sorted(datos["serie"], key=lambda p: p["fecha"], reverse=True)
    hoy = hoy_chile()
    puntos = [p for p in puntos if _fecha_del_dato(p["fecha"]) <= hoy] or puntos

    resultado = _armar(ind, puntos[0])
    if len(puntos) > 1:
        actual, previo = puntos[0]["valor"], puntos[1]["valor"]
        resultado["variacion"] = {
            "respecto_de": _fecha_del_dato(puntos[1]["fecha"]).isoformat(),
            "absoluta": round(actual - previo, 4),
            # un "% de variación" no tiene sentido para indicadores que ya son un %
            "porcentual": (
                round((actual / previo - 1) * 100, 4) if ind.unidad != "porcentaje" and previo else None
            ),
        }
    else:
        resultado["variacion"] = None
    resultado["serie"] = [
        {"fecha": _fecha_del_dato(p["fecha"]).isoformat(), "valor": p["valor"]} for p in puntos[:ultimos]
    ]
    return {"indicador": resultado, "meta": _meta(info)}


def tasas_de_cambio():
    """Valor en pesos de CLP, UF, USD y EUR (para el conversor). Devuelve (tasas, meta)."""
    datos, info = _consultar("", _validar_resumen)
    tasas = {"clp": {"pesos": 1, "fecha_dato": None, "indicador": None}}
    for moneda, codigo in MONEDAS.items():
        if codigo is None:
            continue
        punto = datos.get(codigo)
        if not _punto_valido(punto):
            raise FuenteNoDisponible(f"La fuente no entregó el valor de '{codigo}'.")
        tasas[moneda] = {
            "pesos": punto["valor"],
            "fecha_dato": _fecha_del_dato(punto["fecha"]).isoformat(),
            "indicador": codigo,
        }
    return tasas, _meta(info)


def probar_fuente():
    """
    Para /api/salud/?probar_fuente=1. Llama a la fuente de verdad, SIN usar la caché
    (si no, una caché reciente taparía una caída). Devuelve (ok, detalle).
    """
    try:
        _validar_resumen(_descargar(url_fuente()))
        return True, "La fuente respondió correctamente."
    except FuenteNoDisponible as e:
        return False, str(e)
