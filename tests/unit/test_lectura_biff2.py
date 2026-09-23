"""Tests del parser BIFF2 de escandallos contra fixtures/siddex/escandallo_ficticio.xls.
Comprueba cabecera, niveles, agregación por código (incluida minúscula) e incidencias.
No usa el planning."""

from decimal import Decimal

from idm.siddex.lectura import (
    agregar_compras,
    incidencias,
    leer_escandallo,
    nivel_desde_texto,
    total_materiales,
)


def test_nivel_desde_texto():
    assert nivel_desde_texto("1.0") == 1
    assert nivel_desde_texto(".2") == 2
    assert nivel_desde_texto("..3") == 3
    assert nivel_desde_texto("...4") == 4
    assert nivel_desde_texto("") is None
    assert nivel_desde_texto("Articulo") is None


def test_lee_cabecera_y_filas(fixtures):
    e = leer_escandallo(fixtures / "siddex" / "escandallo_ficticio.xls")
    assert e.codigo_maquina == "M91.000.001"
    assert e.nombre_maquina == "MAQUINA-FICTICIA-1"
    assert len(e.filas) == 18
    assert e.filas[0].tipo == "Producto"
    assert {f.tipo for f in e.filas} == {"Producto", "Conjunto", "MP", "Comercial", "Operacion", "Material"}


def test_agrega_compras_y_normaliza_minusculas(fixtures):
    compras = agregar_compras(leer_escandallo(fixtures / "siddex" / "escandallo_ficticio.xls"))
    assert "t30.000.100" not in compras
    assert compras["T30.000.100"].cantidad == Decimal("48")  # 40 + 8 en dos ramas
    assert compras["T30.000.100"].importe == Decimal("3.84")
    assert compras["I37.000.012"].cantidad == Decimal("4")  # ya explotada por máquina
    assert compras["P20.000.010"].tipo == "MP"
    assert "O00.000.001" not in compras  # operación no se compra
    assert "C10.000.001" not in compras  # conjunto no se compra
    assert total_materiales(compras) == Decimal("490.84")


def test_incidencias(fixtures):
    inc = incidencias(leer_escandallo(fixtures / "siddex" / "escandallo_ficticio.xls"))
    assert any("I34.000.900" in t for t in inc["sin_precio"])
    assert any("M37.000.050" in t for t in inc["conjunto_sin_despiece"])
    assert inc["codigo_minuscula"] == ["t30.000.100 (fila 15)"]
