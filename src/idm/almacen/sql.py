"""Modelos SQLAlchemy 2 (documentos, eventos, encargos, pedidos) y RepositorioSQL / EncargosSQL sobre una sesión.
Las columnas indexadas son las que se filtran; el detalle completo va en JSON (dump de los modelos Pydantic).
Funciona con SQLite y con PostgreSQL cambiando DATABASE_URL; el esquema lo gestiona Alembic (migrations/)."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from idm.almacen.documentos import ConflictoDuplicado, DocumentoRegistrado, Ejecucion, Evento
from idm.dominio.estados import EstadoDocumento, EstadoEncargo, Semaforo, TipoDocumento
from idm.dominio.modelos import Albaran, Pedido
from idm.encargos.registro import Encargo


class Base(DeclarativeBase):
    pass


class DocumentoORM(Base):
    __tablename__ = "documentos"
    __table_args__ = (UniqueConstraint("proveedor", "tipo", "numero", name="uq_documento_proveedor_tipo_numero"),)
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tipo: Mapped[str] = mapped_column(String(12), index=True)
    proveedor: Mapped[str] = mapped_column(String(40), index=True)
    numero: Mapped[str] = mapped_column(String(60))
    recibido: Mapped[datetime] = mapped_column(DateTime, index=True)
    estado: Mapped[str] = mapped_column(String(12), index=True)
    semaforo: Mapped[str | None] = mapped_column(String(6), index=True)
    pedido: Mapped[str | None] = mapped_column(String(40))
    numero_registro_siddex: Mapped[str | None] = mapped_column(String(20))
    datos: Mapped[dict] = mapped_column(JSON)  # DocumentoRegistrado completo


class EventoORM(Base):
    __tablename__ = "eventos"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, index=True)
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    documento_id: Mapped[str | None] = mapped_column(String(12), index=True)
    ejecucion_id: Mapped[str | None] = mapped_column(String(12), index=True)
    datos: Mapped[dict] = mapped_column(JSON)


class EjecucionORM(Base):
    __tablename__ = "ejecuciones"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    tarea: Mapped[str] = mapped_column(String(40), index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime, index=True)
    fin: Mapped[datetime | None] = mapped_column(DateTime)
    version: Mapped[str] = mapped_column(String(20), default="")
    n_documentos: Mapped[int] = mapped_column(Integer, default=0)
    n_nuevos: Mapped[int] = mapped_column(Integer, default=0)
    n_duplicados: Mapped[int] = mapped_column(Integer, default=0)
    n_no_procesables: Mapped[int] = mapped_column(Integer, default=0)
    n_errores: Mapped[int] = mapped_column(Integer, default=0)
    detalle: Mapped[dict] = mapped_column(JSON, default=dict)


class EncargoORM(Base):
    __tablename__ = "encargos"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, index=True)
    proveedor: Mapped[str] = mapped_column(String(80))
    articulo: Mapped[str] = mapped_column(String(80))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    cantidad: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unidad: Mapped[str] = mapped_column(String(10), default="UD")
    quien: Mapped[str] = mapped_column(String(40), default="")
    origen: Mapped[str] = mapped_column(String(12))
    estado: Mapped[str] = mapped_column(String(12), index=True)
    pedido: Mapped[str | None] = mapped_column(String(40))
    notas: Mapped[str] = mapped_column(Text, default="")


class PedidoORM(Base):
    __tablename__ = "pedidos"
    numero: Mapped[str] = mapped_column(String(40), primary_key=True)
    proveedor: Mapped[str] = mapped_column(String(40), index=True)
    fecha: Mapped[datetime | None] = mapped_column(DateTime)
    relacion: Mapped[str] = mapped_column(String(20))
    origen: Mapped[str | None] = mapped_column(String(20))
    numero_siddex: Mapped[str | None] = mapped_column(String(40))
    datos: Mapped[dict] = mapped_column(JSON)


def _fila_documento(d: DocumentoRegistrado) -> DocumentoORM:
    return DocumentoORM(
        id=d.id,
        sha256=d.sha256,
        tipo=d.tipo,
        proveedor=d.proveedor,
        numero=d.numero,
        recibido=d.recibido,
        estado=d.estado,
        semaforo=d.semaforo,
        pedido=d.pedido,
        numero_registro_siddex=d.numero_registro_siddex,
        datos=d.model_dump(mode="json"),
    )


class RepositorioSQL:
    """Implementa almacen.documentos.Repositorio sobre una Session. Cada método hace commit."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def _a_modelo(self, fila: DocumentoORM | None) -> DocumentoRegistrado | None:
        return DocumentoRegistrado.model_validate(fila.datos) if fila else None

    def existe_sha(self, sha256: str) -> DocumentoRegistrado | None:
        return self._a_modelo(self.sesion.scalar(select(DocumentoORM).where(DocumentoORM.sha256 == sha256)))

    def existe_numero(self, proveedor: str, tipo: TipoDocumento, numero: str) -> DocumentoRegistrado | None:
        consulta = select(DocumentoORM).where(
            DocumentoORM.proveedor == proveedor, DocumentoORM.tipo == tipo, DocumentoORM.numero == numero
        )
        return self._a_modelo(self.sesion.scalar(consulta))

    def guardar(self, documento: DocumentoRegistrado) -> DocumentoRegistrado:
        fila = self.sesion.get(DocumentoORM, documento.id)
        nueva = _fila_documento(documento)
        if fila is None:
            self.sesion.add(nueva)
        else:
            for col in (
                "tipo",
                "proveedor",
                "numero",
                "estado",
                "semaforo",
                "pedido",
                "numero_registro_siddex",
                "datos",
            ):
                setattr(fila, col, getattr(nueva, col))
        try:
            self.sesion.commit()
        except IntegrityError as exc:
            # Carrera entre dos procesos o duplicado no detectado antes: la BD manda, se traduce a excepción propia
            self.sesion.rollback()
            texto = str(exc.orig).lower()
            campo = "sha256" if "sha256" in texto else "numero"
            valor = (
                documento.sha256 if campo == "sha256" else f"{documento.proveedor}/{documento.tipo}/{documento.numero}"
            )
            raise ConflictoDuplicado(campo, valor) from exc
        return documento

    def obtener(self, id_documento: str) -> DocumentoRegistrado | None:
        return self._a_modelo(self.sesion.get(DocumentoORM, id_documento))

    def listar(
        self,
        estado: EstadoDocumento | None = None,
        semaforo: Semaforo | None = None,
        proveedor: str | None = None,
        tipo: TipoDocumento | None = None,
    ) -> list[DocumentoRegistrado]:
        consulta = select(DocumentoORM).order_by(DocumentoORM.recibido.desc())
        if estado:
            consulta = consulta.where(DocumentoORM.estado == estado)
        if semaforo:
            consulta = consulta.where(DocumentoORM.semaforo == semaforo)
        if proveedor:
            consulta = consulta.where(DocumentoORM.proveedor == proveedor)
        if tipo:
            consulta = consulta.where(DocumentoORM.tipo == tipo)
        return [DocumentoRegistrado.model_validate(f.datos) for f in self.sesion.scalars(consulta)]

    def albaranes_de(self, proveedor: str) -> list[Albaran]:
        filas = self.sesion.scalars(
            select(DocumentoORM).where(
                DocumentoORM.proveedor == proveedor,
                DocumentoORM.tipo == TipoDocumento.ALBARAN,
                DocumentoORM.estado != EstadoDocumento.RECHAZADO,
            )
        )
        return [Albaran.model_validate(f.datos["albaran"]) for f in filas if f.datos.get("albaran")]

    def registrar_evento(self, evento: Evento) -> Evento:
        self.sesion.add(
            EventoORM(
                id=evento.id,
                fecha=evento.fecha,
                tipo=evento.tipo,
                documento_id=evento.documento_id,
                ejecucion_id=evento.ejecucion_id,
                datos=evento.model_dump(mode="json")["datos"],
            )
        )
        self.sesion.commit()
        return evento

    def eventos(self, documento_id: str | None = None) -> list[Evento]:
        consulta = select(EventoORM).order_by(EventoORM.fecha)
        if documento_id:
            consulta = consulta.where(EventoORM.documento_id == documento_id)
        return [
            Evento(
                id=f.id,
                fecha=f.fecha,
                tipo=f.tipo,
                documento_id=f.documento_id,
                ejecucion_id=f.ejecucion_id,
                datos=f.datos,
            )
            for f in self.sesion.scalars(consulta)
        ]

    def guardar_ejecucion(self, ejecucion: Ejecucion) -> Ejecucion:
        fila = self.sesion.get(EjecucionORM, ejecucion.id)
        datos = ejecucion.model_dump(mode="json")
        if fila is None:
            self.sesion.add(
                EjecucionORM(
                    **{
                        k: getattr(ejecucion, k)
                        for k in (
                            "id",
                            "tarea",
                            "inicio",
                            "fin",
                            "version",
                            "n_documentos",
                            "n_nuevos",
                            "n_duplicados",
                            "n_no_procesables",
                            "n_errores",
                        )
                    },
                    detalle=datos["detalle"],
                )
            )
        else:
            for k in ("fin", "n_documentos", "n_nuevos", "n_duplicados", "n_no_procesables", "n_errores"):
                setattr(fila, k, getattr(ejecucion, k))
            fila.detalle = datos["detalle"]
        self.sesion.commit()
        return ejecucion

    def ejecuciones(self, limite: int = 50) -> list[Ejecucion]:
        consulta = select(EjecucionORM).order_by(EjecucionORM.inicio.desc()).limit(limite)
        return [
            Ejecucion(
                id=f.id,
                tarea=f.tarea,
                inicio=f.inicio,
                fin=f.fin,
                version=f.version,
                n_documentos=f.n_documentos,
                n_nuevos=f.n_nuevos,
                n_duplicados=f.n_duplicados,
                n_no_procesables=f.n_no_procesables,
                n_errores=f.n_errores,
                detalle=f.detalle or {},
            )
            for f in self.sesion.scalars(consulta)
        ]

    def guardar_pedido(self, pedido: Pedido) -> Pedido:
        fila = self.sesion.get(PedidoORM, pedido.numero)
        datos = pedido.model_dump(mode="json")
        fecha = datetime.combine(pedido.fecha, datetime.min.time()) if pedido.fecha else None
        if fila is None:
            self.sesion.add(
                PedidoORM(
                    numero=pedido.numero,
                    proveedor=pedido.proveedor,
                    fecha=fecha,
                    relacion=pedido.relacion,
                    origen=pedido.origen,
                    numero_siddex=pedido.numero_siddex,
                    datos=datos,
                )
            )
        else:
            fila.relacion, fila.numero_siddex, fila.datos = pedido.relacion, pedido.numero_siddex, datos
        self.sesion.commit()
        return pedido

    def pedidos(self, proveedor: str | None = None) -> list[Pedido]:
        consulta = select(PedidoORM).order_by(PedidoORM.fecha.desc())
        if proveedor:
            consulta = consulta.where(PedidoORM.proveedor == proveedor)
        return [Pedido.model_validate(f.datos) for f in self.sesion.scalars(consulta)]


