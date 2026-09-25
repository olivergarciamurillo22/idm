"""Tests de SiddexDesdeExcel sobre los exports ficticios: proveedores, artículos, equivalencias, pedidos, stock.
Comprueba la lectura por cabecera y el mapeo de código Siddex → clave de proveedor.
No usa la base de datos de Siddex."""

from decimal import Decimal

from idm.equivalencias.proveedores import identificar
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel


def test_proveedores(fixtures):
    provs = {p.clave: p for p in SiddexDesdeExcel(fixtures / "siddex").proveedores()}
    assert provs["FICT_VEGA"].codigo_siddex == "9001"
    assert provs["FICT_VEGA"].cif == "B00000001"
    assert provs["FICT_ELECTRO"].email == "ventas@electro.ficticio"


def test_articulos(fixtures):
    arts = SiddexDesdeExcel(fixtures / "siddex").articulos()
    assert arts["T30.000.100"].multiplo_compra == Decimal("100")
    assert arts["T30.000.100"].proveedor_habitual == "FICT_ELECTRO"
    assert arts["SV09001"].precio_compra is None


def test_equivalencias_y_resolucion(fixtures):
    tabla = TablaEquivalencias.desde(SiddexDesdeExcel(fixtures / "siddex").equivalencias())
    assert tabla.resolver("FICT_VEGA", "FXT9550942").codigo_idm == "900.000.842"
    assert tabla.resolver("FICT_VEGA", "fxt9 550942").metodo == "equivalencia_normalizada"
    assert tabla.resolver("FICT_VEGA", "NOEXISTE").metodo == "no_resuelto"
    assert tabla.resolver("FICT_ELECTRO", "FXT9550942").metodo == "no_resuelto"  # otro proveedor


def test_aprender(fixtures, tmp_path):
    tabla = TablaEquivalencias.desde([])
    fichero = tmp_path / "aprendidas.csv"
    tabla.aprender("FICT_VEGA", "nuevo-1", "I99.000.001", fichero)
    assert TablaEquivalencias.desde([], fichero).resolver("FICT_VEGA", "NUEVO-1").metodo == "aprendida"


def test_pedidos_abiertos_y_pendiente(fixtures):
    g = SiddexDesdeExcel(fixtures / "siddex")
    abiertos = {p.numero for p in g.pedidos_abiertos()}
    assert abiertos == {"20269060", "20269061"}  # el 20269055 está recibido entero
    assert [p.numero for p in g.pedidos_abiertos("FICT_VEGA")] == ["20269060"]
    p = g.pedido("20269060")
    assert p.proveedor == "FICT_VEGA" and len(p.lineas) == 3
    assert p.lineas[0].codigo_proveedor == "FXT9550942"
    assert g.pendiente_recibir()["T30.000.100"] == Decimal("100")
    assert g.stock()["T30.000.100"] == Decimal("500")


def test_identificar_proveedor():
    assert identificar(cif="b-00000001") == ("FICT_VEGA", "cif")
    assert identificar(nombre="Recambios La Cepa, S.L.") == ("LA_CEPA", "nombre")
    assert identificar(nombre="Hierros Vélez") == ("HIERROS_VELEZ", "nombre")
    assert identificar(nombre="Nadie") == (None, "no_resuelto")
