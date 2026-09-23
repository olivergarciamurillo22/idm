"""Tests de la función pura cotejar(): cuadra, un céntimo, exceso, descuento, línea sin pedido.
Además: sin precio (pendiente de factura), portes, entrega parcial y albarán sin pedido.
No usa base de datos, ficheros ni lector."""

from decimal import Decimal

from idm.dominio.cotejar import cotejar
from idm.dominio.estados import EstadoEntrega, EstadoPrecio, RelacionPedido, Semaforo, TipoAviso
from idm.dominio.modelos import Albaran, LineaAlbaran, LineaPedido, Pedido
from idm.dominio.reglas import ReglasCotejo


def pedido_base() -> Pedido:
    return Pedido(
        numero="20261060",
        proveedor="FICT_VEGA",
        lineas=[
            LineaPedido(
                codigo_idm="134.000.842",
                codigo_proveedor="PVCC550942",
                descripcion="TERMINAL FASTON H. 9,4 AMAR",
                cantidad=Decimal("100"),
                precio_bruto=Decimal("0.30"),
                descuento_pct=Decimal("45"),
            ),
            LineaPedido(
                codigo_idm="I33.000.786",
                codigo_proveedor="ABR-6205",
                descripcion="RODAMIENTO 6205 2RS",
                cantidad=Decimal("5"),
                precio_bruto=Decimal("9.14"),
                descuento_pct=Decimal("45"),
            ),
        ],
    )


def albaran_base(**cambios) -> Albaran:
    lineas = [
        LineaAlbaran(
            codigo_proveedor="PVCC550942",
            codigo_idm="134.000.842",
            descripcion="TERMINAL FASTON H 9,4 AMARILLO",
            cantidad=Decimal("100"),
            precio_bruto=Decimal("0.30"),
            descuento_pct=Decimal("45"),
        ),
        LineaAlbaran(
            codigo_proveedor="ABR-6205",
            codigo_idm="I33.000.786",
            descripcion="RODAMIENTO 6205 2RS",
            cantidad=Decimal("5"),
            precio_bruto=Decimal("9.14"),
            descuento_pct=Decimal("45"),
        ),
    ]
    datos = dict(proveedor="FICT_VEGA", numero_original="AC B26 0100005283",
                 numero="B26 0100005283", nuestro_pedido="20261060", lineas=lineas)
    datos.update(cambios)
    return Albaran(**datos)


def tipos(cotejo) -> set[TipoAviso]:
    return {a.tipo for a in cotejo.todos_los_avisos}


def test_cuadra_todo_verde():
    cotejo = cotejar(albaran_base(), pedido_base())
    assert cotejo.semaforo == Semaforo.VERDE
    assert cotejo.relacion == RelacionPedido.CON_PEDIDO
    assert cotejo.entrega == EstadoEntrega.COMPLETA
    assert cotejo.precio == EstadoPrecio.CONOCIDO
    assert cotejo.pendientes_pedido == []
    assert cotejo.total_albaran == Decimal("41.64")  # 16,50 + 25,14
    assert cotejo.total_cotejado_pedido == Decimal("41.64")
    assert all(linea.semaforo == Semaforo.VERDE for linea in cotejo.lineas)


def test_precio_distinto_en_un_centimo_es_ambar():
    albaran = albaran_base()
    albaran.lineas[1].precio_bruto = Decimal("9.15")
    cotejo = cotejar(albaran, pedido_base())
    assert cotejo.semaforo == Semaforo.AMBAR
    assert cotejo.lineas[0].semaforo == Semaforo.VERDE
    assert cotejo.lineas[1].semaforo == Semaforo.AMBAR
    aviso = cotejo.lineas[1].avisos[0]
    assert aviso.tipo == TipoAviso.PRECIO_DISTINTO
    assert aviso.detalle["diferencia"] == "0.01"


def test_exceso_de_cantidad_es_ambar():
    albaran = albaran_base()
    albaran.lineas[0].cantidad = Decimal("120")
    cotejo = cotejar(albaran, pedido_base())
    assert cotejo.semaforo == Semaforo.AMBAR
    assert cotejo.entrega == EstadoEntrega.EXCESO
    assert cotejo.lineas[0].entrega == EstadoEntrega.EXCESO
    assert TipoAviso.EXCESO_CANTIDAD in tipos(cotejo)


