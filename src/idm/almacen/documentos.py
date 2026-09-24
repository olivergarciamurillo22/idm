"""DocumentoRegistrado (lo que se guarda de cada documento) e interfaz Repositorio con implementación en memoria.
Idempotencia: existe(sha256) y existe(proveedor, tipo, número normalizado) antes de guardar.
La implementación SQL está en almacen/sql.py; esta no persiste nada."""

import uuid
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field

from idm.dominio.estados import (
    EstadoDocumento,
    EstadoEntrega,
    EstadoPrecio,
    RelacionPedido,
    ResultadoLectura,
    Semaforo,
    TipoDocumento,
)
from idm.dominio.modelos import Albaran, Cotejo, DocumentoLeido, ErrorProcesamiento, Factura, Pedido


class ConflictoDuplicado(Exception):
    """Otro proceso guardó antes un documento con el mismo sha256 o el mismo (proveedor, tipo, número)."""

    def __init__(self, campo: str, valor: str) -> None:
        super().__init__(f"Ya existe un documento con {campo}={valor}")
        self.campo, self.valor = campo, valor


class ArticuloTrazado(BaseModel):
    linea: int
    codigo_proveedor: str | None
    codigo_idm: str | None
    metodo: str | None


class ReglaTrazada(BaseModel):
    linea: int | None
    regla: str
    resultado: str
    detalle: str = ""


class Traza(BaseModel):
    """Qué ocurrió con un documento en una ejecución: la explicación completa, legible sin abrir el código."""

    ejecucion_id: str | None = None
    version: str
    inicio: datetime
    fin: datetime | None = None
    fichero: str
    sha256: str
    origen: str
    resultado_lectura: ResultadoLectura | None = None
    metodo_lectura: str | None = None
    confianza: float | None = None
    tipo: TipoDocumento = TipoDocumento.DESCONOCIDO
    proveedor: str | None = None
    proveedor_metodo: str | None = None
    campos_extraidos: dict[str, str | None] = Field(default_factory=dict)
    normalizaciones: list[str] = Field(default_factory=list)
    articulos: list[ArticuloTrazado] = Field(default_factory=list)
    pedido: str | None = None
    pedido_metodo: str | None = None
    pedido_propuesto: str | None = None
    albaranes_relacionados: list[str] = Field(default_factory=list)
    albaranes_no_encontrados: list[str] = Field(default_factory=list)
    factura: str | None = None
    reglas: list[ReglaTrazada] = Field(default_factory=list)
    diferencias: list[str] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)
    estado_final: EstadoDocumento | None = None
    semaforo: Semaforo | None = None
    reproceso: int = 0


