"""Planning × escandallo: necesidad por artículo = Σ (cantidad por máquina × nº de máquinas), agregada por código.
Descuenta stock y pendiente de recibir si se le pasan, redondea al múltiplo de compra y aparta el hierro.
No lee ficheros: recibe líneas de planning, un resolvedor de códigos y un gateway ya construidos."""

import math
from dataclasses import dataclass, field
from decimal import Decimal

from idm.dominio.dinero import CERO, redondear
from idm.dominio.modelos import Articulo
from idm.dominio.reglas import REGLAS_POR_DEFECTO, es_hierro
from idm.necesidades import mapa as mapa_mod
from idm.necesidades.planning import LineaPlanning
from idm.siddex.gateway import SiddexGateway
from idm.siddex.lectura import agregar_compras


@dataclass
class Necesidad:
    codigo: str
    descripcion: str
    unidad: str
    tipo: str
    proveedor: str | None
    cantidad_bruta: Decimal = CERO
    stock: Decimal = CERO
    pendiente_recibir: Decimal = CERO
    cantidad_neta: Decimal = CERO
    multiplo: Decimal = Decimal("1")
    cantidad_pedir: Decimal = CERO
    precio: Decimal | None = None
    importe: Decimal = CERO
    maquinas: dict[str, Decimal] = field(default_factory=dict)  # código máquina → nº de máquinas
    fuera_circuito: bool = False  # hierro: se pide por WhatsApp, sin pedido automático


@dataclass
class ResultadoNecesidades:
    hoja: str
    necesidades: list[Necesidad] = field(default_factory=list)
    fuera_circuito: list[Necesidad] = field(default_factory=list)
    incidencias: list[str] = field(default_factory=list)
    maquinas: dict[str, Decimal] = field(default_factory=dict)

    @property
    def total(self) -> Decimal:
        return redondear(sum((n.importe for n in self.necesidades), CERO))


def redondear_a_multiplo(cantidad: Decimal, multiplo: Decimal) -> Decimal:
    """13 con múltiplo 10 → 20; 0 → 0; múltiplo ≤ 1 → la cantidad tal cual (entera hacia arriba)."""
    if cantidad <= CERO:
        return CERO
    if multiplo <= Decimal("1"):
        return Decimal(math.ceil(cantidad))
    return Decimal(math.ceil(cantidad / multiplo)) * multiplo


def calcular(
    planning: list[LineaPlanning],
    gateway: SiddexGateway,
    mapa: dict[str, mapa_mod.EntradaMapa],
    hoja: str = "",
    descontar_stock: bool = False,
    articulos: dict[str, Articulo] | None = None,
) -> ResultadoNecesidades:
    resultado = ResultadoNecesidades(hoja=hoja)
    articulos = articulos if articulos is not None else gateway.articulos()
    por_codigo: dict[str, Necesidad] = {}

    for linea in planning:
        res = mapa_mod.resolver(linea.producto, mapa)
        if res.codigo is None:
            resultado.incidencias.append(
                f"Fila {linea.fila}: '{linea.producto}' ({res.metodo}, variante {res.variante}) sin código Siddex"
            )
            continue
        escandallo = gateway.escandallo(res.codigo)
        if escandallo is None:
            resultado.incidencias.append(f"Fila {linea.fila}: no hay escandallo para {res.codigo} ('{linea.producto}')")
            continue
        resultado.maquinas[res.codigo] = resultado.maquinas.get(res.codigo, CERO) + linea.cantidad
        for compra in agregar_compras(escandallo).values():
            n = por_codigo.get(compra.codigo)
            if n is None:
                articulo = articulos.get(compra.codigo)
                n = Necesidad(
                    codigo=compra.codigo,
                    descripcion=(articulo.descripcion if articulo and articulo.descripcion else compra.descripcion),
                    unidad=compra.unidad,
                    tipo=compra.tipo,
                    proveedor=articulo.proveedor_habitual if articulo else None,
                    multiplo=articulo.multiplo_compra if articulo else Decimal("1"),
                    precio=(
                        compra.precio if compra.precio is not None else (articulo.precio_compra if articulo else None)
                    ),
                    fuera_circuito=es_hierro(compra.descripcion, REGLAS_POR_DEFECTO),
                )
                por_codigo[compra.codigo] = n
            n.cantidad_bruta += compra.cantidad * linea.cantidad
            n.maquinas[res.codigo] = n.maquinas.get(res.codigo, CERO) + linea.cantidad

    stock = gateway.stock() if descontar_stock else {}
    pendiente = gateway.pendiente_recibir() if descontar_stock else {}
    for n in por_codigo.values():
        n.stock = stock.get(n.codigo, CERO)
        n.pendiente_recibir = pendiente.get(n.codigo, CERO)
        n.cantidad_neta = max(CERO, n.cantidad_bruta - n.stock - n.pendiente_recibir)
        n.cantidad_pedir = redondear_a_multiplo(n.cantidad_neta, n.multiplo)
        n.importe = redondear(n.cantidad_pedir * n.precio) if n.precio is not None else CERO
        if n.precio is None:
            resultado.incidencias.append(f"{n.codigo} {n.descripcion}: sin precio en escandallo ni maestro")
        (resultado.fuera_circuito if n.fuera_circuito else resultado.necesidades).append(n)

    resultado.necesidades.sort(key=lambda n: (n.proveedor or "~", n.codigo))
    resultado.fuera_circuito.sort(key=lambda n: n.codigo)
    return resultado
