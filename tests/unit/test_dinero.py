"""Tests de dominio/dinero.py: conversión de texto español, redondeo y importe de línea.
Cubre el ejemplo real del AS-IS: 5 × 9,14 con 45 % = 25,14.
No prueba nada de cotejo."""

from decimal import Decimal

from idm.dominio.dinero import a_decimal, formatear, importe_linea, redondear


def test_redondear_mitad_hacia_arriba():
    assert redondear(Decimal("25.135")) == Decimal("25.14")
    assert redondear(Decimal("0.005")) == Decimal("0.01")
    assert redondear("2.675") == Decimal("2.68")  # con float sería 2.67


def test_a_decimal_formatos():
    assert a_decimal("9,14") == Decimal("9.14")
    assert a_decimal("1.234,56 €") == Decimal("1234.56")
    assert a_decimal("1234.56") == Decimal("1234.56")
    assert a_decimal("") is None
    assert a_decimal("abc") is None
    assert a_decimal(0.3) == Decimal("0.3")


def test_importe_linea_ejemplo_as_is():
    assert importe_linea(Decimal("5"), Decimal("9.14"), Decimal("45")) == Decimal("25.14")
    assert importe_linea(Decimal("5"), Decimal("6.40")) == Decimal("32.00")


def test_formatear():
    assert formatear(Decimal("1234.5")) == "1.234,50"
    assert formatear(None) == ""
