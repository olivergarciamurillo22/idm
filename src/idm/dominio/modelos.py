"""Modelos Pydantic del dominio: proveedor, artículo, equivalencia, pedido, albarán, factura, cotejo, aviso.
Importes en Decimal; los importes de línea se calculan aquí con dinero.importe_linea.
No sabe de tablas de Siddex, de la base de datos ni de cómo se leyó el documento."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from idm.dominio.dinero import CERO, importe_linea, redondear
from idm.dominio.estados import (
    CodigoError,
    EstadoEntrega,
    EstadoPrecio,
    RelacionPedido,
    ResultadoLectura,
    Semaforo,
    TipoAviso,
    TipoDocumento,
)


def _normalizar_codigo(codigo: str | None) -> str | None:
    """Códigos de artículo: sin espacios alrededor y en mayúsculas ('i33.000.786' → 'I33.000.786')."""
    if codigo is None:
        return None
    limpio = codigo.strip().upper()
    return limpio or None


class Proveedor(BaseModel):
    clave: str  # identificador interno estable, p. ej. "LA_CEPA"
    codigo_siddex: str | None = None
    nombre: str
    cif: str | None = None
    email: str | None = None
    alias: list[str] = Field(default_factory=list)  # otros nombres con los que aparece


class Articulo(BaseModel):
    codigo: str
    descripcion: str = ""
    unidad: str = "UD"
    proveedor_habitual: str | None = None  # clave de proveedor
    precio_compra: Decimal | None = None
    descuento_pct: Decimal = CERO
    multiplo_compra: Decimal = Decimal("1")  # caja, rollo, bolsa
    tipo: str | None = None  # Comercial, MP...

    @field_validator("codigo", mode="before")
    @classmethod
    def _codigo(cls, v: str) -> str:
        return _normalizar_codigo(v) or v


class Equivalencia(BaseModel):
    proveedor: str  # clave
    codigo_proveedor: str
    codigo_idm: str
    descripcion_proveedor: str = ""


class LineaPedido(BaseModel):
    codigo_idm: str
    descripcion: str = ""
    cantidad: Decimal
    unidad: str = "UD"
    precio_bruto: Decimal
    descuento_pct: Decimal = CERO
    codigo_proveedor: str | None = None
    cantidad_recibida: Decimal = CERO

    @field_validator("codigo_idm", "codigo_proveedor", mode="before")
    @classmethod
    def _codigos(cls, v: str | None) -> str | None:
        return _normalizar_codigo(v)

    @property
    def pendiente(self) -> Decimal:
        return self.cantidad - self.cantidad_recibida

    @property
    def importe(self) -> Decimal:
        return importe_linea(self.cantidad, self.precio_bruto, self.descuento_pct)


class Pedido(BaseModel):
    numero: str
    proveedor: str  # clave
    fecha: date | None = None
    lineas: list[LineaPedido] = Field(default_factory=list)
    relacion: RelacionPedido = RelacionPedido.CON_PEDIDO
    numero_siddex: str | None = None
    origen: str | None = None

    @property
    def total(self) -> Decimal:
        return redondear(sum((linea.importe for linea in self.lineas), CERO))


class LineaAlbaran(BaseModel):
    codigo_proveedor: str | None = None
    codigo_idm: str | None = None
    descripcion: str = ""
    cantidad: Decimal
    unidad: str = "UD"
    precio_bruto: Decimal | None = None  # None = el precio llega con la factura
    descuento_pct: Decimal = CERO
    es_portes: bool = False
    metodo_resolucion: str | None = None  # cómo se llegó a codigo_idm

    @field_validator("codigo_idm", "codigo_proveedor", mode="before")
    @classmethod
    def _codigos(cls, v: str | None) -> str | None:
        return _normalizar_codigo(v)

    @property
    def importe(self) -> Decimal | None:
        if self.precio_bruto is None:
            return None
        return importe_linea(self.cantidad, self.precio_bruto, self.descuento_pct)


class Albaran(BaseModel):
    proveedor: str  # clave
    numero_original: str
    numero: str  # normalizado según reglas del proveedor
    fecha: date | None = None
    nuestro_pedido: str | None = None
    lineas: list[LineaAlbaran] = Field(default_factory=list)
    sha256: str | None = None

    @property
    def total(self) -> Decimal | None:
        importes = [linea.importe for linea in self.lineas]
        if any(i is None for i in importes):
            return None
        return redondear(sum(importes, CERO))


class LineaFactura(BaseModel):
    albaran: str | None = None  # número de albarán del proveedor, tal como viene
    codigo_proveedor: str | None = None
    descripcion: str = ""
    cantidad: Decimal = Decimal("1")
    precio_bruto: Decimal
    descuento_pct: Decimal = CERO
    es_portes: bool = False

    @property
    def importe(self) -> Decimal:
        return importe_linea(self.cantidad, self.precio_bruto, self.descuento_pct)


class Factura(BaseModel):
    proveedor: str
    numero: str
    fecha: date | None = None
    albaranes: list[str] = Field(default_factory=list)  # números tal como vienen en la factura
    lineas: list[LineaFactura] = Field(default_factory=list)
    base: Decimal | None = None
    iva: Decimal | None = None
    total: Decimal | None = None
    sha256: str | None = None


class Aviso(BaseModel):
    tipo: TipoAviso
    mensaje: str
    linea: int | None = None  # índice de línea del albarán (0-based) si aplica
    detalle: dict[str, str] = Field(default_factory=dict)


class ErrorProcesamiento(BaseModel):
    """Error conocido representado como dato, no solo como excepción: se guarda con el documento y se puede filtrar."""

    codigo: CodigoError
    mensaje: str
    recuperable: bool = True  # True = tiene sentido reprocesar (p. ej. Siddex caído); False = hay que actuar a mano
    detalle: dict[str, str] = Field(default_factory=dict)


class ReglaEvaluada(BaseModel):
    """Una regla de cotejo aplicada a una línea, con su resultado. Es la base de la trazabilidad del cotejo."""

    regla: str  # ARTICULO_EN_PEDIDO, CANTIDAD, PRECIO_BRUTO, DESCUENTO, PORTES_PACTADOS
    resultado: str  # OK, AVISO, NO_APLICA
    detalle: str = ""


class CotejoLinea(BaseModel):
    indice_albaran: int
    codigo_idm: str | None
    indice_pedido: int | None
    semaforo: Semaforo
    entrega: EstadoEntrega | None
    precio: EstadoPrecio
    importe_albaran: Decimal | None
    importe_pedido: Decimal | None
    avisos: list[Aviso] = Field(default_factory=list)
    reglas: list[ReglaEvaluada] = Field(default_factory=list)


class LineaPendiente(BaseModel):
    indice_pedido: int
    codigo_idm: str
    cantidad_pendiente: Decimal


class Cotejo(BaseModel):
    proveedor: str
    albaran: str
    pedido: str | None
    relacion: RelacionPedido
    semaforo: Semaforo
    entrega: EstadoEntrega | None
    precio: EstadoPrecio
    lineas: list[CotejoLinea] = Field(default_factory=list)
    avisos: list[Aviso] = Field(default_factory=list)
    pendientes_pedido: list[LineaPendiente] = Field(default_factory=list)
    total_albaran: Decimal | None = None
    total_cotejado_pedido: Decimal | None = None

    @property
    def todos_los_avisos(self) -> list[Aviso]:
        return self.avisos + [a for linea in self.lineas for a in linea.avisos]


class LineaLeida(BaseModel):
    """Una línea tal como la ha sacado el lector, sin interpretar todavía."""

    codigo_proveedor: str | None = None
    descripcion: str = ""
    cantidad: Decimal | None = None
    unidad: str | None = None
    precio_bruto: Decimal | None = None
    descuento_pct: Decimal | None = None
    importe: Decimal | None = None
    albaran: str | None = None  # en facturas: a qué albarán pertenece la línea
    es_portes: bool = False


class DocumentoLeido(BaseModel):
    """Resultado de leer(ruta): lo que dice el documento, sin decisiones."""

    ruta: str
    sha256: str
    tipo: TipoDocumento = TipoDocumento.DESCONOCIDO
    proveedor_texto: str | None = None
    cif: str | None = None
    numero: str | None = None
    fecha: date | None = None
    nuestro_pedido: str | None = None
    albaranes_referenciados: list[str] = Field(default_factory=list)
    lineas: list[LineaLeida] = Field(default_factory=list)
    base: Decimal | None = None
    iva: Decimal | None = None
    total: Decimal | None = None
    metodo: str = "desconocido"  # pdf_texto, imagen_nulo, ...
    resultado: ResultadoLectura = ResultadoLectura.NO_SOPORTADO
    confianza: float = 0.0
    avisos: list[str] = Field(default_factory=list)
    errores: list[ErrorProcesamiento] = Field(default_factory=list)
    texto: str | None = None

    @property
    def leido(self) -> bool:
        return self.resultado == ResultadoLectura.PDF_TEXTO
