"""cotejar(albaran, pedido, reglas): compara un albarán con su pedido al céntimo, bruto y descuento aparte.
Devuelve un Cotejo con semáforo por línea y global, estados de entrega y precio, y avisos con motivo.
No lee documentos, no busca el pedido, no toca la base de datos: es una función pura."""

from decimal import Decimal

from idm.dominio.dinero import CERO, redondear
from idm.dominio.estados import EstadoEntrega, EstadoPrecio, RelacionPedido, Semaforo, TipoAviso
from idm.dominio.modelos import (
    Albaran,
    Aviso,
    Cotejo,
    CotejoLinea,
    LineaAlbaran,
    LineaPedido,
    LineaPendiente,
    Pedido,
)
from idm.dominio.reglas import REGLAS_POR_DEFECTO, ReglasCotejo, es_linea_portes


def cotejar(albaran: Albaran, pedido: Pedido | None, reglas: ReglasCotejo = REGLAS_POR_DEFECTO) -> Cotejo:
    """Punto de entrada. Sin pedido → todo ámbar con aviso SIN_PEDIDO (el pedido se propondrá aparte)."""
    if pedido is None:
        return _cotejo_sin_pedido(albaran, reglas)

    # Cantidad ya asignada a cada línea de pedido durante este cotejo (por si un artículo se repite).
    asignado: dict[int, Decimal] = {i: CERO for i in range(len(pedido.lineas))}
    lineas_cotejo: list[CotejoLinea] = []

    for indice, linea in enumerate(albaran.lineas):
        if linea.es_portes or es_linea_portes(linea.descripcion, reglas):
            lineas_cotejo.append(_cotejar_portes(indice, linea, albaran.proveedor, reglas))
            continue
        indice_pedido = _buscar_linea_pedido(linea, pedido.lineas, asignado)
        if indice_pedido is None:
            lineas_cotejo.append(_linea_sin_pedido(indice, linea))
            continue
        linea_pedido = pedido.lineas[indice_pedido]
        lineas_cotejo.append(_cotejar_linea(indice, linea, indice_pedido, linea_pedido, asignado, reglas))
        asignado[indice_pedido] += linea.cantidad

    pendientes = _pendientes(pedido.lineas, asignado)
    entrega = _entrega_global(lineas_cotejo, pendientes)
    precio = _precio_global(lineas_cotejo)
    semaforo = _semaforo_global(lineas_cotejo)
    return Cotejo(
        proveedor=albaran.proveedor,
        albaran=albaran.numero,
        pedido=pedido.numero,
        relacion=RelacionPedido.CON_PEDIDO,
        semaforo=semaforo,
        entrega=entrega,
        precio=precio,
        lineas=lineas_cotejo,
        avisos=[],
        pendientes_pedido=pendientes,
        total_albaran=albaran.total,
        total_cotejado_pedido=_total_cotejado(lineas_cotejo),
    )


# ---------------------------------------------------------------- búsqueda de línea de pedido


def _buscar_linea_pedido(
    linea: LineaAlbaran, lineas_pedido: list[LineaPedido], asignado: dict[int, Decimal]
) -> int | None:
    """Primero por código IDM, después por código del proveedor. Prefiere líneas con cantidad pendiente."""
    candidatos = [
        i
        for i, lp in enumerate(lineas_pedido)
        if (linea.codigo_idm and lp.codigo_idm == linea.codigo_idm)
        or (linea.codigo_idm is None and linea.codigo_proveedor and lp.codigo_proveedor == linea.codigo_proveedor)
    ]
    if not candidatos:
        return None
    for i in candidatos:
        if lineas_pedido[i].pendiente - asignado[i] > CERO:
            return i
    return candidatos[0]


# ---------------------------------------------------------------- cotejo de una línea


