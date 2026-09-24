"""Factura contra N albaranes: localiza cada albarán por su número normalizado, compara línea a línea al céntimo,
separa los portes, completa los precios que quedaron pendientes y avisa si el precio de compra del maestro ha cambiado.
No modifica el maestro ni precios de venta: solo devuelve avisos y precios completados para que una persona decida."""

from decimal import Decimal

from pydantic import BaseModel, Field

from idm.albaranes.normalizar import normalizar_numero
from idm.dominio.dinero import CERO, importe_linea, redondear
from idm.dominio.estados import Semaforo, TipoAviso
from idm.dominio.modelos import Albaran, Articulo, Aviso, Factura, LineaAlbaran, LineaFactura
from idm.dominio.reglas import REGLAS_POR_DEFECTO, ReglasCotejo, es_linea_portes


class PrecioCompletado(BaseModel):
    albaran: str
    codigo_proveedor: str | None
    codigo_idm: str | None
    precio_bruto: Decimal
    descuento_pct: Decimal


class PrecioCambiado(BaseModel):
    codigo_idm: str
    precio_maestro: Decimal
    precio_factura: Decimal
    descuento_factura: Decimal


class CotejoFactura(BaseModel):
    proveedor: str
    factura: str
    semaforo: Semaforo
    albaranes_encontrados: list[str] = Field(default_factory=list)
    albaranes_no_encontrados: list[str] = Field(default_factory=list)
    portes: Decimal = CERO
    total_lineas_factura: Decimal = CERO  # sin portes
    total_albaranes: Decimal = CERO  # con precios completados
    precios_completados: list[PrecioCompletado] = Field(default_factory=list)
    precios_cambiados: list[PrecioCambiado] = Field(default_factory=list)
    # Informativo: líneas de albaranes recibidos que esta factura no incluye (factura parcial). No cambia el semáforo
    # hasta que IDM diga si se avisa o se espera a la siguiente factura (docs/PENDIENTE-IDM.md).
    lineas_no_facturadas: list[str] = Field(default_factory=list)
    avisos: list[Aviso] = Field(default_factory=list)


def _clave_linea(codigo: str | None, descripcion: str) -> str:
    return (codigo or "").strip().upper() or descripcion.strip().upper()


def _emparejar(lineas_factura: list[LineaFactura], albaran: Albaran) -> list[tuple[LineaFactura, LineaAlbaran | None]]:
    pendientes = list(enumerate(albaran.lineas))
    parejas = []
    for lf in lineas_factura:
        clave = _clave_linea(lf.codigo_proveedor, lf.descripcion)
        encontrada = next(
            (
                (i, la)
                for i, la in pendientes
                if _clave_linea(la.codigo_proveedor, la.descripcion) == clave and la.cantidad == lf.cantidad
            ),
            None,
        )
        if encontrada is None:
            encontrada = next(
                ((i, la) for i, la in pendientes if _clave_linea(la.codigo_proveedor, la.descripcion) == clave), None
            )
        if encontrada is not None:
            pendientes.remove(encontrada)
            parejas.append((lf, encontrada[1]))
        else:
            parejas.append((lf, None))
    return parejas


