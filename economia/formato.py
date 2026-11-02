"""Formato de números al estilo chileno: 41.215,77 (punto para miles, coma para decimales)."""


def formato_cl(numero, decimales=2):
    """
    formato_cl(41215.77)  -> '41.215,77'
    formato_cl(72151)     -> '72.151'      (sin ceros inútiles)
    formato_cl(4.5)       -> '4,5'
    formato_cl(-0.2)      -> '-0,2'
    """
    texto = f"{numero:,.{decimales}f}"  # '41,215.77' (formato inglés)
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")  # '41.215,77'
    if "," in texto:
        texto = texto.rstrip("0").rstrip(",")
    return texto