def _cotejar_linea(
    indice: int,
    linea: LineaAlbaran,
    indice_pedido: int,
    linea_pedido: LineaPedido,
    asignado: dict[int, Decimal],
    reglas: ReglasCotejo,
) -> CotejoLinea:
    avisos: list[Aviso] = []
    pendiente = linea_pedido.pendiente - asignado[indice_pedido]
    entrega = _entrega_linea(linea.cantidad, pendiente)
    if entrega == EstadoEntrega.EXCESO and not reglas.aceptar_exceso:
        avisos.append(
            Aviso(
                tipo=TipoAviso.EXCESO_CANTIDAD,
                mensaje=f"Llegan {linea.cantidad} y quedaban {pendiente} pendientes",
                linea=indice,
                detalle={"albaran": str(linea.cantidad), "pedido": str(pendiente)},
            )
        )

    if linea.precio_bruto is None:
        precio = EstadoPrecio.PENDIENTE_FACTURA
        avisos.append(
            Aviso(
                tipo=TipoAviso.PRECIO_PENDIENTE,
                mensaje="El albarán no trae precio: se completará con la factura",
                linea=indice,
            )
        )
        importe_albaran = None
    else:
        precio = EstadoPrecio.CONOCIDO
        avisos.extend(_comparar_precio(indice, linea, linea_pedido, reglas))
        importe_albaran = linea.importe

    semaforo = Semaforo.VERDE if not avisos else Semaforo.AMBAR
    return CotejoLinea(
        indice_albaran=indice,
        codigo_idm=linea_pedido.codigo_idm,
        indice_pedido=indice_pedido,
        semaforo=semaforo,
        entrega=entrega,
        precio=precio,
        importe_albaran=importe_albaran,
        importe_pedido=_importe_pedido_para(linea, linea_pedido),
        avisos=avisos,
    )


def _comparar_precio(indice: int, linea: LineaAlbaran, linea_pedido: LineaPedido, reglas: ReglasCotejo) -> list[Aviso]:
    """Bruto y descuento por separado, cada uno al céntimo (o a la tolerancia de las reglas)."""
    avisos: list[Aviso] = []
    assert linea.precio_bruto is not None
    bruto_albaran = redondear(linea.precio_bruto)
    bruto_pedido = redondear(linea_pedido.precio_bruto)
    if abs(bruto_albaran - bruto_pedido) > reglas.tolerancia_precio:
        avisos.append(
            Aviso(
                tipo=TipoAviso.PRECIO_DISTINTO,
                mensaje=f"Precio bruto {bruto_albaran} en albarán y {bruto_pedido} en pedido",
                linea=indice,
                detalle={
                    "albaran": str(bruto_albaran),
                    "pedido": str(bruto_pedido),
                    "diferencia": str(bruto_albaran - bruto_pedido),
                },
            )
        )
    if abs(linea.descuento_pct - linea_pedido.descuento_pct) > reglas.tolerancia_descuento_pct:
        avisos.append(
            Aviso(
                tipo=TipoAviso.DESCUENTO_DISTINTO,
                mensaje=(f"Descuento {linea.descuento_pct} % en albarán y {linea_pedido.descuento_pct} % en pedido"),
                linea=indice,
                detalle={
                    "albaran": str(linea.descuento_pct),
                    "pedido": str(linea_pedido.descuento_pct),
                },
            )
        )
    return avisos


def _importe_pedido_para(linea: LineaAlbaran, linea_pedido: LineaPedido) -> Decimal:
    """Lo que valdría esta cantidad al precio del pedido (para comparar importes al céntimo)."""
    from idm.dominio.dinero import importe_linea

    return importe_linea(linea.cantidad, linea_pedido.precio_bruto, linea_pedido.descuento_pct)


def _entrega_linea(cantidad: Decimal, pendiente: Decimal) -> EstadoEntrega:
    if cantidad > pendiente:
        return EstadoEntrega.EXCESO
    if cantidad < pendiente:
        return EstadoEntrega.PARCIAL
    return EstadoEntrega.COMPLETA


# ---------------------------------------------------------------- casos especiales