class Ejecucion(BaseModel):
    """Una pasada de procesar_buzon (o de un reproceso): agrupa documentos y eventos y guarda el resumen."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    tarea: str = "procesar_buzon"
    inicio: datetime = Field(default_factory=datetime.now)
    fin: datetime | None = None
    version: str = ""
    n_documentos: int = 0
    n_nuevos: int = 0
    n_duplicados: int = 0
    n_no_procesables: int = 0
    n_errores: int = 0
    detalle: dict = Field(default_factory=dict)


class DocumentoRegistrado(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    sha256: str
    tipo: TipoDocumento
    proveedor: str
    numero: str  # normalizado
    numero_original: str
    ruta: str
    origen: str = "carpeta"
    recibido: datetime = Field(default_factory=datetime.now)
    estado: EstadoDocumento = EstadoDocumento.RECIBIDO
    relacion: RelacionPedido | None = None
    precio: EstadoPrecio | None = None
    entrega: EstadoEntrega | None = None
    semaforo: Semaforo | None = None
    pedido: str | None = None
    leido: DocumentoLeido | None = None
    albaran: Albaran | None = None
    factura: Factura | None = None
    cotejo: Cotejo | None = None
    cotejo_factura: dict | None = None
    pedido_propuesto: Pedido | None = None
    avisos: list[str] = Field(default_factory=list)
    errores: list[ErrorProcesamiento] = Field(default_factory=list)
    traza: Traza | None = None
    ejecucion_id: str | None = None
    version_procesamiento: str | None = None
    reprocesos: int = 0
    numero_registro_siddex: str | None = None
    decidido_por: str | None = None
    decidido_en: datetime | None = None
    notas: str = ""

    @property
    def n_avisos(self) -> int:
        n = len(self.avisos)
        if self.cotejo:
            n += len(self.cotejo.todos_los_avisos)
        if self.cotejo_factura:
            n += len(self.cotejo_factura.get("avisos", []))
        return n


class Evento(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    fecha: datetime = Field(default_factory=datetime.now)
    tipo: str
    documento_id: str | None = None
    ejecucion_id: str | None = None
    datos: dict = Field(default_factory=dict)


class Repositorio(Protocol):
    def existe_sha(self, sha256: str) -> DocumentoRegistrado | None: ...

    def existe_numero(self, proveedor: str, tipo: TipoDocumento, numero: str) -> DocumentoRegistrado | None: ...

    def guardar(self, documento: DocumentoRegistrado) -> DocumentoRegistrado: ...

    def obtener(self, id_documento: str) -> DocumentoRegistrado | None: ...

    def listar(
        self,
        estado: EstadoDocumento | None = None,
        semaforo: Semaforo | None = None,
        proveedor: str | None = None,
        tipo: TipoDocumento | None = None,
    ) -> list[DocumentoRegistrado]: ...

    def albaranes_de(self, proveedor: str) -> list[Albaran]: ...

    def registrar_evento(self, evento: Evento) -> Evento: ...

    def eventos(self, documento_id: str | None = None) -> list[Evento]: ...

    def guardar_ejecucion(self, ejecucion: Ejecucion) -> Ejecucion: ...

    def ejecuciones(self, limite: int = 50) -> list[Ejecucion]: ...


class RepositorioMemoria:
    def __init__(self) -> None:
        self._docs: dict[str, DocumentoRegistrado] = {}
        self._eventos: list[Evento] = []
        self._ejecuciones: dict[str, Ejecucion] = {}

    def existe_sha(self, sha256: str) -> DocumentoRegistrado | None:
        return next((d for d in self._docs.values() if d.sha256 == sha256), None)

    def existe_numero(self, proveedor: str, tipo: TipoDocumento, numero: str) -> DocumentoRegistrado | None:
        return next(
            (d for d in self._docs.values() if d.proveedor == proveedor and d.tipo == tipo and d.numero == numero), None
        )

    def guardar(self, documento: DocumentoRegistrado) -> DocumentoRegistrado:
        """Mismo contrato que la BD: sha256 único y (proveedor, tipo, número) único entre documentos distintos."""
        for otro in self._docs.values():
            if otro.id == documento.id:
                continue
            if otro.sha256 == documento.sha256:
                raise ConflictoDuplicado("sha256", documento.sha256)
            if (otro.proveedor, otro.tipo, otro.numero) == (documento.proveedor, documento.tipo, documento.numero):
                raise ConflictoDuplicado("numero", f"{documento.proveedor}/{documento.tipo}/{documento.numero}")
        self._docs[documento.id] = documento
        return documento

    def obtener(self, id_documento: str) -> DocumentoRegistrado | None:
        return self._docs.get(id_documento)

    def listar(self, estado=None, semaforo=None, proveedor=None, tipo=None) -> list[DocumentoRegistrado]:
        docs = [
            d
            for d in self._docs.values()
            if (estado is None or d.estado == estado)
            and (semaforo is None or d.semaforo == semaforo)
            and (proveedor is None or d.proveedor == proveedor)
            and (tipo is None or d.tipo == tipo)
        ]
        return sorted(docs, key=lambda d: d.recibido, reverse=True)

    def albaranes_de(self, proveedor: str) -> list[Albaran]:
        return [
            d.albaran
            for d in self._docs.values()
            if d.albaran is not None and d.proveedor == proveedor and d.estado != EstadoDocumento.RECHAZADO
        ]

    def registrar_evento(self, evento: Evento) -> Evento:
        self._eventos.append(evento)
        return evento

    def eventos(self, documento_id: str | None = None) -> list[Evento]:
        return [e for e in self._eventos if documento_id is None or e.documento_id == documento_id]

    def guardar_ejecucion(self, ejecucion: Ejecucion) -> Ejecucion:
        self._ejecuciones[ejecucion.id] = ejecucion
        return ejecucion

    def ejecuciones(self, limite: int = 50) -> list[Ejecucion]:
        return sorted(self._ejecuciones.values(), key=lambda e: e.inicio, reverse=True)[:limite]
