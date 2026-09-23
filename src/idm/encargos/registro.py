"""Modelo Encargo e interfaz RepositorioEncargos con una implementación en fichero JSONL (datos/encargos.jsonl).
Un encargo nace PENDIENTE, pasa a EN_PEDIDO cuando generar_pedidos lo incluye, o ANULADO a mano.
No genera pedidos ni conoce Siddex."""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from idm.dominio.estados import EstadoEncargo, OrigenEncargo


class Encargo(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    fecha: datetime = Field(default_factory=datetime.now)
    proveedor: str  # clave o nombre tal como lo escribió quien lo registró
    articulo: str  # código IDM si se conoce; si no, texto libre
    descripcion: str = ""
    cantidad: Decimal
    unidad: str = "UD"
    quien: str = ""
    origen: OrigenEncargo = OrigenEncargo.WEB
    estado: EstadoEncargo = EstadoEncargo.PENDIENTE
    pedido: str | None = None  # número del pedido en el que se incluyó
    notas: str = ""


class RepositorioEncargos(Protocol):
    def guardar(self, encargo: Encargo) -> Encargo: ...

    def listar(self, estado: EstadoEncargo | None = None) -> list[Encargo]: ...

    def obtener(self, id_encargo: str) -> Encargo | None: ...

    def marcar(self, ids: list[str], estado: EstadoEncargo, pedido: str | None = None) -> int: ...


class EncargosJSONL:
    """Una línea JSON por encargo; el estado más reciente de cada id gana. Sencillo y legible con un editor."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = Path(ruta)

    def _todos(self) -> dict[str, Encargo]:
        if not self.ruta.exists():
            return {}
        encargos: dict[str, Encargo] = {}
        with self.ruta.open(encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    e = Encargo.model_validate_json(linea)
                    encargos[e.id] = e
        return encargos

    def _anadir(self, encargo: Encargo) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(encargo.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def guardar(self, encargo: Encargo) -> Encargo:
        self._anadir(encargo)
        return encargo

    def listar(self, estado: EstadoEncargo | None = None) -> list[Encargo]:
        encargos = sorted(self._todos().values(), key=lambda e: e.fecha)
        return [e for e in encargos if estado is None or e.estado == estado]

    def obtener(self, id_encargo: str) -> Encargo | None:
        return self._todos().get(id_encargo)

    def marcar(self, ids: list[str], estado: EstadoEncargo, pedido: str | None = None) -> int:
        todos = self._todos()
        n = 0
        for id_encargo in ids:
            if (e := todos.get(id_encargo)) is not None:
                e.estado = estado
                if pedido:
                    e.pedido = pedido
                self._anadir(e)
                n += 1
        return n