def cotejar_factura(
    factura: Factura,
    albaranes: list[Albaran],
    articulos: dict[str, Articulo] | None = None,
    reglas: ReglasCotejo = REGLAS_POR_DEFECTO,
) -> CotejoFactura:
    articulos = articulos or {}
    r = CotejoFactura(proveedor=factura.proveedor, factura=factura.numero, semaforo=Semaforo.VERDE)
    por_numero = {a.numero: a for a in albaranes if a.proveedor == factura.proveedor}

    referencias = list(factura.albaranes) + [li.albaran for li in factura.lineas if li.albaran]
    numeros = []
    for ref in referencias:
        n = normalizar_numero(factura.proveedor, ref)
        if n not in numeros:
            numeros.append(n)
    for n in numeros:
        (r.albaranes_encontrados if n in por_numero else r.albaranes_no_encontrados).append(n)
    for n in r.albaranes_no_encontrados:
        r.avisos.append(
            Aviso(tipo=TipoAviso.ALBARAN_NO_ENCONTRADO, mensaje=f"El albarán {n} de la factura no está recibido")
        )

    # Portes y líneas sin albarán
    por_albaran: dict[str, list[LineaFactura]] = {}
    for li in factura.lineas:
        if li.es_portes or (not li.albaran and es_linea_portes(li.descripcion, reglas)):
            r.portes += li.importe
            continue
        clave = normalizar_numero(factura.proveedor, li.albaran) if li.albaran else ""
        por_albaran.setdefault(clave, []).append(li)
    if r.portes > CERO:
        pactado = reglas.portes_pactados.get(factura.proveedor)
        if pactado is None or redondear(pactado) != redondear(r.portes):
            r.avisos.append(
                Aviso(tipo=TipoAviso.PORTES_NO_PACTADOS, mensaje=f"Portes de {redondear(r.portes)} en la factura")
            )
    if "" in por_albaran and len(numeros) == 1:
        por_albaran[numeros[0]] = por_albaran.pop("") + por_albaran.get(numeros[0], [])

    total_albaranes = CERO
    for numero, lineas in por_albaran.items():
        r.total_lineas_factura += sum((li.importe for li in lineas), CERO)
        albaran = por_numero.get(numero)
        if albaran is None:
            if numero and numero not in r.albaranes_no_encontrados:
                r.albaranes_no_encontrados.append(numero)
                r.avisos.append(
                    Aviso(
                        tipo=TipoAviso.ALBARAN_NO_ENCONTRADO,
                        mensaje=f"Líneas de la factura para el albarán {numero}, no recibido",
                    )
                )
            elif not numero:
                r.avisos.append(
                    Aviso(tipo=TipoAviso.LINEA_SIN_PEDIDO, mensaje="Líneas de la factura sin albarán asignado")
                )
            continue
        parejas = _emparejar(lineas, albaran)
        facturadas = {id(la) for _, la in parejas if la is not None}
        r.lineas_no_facturadas += [
            f"{numero}: {la.codigo_proveedor or la.descripcion} × {la.cantidad}"
            for la in albaran.lineas
            if id(la) not in facturadas and not la.es_portes
        ]
        for lf, la in parejas:
            if la is None:
                r.avisos.append(
                    Aviso(
                        tipo=TipoAviso.LINEA_SIN_PEDIDO,
                        mensaje=f"'{lf.descripcion}' facturada en {numero} pero no está en el albarán",
                    )
                )
                continue
            if la.precio_bruto is None:
                r.precios_completados.append(
                    PrecioCompletado(
                        albaran=numero,
                        codigo_proveedor=la.codigo_proveedor,
                        codigo_idm=la.codigo_idm,
                        precio_bruto=lf.precio_bruto,
                        descuento_pct=lf.descuento_pct,
                    )
                )
                total_albaranes += importe_linea(la.cantidad, lf.precio_bruto, lf.descuento_pct)
            else:
                total_albaranes += la.importe or CERO
                if redondear(la.precio_bruto) != redondear(lf.precio_bruto) or la.descuento_pct != lf.descuento_pct:
                    r.avisos.append(
                        Aviso(
                            tipo=TipoAviso.PRECIO_DISTINTO,
                            mensaje=f"{numero} '{lf.descripcion}': albarán {la.precio_bruto} / {la.descuento_pct} %, "
                            f"factura {lf.precio_bruto} / {lf.descuento_pct} %",
                        )
                    )
            if lf.cantidad != la.cantidad:
                r.avisos.append(
                    Aviso(
                        tipo=TipoAviso.IMPORTE_NO_CUADRA,
                        mensaje=f"{numero} '{lf.descripcion}': cantidad {la.cantidad} en albarán "
                        f"y {lf.cantidad} en factura",
                    )
                )
            art = articulos.get(la.codigo_idm) if la.codigo_idm else None
            if art and art.precio_compra is not None and redondear(art.precio_compra) != redondear(lf.precio_bruto):
                r.precios_cambiados.append(
                    PrecioCambiado(
                        codigo_idm=la.codigo_idm,
                        precio_maestro=art.precio_compra,
                        precio_factura=lf.precio_bruto,
                        descuento_factura=lf.descuento_pct,
                    )
                )
    r.total_albaranes = redondear(total_albaranes)
    r.total_lineas_factura = redondear(r.total_lineas_factura)
    if r.total_lineas_factura != r.total_albaranes:
        r.avisos.append(
            Aviso(
                tipo=TipoAviso.IMPORTE_NO_CUADRA,
                mensaje=f"Líneas de factura {r.total_lineas_factura} frente a albaranes {r.total_albaranes}",
            )
        )
    if factura.base is not None and redondear(factura.base) != redondear(r.total_lineas_factura + r.portes):
        r.avisos.append(
            Aviso(
                tipo=TipoAviso.IMPORTE_NO_CUADRA,
                mensaje=f"Base {factura.base} no cuadra con líneas + portes "
                f"{redondear(r.total_lineas_factura + r.portes)}",
            )
        )
    for pc in r.precios_cambiados:
        r.avisos.append(
            Aviso(
                tipo=TipoAviso.PRECIO_CAMBIADO,
                mensaje=f"{pc.codigo_idm}: maestro {pc.precio_maestro}, factura {pc.precio_factura} "
                "(revisar, no se cambia)",
            )
        )
    r.semaforo = Semaforo.VERDE if not r.avisos else Semaforo.AMBAR
    return r
