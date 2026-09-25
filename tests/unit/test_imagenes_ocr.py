"""Imágenes y OCR sobre fixtures FICTICIOS (fixtures/ficticios/imagenes): detección HEIC/JPG/PNG, orientación EXIF,
derivados e inventario, preprocesado, reconstrucción de filas, limpieza de texto OCR y lector de imagen con Tesseract
(si está instalado; si no, se comprueba que responde REQUIERE_OCR y no revienta)."""

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from idm.albaranes import imagenes, preprocesado
from idm.albaranes.lector import (
    LectorAutomatico,
    LectorImagenNulo,
    LectorImagenOCR,
    limpiar_texto_ocr,
    tuberias_desde_texto,
)
from idm.albaranes.ocr import MotorNulo, MotorTesseract, PalabraOCR, ResultadoOCR, reconstruir_filas
from idm.dominio.estados import CodigoError, ResultadoLectura, TipoDocumento

IMG = "imagenes"
TESSERACT = MotorTesseract().disponible()


def test_detecta_formatos(fixtures):
    carpeta = fixtures / IMG
    assert imagenes.es_heic(carpeta / "albaran_sintetico.heic")
    assert imagenes.es_imagen(carpeta / "albaran_sintetico.jpg") and imagenes.es_imagen(
        carpeta / "albaran_sintetico.png"
    )
    assert not imagenes.es_imagen(carpeta / "albaran_sintetico.json")


def test_abrir_heic_aplica_orientacion_exif(fixtures):
    normal = imagenes.abrir(fixtures / IMG / "albaran_sintetico.heic")
    exif6 = imagenes.abrir(fixtures / IMG / "albaran_sintetico_exif6.heic")
    assert normal.size == (1800, 1300)
    assert exif6.size == (1800, 1300), "la imagen guardada girada con Orientation=6 debe enderezarse al abrirla"


def test_heic_corrupto_es_imagen_no_legible(fixtures):
    with pytest.raises(imagenes.ImagenNoLegible):
        imagenes.abrir(fixtures / IMG / "corrupto.heic")
    d = imagenes.datos(fixtures / IMG / "corrupto.heic")
    assert not d.legible and d.error and d.sha256


def test_inventario_y_duplicados(fixtures, tmp_path):
    for n in ("albaran_sintetico.heic", "albaran_sintetico.jpg", "corrupto.heic"):
        shutil.copy(fixtures / IMG / n, tmp_path / n)
    shutil.copy(fixtures / IMG / "albaran_sintetico.jpg", tmp_path / "copia_con_otro_nombre.jpg")
    inv = imagenes.inventariar(tmp_path)
    por_nombre = {d.fichero: d for d in inv}
    assert por_nombre["albaran_sintetico.heic"].formato == "HEIF" and por_nombre["albaran_sintetico.heic"].legible
    assert por_nombre["copia_con_otro_nombre.jpg"].duplicado_de == "albaran_sintetico.jpg"
    assert por_nombre["corrupto.heic"].legible is False
    ruta_json, ruta_md = imagenes.escribir_inventario(tmp_path, inv)
    assert len(json.loads(ruta_json.read_text(encoding="utf-8"))) == 4 and "duplicado" in ruta_md.read_text(
        encoding="utf-8"
    )


def test_derivado_jpeg_idempotente_y_registra_relacion(fixtures, tmp_path):
    original = fixtures / IMG / "albaran_sintetico_exif6.heic"
    d1 = imagenes.derivado_jpeg(original, tmp_path / "derivados", lado_maximo=900)
    d2 = imagenes.derivado_jpeg(original, tmp_path / "derivados", lado_maximo=900)
    assert d1 == d2 and d1.suffix == ".jpg" and d1.stem.startswith(imagenes.sha256_fichero(original)[:16])
    assert Image.open(d1).size[0] == 900  # orientación aplicada y reescalado
    relacion = (tmp_path / "derivados" / imagenes.NOMBRE_RELACION).read_text(encoding="utf-8").splitlines()
    assert len(relacion) == 1 and json.loads(relacion[0])["sha256_original"] == imagenes.sha256_fichero(original)
    assert original.read_bytes()[:4] == (fixtures / IMG / "albaran_sintetico_exif6.heic").read_bytes()[:4]  # intacto


def test_preprocesado_no_destructivo_y_tuberias():
    img = Image.new("RGB", (4000, 3000), (120, 120, 120))
    salida = preprocesado.preparar(img, preprocesado.TUBERIAS["contraste"])
    assert img.size == (4000, 3000) and img.mode == "RGB"  # el original no cambia
    assert salida.size == (2400, 1800) and salida.mode == "L"
    assert preprocesado.preparar(img, ()).size == img.size
    with pytest.raises(KeyError, match="desconocido"):
        preprocesado.preparar(img, ("inventado",))
    assert tuberias_desde_texto("contraste_3200, recorte_3200") == (
        preprocesado.TUBERIAS["contraste_3200"],
        preprocesado.TUBERIAS["recorte_3200"],
    )
    with pytest.raises(KeyError):
        tuberias_desde_texto("nada")


def test_recortar_texto_reduce_al_area_con_texto(fixtures):
    img = imagenes.abrir(fixtures / IMG / "albaran_sintetico.png")
    lienzo = Image.new("RGB", (3600, 2600), (245, 245, 245))
    lienzo.paste(img, (900, 650))
    rec = preprocesado.recortar_texto()(lienzo)
    assert rec.size[0] < 2200 and rec.size[1] < 1500  # se queda con el documento y su margen


