"""Normalización previa al proveedor: del fichero en disco a DocumentoEntrada (bytes + MIME). PDF, JPEG y PNG van tal
cual; para proveedores externos HEIC/HEIF/TIFF/BMP/WEBP se convierten a un JPEG derivado local a resolución completa.
Los locales reciben el original (convertir pierde resolución y aciertos). Los sha de original y enviado, a la traza."""

import hashlib
import io
from pathlib import Path

from PIL import Image

from idm.albaranes.imagenes import abrir, derivado_jpeg, es_imagen, sha256_fichero

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


def _ajustar_a_limite(contenido: bytes, max_bytes: int) -> tuple[bytes, str]:
    """JPEG más ligero hasta caber en max_bytes: primero baja la calidad, después reduce el tamaño en pasos del 15 %.
    Nunca por debajo de 1.500 px de lado (a partir de ahí las cifras de una foto de albarán dejan de leerse)."""
    img = abrir(io.BytesIO(contenido)).convert("RGB")
    antes = len(contenido)
    calidad, escala = 85, 1.0
    while True:
        muestra = (
            img if escala == 1.0 else img.resize((int(img.size[0] * escala), int(img.size[1] * escala)), Image.LANCZOS)
        )
        salida = io.BytesIO()
        muestra.save(salida, "JPEG", quality=calidad, optimize=True)
        datos = salida.getvalue()
        if len(datos) <= max_bytes or max(muestra.size) <= 1500:
            break
        if calidad > 70:
            calidad -= 15
        else:
            escala *= 0.85
    if len(datos) > max_bytes:
        raise FormatoNoAdmitido(f"La imagen no cabe en {max_bytes / 1e6:.1f} MB sin perder legibilidad")
    return (
        datos,
        f"recomprimida de {antes / 1e6:.1f} MB a {len(datos) / 1e6:.1f} MB ({max(muestra.size)} px, calidad {calidad})",
    )


def preparar(
    ruta: Path,
    carpeta_derivados: Path,
    convertir: bool = True,
    lado_maximo: int | None = None,
    max_bytes: int | None = None,
):
    """Devuelve DocumentoEntrada. convertir=False (proveedor local): el original tal cual, sea cual sea el formato.
    max_bytes (límite del proveedor externo): una imagen más grande se recomprime; un PDF más grande se rechaza."""
    documento = _preparar(Path(ruta), carpeta_derivados, convertir, lado_maximo)
    if max_bytes is None or len(documento.contenido) <= max_bytes:
        return documento
    if documento.tipo_mime == "application/pdf":
        raise FormatoNoAdmitido(
            f"El PDF pesa {len(documento.contenido) / 1e6:.1f} MB y el proveedor admite {max_bytes / 1e6:.1f} MB"
        )
    from idm.documental.base import DocumentoEntrada

    datos, nota = _ajustar_a_limite(documento.contenido, max_bytes)
    return DocumentoEntrada(
        datos, "image/jpeg", documento.sha256_original, hashlib.sha256(datos).hexdigest(), documento.nombre, nota
    )


def _preparar(ruta: Path, carpeta_derivados: Path, convertir: bool, lado_maximo: int | None):
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
