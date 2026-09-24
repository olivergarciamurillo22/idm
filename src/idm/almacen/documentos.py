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
    Semaforo,
    TipoDocumento,
)
from idm.dominio.modelos import Albaran, Cotejo, DocumentoLeido, ErrorProcesamiento, Factura, Pedido


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


class RepositorioMemoria:
    def __init__(self) -> None:
        self._docs: dict[str, DocumentoRegistrado] = {}
        self._eventos: list[Evento] = []

    def existe_sha(self, sha256: str) -> DocumentoRegistrado | None:
        return next((d for d in self._docs.values() if d.sha256 == sha256), None)

    def existe_numero(self, proveedor: str, tipo: TipoDocumento, numero: str) -> DocumentoRegistrado | None:
        return next(
            (d for d in self._docs.values() if d.proveedor == proveedor and d.tipo == tipo and d.numero == numero), None
        )

    def guardar(self, documento: DocumentoRegistrado) -> DocumentoRegistrado:
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