def test_reconstruir_filas_por_geometria():
    palabras = [
        PalabraOCR("REF-1", 90, 10, 100, 60, 20, 0),
        PalabraOCR("9,14", 90, 400, 103, 40, 20, 5),
        PalabraOCR("REF-2", 90, 10, 140, 60, 20, 1),
        PalabraOCR("6,40", 90, 400, 141, 40, 20, 6),
    ]
    assert reconstruir_filas(palabras) == ["REF-1 9,14", "REF-2 6,40"]
    assert reconstruir_filas([]) == []
    r = ResultadoOCR("x", "t", palabras)
    assert r.confianza_media == 90.0 and r.puntuacion_orientacion() == 360.0


def test_limpiar_texto_ocr():
    assert limpiar_texto_ocr("| REF-1 CINTA 9,14 |\n\n  __ ; 25,14 ]\n") == "REF-1 CINTA 9,14\n25,14"


def test_lector_automatico_con_heic_sin_motor(fixtures):
    doc = LectorAutomatico(imagen=LectorImagenNulo()).leer(fixtures / IMG / "albaran_sintetico.heic")
    assert doc.resultado == ResultadoLectura.REQUIERE_OCR and doc.errores[0].codigo == CodigoError.LECTURA_REQUIERE_OCR
    doc = LectorAutomatico().leer(fixtures / IMG / "corrupto.heic")
    assert doc.resultado == ResultadoLectura.CORRUPTO and doc.errores[0].codigo == CodigoError.LECTURA_CORRUPTO


def test_lector_ocr_sin_motor_disponible_no_revienta(fixtures):
    doc = LectorImagenOCR(MotorNulo()).leer(fixtures / IMG / "albaran_sintetico.jpg")
    assert doc.resultado == ResultadoLectura.REQUIERE_OCR and any("no disponible" in a for a in doc.avisos)


@pytest.mark.skipif(not TESSERACT, reason="tesseract no instalado")
def test_lector_ocr_lee_albaran_sintetico(fixtures):
    lector = LectorImagenOCR(MotorTesseract(), preprocesado.TUBERIAS["contraste"], {"B99999999"}, psms=(4, 6))
    doc = lector.leer(fixtures / IMG / "albaran_sintetico.jpg")
    assert doc.resultado == ResultadoLectura.IMAGEN_OCR and doc.metodo == "ocr_tesseract"
    assert doc.tipo == TipoDocumento.ALBARAN and doc.cif == "B00000001"
    assert doc.numero == "AC B26 0100009999" and str(doc.fecha) == "2026-09-20"
    assert [li.codigo_proveedor for li in doc.lineas] == ["REF-A1", "REF-B22"]
    assert doc.lineas[0].precio_bruto == Decimal("0.12") and doc.lineas[0].descuento_pct == Decimal("45")
    assert doc.lineas[0].cantidad == Decimal("100") and doc.lineas[0].importe == Decimal("6.60")
    assert any("Leído por OCR" in a for a in doc.avisos) and 0 < doc.confianza <= 1


@pytest.mark.skipif(not TESSERACT, reason="tesseract no instalado")
def test_lector_ocr_endereza_foto_girada(fixtures):
    lector = LectorImagenOCR(MotorTesseract(), preprocesado.TUBERIAS["contraste"], {"B99999999"}, psms=(4,))
    doc = lector.leer(fixtures / IMG / "albaran_sintetico_girado90.jpg")
    assert lector.ultima_orientacion in (90, 270) and doc.numero == "AC B26 0100009999"
    assert any("girada" in a for a in doc.avisos)


@pytest.mark.skipif(not TESSERACT, reason="tesseract no instalado")
def test_lector_ocr_heic_con_exif(fixtures):
    lector = LectorImagenOCR(MotorTesseract(), preprocesado.TUBERIAS["contraste"], {"B99999999"}, psms=(4,))
    doc = lector.leer(fixtures / IMG / "albaran_sintetico_exif6.heic")
    assert doc.numero == "AC B26 0100009999" and lector.ultima_orientacion == 0


@pytest.mark.skipif(not TESSERACT, reason="tesseract no instalado")
def test_lector_ocr_borroso_y_cortado_no_revientan(fixtures):
    lector = LectorImagenOCR(MotorTesseract(), preprocesado.TUBERIAS["contraste"], {"B99999999"}, psms=(4,))
    borroso = lector.leer(fixtures / IMG / "albaran_sintetico_borroso.jpg")
    assert borroso.resultado == ResultadoLectura.IMAGEN_OCR and borroso.confianza < 1
    cortado = lector.leer(fixtures / IMG / "albaran_sintetico_cortado.jpg")
    assert cortado.resultado == ResultadoLectura.IMAGEN_OCR and cortado.numero == "AC B26 0100009999"


def test_abrir_no_deja_el_fichero_abierto(fixtures, tmp_path):
    """En Windows un fichero abierto no se puede mover: tras abrir e inventariar, el original debe poder moverse."""
    import shutil as sh

    for nombre in ("albaran_sintetico.heic", "albaran_sintetico.jpg"):
        copia = tmp_path / nombre
        sh.copy(fixtures / IMG / nombre, copia)
        imagenes.abrir(copia)
        imagenes.datos(copia)
        movido = sh.move(str(copia), str(tmp_path / f"movido_{nombre}"))
        assert Path(movido).exists() and not copia.exists()
    assert imagenes.datos(fixtures / IMG / "albaran_sintetico_exif6.heic").orientacion == "horizontal"
