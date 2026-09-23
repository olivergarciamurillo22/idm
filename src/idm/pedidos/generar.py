"""Agrupa necesidades y encargos por proveedor y construye un Pedido (dominio) por cada uno.
Numera provisionalmente (P-AAAAMMDD-NN); el número de Siddex se asigna cuando se graba allí.
No escribe PDF ni correo: solo devuelve pedidos y qué encargos entraron en cada uno."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from idm.dominio.dinero import CERO
from idm.dominio.estados import OrigenEncargo, RelacionPedido
from idm.dominio.modelos import Articulo, LineaPedido, Pedido, Proveedor
from idm.encargos.registro import Encargo
from idm.equivalencias.proveedores import identificar
from idm.necesidades.calculo import Necesidad


@dataclass
class ResultadoGeneracion:
    pedidos: list[Pedido] = field(default_factory=list)
    encargos_por_pedido: dict[str, list[str]] = field(default_factory=dict)  # nº pedido → ids de encargo
    sin_proveedor: list[str] = field(default_factory=list)


def numero_provisional(fecha: date, indice: int) -> str:
    return f"P-{fecha:%Y%m%d}-{indice:02d}"


def _resolver_proveedor(texto: str, proveedores: list[Proveedor]) -> str | None:
    if any(p.clave == texto for p in proveedores):
        return texto
    clave, _ = identificar(nombre=texto, proveedores=proveedores)
    return clave


def generar(
    necesidades: list[Necesidad],
    encargos: list[Encargo],
    articulos: dict[str, Articulo],
    proveedores: list[Proveedor],
    fecha: date | None = None,
    origen: str = "planning+encargos",
) -> ResultadoGeneracion:
    fecha = fecha or date.today()
    resultado = ResultadoGeneracion()
    por_proveedor: dict[str, list[LineaPedido]] = {}
    encargos_por_proveedor: dict[str, list[str]] = {}

    for n in necesidades:
        if n.cantidad_pedir <= CERO or n.fuera_circuito:
            continue
        if not n.proveedor:
            resultado.sin_proveedor.append(f"{n.codigo} {n.descripcion}: sin proveedor habitual en el maestro")
            continue
        art = articulos.get(n.codigo)
        por_proveedor.setdefault(n.proveedor, []).append(
            LineaPedido(
                codigo_idm=n.codigo,
                descripcion=n.descripcion,
                cantidad=n.cantidad_pedir,
                unidad=n.unidad,
                precio_bruto=n.precio if n.precio is not None else CERO,
                descuento_pct=art.descuento_pct if art else CERO,
            )
        )

    for e in encargos:
        clave = _resolver_proveedor(e.proveedor, proveedores)
        if clave is None:
            resultado.sin_proveedor.append(f"Encargo {e.id} ({e.proveedor} / {e.articulo}): proveedor no reconocido")
            continue
        art = articulos.get(e.articulo.strip().upper())
        lineas = por_proveedor.setdefault(clave, [])
        existente = next((li for li in lineas if art and li.codigo_idm == art.codigo), None)
        if existente is not None:
            existente.cantidad += e.cantidad
        else:
            lineas.append(
                LineaPedido(
                    codigo_idm=art.codigo if art else e.articulo,
                    descripcion=art.descripcion if art else (e.descripcion or e.articulo),
                    cantidad=e.cantidad,
                    unidad=art.unidad if art else e.unidad,
                    precio_bruto=(art.precio_compra if art and art.precio_compra is not None else CERO),
                    descuento_pct=art.descuento_pct if art else CERO,
                )
            )
        encargos_por_proveedor.setdefault(clave, []).append(e.id)

    for indice, (clave, lineas) in enumerate(sorted(por_proveedor.items()), start=1):
        numero = numero_provisional(fecha, indice)
        resultado.pedidos.append(
            Pedido(
                numero=numero,
                proveedor=clave,
                fecha=fecha,
                lineas=lineas,
                relacion=RelacionPedido.CON_PEDIDO,
                origen=origen,
            )
        )
        resultado.encargos_por_pedido[numero] = encargos_por_proveedor.get(clave, [])
    return resultado


def desde_encargo_urgente(
    encargo: Encargo, articulos: dict[str, Articulo], proveedores: list[Proveedor], fecha: date | None = None
) -> ResultadoGeneracion:
    """Un solo encargo → un pedido, para el caso 'llamo ahora y quiero el pedido ya'."""
    r = generar([], [encargo], articulos, proveedores, fecha, origen=OrigenEncargo.WEB)
    return r


def total_lineas(pedido: Pedido) -> Decimal:
    return pedido.total
