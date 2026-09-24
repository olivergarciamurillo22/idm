"""Imágenes de documentos (fotos de móvil): detección de formato (HEIC/HEIF/JPG/PNG/TIF), apertura con orientación EXIF,
derivado JPEG local sin tocar el original (relación original→derivado en derivados.jsonl) e inventario con hash y EXIF.
No hace OCR ni interpreta nada; los derivados nunca deben entrar en git (datos/ está ignorada)."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

try:  # pillow-heif registra el opener HEIC/HEIF en Pillow; si no está, HEIC se detecta pero no se abre
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_DISPONIBLE = True
except ImportError:  # pragma: no cover - depende del entorno
    HEIF_DISPONIBLE = False

EXTENSIONES_HEIC = {".heic", ".heif", ".hif"}
EXTENSIONES_RASTER = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
EXTENSIONES_IMAGEN = EXTENSIONES_HEIC | EXTENSIONES_RASTER
EXIF_ORIENTACION = 0x0112
EXIF_FECHA = 0x9003  # DateTimeOriginal
EXIF_FECHA_ALT = 0x0132
NOMBRE_RELACION = "derivados.jsonl"


def es_heic(ruta: Path) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_HEIC


def es_imagen(ruta: Path) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_IMAGEN


def sha256_fichero(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


class ImagenNoLegible(Exception):
    pass


def abrir(ruta) -> Image.Image:
    """Abre cualquier formato admitido (ruta o fichero en memoria) y aplica la orientación EXIF (una foto de iPhone en
    vertical llega girada)."""
    nombre = getattr(ruta, "name", None) or (Path(ruta).name if isinstance(ruta, str | Path) else "documento")
    if isinstance(ruta, str | Path):
        ruta = Path(ruta)
        if es_heic(ruta) and not HEIF_DISPONIBLE:
            raise ImagenNoLegible(f"{ruta.name}: HEIC sin soporte; instala pillow-heif")
    try:
        img = Image.open(ruta)
        img.load()
    except Exception as exc:  # noqa: BLE001 - Pillow lanza tipos variados según el formato
        raise ImagenNoLegible(f"{nombre}: {type(exc).__name__}: {str(exc)[:200]}") from exc
    return ImageOps.exif_transpose(img) or img


@dataclass
class DatosImagen:
    fichero: str
    tamano_bytes: int
    formato: str | None
    sha256: str
    ancho: int | None
    alto: int | None
    orientacion_exif: int | None
    orientacion: str | None  # vertical / horizontal / cuadrada (tras aplicar EXIF)
    fecha_exif: str | None
    legible: bool
    error: str | None = None
    duplicado_de: str | None = None


def _exif(img: Image.Image) -> tuple[int | None, str | None]:
    try:
        exif = img.getexif()
    except Exception:  # noqa: BLE001
        return None, None
    orientacion = exif.get(EXIF_ORIENTACION)
    fecha = exif.get(EXIF_FECHA) or exif.get(EXIF_FECHA_ALT)
    try:
        fecha_iso = datetime.strptime(str(fecha), "%Y:%m:%d %H:%M:%S").isoformat() if fecha else None
    except ValueError:
        fecha_iso = str(fecha) if fecha else None
    return (int(orientacion) if orientacion else None), fecha_iso


def datos(ruta: Path) -> DatosImagen:
    ruta = Path(ruta)
    sha = sha256_fichero(ruta)
    try:
        crudo = Image.open(ruta)
        formato = crudo.format
        orientacion_exif, fecha = _exif(crudo)
        img = ImageOps.exif_transpose(crudo) or crudo
        ancho, alto = img.size
    except Exception as exc:  # noqa: BLE001
        return DatosImagen(
            ruta.name,
            ruta.stat().st_size,
            None,
            sha,
            None,
            None,
            None,
            None,
            None,
            False,
            f"{type(exc).__name__}: {str(exc)[:120]}",
        )
    orient = "vertical" if alto > ancho else ("horizontal" if ancho > alto else "cuadrada")
    return DatosImagen(ruta.name, ruta.stat().st_size, formato, sha, ancho, alto, orientacion_exif, orient, fecha, True)


def inventariar(carpeta: Path) -> list[DatosImagen]:
    """Inventario de todas las imágenes de una carpeta; marca duplicados exactos por sha256 (misma foto dos veces)."""
    vistos: dict[str, str] = {}
    resultado = []
    for ruta in sorted(
        p for p in Path(carpeta).iterdir() if p.is_file() and es_imagen(p) and not p.name.startswith("._")
    ):
        d = datos(ruta)
        if d.sha256 in vistos:
            d.duplicado_de = vistos[d.sha256]
        else:
            vistos[d.sha256] = d.fichero
        resultado.append(d)
    return resultado


def derivado_jpeg(original: Path, carpeta_derivados: Path, lado_maximo: int | None = None, calidad: int = 92) -> Path:
    """JPEG con orientación ya aplicada, nombrado por el sha del original. Idempotente: si existe, no recomprime.
    Deja la relación original→derivado en derivados.jsonl de la carpeta de derivados."""
    original = Path(original)
    carpeta_derivados = Path(carpeta_derivados)
    carpeta_derivados.mkdir(parents=True, exist_ok=True)
    sha = sha256_fichero(original)
    sufijo = f"_{lado_maximo}" if lado_maximo else ""
    destino = carpeta_derivados / f"{sha}{sufijo}.jpg"
    if destino.exists():
        return destino
    img = abrir(original)
    if lado_maximo and max(img.size) > lado_maximo:
        img.thumbnail((lado_maximo, lado_maximo))
    img.convert("RGB").save(destino, "JPEG", quality=calidad, optimize=True)
    with (carpeta_derivados / NOMBRE_RELACION).open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "original": str(original),
                    "sha256_original": sha,
                    "derivado": str(destino),
                    "lado_maximo": lado_maximo,
                    "fecha": datetime.now().isoformat(),
                }
            )
            + "\n"
        )
    return destino


def escribir_inventario(carpeta: Path, datos_lista: list[DatosImagen]) -> tuple[Path, Path]:
    """inventario.json (completo) e inventario.md (tabla) dentro de la carpeta analizada. Sin datos de negocio."""
    carpeta = Path(carpeta)
    ruta_json = carpeta / "inventario.json"
    ruta_json.write_text(json.dumps([asdict(d) for d in datos_lista], indent=2, ensure_ascii=False), encoding="utf-8")
    lineas = [
        "| fichero | KB | formato | sha256 (8) | ancho×alto | orient. | EXIF | fecha EXIF | duplicado |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in datos_lista:
        lineas.append(
            f"| {d.fichero} | {d.tamano_bytes // 1024} | {d.formato or 'ERROR'} | {d.sha256[:8]} | "
            f"{d.ancho}×{d.alto} | {d.orientacion or ''} | {d.orientacion_exif or ''} | {d.fecha_exif or ''} | "
            f"{d.duplicado_de or ''} |"
        )
    ruta_md = carpeta / "inventario.md"
    ruta_md.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta_json, ruta_md
