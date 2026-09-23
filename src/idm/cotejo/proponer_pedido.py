"""Albarán sin pedido → pedido propuesto con las líneas del albarán, para que Fernandillo lo confirme.
El precio sale del albarán; si el albarán no lo trae, del maestro; si tampoco, cero y aviso.
No graba nada en Siddex: el pedido propuesto se confirma en la bandeja y se exporta como los demás."""

from idm.dominio.dinero import CERO
from idm.dominio.estados import OrigenEncargo, RelacionPedido
from idm.dominio.modelos import Albaran, Articulo, LineaPedido, Pedido


def proponer(albaran: Albaran, articulos: dict[str, Articulo]) -> Pedido:
    lineas: list[LineaPedido] = []
    for li in albaran.lineas:
        if li.es_portes:
            continue
        art = articulos.get(li.codigo_idm) if li.codigo_idm else None
        precio = li.precio_bruto
        if precio is None and art and art.precio_compra is not None:
            precio = art.precio_compra
        lineas.append(
            LineaPedido(
                codigo_idm=li.codigo_idm or (li.codigo_proveedor or "SIN-CODIGO"),
                codigo_proveedor=li.codigo_proveedor,
                descripcion=art.descripcion if art and art.descripcion else li.descripcion,
                cantidad=li.cantidad,
                unidad=li.unidad,
                precio_bruto=precio if precio is not None else CERO,
                descuento_pct=li.descuento_pct if li.precio_bruto is not None else (art.descuento_pct if art else CERO),
            )
        )
    return Pedido(
        numero=f"PP-{albaran.numero}",
        proveedor=albaran.proveedor,
        fecha=albaran.fecha,
        lineas=lineas,
        relacion=RelacionPedido.PEDIDO_PROPUESTO,
        origen=OrigenEncargo.ALBARAN,
    )
