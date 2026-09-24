"""Extrae texto y tablas de un PDF con pdfplumber y decide si el documento "tiene texto" (> 80 caracteres).
Si no tiene texto (escaneo) o es una imagen (jpg/png), la lectura va por el lector de imagen.
No interpreta nada: devuelve texto crudo y tablas crudas."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

UMBRAL_TEXTO = 80
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif", ".hif", ".webp", ".bmp"}
EXTENSIONES_PDF = {".pdf"}
EXTENSIONES_EXCEL = {".xls", ".xlsx", ".xlsm", ".csv", ".ods"}


@dataclass
class Extraccion:
    texto: str = ""
    tablas: list[list[list[str | None]]] = field(default_factory=list)
    paginas: int = 0

    @property
    def tiene_texto(self) -> bool:
        return len(self.texto.strip()) > UMBRAL_TEXTO


def sha256_fichero(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def es_imagen(ruta: Path) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_IMAGEN


def es_pdf(ruta: Path) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_PDF


def es_excel(ruta: Path) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_EXCEL


def extraer_pdf(ruta: Path) -> Extraccion:
    resultado = Extraccion()
    with pdfplumber.open(str(ruta)) as pdf:
        resultado.paginas = len(pdf.pages)
        trozos = []
        for pagina in pdf.pages:
            trozos.append(pagina.extract_text() or "")
            for tabla in pagina.extract_tables() or []:
                if tabla and len(tabla) > 1:
                    resultado.tablas.append(tabla)
        resultado.texto = "\n".join(trozos)
    return resultado


def extraer(ruta: Path) -> Extraccion:
    """PDF → texto y tablas; imagen → extracción vacía (sin texto), para que el despachador elija lector de imagen."""
    if es_pdf(ruta):
        return extraer_pdf(ruta)
    return Extraccion()
