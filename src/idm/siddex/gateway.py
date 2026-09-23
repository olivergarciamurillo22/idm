"""Interfaz SiddexGateway: lo que el resto del programa puede pedirle a Siddex, sin saber cómo se obtiene.
Hoy: proveedores, artículos, equivalencias, pedidos abiertos, stock, pendiente de recibir y escandallos.
No escribe nada: la escritura irá en una interfaz aparte y solo por una vía soportada (ARQUITECTURA §8)."""

from decimal import Decimal
from typing import Protocol

from idm.dominio.modelos import Articulo, Equivalencia, Pedido, Proveedor
from idm.siddex.lectura import Escandallo


class SiddexGateway(Protocol):
    def proveedores(self) -> list[Proveedor]: ...

    def articulos(self) -> dict[str, Articulo]: ...

    def equivalencias(self) -> list[Equivalencia]: ...

    def pedidos_abiertos(self, proveedor: str | None = None) -> list[Pedido]: ...

    def pedido(self, numero: str) -> Pedido | None: ...

    def stock(self) -> dict[str, Decimal]: ...

    def pendiente_recibir(self) -> dict[str, Decimal]: ...

    def escandallo(self, codigo_maquina: str) -> Escandallo | None: ...


class SiddexEscritura(Protocol):
    """Escritura en Siddex. Solo se implementará por una vía que Siddex soporte (importación o API oficial).
    Nunca contra la base de datos de producción por detrás de la aplicación."""

    def crear_pedido(self, pedido: Pedido) -> str: ...

    def crear_entrada(self, numero_pedido: str, albaran: str) -> str: ...
