"""Traza de cada llamada a un proveedor documental: proveedor, modelo, fecha, hash del documento, tiempo, estado,
cuánto devolvió, confianza media, coste estimado y request id. Se escribe en datos/llamadas_documentales.jsonl.
Se construye campo a campo desde valores permitidos: nunca claves, cabeceras, cuerpo ni texto del documento."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from idm.documental.modelo import ResultadoDocumental


class LlamadaDocumental(BaseModel):
    proveedor: str
    modelo: str
    externo: bool
    fecha: datetime = Field(default_factory=datetime.now)
    sha256_documento: str
    sha256_enviado: str | None = None
    tiempo_s: float = 0.0
    estado: str  # ok / error_transitorio / error_permanente / rechazado_privacidad
    error: str | None = None
    campos_recibidos: dict[str, int] = Field(default_factory=dict)
    confianza_media: float | None = None
    paginas: int = 0
    coste_estimado_eur: Decimal | None = None
    request_id: str | None = None
    ejecucion_id: str | None = None

    @classmethod
    def desde_resultado(cls, resultado: ResultadoDocumental, sha256_documento: str) -> "LlamadaDocumental":
        m = resultado.metadatos
        return cls(
            proveedor=m.proveedor,
            modelo=m.modelo,
            externo=m.externo,
            sha256_documento=sha256_documento,
            sha256_enviado=m.sha256_enviado,
            tiempo_s=m.tiempo_s,
            estado="ok",
            campos_recibidos=resultado.resumen_campos(),
            confianza_media=resultado.confianza_media,
            paginas=m.paginas_procesadas,
            coste_estimado_eur=m.coste_estimado_eur,
            request_id=m.request_id,
        )


class RegistroLlamadas(Protocol):
    def registrar(self, llamada: LlamadaDocumental) -> None: ...


class RegistroMemoria:
    def __init__(self) -> None:
        self.llamadas: list[LlamadaDocumental] = []

    def registrar(self, llamada: LlamadaDocumental) -> None:
        self.llamadas.append(llamada)


class RegistroJSONL:
    def __init__(self, ruta: Path) -> None:
        self.ruta = Path(ruta)

    def registrar(self, llamada: LlamadaDocumental) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(llamada.model_dump(mode="json"), ensure_ascii=False) + "\n")
