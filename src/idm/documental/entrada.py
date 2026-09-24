"""Normalización previa al proveedor: del fichero en disco a DocumentoEntrada (bytes + MIME). PDF, JPEG y PNG van tal
cual; para proveedores externos HEIC/HEIF/TIFF/BMP/WEBP se convierten a un JPEG derivado local a resolución completa.
Los locales reciben el original (convertir pierde resolución y aciertos). Los sha de original y enviado, a la traza."""

import hashlib
from pathlib import Path

from idm.albaranes.imagenes import derivado_jpeg, es_imagen, sha256_fichero

MIME_DIRECTOS = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
MIME_IMAGEN = {
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".hif": "image/heif",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


class FormatoNoAdmitido(Exception):
    pass


def preparar(ruta: Path, carpeta_derivados: Path, convertir: bool = True, lado_maximo: int | None = None):
    """Devuelve DocumentoEntrada. convertir=False (proveedor local): el original tal cual, sea cual sea el formato."""
    from idm.documental.base import DocumentoEntrada

    ruta = Path(ruta)
    sha_original = sha256_fichero(ruta)
    extension = ruta.suffix.lower()
    if extension in MIME_DIRECTOS:
        contenido = ruta.read_bytes()
        return DocumentoEntrada(contenido, MIME_DIRECTOS[extension], sha_original, sha_original, ruta.name)
    if es_imagen(ruta) and not convertir:
        return DocumentoEntrada(
            ruta.read_bytes(), MIME_IMAGEN.get(extension, "image/*"), sha_original, sha_original, ruta.name
        )
    if es_imagen(ruta):
        derivado = derivado_jpeg(ruta, carpeta_derivados, lado_maximo)  # lanza ImagenNoLegible si no se abre
        contenido = derivado.read_bytes()
        return DocumentoEntrada(
            contenido, "image/jpeg", sha_original, hashlib.sha256(contenido).hexdigest(), f"{ruta.stem}.jpg"
        )
    raise FormatoNoAdmitido(f"{ruta.suffix} no se envía a proveedores documentales (PDF o imagen)")
