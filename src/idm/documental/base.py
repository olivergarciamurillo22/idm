"""Contrato DocumentProvider (analizar(DocumentoEntrada) -> ResultadoDocumental) y errores tipados de proveedor.
ProveedorExternoBase obliga a pasar por la política de envío externo ANTES de construir ninguna petición.
Se llama DocumentProvider y no "proveedor" para no confundirlo con el proveedor de IDM (quien envía el albarán)."""

import time
from dataclasses import dataclass
from typing import Protocol

from idm.documental.modelo import ResultadoDocumental
from idm.documental.privacidad import PoliticaEnvioExterno


@dataclass(frozen=True)
class DocumentoEntrada:
    """Lo que se entrega al proveedor: bytes ya normalizados (HEIC → JPEG), tipo MIME y la huella del original."""

    contenido: bytes
    tipo_mime: str
    sha256_original: str
    sha256_enviado: str
    nombre: str
    nota: str | None = None  # p. ej. "recomprimida de 7,9 MB a 3,8 MB para el límite del proveedor"

    def __repr__(self) -> str:  # nunca volcar el contenido en logs
        return f"DocumentoEntrada({self.nombre!r}, {self.tipo_mime}, {len(self.contenido)} bytes)"


class ErrorProveedorDocumental(Exception):
    recuperable = False
    codigo = "PROVEEDOR_DOCUMENTAL_ERROR"

    def __init__(self, mensaje: str, request_id: str | None = None, estado_http: int | None = None) -> None:
        super().__init__(mensaje)
        self.request_id = request_id
        self.estado_http = estado_http


class ErrorTransitorio(ErrorProveedorDocumental):
    """Red, 429, 5xx, tiempo agotado: el documento queda pendiente de reintento. NUNCA se manda a otro tercero solo."""

    recuperable = True
    codigo = "PROVEEDOR_DOCUMENTAL_NO_DISPONIBLE"


class ErrorPermanente(ErrorProveedorDocumental):
    """Credenciales, documento rechazado, configuración: reintentar igual no sirve; hay que actuar."""

    codigo = "PROVEEDOR_DOCUMENTAL_ERROR"


class ProcesamientoExternoNoAutorizado(ErrorProveedorDocumental):
    codigo = "PROCESAMIENTO_EXTERNO_NO_AUTORIZADO"


class ConfiguracionDocumentalInvalida(Exception):
    """Configuración imposible (proveedor desconocido, faltan credenciales, externo sin autorización)."""


class DocumentProvider(Protocol):
    nombre: str
    modelo: str
    externo: bool

    def disponible(self) -> bool: ...

    def analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental: ...


class ProveedorExternoBase:
    """Base de los proveedores cloud. analizar() comprueba la política antes de nada; las subclases hacen _analizar.
    No se puede saltar: _analizar no se llama desde fuera de esta clase ni desde el router."""

    nombre = "externo"
    modelo = ""
    externo = True

    def __init__(self, politica: PoliticaEnvioExterno) -> None:
        self._politica = politica

    def analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental:
        self._politica.comprobar(self.nombre)  # lanza ProcesamientoExternoNoAutorizado: no sale ni un byte
        inicio = time.perf_counter()
        resultado = self._analizar(documento)
        resultado.metadatos.tiempo_s = round(time.perf_counter() - inicio, 2)
        resultado.metadatos.sha256_enviado = documento.sha256_enviado
        resultado.metadatos.tipo_enviado = documento.tipo_mime
        return resultado

    def _analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental:  # pragma: no cover - abstracto
        raise NotImplementedError
