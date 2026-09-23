"""Tests de cotejo/: interpretar (proveedor, número normalizado, códigos con método), buscar pedido, proponer pedido,
cotejar_documento de punta a punta sobre los PDF y exports ficticios."""

from decimal import Decimal

from idm.albaranes.lector import leer
from idm.cotejo.cotejar import buscar_pedido, cotejar_documento
from idm.cotejo.interpretar import interpretar_albaran, interpretar_factura
from idm.cotejo.proponer_pedido import proponer
from idm.dominio.estados import RelacionPedido, Semaforo, TipoAviso
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel

DOCS = "documentos"


def _entorno(fixtures):
    g = SiddexDesdeExcel(fixtures / "siddex")
    return g, TablaEquivalencias.desde(g.equivalencias())


def test_interpretar_albaran_resuelve_proveedor_numero_y_codigos(fixtures):
    g, tabla = _entorno(fixtures)
    r = interpretar_albaran(leer(fixtures / DOCS / "albaran_vega_bruto_descuento.pdf"), tabla, g.proveedores())
    a = r.albaran
    assert a.proveedor == "FICT_VEGA" and r.proveedor_metodo == "cif"
    assert a.numero_original == "AC B26 0100005283" and a.numero == "B26 0100005283"
    assert [li.codigo_idm for li in a.lineas] == ["134.000.842", "I33.000.786", "I37.000.012"]
    assert all(li.metodo_resolucion == "equivalencia" for li in a.lineas)
    assert [e.tipo for e in r.eventos][:2] == ["proveedor.resuelto", "articulo.resuelto"]
    assert r.avisos == []


def test_interpretar_albaran_sin_equivalencia_avisa(fixtures):
    g, tabla = _entorno(fixtures)
    r = interpretar_albaran(leer(fixtures / DOCS / "albaran_electro_puntos_prefijo.pdf"), tabla, g.proveedores())
    assert r.albaran.numero == "2026/1234"
    assert [li.codigo_idm for li in r.albaran.lineas] == [None, "I34.000.900", None, None]
    assert [a.tipo for a in r.avisos] == [TipoAviso.ARTICULO_NO_RESUELTO, TipoAviso.ARTICULO_NO_RESUELTO]
    assert r.albaran.lineas[3].es_portes and r.albaran.lineas[3].metodo_resolucion is None


def test_buscar_pedido_por_numero_y_por_lineas(fixtures):
    g, tabla = _entorno(fixtures)
    a = interpretar_albaran(leer(fixtures / DOCS / "albaran_vega_bruto_descuento.pdf"), tabla, g.proveedores()).albaran
    pedido, metodo = buscar_pedido(a, g)
    assert pedido.numero == "20261060" and metodo == "nuestro_pedido"
    a.nuestro_pedido = None
    pedido, metodo = buscar_pedido(a, g)
    assert pedido.numero == "20261060" and metodo == "pedido_abierto"
    a.nuestro_pedido = "999999"
    assert buscar_pedido(a, g)[1] == "pedido_abierto"  # el número no existe: se busca por líneas
    a.lineas = []
    assert buscar_pedido(a, g) == (None, "ninguno")


def test_cotejar_documento_con_pedido_cuadra(fixtures):
    g, tabla = _entorno(fixtures)
    r = cotejar_documento(leer(fixtures / DOCS / "albaran_vega_bruto_descuento.pdf"), g, tabla)
    assert r.cotejo.semaforo == Semaforo.VERDE and r.pedido_propuesto is None
    assert r.cotejo.total_albaran == Decimal("73.64")
    assert [e.tipo for e in r.eventos][-2:] == ["pedido.buscado", "precio.comparado"]


def test_cotejar_documento_sin_pedido_propone(fixtures):
    g, tabla = _entorno(fixtures)
    r = cotejar_documento(leer(fixtures / DOCS / "albaran_recambios_sin_precio.pdf"), g, tabla)
    assert r.pedido is None and r.metodo_pedido == "ninguno"
    assert r.cotejo.relacion == RelacionPedido.SIN_PEDIDO
    pp = r.pedido_propuesto
    assert pp.relacion == RelacionPedido.PEDIDO_PROPUESTO and pp.numero == "PP-5526/2063"
    assert [li.codigo_idm for li in pp.lineas] == ["MO01001", "FL-2240"]  # el no resuelto lleva la ref. del proveedor
    assert pp.lineas[0].descripcion == "SERVICIO TURISMO (CONTRATOS)"
    assert r.eventos[-1].tipo == "pedido.propuesto"


def test_proponer_excluye_portes_y_toma_precio_del_maestro(fixtures):
    g, tabla = _entorno(fixtures)
    a = interpretar_albaran(
        leer(fixtures / DOCS / "albaran_electro_puntos_prefijo.pdf"), tabla, g.proveedores()
    ).albaran
    for li in a.lineas:
        li.precio_bruto = None
    pp = proponer(a, g.articulos())
    assert len(pp.lineas) == 3
    assert pp.lineas[1].precio_bruto == Decimal("3.1") and pp.lineas[1].descuento_pct == Decimal("10")
    assert pp.lineas[0].precio_bruto == Decimal("0")


def test_interpretar_factura(fixtures):
    g, _ = _entorno(fixtures)
    r = interpretar_factura(leer(fixtures / DOCS / "factura_vega_agrupa.pdf"), g.proveedores())
    f = r.factura
    assert f.proveedor == "FICT_VEGA" and f.numero == "F26/000731"
    assert f.albaranes == ["AC B26 0100005283", "AC B26 0100005301"]
    assert len(f.lineas) == 5 and f.lineas[4].es_portes and f.base == Decimal("140.34")