def test_descuento_distinto_es_ambar_aunque_el_bruto_cuadre():
    albaran = albaran_base()
    albaran.lineas[0].descuento_pct = Decimal("40")
    cotejo = cotejar(albaran, pedido_base())
    assert cotejo.semaforo == Semaforo.AMBAR
    assert tipos(cotejo) == {TipoAviso.DESCUENTO_DISTINTO}


def test_linea_sin_pedido():
    albaran = albaran_base()
    albaran.lineas.append(
        LineaAlbaran(codigo_proveedor="ZZZ-1", descripcion="TORNILLO M8", cantidad=Decimal("10"),
                     precio_bruto=Decimal("0.10"))
    )
    cotejo = cotejar(albaran, pedido_base())
    assert cotejo.semaforo == Semaforo.AMBAR
    assert cotejo.lineas[2].indice_pedido is None
    assert cotejo.lineas[2].avisos[0].tipo == TipoAviso.LINEA_SIN_PEDIDO
    assert cotejo.lineas[2].avisos[0].detalle["motivo"] == "artículo no resuelto a código IDM"
    assert cotejo.entrega == EstadoEntrega.COMPLETA


def test_sin_precio_queda_pendiente_de_factura():
    albaran = albaran_base()
    for linea in albaran.lineas:
        linea.precio_bruto = None
    cotejo = cotejar(albaran, pedido_base())
    assert cotejo.precio == EstadoPrecio.PENDIENTE_FACTURA
    assert cotejo.entrega == EstadoEntrega.COMPLETA
    assert cotejo.total_albaran is None
    assert tipos(cotejo) == {TipoAviso.PRECIO_PENDIENTE}


def test_entrega_parcial_deja_pendiente():
    albaran = albaran_base()
    albaran.lineas[1].cantidad = Decimal("2")
    cotejo = cotejar(albaran, pedido_base())
    assert cotejo.semaforo == Semaforo.VERDE  # lo que ha llegado cuadra
    assert cotejo.entrega == EstadoEntrega.PARCIAL
    assert cotejo.pendientes_pedido[0].cantidad_pendiente == Decimal("3")


def test_portes_ambar_salvo_pactados():
    albaran = albaran_base()
    albaran.lineas.append(
        LineaAlbaran(descripcion="PORTES", cantidad=Decimal("1"), precio_bruto=Decimal("12.50"))
    )
    cotejo = cotejar(albaran, pedido_base())
    assert TipoAviso.PORTES_NO_PACTADOS in tipos(cotejo)
    reglas = ReglasCotejo(portes_pactados={"FICT_VEGA": Decimal("12.5")})
    cotejo = cotejar(albaran, pedido_base(), reglas)
    assert cotejo.semaforo == Semaforo.VERDE


def test_albaran_sin_pedido():
    cotejo = cotejar(albaran_base(nuestro_pedido=None), None)
    assert cotejo.relacion == RelacionPedido.SIN_PEDIDO
    assert cotejo.semaforo == Semaforo.AMBAR
    assert cotejo.avisos[0].tipo == TipoAviso.SIN_PEDIDO
    assert all(linea.indice_pedido is None for linea in cotejo.lineas)


def test_articulo_repetido_en_pedido_reparte_cantidad():
    pedido = pedido_base()
    pedido.lineas.append(pedido.lineas[1].model_copy(update={"cantidad": Decimal("3")}))
    albaran = albaran_base()
    albaran.lineas[1].cantidad = Decimal("8")
    cotejo = cotejar(albaran, pedido)
    # 8 contra la primera línea (5 pendientes) es exceso: se avisa, no se reparte en silencio.
    assert cotejo.entrega == EstadoEntrega.EXCESO


def test_cotejo_serializa_a_json():
    cotejo = cotejar(albaran_base(), pedido_base())
    datos = cotejo.model_dump(mode="json")
    assert datos["semaforo"] == "VERDE"
    assert datos["total_albaran"] == "41.64"
