"""TesseractProvider: fallback local, desarrollo y baseline del benchmark. Envuelve el reconocimiento de
albaranes/lector.LectorImagenOCR (preprocesado, mejor giro, varios psm) y lo devuelve como ResultadoDocumental.
Congelado: no se optimiza más (baseline 24/09/2026 en docs/benchmark-lector-real.md). No sale nada de la máquina."""

import io
import shutil
import subprocess
import time

from PIL import Image

from idm.albaranes.imagenes import ImagenNoLegible, abrir
from idm.albaranes.lector import LectorImagenOCR
from idm.albaranes.ocr import MotorTesseract
from idm.albaranes.preprocesado import TUBERIAS
from idm.documental.base import DocumentoEntrada, ErrorPermanente, ErrorTransitorio
from idm.documental.modelo import Caja, MetadatosMotor, Pagina, Palabra, ResultadoDocumental


def _version(ejecutable: str) -> str:
    try:
        salida = subprocess.run([ejecutable, "--version"], capture_output=True, text=True, timeout=10, check=False)
        return (salida.stdout or salida.stderr).split()[1]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return "desconocida"


class TesseractProvider:
    nombre = "tesseract"
    externo = False

    def __init__(
        self,
        pasos: tuple[str, ...] = TUBERIAS["contraste_3200"],
        pasos_extra: tuple[tuple[str, ...], ...] = (TUBERIAS["recorte_3200"],),
        psms: tuple[int, ...] = (4, 6, 11),
        lang: str = "spa+eng",
        orientar: bool = True,
    ) -> None:
        self._motor = MotorTesseract(lang=lang)
        self._lector = LectorImagenOCR(self._motor, pasos, None, orientar, psms, pasos_extra)
        self.modelo = f"tesseract-{lang}"

    def disponible(self) -> bool:
        return shutil.which(self._motor.ejecutable) is not None

    def _imagen(self, documento: DocumentoEntrada) -> Image.Image:
        if documento.tipo_mime == "application/pdf":
            import pdfplumber

            with pdfplumber.open(io.BytesIO(documento.contenido)) as pdf:
                return pdf.pages[0].to_image(resolution=200).original.convert("RGB")
        try:
            return abrir(io.BytesIO(documento.contenido))
        except ImagenNoLegible as exc:
            raise ErrorPermanente(str(exc)) from exc

    def analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental:
        if not self.disponible():
            raise ErrorTransitorio("tesseract no está instalado o no está en el PATH")
        inicio = time.perf_counter()
        ocr = self._lector.reconocer_imagen(self._imagen(documento))
        if not ocr.disponible:
            raise ErrorTransitorio(f"tesseract falló: {ocr.error}")
        palabras = [
            Palabra(
                texto=p.texto,
                confianza=round(p.confianza / 100.0, 4),
                caja=Caja(x0=p.x, y0=p.y, x1=p.x + p.ancho, y1=p.y + p.alto),
            )
            for p in ocr.palabras
        ]
        avisos = (
            [f"Foto girada {self._lector.ultima_orientacion}° para leerla"] if self._lector.ultima_orientacion else []
        )
        return ResultadoDocumental(
            texto=ocr.texto,
            texto_alternativo=ocr.texto_filas,
            paginas=[Pagina(numero=1, unidad="px", angulo=float(self._lector.ultima_orientacion), palabras=palabras)],
            metadatos=MetadatosMotor(
                proveedor=self.nombre,
                modelo=self.modelo,
                externo=False,
                version_api=_version(self._motor.ejecutable),
                tiempo_s=round(time.perf_counter() - inicio, 2),
                paginas_procesadas=1,
                sha256_enviado=None,
                tipo_enviado=documento.tipo_mime,
            ),
            avisos=avisos,
        )
