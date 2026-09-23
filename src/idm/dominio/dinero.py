"""Dinero con Decimal: conversión desde texto y redondeo a dos decimales en un solo sitio.
Todo importe del proyecto pasa por redondear() antes de compararse o guardarse.
No hace cálculos de negocio (descuentos, IVA): eso está en modelos y cotejar."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DOS_DECIMALES = Decimal("0.01")
CERO = Decimal("0")
CIEN = Decimal("100")


def redondear(valor: Decimal | int | str) -> Decimal:
    """Único punto de redondeo del proyecto: dos decimales, mitad hacia arriba (como Siddex)."""
    return Decimal(valor).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def a_decimal(texto: str | int | float | Decimal | None) -> Decimal | None:
    """Convierte '1.234,56', '1234.56', '9,14 €' o '-3' a Decimal. Devuelve None si no hay número."""
    if texto is None:
        return None
    if isinstance(texto, Decimal):
        return texto
    if isinstance(texto, int):
        return Decimal(texto)
    if isinstance(texto, float):
        # Solo para valores que vienen de librerías (xlrd, openpyxl); nunca de cálculos propios.
        return Decimal(repr(texto))
    limpio = texto.strip().replace("€", "").replace(" ", "")
    if not limpio:
        return None
    if "," in limpio and "." in limpio:
        # Formato español: el punto es millar y la coma decimal.
        limpio = limpio.replace(".", "").replace(",", ".")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def importe_linea(cantidad: Decimal, precio_bruto: Decimal, descuento_pct: Decimal = CERO) -> Decimal:
    """cantidad × bruto × (1 − dto/100), redondeado. Ej.: 5 × 9,14 con 45 % = 25,14."""
    factor = (CIEN - descuento_pct) / CIEN
    return redondear(cantidad * precio_bruto * factor)


def formatear(valor: Decimal | None) -> str:
    """Texto en formato español con dos decimales: 1234.5 → '1.234,50'. None → ''."""
    if valor is None:
        return ""
    entero, _, dec = f"{redondear(valor):,.2f}".partition(".")
    return f"{entero.replace(',', '.')},{dec}"
