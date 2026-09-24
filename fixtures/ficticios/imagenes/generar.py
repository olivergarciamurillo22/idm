"""Genera imágenes FICTICIAS para los tests de HEIC, orientación y OCR: un albarán sintético renderizado con Pillow en
PNG, JPEG y HEIC (con EXIF de orientación), girado, borroso, cortado, dos documentos en una foto y un HEIC corrupto.
Ningún dato real. Ejecutar: PYTHONPATH=src .venv/bin/python fixtures/ficticios/imagenes/generar.py"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF = True
except ImportError:  # pragma: no cover
    HEIF = False

# Albarán ficticio con LAYOUT_A (etiqueta y valor en líneas distintas, familia/ref/desc/precio/dtos/cant/importe)
DOC = {
    "tipo": "ALBARAN",
    "cif": "B00000001",
    "numero": "AC B26 0100009999",
    "fecha": "2026-09-20",
    "nuestro_pedido": None,
    "lineas": [
        {
            "codigo_proveedor": "REF-A1",
            "descripcion": "TORNILLO M8X30",
            "cantidad": "100",
            "precio_bruto": "0.12",
            "descuento_pct": "45",
            "importe": "6.60",
        },
        {
            "codigo_proveedor": "REF-B22",
            "descripcion": "TUERCA M8",
            "cantidad": "50",
            "precio_bruto": "0.04",
            "descuento_pct": "0",
            "importe": "2.00",
        },
    ],
    "base": "8.60",
    "iva": "1.81",
    "total": "10.41",
}


def fuente(tamano: int):
    for nombre in (
        "DejaVuSans.ttf",
        "Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default()


def albaran(ancho: int = 1800, alto: int = 1300) -> Image.Image:
    img = Image.new("RGB", (ancho, alto), (250, 250, 248))
    d = ImageDraw.Draw(img)
    f, fb, fs = fuente(34), fuente(40), fuente(30)
    y = 80
    d.text((120, y), "SUMINISTROS FICTICIOS LA VEGA S.L.", fill="black", font=fb)
    d.text((120, y + 50), "CIF. B00000001   Tlf.: 950 000 001", fill="black", font=f)
    d.text((1000, y), "Direccion de Envio del Cliente", fill="black", font=fs)
    d.text((1000, y + 40), "EMPRESA CLIENTE FICTICIA S.L.", fill="black", font=fs)
    d.text((1000, y + 80), "B99999999", fill="black", font=fs)
    y = 330
    d.text((120, y), "Tipo / Serie / No Albaran", fill="black", font=fs)
    d.text((560, y), "Fecha/Hora", fill="black", font=fs)
    d.text((1000, y), "Pedido", fill="black", font=fs)
    d.text((120, y + 45), "AC B26 0100009999", fill="black", font=f)
    d.text((560, y + 45), "20/09/2026 / 10:15:00", fill="black", font=f)
    d.text((1000, y + 45), "0", fill="black", font=f)
    y = 480
    for x, t in (
        (120, "Familia"),
        (260, "Referencia"),
        (560, "Denominacion"),
        (1000, "Precio"),
        (1150, "% Descuentos"),
        (1450, "Cantidad"),
        (1620, "Imp. Linea"),
    ):
        d.text((x, y), t, fill="black", font=fs)
    # Las tres columnas de descuento van separadas de verdad (como en el papel): si no, el OCR las junta ("4500")
    filas = [
        ("TORN", "REF-A1", "TORNILLO M8X30", "0,12", "45", "0", "0", "100,00", "6,60"),
        ("TORN", "REF-B22", "TUERCA M8", "0,04", "0", "0", "0", "50,00", "2,00"),
    ]
    for i, fila in enumerate(filas):
        yy = y + 60 + i * 50
        for x, t in zip((120, 260, 560, 1000, 1150, 1260, 1360, 1450, 1620), fila, strict=True):
            d.text((x, yy), t, fill="black", font=f)
    y = 1050
    for x, t in (
        (120, "Importe Neto"),
        (420, "Portes"),
        (720, "B. Imponible"),
        (1020, "%IVA"),
        (1200, "Importe IVA"),
        (1500, "Importe Total"),
    ):
        d.text((x, y), t, fill="black", font=fs)
    for x, t in ((120, "8,60"), (420, "0,00"), (720, "8,60"), (1020, "21,00"), (1200, "1,81"), (1500, "10,41")):
        d.text((x, y + 45), t, fill="black", font=f)
    d.text((1500, 300), "2921", fill=(60, 60, 120), font=fuente(48))  # anotación manuscrita simulada
    return img


def main() -> None:
    base = albaran()
    base.save(AQUI / "albaran_sintetico.png")
    base.save(AQUI / "albaran_sintetico.jpg", quality=90)
    (AQUI / "albaran_sintetico.json").write_text(json.dumps(DOC, indent=1), encoding="utf-8")
    # Girado 90° en píxeles (como una foto en horizontal de un documento vertical)
    base.rotate(-90, expand=True).save(AQUI / "albaran_sintetico_girado90.jpg", quality=90)
    (AQUI / "albaran_sintetico_girado90.json").write_text(json.dumps(DOC, indent=1), encoding="utf-8")
    # Borroso
    base.filter(ImageFilter.GaussianBlur(6)).save(AQUI / "albaran_sintetico_borroso.jpg", quality=80)
    # Cortado (falta el tercio derecho)
    base.crop((0, 0, 1150, base.size[1])).save(AQUI / "albaran_sintetico_cortado.jpg", quality=90)
    # Dos documentos en una foto
    doble = Image.new("RGB", (base.size[0], base.size[1] * 2 + 60), (200, 200, 200))
    doble.paste(base, (0, 0))
    doble.paste(base, (0, base.size[1] + 60))
    doble.save(AQUI / "dos_documentos.jpg", quality=85)
    if HEIF:
        # HEIC con EXIF Orientation=6 (la imagen se guarda girada y el visor la endereza)
        girada = base.rotate(90, expand=True)
        exif = Image.Exif()
        exif[0x0112] = 6
        girada.save(AQUI / "albaran_sintetico_exif6.heic", quality=85, exif=exif.tobytes())
        base.save(AQUI / "albaran_sintetico.heic", quality=85)
        (AQUI / "albaran_sintetico_exif6.json").write_text(json.dumps(DOC, indent=1), encoding="utf-8")
    (AQUI / "corrupto.heic").write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 200)
    print("imágenes ficticias generadas en", AQUI)


if __name__ == "__main__":
    main()
