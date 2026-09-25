"""Escenarios reales que el piloto tendrá que soportar (BLOQUE 7), sobre el dominio puro y las facturas:
pedido con varios albaranes, factura de varios albaranes, entrega parcial, factura parcial, referencias alternativas por
proveedor, cantidades y precios distintos, redondeos, descuentos, portes, líneas de más y de menos, factura y albarán
sin pedido. Lo que depende de una regla de IDM que no tenemos está xfail y apuntado en docs/PENDIENTE-IDM.md."""

from decimal import Decimal

import pytest

from idm.cotejo.facturas import cotejar_factura
from idm.dominio.cotejar import cotejar
from idm.dominio.dinero import importe_linea
from idm.dominio.estados import EstadoEntrega, RelacionPedido, Semaforo, TipoAviso
from idm.dominio.modelos import Albaran, Equivalencia, Factura, LineaAlbaran, LineaFactura, LineaPedido, Pedido
from idm.equivalencias.tabla import TablaEquivalencias

D = Decimal


def _pedido(lineas, numero="P1", proveedor="PROV"):
    return Pedido(numero=numero, proveedor=proveedor, lineas=lineas)


def _lp(codigo, cantidad, precio, dto="0", ref=None, recibida="0"):
    return LineaPedido(
        codigo_idm=codigo,
        codigo_proveedor=ref,
        cantidad=D(cantidad),
        precio_bruto=D(precio),
        descuento_pct=D(dto),
        cantidad_recibida=D(recibida),
    )


def _albaran(lineas, numero="A1", proveedor="PROV", pedido="P1"):
    return Albaran(proveedor=proveedor, numero_original=numero, numero=numero, nuestro_pedido=pedido, lineas=lineas)


def _la(codigo, cantidad, precio=None, dto="0", ref=None, desc="X"):
    return LineaAlbaran(
        codigo_idm=codigo,
        codigo_proveedor=ref,
        descripcion=desc,
        cantidad=D(cantidad),
        precio_bruto=D(precio) if precio is not None else None,
        descuento_pct=D(dto),
    )


def tipos(cotejo):
    return {a.tipo for a in cotejo.todos_los_avisos}


# ---------------------------------------------------------------- pedido con varios albaranes


def test_pedido_con_varios_albaranes_con_siddex_al_dia():
    """Primer albarán: 2 de 5 → PARCIAL. Segundo albarán con Siddex ya actualizado (recibida=2): 3 → COMPLETA."""
    pedido = _pedido([_lp("A", "5", "9.14", "45")])
    c1 = cotejar(_albaran([_la("A", "2", "9.14", "45")]), pedido)
    assert c1.semaforo == Semaforo.VERDE and c1.entrega == EstadoEntrega.PARCIAL
    assert c1.pendientes_pedido[0].cantidad_pendiente == D("3")
    pedido_actualizado = _pedido([_lp("A", "5", "9.14", "45", recibida="2")])
    c2 = cotejar(_albaran([_la("A", "3", "9.14", "45")], numero="A2"), pedido_actualizado)
    assert c2.semaforo == Semaforo.VERDE and c2.entrega == EstadoEntrega.COMPLETA and c2.pendientes_pedido == []


@pytest.mark.xfail(
    strict=True, reason="P01: fuente de 'cantidad recibida' cuando Siddex no está al día (PENDIENTE-IDM)"
)
def test_pedido_con_varios_albaranes_sin_refrescar_siddex():
    pedido = _pedido([_lp("A", "5", "9.14", "45", recibida="0")])  # Siddex aún no refleja el primer albarán de 2
    c2 = cotejar(_albaran([_la("A", "3", "9.14", "45")], numero="A2"), pedido)
    assert c2.entrega == EstadoEntrega.COMPLETA


def test_tercer_albaran_que_excede_el_pedido():
    pedido = _pedido([_lp("A", "5", "1", recibida="5")])
    c = cotejar(_albaran([_la("A", "1", "1")]), pedido)
    assert c.entrega == EstadoEntrega.EXCESO and TipoAviso.EXCESO_CANTIDAD in tipos(c)


# ---------------------------------------------------------------- referencias alternativas por proveedor


def test_mismo_articulo_idm_con_referencias_distintas_por_proveedor():
    tabla = TablaEquivalencias.desde(
        [
            Equivalencia(proveedor="PROV_A", codigo_proveedor="RUEDA-400-A", codigo_idm="R40.000.001"),
            Equivalencia(proveedor="PROV_B", codigo_proveedor="W400/8", codigo_idm="R40.000.001"),
        ]
    )
    assert tabla.resolver("PROV_A", "RUEDA-400-A").codigo_idm == "R40.000.001"
    assert tabla.resolver("PROV_B", "w400/8").codigo_idm == "R40.000.001"
    assert tabla.resolver("PROV_A", "W400/8").metodo == "no_resuelto"  # la referencia de B no vale para A


