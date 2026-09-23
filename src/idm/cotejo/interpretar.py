"""De DocumentoLeido (lo que dice el papel) a Albaran/Factura (dominio): proveedor, número normalizado, códigos IDM.
Cada resolución deja un evento con su método (cif/nombre; equivalencia/aprendida/no_resuelto) para la trazabilidad.
No coteja ni busca pedidos."""

from dataclasses import dataclass, field

from idm.albaranes.normalizar import normalizar_numero
from idm.dominio.dinero import CERO
from idm.dominio.estados import TipoAviso
from idm.dominio.modelos import (
    Albaran,
    Aviso,
    DocumentoLeido,
    Factura,
    LineaAlbaran,
    LineaFactura,
    Proveedor,
)
from idm.equivalencias.proveedores import identificar
from idm.equivalencias.tabla import TablaEquivalencias


@dataclass
class Evento:
    tipo: str
    datos: dict = field(default_factory=dict)


@dataclass
class AlbaranInterpretado:
    albaran: Albaran
    proveedor_metodo: str
    avisos: list[Aviso] = field(default_factory=list)
    eventos: list[Evento] = field(default_factory=list)


@dataclass
class FacturaInterpretada:
    factura: Factura
    proveedor_metodo: str
    avisos: list[Aviso] = field(default_factory=list)
    eventos: list[Evento] = field(default_factory=list)


def _proveedor(doc: DocumentoLeido, proveedores: list[Proveedor]) -> tuple[str, str, list[Evento]]:
    clave, metodo = identificar(nombre=doc.proveedor_texto, cif=doc.cif, proveedores=proveedores)
    if clave is None and doc.texto:
        clave, metodo = identificar(nombre=doc.texto[:400], proveedores=proveedores)
    eventos = [
        Evento("proveedor.resuelto", {"clave": clave, "metodo": metodo, "cif": doc.cif, "texto": doc.proveedor_texto})
    ]
    return clave or "DESCONOCIDO", metodo, eventos


def interpretar_albaran(
    doc: DocumentoLeido, tabla: TablaEquivalencias, proveedores: list[Proveedor]
) -> AlbaranInterpretado:
    clave, metodo, eventos = _proveedor(doc, proveedores)
    avisos: list[Aviso] = []
    if clave == "DESCONOCIDO":
        avisos.append(Aviso(tipo=TipoAviso.LECTURA_INCOMPLETA, mensaje="Proveedor no identificado"))
    if not doc.numero:
        avisos.append(Aviso(tipo=TipoAviso.LECTURA_INCOMPLETA, mensaje="Número de albarán no leído"))
    lineas: list[LineaAlbaran] = []
    for i, li in enumerate(doc.lineas):
        if li.cantidad is None:
            avisos.append(Aviso(tipo=TipoAviso.LECTURA_INCOMPLETA, mensaje=f"Línea {i + 1} sin cantidad", linea=i))
            continue
        resolucion = tabla.resolver(clave, li.codigo_proveedor) if not li.es_portes else None
        codigo_idm = resolucion.codigo_idm if resolucion else None
        if resolucion is not None:
            eventos.append(
                Evento(
                    "articulo.resuelto",
                    {
                        "linea": i,
                        "codigo_proveedor": li.codigo_proveedor,
                        "codigo_idm": codigo_idm,
                        "metodo": resolucion.metodo,
                    },
                )
            )
            if codigo_idm is None:
                avisos.append(
                    Aviso(
                        tipo=TipoAviso.ARTICULO_NO_RESUELTO,
                        linea=i,
                        mensaje=f"'{li.codigo_proveedor or li.descripcion}' sin equivalencia a código IDM",
                    )
                )
        lineas.append(
            LineaAlbaran(
                codigo_proveedor=li.codigo_proveedor,
                codigo_idm=codigo_idm,
                descripcion=li.descripcion,
                cantidad=li.cantidad,
                unidad=li.unidad or "UD",
                precio_bruto=li.precio_bruto,
                descuento_pct=li.descuento_pct if li.descuento_pct is not None else CERO,
                es_portes=li.es_portes,
                metodo_resolucion=resolucion.metodo if resolucion else None,
            )
        )
    numero_original = doc.numero or f"SIN-NUMERO-{doc.sha256[:8]}"
    albaran = Albaran(
        proveedor=clave,
        numero_original=numero_original,
        numero=normalizar_numero(clave, numero_original),
        fecha=doc.fecha,
        nuestro_pedido=doc.nuestro_pedido,
        lineas=lineas,
        sha256=doc.sha256,
    )
    return AlbaranInterpretado(albaran=albaran, proveedor_metodo=metodo, avisos=avisos, eventos=eventos)


def interpretar_factura(doc: DocumentoLeido, proveedores: list[Proveedor]) -> FacturaInterpretada:
    clave, metodo, eventos = _proveedor(doc, proveedores)
    avisos: list[Aviso] = []
    if clave == "DESCONOCIDO":
        avisos.append(Aviso(tipo=TipoAviso.LECTURA_INCOMPLETA, mensaje="Proveedor no identificado"))
    lineas = [
        LineaFactura(
            albaran=li.albaran,
            codigo_proveedor=li.codigo_proveedor,
            descripcion=li.descripcion,
            cantidad=li.cantidad if li.cantidad is not None else CERO,
            precio_bruto=li.precio_bruto,
            descuento_pct=li.descuento_pct if li.descuento_pct is not None else CERO,
            es_portes=li.es_portes,
        )
        for li in doc.lineas
        if li.precio_bruto is not None
    ]
    if len(lineas) != len(doc.lineas):
        avisos.append(Aviso(tipo=TipoAviso.LECTURA_INCOMPLETA, mensaje="Alguna línea de la factura no trae precio"))
    factura = Factura(
        proveedor=clave,
        numero=doc.numero or f"SIN-NUMERO-{doc.sha256[:8]}",
        fecha=doc.fecha,
        albaranes=list(doc.albaranes_referenciados),
        lineas=lineas,
        base=doc.base,
        iva=doc.iva,
        total=doc.total,
        sha256=doc.sha256,
    )
    return FacturaInterpretada(factura=factura, proveedor_metodo=metodo, avisos=avisos, eventos=eventos)