def _linea_sin_pedido(indice: int, linea: LineaAlbaran) -> CotejoLinea:
    aviso = Aviso(
        tipo=TipoAviso.LINEA_SIN_PEDIDO,
        mensaje=f"'{linea.descripcion}' ({linea.codigo_proveedor or 'sin código'}) no está en el pedido",
        linea=indice,
    )
    if linea.codigo_idm is None and linea.codigo_proveedor:
        aviso.detalle["motivo"] = "artículo no resuelto a código IDM"
    return CotejoLinea(
        indice_albaran=indice,
        codigo_idm=linea.codigo_idm,
        indice_pedido=None,
        semaforo=Semaforo.AMBAR,
        entrega=None,
        precio=EstadoPrecio.CONOCIDO if linea.precio_bruto is not None else EstadoPrecio.PENDIENTE_FACTURA,
        importe_albaran=linea.importe,
        importe_pedido=None,
        avisos=[aviso],
    )


def _cotejar_portes(indice: int, linea: LineaAlbaran, proveedor: str, reglas: ReglasCotejo) -> CotejoLinea:
    pactado = reglas.portes_pactados.get(proveedor)
    importe = linea.importe
    avisos: list[Aviso] = []
    if pactado is None or importe is None or redondear(pactado) != importe:
        avisos.append(
            Aviso(
                tipo=TipoAviso.PORTES_NO_PACTADOS,
                mensaje=f"Portes de {importe} sin importe pactado"
                if pactado is None
                else f"Portes de {importe}; pactados {redondear(pactado)}",
                linea=indice,
            )
        )
    return CotejoLinea(
        indice_albaran=indice,
        codigo_idm=None,
        indice_pedido=None,
        semaforo=Semaforo.VERDE if not avisos else Semaforo.AMBAR,
        entrega=None,
        precio=EstadoPrecio.CONOCIDO if importe is not None else EstadoPrecio.PENDIENTE_FACTURA,
        importe_albaran=importe,
        importe_pedido=None,
        avisos=avisos,
    )


def _cotejo_sin_pedido(albaran: Albaran, reglas: ReglasCotejo) -> Cotejo:
    lineas = []
    for indice, linea in enumerate(albaran.lineas):
        if linea.es_portes or es_linea_portes(linea.descripcion, reglas):
            lineas.append(_cotejar_portes(indice, linea, albaran.proveedor, reglas))
        else:
            lineas.append(_linea_sin_pedido(indice, linea))
    return Cotejo(
        proveedor=albaran.proveedor,
        albaran=albaran.numero,
        pedido=None,
        relacion=RelacionPedido.SIN_PEDIDO,
        semaforo=Semaforo.AMBAR,
        entrega=None,
        precio=_precio_global(lineas),
        lineas=lineas,
        avisos=[
            Aviso(
                tipo=TipoAviso.SIN_PEDIDO,
                mensaje="No hay pedido para este albarán: se propondrá uno con sus líneas",
            )
        ],
        total_albaran=albaran.total,
        total_cotejado_pedido=None,
    )


# ---------------------------------------------------------------- agregados


def _pendientes(lineas_pedido: list[LineaPedido], asignado: dict[int, Decimal]) -> list[LineaPendiente]:
    resultado = []
    for i, lp in enumerate(lineas_pedido):
        resto = lp.pendiente - asignado[i]
        if resto > CERO:
            resultado.append(LineaPendiente(indice_pedido=i, codigo_idm=lp.codigo_idm, cantidad_pendiente=resto))
    return resultado


def _entrega_global(lineas: list[CotejoLinea], pendientes: list[LineaPendiente]) -> EstadoEntrega:
    if any(linea.entrega == EstadoEntrega.EXCESO for linea in lineas):
        return EstadoEntrega.EXCESO
    if pendientes:
        return EstadoEntrega.PARCIAL
    return EstadoEntrega.COMPLETA


def _precio_global(lineas: list[CotejoLinea]) -> EstadoPrecio:
    if any(linea.precio == EstadoPrecio.PENDIENTE_FACTURA for linea in lineas):
        return EstadoPrecio.PENDIENTE_FACTURA
    return EstadoPrecio.CONOCIDO


def _semaforo_global(lineas: list[CotejoLinea]) -> Semaforo:
    if all(linea.semaforo == Semaforo.VERDE for linea in lineas):
        return Semaforo.VERDE
    return Semaforo.AMBAR


def _total_cotejado(lineas: list[CotejoLinea]) -> Decimal:
    return redondear(sum((linea.importe_pedido or CERO for linea in lineas), CERO))