def test_linea_sin_codigo_idm_casa_por_referencia_del_pedido():
    pedido = _pedido([_lp("A", "1", "1", ref="REF-1")])
    c = cotejar(_albaran([_la(None, "1", "1", ref="REF-1")]), pedido)
    assert c.semaforo == Semaforo.VERDE and c.lineas[0].indice_pedido == 0


# ---------------------------------------------------------------- cantidades, precios, redondeos, descuentos


def test_cantidad_distinta_menor_y_mayor():
    pedido = _pedido([_lp("A", "10", "1")])
    assert cotejar(_albaran([_la("A", "9", "1")]), pedido).entrega == EstadoEntrega.PARCIAL
    assert cotejar(_albaran([_la("A", "11", "1")]), pedido).entrega == EstadoEntrega.EXCESO


def test_precio_con_tres_decimales_se_compara_redondeado():
    """0,335 y 0,34 son iguales al céntimo; 0,334 y 0,34 no."""
    pedido = _pedido([_lp("A", "1", "0.335")])
    assert cotejar(_albaran([_la("A", "1", "0.34")]), pedido).semaforo == Semaforo.VERDE
    assert cotejar(_albaran([_la("A", "1", "0.334")]), pedido).semaforo == Semaforo.AMBAR


def test_importe_linea_redondea_como_siddex():
    assert importe_linea(D("7"), D("0.335")) == D("2.35")  # 2,345 → 2,35 (mitad hacia arriba)
    assert importe_linea(D("3"), D("0.335"), D("10")) == D("0.90")  # 0,9045 → 0,90


@pytest.mark.xfail(
    strict=True, reason="P02: qué manda si el total impreso no cuadra con la suma de líneas (PENDIENTE-IDM)"
)
def test_total_impreso_distinto_de_la_suma_de_lineas():
    pedido = _pedido([_lp("A", "7", "0.335"), _lp("B", "7", "0.335"), _lp("C", "7", "0.335")])
    c = cotejar(_albaran([_la("A", "7", "0.335"), _la("B", "7", "0.335"), _la("C", "7", "0.335")]), pedido)
    assert c.total_albaran == D("7.05")
    assert TipoAviso.IMPORTE_NO_CUADRA in tipos(c)  # el proveedor imprimió 7,04


def test_descuento_en_cascada_no_se_soporta_y_se_ve():
    """Si el proveedor aplica 45 % + 5 %, hoy llega como un solo porcentaje: si no coincide con el pedido, ámbar."""
    pedido = _pedido([_lp("A", "1", "10", "45")])
    c = cotejar(_albaran([_la("A", "1", "10", "47.75")]), pedido)
    assert TipoAviso.DESCUENTO_DISTINTO in tipos(c)


# ---------------------------------------------------------------- portes, líneas de más y de menos


def test_portes_en_albaran_y_en_factura():
    pedido = _pedido([_lp("A", "1", "10")])
    c = cotejar(
        _albaran([_la("A", "1", "10"), LineaAlbaran(descripcion="TRANSPORTE", cantidad=D("1"), precio_bruto=D("6"))]),
        pedido,
    )
    assert TipoAviso.PORTES_NO_PACTADOS in tipos(c) and c.lineas[1].indice_pedido is None
    factura = Factura(
        proveedor="PROV",
        numero="F",
        albaranes=["A1"],
        lineas=[
            LineaFactura(albaran="A1", codigo_proveedor=None, descripcion="X", cantidad=D("1"), precio_bruto=D("10")),
            LineaFactura(albaran=None, descripcion="PORTES", cantidad=D("1"), precio_bruto=D("6"), es_portes=True),
        ],
    )
    r = cotejar_factura(factura, [_albaran([_la("A", "1", "10")])])
    assert r.portes == D("6") and r.total_lineas_factura == D("10")


def test_linea_de_mas_y_linea_de_menos():
    pedido = _pedido([_lp("A", "1", "1"), _lp("B", "1", "1")])
    c = cotejar(_albaran([_la("A", "1", "1"), _la("Z", "1", "1")]), pedido)
    assert c.lineas[1].avisos[0].tipo == TipoAviso.LINEA_SIN_PEDIDO  # de más
    assert [p.codigo_idm for p in c.pendientes_pedido] == ["B"]  # de menos: queda pendiente, sin aviso
    assert c.entrega == EstadoEntrega.PARCIAL


