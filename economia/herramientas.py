"""
Calculadoras para entender los conceptos con números propios.

Son funciones puras (no llaman a internet ni a Django), por eso son fáciles de
probar. Usan Decimal en vez de float para que el dinero no tenga errores de
redondeo del tipo 0.1 + 0.2 = 0.30000000000000004.
"""
from decimal import ROUND_HALF_UP, Decimal

from .formato import formato_cl

CIEN = Decimal(100)
DOS_DECIMALES = Decimal("0.01")


def _r(x):
    """Redondea a 2 decimales y entrega un float listo para JSON."""
    return float(x.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP))


def _pesos(x):
    return "$" + formato_cl(float(x.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)))


def interes_compuesto(capital, tasa_anual_pct, anios):
    """
    Concepto: Interés compuesto. El interés de cada año se calcula sobre el capital
    MÁS los intereses ya ganados. Se compara con el interés simple (solo sobre el capital).

    Ejemplo del PDF: $100.000 al 10% anual -> $110.000 el año 1 y $121.000 el año 2.
    """
    tasa = tasa_anual_pct / CIEN
    saldo = capital
    detalle = []
    for anio in range(1, anios + 1):
        interes = saldo * tasa
        saldo += interes
        detalle.append({"anio": anio, "interes_ganado": _r(interes), "saldo": _r(saldo)})

    con_simple = capital * (1 + tasa * anios)
    diferencia = saldo - con_simple
    return {
        "capital_inicial": _r(capital),
        "tasa_anual_pct": float(tasa_anual_pct),
        "anios": anios,
        "saldo_final": _r(saldo),
        "ganancia_total": _r(saldo - capital),
        "saldo_con_interes_simple": _r(con_simple),
        "ventaja_del_interes_compuesto": _r(diferencia),
        "detalle_por_anio": detalle,
        "lectura_simple": (
            f"Si dejas {_pesos(capital)} durante {anios} {'año' if anios == 1 else 'años'} "
            f"al {formato_cl(float(tasa_anual_pct))} % anual, terminas con {_pesos(saldo)}. "
            f"Con interés simple serían {_pesos(con_simple)}: "
            f"la diferencia ({_pesos(diferencia)}) es el efecto del interés compuesto."
        ),
    }


def tasa_real(nominal_pct, inflacion_pct):
    """
    Concepto: Tasa nominal y real. La nominal es la que te informan; la real es la que
    de verdad hace crecer tu poder de compra, porque descuenta la inflación.

    Exacta:       ((1 + nominal) / (1 + inflación)) - 1
    Aproximada:   nominal - inflación        (la del PDF: 5% y 4% -> "ronda 1%")
    """
    exacta = ((1 + nominal_pct / CIEN) / (1 + inflacion_pct / CIEN) - 1) * CIEN
    aproximada = nominal_pct - inflacion_pct
    if exacta > 0:
        lectura = "Tu poder de compra crece: ganas más de lo que suben los precios."
    elif exacta < 0:
        lectura = "Pierdes poder de compra: los precios suben más de lo que crece tu dinero."
    else:
        lectura = "Tu poder de compra se mantiene igual: ganas justo lo que suben los precios."
    return {
        "tasa_nominal_pct": float(nominal_pct),
        "inflacion_pct": float(inflacion_pct),
        "tasa_real_exacta_pct": float(exacta.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "tasa_real_aproximada_pct": float(aproximada),
        "lectura_simple": (
            f"Ganas {formato_cl(float(nominal_pct))} % y la inflación es {formato_cl(float(inflacion_pct))} %: "
            f"tu ganancia real ronda {formato_cl(float(exacta), 2)} %. {lectura}"
        ),
    }


def convertir(monto, de, a, tasas):
    """
    Concepto: Tipo de cambio y UF. Convierte entre CLP, UF, USD y EUR.
    `tasas` = {'clp': {'pesos': 1}, 'uf': {'pesos': 41215.77}, 'usd': {...}, 'eur': {...}}
    (cuánto vale 1 unidad de cada moneda, en pesos).
    """
    pesos_de_origen = monto * Decimal(str(tasas[de]["pesos"]))
    resultado = pesos_de_origen / Decimal(str(tasas[a]["pesos"]))
    return {
        "de": de,
        "a": a,
        "monto": float(monto),
        "resultado": float(resultado.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "lectura_simple": (
            f"{formato_cl(float(monto))} {de.upper()} = "
            f"{formato_cl(float(resultado.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)))} {a.upper()}"
        ),
    }
