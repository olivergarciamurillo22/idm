"""Preprocesado no destructivo de fotos de documentos antes del OCR: orientación EXIF, giro por OSD, gris, contraste,
escala, suavizado y binarización. Cada paso es una función pura imagen→imagen y la tubería es una lista de nombres.
El original nunca se toca; el benchmark decide qué pasos merecen la pena (ninguno se aplica "porque parece bueno")."""

from collections.abc import Callable

from PIL import Image, ImageFilter, ImageOps

Paso = Callable[[Image.Image], Image.Image]

LADO_MAXIMO_POR_DEFECTO = 2400


def a_gris(img: Image.Image) -> Image.Image:
    return ImageOps.grayscale(img)


def autocontraste(img: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(img, cutoff=1)


def escalar(lado_maximo: int = LADO_MAXIMO_POR_DEFECTO) -> Paso:
    def paso(img: Image.Image) -> Image.Image:
        if max(img.size) <= lado_maximo:
            return img
        copia = img.copy()
        copia.thumbnail((lado_maximo, lado_maximo), Image.LANCZOS)
        return copia

    paso.__name__ = f"escalar_{lado_maximo}"
    return paso


def suavizar(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.MedianFilter(3))


def binarizar(umbral: int = 160) -> Paso:
    def paso(img: Image.Image) -> Image.Image:
        gris = img if img.mode == "L" else ImageOps.grayscale(img)
        return gris.point(lambda v: 255 if v > umbral else 0, mode="1").convert("L")

    paso.__name__ = f"binarizar_{umbral}"
    return paso


def recortar_texto(umbral: int = 110, margen: float = 0.02) -> Paso:
    """Recorta al rectángulo que contiene píxeles oscuros (el texto), con margen. Un documento pequeño en una foto
    queda así con letras más grandes tras reescalar. Si no hay píxeles oscuros, devuelve la imagen tal cual."""

    def paso(img: Image.Image) -> Image.Image:
        pequena = ImageOps.grayscale(img)
        pequena.thumbnail((800, 800))
        escala = img.size[0] / pequena.size[0]
        caja = pequena.point(lambda v: 255 if v < umbral else 0).getbbox()
        if not caja:
            return img
        x0, y0, x1, y1 = (int(c * escala) for c in caja)
        mx, my = int(img.size[0] * margen), int(img.size[1] * margen)
        return img.crop((max(0, x0 - mx), max(0, y0 - my), min(img.size[0], x1 + mx), min(img.size[1], y1 + my)))

    paso.__name__ = f"recortar_texto_{umbral}"
    return paso


def girar(grados: int) -> Paso:
    def paso(img: Image.Image) -> Image.Image:
        return img.rotate(-grados, expand=True) if grados % 360 else img

    paso.__name__ = f"girar_{grados}"
    return paso


PASOS: dict[str, Paso] = {
    "gris": a_gris,
    "contraste": autocontraste,
    "escalar": escalar(),
    "escalar_1600": escalar(1600),
    "escalar_3000": escalar(3200),
    "suavizar": suavizar,
    "recortar": recortar_texto(),
    "binarizar": binarizar(),
    "girar_90": girar(90),
    "girar_180": girar(180),
    "girar_270": girar(270),
}

TUBERIAS: dict[str, tuple[str, ...]] = {
    "ninguna": (),
    "basica": ("escalar", "gris"),
    "contraste": ("escalar", "gris", "contraste"),
    "contraste_3200": ("escalar_3000", "gris", "contraste"),
    "recorte_3200": ("recortar", "escalar_3000", "gris", "contraste"),
    "limpia": ("escalar", "gris", "contraste", "suavizar"),
    "binaria": ("escalar", "gris", "contraste", "binarizar"),
}


def preparar(img: Image.Image, pasos: tuple[str, ...]) -> Image.Image:
    """Aplica los pasos en orden sobre una copia. Nombres desconocidos lanzan KeyError con la lista válida."""
    resultado = img
    for nombre in pasos:
        if nombre not in PASOS:
            raise KeyError(f"Paso de preprocesado desconocido '{nombre}'. Válidos: {', '.join(PASOS)}")
        resultado = PASOS[nombre](resultado)
    return resultado
