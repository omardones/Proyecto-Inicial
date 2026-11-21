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


def credito(monto, tasa_anual_pct, meses):
    """
    Conceptos: Deuda, Interés, CAE y Crédito hipotecario.
    Cuota fija mensual (sistema francés, el más usado en Chile): todas las cuotas son iguales;
    al principio casi todo es interés y al final casi todo es capital.

    La tasa anual se pasa a mensual dividiendo por 12 (como la informan los bancos).
    No incluye seguros ni comisiones: por eso el CAE real de un crédito es más alto.
    """
    i = tasa_anual_pct / CIEN / 12
    if i == 0:
        cuota = monto / meses
    else:
        cuota = monto * i / (1 - (1 + i) ** -meses)

    saldo = monto
    por_anio = []
    interes_anio = capital_anio = Decimal(0)
    for mes in range(1, meses + 1):
        interes = saldo * i
        amortizacion = cuota - interes
        saldo -= amortizacion
        interes_anio += interes
        capital_anio += amortizacion
        if mes % 12 == 0 or mes == meses:
            por_anio.append({
                "anio": (mes + 11) // 12,
                "intereses_pagados": _r(interes_anio),
                "capital_pagado": _r(capital_anio),
                "saldo_pendiente": _r(max(saldo, Decimal(0))),
            })
            interes_anio = capital_anio = Decimal(0)

    total = cuota * meses
    intereses = total - monto
    tasa_efectiva = ((1 + i) ** 12 - 1) * CIEN
    return {
        "monto": _r(monto),
        "tasa_anual_pct": float(tasa_anual_pct),
        "meses": meses,
        "cuota_mensual": _r(cuota),
        "total_pagado": _r(total),
        "total_intereses": _r(intereses),
        "intereses_sobre_monto_pct": _r(intereses / monto * CIEN),
        "tasa_efectiva_anual_pct": _r(tasa_efectiva),
        "detalle_por_anio": por_anio,
        "advertencia": "No incluye seguros, comisiones ni impuestos: el CAE que informa el banco será mayor.",
        "lectura_simple": (
            f"Pides {formato_cl(_r(monto))} a {meses} {'mes' if meses == 1 else 'meses'} al "
            f"{formato_cl(float(tasa_anual_pct))} % anual: pagas {meses} cuotas de "
            f"{formato_cl(_r(cuota))}. En total devuelves {formato_cl(_r(total))}, "
            f"o sea {formato_cl(_r(intereses))} en intereses."
        ),
    }


# Regla 50/30/20: una guía común de educación financiera (no es una norma oficial).
REGLA_PRESUPUESTO = (
    ("necesidades", "Necesidades", 50, "Arriendo, comida, transporte, cuentas básicas y deudas mínimas."),
    ("deseos", "Gustos", 30, "Salidas, ropa que no es urgente, suscripciones, viajes."),
    ("ahorro", "Ahorro e inversión", 20, "Fondo de emergencia, metas y pagar deudas antes de tiempo."),
)


def presupuesto(ingreso):
    """
    Conceptos: Presupuesto, Ahorro y Capacidad de ahorro.
    Reparte un ingreso mensual con la regla 50/30/20.
    """
    partes = []
    for clave, nombre, pct, ejemplos in REGLA_PRESUPUESTO:
        partes.append({
            "clave": clave,
            "nombre": nombre,
            "porcentaje": pct,
            "monto": _r(ingreso * pct / CIEN),
            "ejemplos": ejemplos,
        })
    ahorro = partes[2]["monto"]
    return {
        "ingreso_mensual": _r(ingreso),
        "partes": partes,
        "ahorro_en_un_anio": _r(Decimal(str(ahorro)) * 12),
        "lectura_simple": (
            f"Con {_pesos(ingreso)} al mes: {_pesos(Decimal(str(partes[0]['monto'])))} para necesidades, "
            f"{_pesos(Decimal(str(partes[1]['monto'])))} para gustos y {_pesos(Decimal(str(ahorro)))} para ahorrar. "
            f"Ahorrando eso cada mes juntas {_pesos(Decimal(str(ahorro)) * 12)} en un año."
        ),
        "nota": "La regla 50/30/20 es una guía de referencia, no una norma: ajústala a tu realidad.",
    }
