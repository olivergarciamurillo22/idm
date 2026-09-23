"""Estados por dimensión (documento, pedido, precio, entrega) y semáforo del cotejo.
Cada enumeración es una dimensión independiente: un documento tiene las cuatro a la vez.
No contiene transiciones ni lógica: eso lo decide el código que cambia el estado."""

from enum import StrEnum


class EstadoDocumento(StrEnum):
    RECIBIDO = "RECIBIDO"
    LEIDO = "LEIDO"
    COTEJADO = "COTEJADO"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class RelacionPedido(StrEnum):
    CON_PEDIDO = "CON_PEDIDO"
    SIN_PEDIDO = "SIN_PEDIDO"
    PEDIDO_PROPUESTO = "PEDIDO_PROPUESTO"


class EstadoPrecio(StrEnum):
    CONOCIDO = "CONOCIDO"
    PENDIENTE_FACTURA = "PENDIENTE_FACTURA"


class EstadoEntrega(StrEnum):
    COMPLETA = "COMPLETA"
    PARCIAL = "PARCIAL"
    EXCESO = "EXCESO"


class Semaforo(StrEnum):
    VERDE = "VERDE"  # todo cuadra: artículo, cantidad, precio y descuento
    AMBAR = "AMBAR"  # algo no cuadra o falta: revisión humana con motivo


class TipoDocumento(StrEnum):
    ALBARAN = "ALBARAN"
    FACTURA = "FACTURA"
    DESCONOCIDO = "DESCONOCIDO"


class TipoAviso(StrEnum):
    SIN_PEDIDO = "SIN_PEDIDO"
    LINEA_SIN_PEDIDO = "LINEA_SIN_PEDIDO"
    ARTICULO_NO_RESUELTO = "ARTICULO_NO_RESUELTO"
    PRECIO_DISTINTO = "PRECIO_DISTINTO"
    DESCUENTO_DISTINTO = "DESCUENTO_DISTINTO"
    EXCESO_CANTIDAD = "EXCESO_CANTIDAD"
    PRECIO_PENDIENTE = "PRECIO_PENDIENTE"
    PORTES_NO_PACTADOS = "PORTES_NO_PACTADOS"
    ALBARAN_NO_ENCONTRADO = "ALBARAN_NO_ENCONTRADO"
    IMPORTE_NO_CUADRA = "IMPORTE_NO_CUADRA"
    PRECIO_CAMBIADO = "PRECIO_CAMBIADO"
    LECTURA_INCOMPLETA = "LECTURA_INCOMPLETA"


class OrigenEncargo(StrEnum):
    PLANNING = "PLANNING"
    WEB = "WEB"
    MENSAJE = "MENSAJE"
    ALBARAN = "ALBARAN"  # pedido propuesto a partir de un albarán sin pedido


class EstadoEncargo(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_PEDIDO = "EN_PEDIDO"
    ANULADO = "ANULADO"
