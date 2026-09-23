"""Tests de cotejo/facturas.py: factura contra N albaranes, portes aparte, precios pendientes completados,
precio de compra cambiado (aviso, no cambio), albarán no recibido y diferencias al céntimo."""

from decimal import Decimal

from idm.cotejo.facturas import cotejar_factura
from idm.dominio.estados import Semaforo, TipoAviso
from idm.dominio.modelos import Albaran, Articulo, Factura, LineaAlbaran, LineaFactura
from idm.dominio.reglas import ReglasCotejo


def _albaran(numero, lineas):
    return Albaran(proveedor="FICT_VEGA", numero_original="AC " + numero, numero=numero, lineas=lineas)


def _lin(codigo, cantidad, precio=None, dto="0", descripcion="X"):
    return LineaAlbaran(
        codigo_proveedor=codigo,
        codigo_idm=None,
        descripcion=descripcion,
        cantidad=Decimal(cantidad),
        precio_bruto=Decimal(precio) if precio is not None else None,
        descuento_pct=Decimal(dto),
    )


def _factura(lineas, albaranes, base=None):
    return Factura(proveedor="FICT_VEGA", numero="F1", albaranes=albaranes, lineas=lineas, base=base)


def _lf(albaran, codigo, cantidad, precio, dto="0", descripcion="X", portes=False):
    return LineaFactura(
        albaran=albaran,
        codigo_proveedor=codigo,
        descripcion=descripcion,
        cantidad=Decimal(cantidad),
        precio_bruto=Decimal(precio),
        descuento_pct=Decimal(dto),
        es_portes=portes,
    )


def test_factura_cuadra_con_dos_albaranes():
    a1 = _albaran("B26 1", [_lin("A", "100", "0.30", "45"), _lin("B", "5", "9.14", "45")])
    a2 = _albaran("B26 2", [_lin("B", "10", "9.40", "45")])
    f = _factura(
        [
            _lf("AC B26 1", "A", "100", "0.30", "45"),
            _lf("AC B26 1", "B", "5", "9.14", "45"),
            _lf("AC B26 2", "B", "10", "9.40", "45"),
        ],
        ["AC B26 1", "AC B26 2"],
        base=Decimal("93.34"),
    )
    r = cotejar_factura(f, [a1, a2])
    assert r.semaforo == Semaforo.VERDE
    assert r.albaranes_encontrados == ["B26 1", "B26 2"] and r.albaranes_no_encontrados == []
    assert r.total_lineas_factura == r.total_albaranes == Decimal("93.34")


def test_portes_aparte_y_pactados():
    a1 = _albaran("B26 1", [_lin("A", "1", "10")])
    f = _factura(
        [_lf("AC B26 1", "A", "1", "10"), _lf(None, None, "1", "12.50", descripcion="PORTES", portes=True)],
        ["AC B26 1"],
        base=Decimal("22.50"),
    )
    r = cotejar_factura(f, [a1])
    assert r.portes == Decimal("12.50") and r.total_lineas_factura == Decimal("10.00")
    assert [a.tipo for a in r.avisos] == [TipoAviso.PORTES_NO_PACTADOS]
    r = cotejar_factura(f, [a1], reglas=ReglasCotejo(portes_pactados={"FICT_VEGA": Decimal("12.5")}))
    assert r.semaforo == Semaforo.VERDE


def test_completa_precios_pendientes_y_avisa_precio_cambiado():
    a1 = _albaran("5526/2063", [_lin("MO01001", "1"), _lin("FL-2240", "2")])
    a1.proveedor = "FICT_RECAMBIOS"
    a1.lineas[0].codigo_idm = "MO01001"
    f = Factura(
        proveedor="FICT_RECAMBIOS",
        numero="F2",
        albaranes=["5526/2.063"],
        base=Decimal("70.00"),
        lineas=[_lf("5526/2.063", "MO01001", "1", "50"), _lf("5526/2.063", "FL-2240", "2", "10")],
    )
    articulos = {"MO01001": Articulo(codigo="MO01001", precio_compra=Decimal("45"))}
    r = cotejar_factura(f, [a1], articulos)
    assert [(p.codigo_proveedor, p.precio_bruto) for p in r.precios_completados] == [
        ("MO01001", Decimal("50")),
        ("FL-2240", Decimal("10")),
    ]
    assert r.total_albaranes == Decimal("70.00")
    assert [a.tipo for a in r.avisos] == [TipoAviso.PRECIO_CAMBIADO]
    assert r.precios_cambiados[0].precio_maestro == Decimal("45")
    assert articulos["MO01001"].precio_compra == Decimal("45")  # no se toca el maestro


def test_albaran_no_recibido_y_precio_distinto():
    a1 = _albaran("B26 1", [_lin("A", "100", "0.30", "45")])
    f = _factura([_lf("AC B26 1", "A", "100", "0.31", "45"), _lf("AC B26 9", "Z", "1", "5")], ["AC B26 1", "AC B26 9"])
    r = cotejar_factura(f, [a1])
    tipos = [a.tipo for a in r.avisos]
    assert TipoAviso.ALBARAN_NO_ENCONTRADO in tipos and TipoAviso.PRECIO_DISTINTO in tipos
    assert TipoAviso.IMPORTE_NO_CUADRA in tipos
    assert r.semaforo == Semaforo.AMBAR