# ---------------------------------------------------------------- facturas


def test_factura_de_varios_albaranes_y_entrega_parcial_previa():
    a1 = _albaran([_la("A", "2", "9.14", "45")], numero="A1")
    a2 = _albaran([_la("A", "3", "9.14", "45")], numero="A2")
    # Cada albarán redondea su línea por separado: 10,05 + 15,08 = 25,13 (y no 25,14 como 5 unidades de golpe)
    factura = Factura(
        proveedor="PROV",
        numero="F",
        albaranes=["A1", "A2"],
        base=D("25.13"),
        lineas=[
            LineaFactura(albaran="A1", descripcion="X", cantidad=D("2"), precio_bruto=D("9.14"), descuento_pct=D("45")),
            LineaFactura(albaran="A2", descripcion="X", cantidad=D("3"), precio_bruto=D("9.14"), descuento_pct=D("45")),
        ],
    )
    r = cotejar_factura(factura, [a1, a2])
    assert r.semaforo == Semaforo.VERDE and r.albaranes_encontrados == ["A1", "A2"]
    assert r.total_albaranes == D("25.13")


def test_factura_parcial_informa_lineas_no_facturadas():
    a1 = _albaran([_la("A", "1", "10", ref="RA"), _la("B", "2", "5", ref="RB"), _la("C", "1", "1", ref="RC")])
    factura = Factura(
        proveedor="PROV",
        numero="F",
        albaranes=["A1"],
        lineas=[
            LineaFactura(albaran="A1", codigo_proveedor="RA", descripcion="X", cantidad=D("1"), precio_bruto=D("10"))
        ],
    )
    r = cotejar_factura(factura, [a1])
    assert r.lineas_no_facturadas == ["A1: RB × 2", "A1: RC × 1"]
    # Comportamiento PROVISIONAL: una factura parcial correcta sale VERDE y solo informa. Falta la regla de IDM.
    assert r.semaforo == Semaforo.VERDE and r.avisos == []


@pytest.mark.xfail(
    strict=True, reason="factura parcial: ¿se acepta y se espera a la siguiente, o se avisa? (PENDIENTE-IDM)"
)
def test_factura_parcial_regla_pendiente():
    a1 = _albaran([_la("A", "1", "10", ref="RA"), _la("B", "2", "5", ref="RB")])
    factura = Factura(
        proveedor="PROV",
        numero="F",
        albaranes=["A1"],
        lineas=[
            LineaFactura(albaran="A1", codigo_proveedor="RA", descripcion="X", cantidad=D("1"), precio_bruto=D("10"))
        ],
    )
    r = cotejar_factura(factura, [a1])
    assert r.avisos != [] and r.semaforo == Semaforo.AMBAR  # si IDM decide que hay que avisar de lo no facturado


def test_factura_sin_pedido_identificado_por_albaran_propuesto():
    """Un albarán que entró SIN_PEDIDO (pedido propuesto) se factura igual: la factura lo encuentra por su número."""
    a1 = _albaran([_la("A", "1", "10")], numero="4410/3172", pedido=None)
    factura = Factura(
        proveedor="PROV",
        numero="F",
        albaranes=["4410/3.172"],
        lineas=[LineaFactura(albaran="4410/3.172", descripcion="X", cantidad=D("1"), precio_bruto=D("10"))],
    )
    a1.proveedor = factura.proveedor = "RECACOR"  # RECACOR quita los puntos al normalizar
    r = cotejar_factura(factura, [a1])
    assert r.albaranes_encontrados == ["4410/3172"] and r.semaforo == Semaforo.VERDE


def test_factura_sin_ningun_albaran_conocido():
    factura = Factura(
        proveedor="PROV",
        numero="F",
        albaranes=["ZZ-1"],
        lineas=[LineaFactura(albaran="ZZ-1", descripcion="X", cantidad=D("1"), precio_bruto=D("10"))],
    )
    r = cotejar_factura(factura, [])
    assert r.albaranes_no_encontrados == ["ZZ-1"] and r.semaforo == Semaforo.AMBAR
    assert {a.tipo for a in r.avisos} >= {TipoAviso.ALBARAN_NO_ENCONTRADO, TipoAviso.IMPORTE_NO_CUADRA}


def test_albaran_sin_pedido_identificado():
    c = cotejar(_albaran([_la("A", "1", "10")], pedido=None), None)
    assert c.relacion == RelacionPedido.SIN_PEDIDO and c.semaforo == Semaforo.AMBAR