class EncargosSQL:
    """Implementa encargos.registro.RepositorioEncargos sobre la misma base de datos."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    @staticmethod
    def _a_modelo(f: EncargoORM) -> Encargo:
        return Encargo(
            id=f.id,
            fecha=f.fecha,
            proveedor=f.proveedor,
            articulo=f.articulo,
            descripcion=f.descripcion,
            cantidad=Decimal(f.cantidad),
            unidad=f.unidad,
            quien=f.quien,
            origen=f.origen,
            estado=f.estado,
            pedido=f.pedido,
            notas=f.notas,
        )

    def guardar(self, encargo: Encargo) -> Encargo:
        self.sesion.add(
            EncargoORM(
                id=encargo.id,
                fecha=encargo.fecha,
                proveedor=encargo.proveedor,
                articulo=encargo.articulo,
                descripcion=encargo.descripcion,
                cantidad=encargo.cantidad,
                unidad=encargo.unidad,
                quien=encargo.quien,
                origen=encargo.origen,
                estado=encargo.estado,
                pedido=encargo.pedido,
                notas=encargo.notas,
            )
        )
        self.sesion.commit()
        return encargo

    def listar(self, estado: EstadoEncargo | None = None) -> list[Encargo]:
        consulta = select(EncargoORM).order_by(EncargoORM.fecha)
        if estado:
            consulta = consulta.where(EncargoORM.estado == estado)
        return [self._a_modelo(f) for f in self.sesion.scalars(consulta)]

    def obtener(self, id_encargo: str) -> Encargo | None:
        f = self.sesion.get(EncargoORM, id_encargo)
        return self._a_modelo(f) if f else None

    def marcar(self, ids: list[str], estado: EstadoEncargo, pedido: str | None = None) -> int:
        n = 0
        for id_encargo in ids:
            if (f := self.sesion.get(EncargoORM, id_encargo)) is not None:
                f.estado = estado
                if pedido:
                    f.pedido = pedido
                n += 1
        self.sesion.commit()
        return n
