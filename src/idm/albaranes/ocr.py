"""Interfaz MotorOCR: reconocer(imagen) -> ResultadoOCR (texto, palabras con confianza y caja, motor, tiempo).
Implementaciones: MotorTesseract (binario local por subprocess, salida TSV; nada sale de la máquina) y MotorNulo.
No preprocesa imágenes (preprocesado.py) ni interpreta el texto (lector.py): solo convierte píxeles en palabras."""

import csv
import io
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class PalabraOCR:
    texto: str
    confianza: float  # 0..100
    x: int
    y: int
    ancho: int
    alto: int
    linea: int  # índice de línea (bloque/párrafo/línea aplanado)


@dataclass
class ResultadoOCR:
    texto: str
    motor: str
    palabras: list[PalabraOCR] = field(default_factory=list)
    tiempo_s: float = 0.0
    error: str | None = None
    texto_filas: str = ""  # filas reconstruidas por geometría (solo se usa si el texto normal no da líneas)

    @property
    def confianza_media(self) -> float:
        if not self.palabras:
            return 0.0
        return round(sum(p.confianza for p in self.palabras) / len(self.palabras), 1)

    @property
    def disponible(self) -> bool:
        return self.error is None

    @property
    def texto_por_filas(self) -> str:
        return "\n".join(reconstruir_filas(self.palabras))

    def puntuacion_orientacion(self, minimo: float = 60.0, longitud: int = 3) -> float:
        """Suma de confianzas de las palabras fiables (≥ minimo, ≥ longitud caracteres): discrimina el giro correcto."""
        return sum(p.confianza for p in self.palabras if p.confianza >= minimo and len(p.texto) >= longitud)


class MotorOCR(Protocol):
    nombre: str

    def reconocer(self, imagen: Image.Image) -> ResultadoOCR: ...

    def disponible(self) -> bool: ...


class MotorNulo:
    """No reconoce nada. Es lo que hay cuando no se ha configurado ningún motor."""

    nombre = "ninguno"

    def reconocer(self, imagen: Image.Image) -> ResultadoOCR:
        return ResultadoOCR(texto="", motor=self.nombre, error="sin motor OCR configurado")

    def disponible(self) -> bool:
        return False


class MotorTesseract:
    """Tesseract instalado en la máquina (brew/apt, o instalador UB Mannheim en Windows). Se llama al binario.
    lang 'spa+eng' porque los documentos mezclan; psm 6 (bloque uniforme) o 4 (columnas) para albaranes; 11 disperso."""

    nombre = "tesseract"

    def __init__(
        self, ejecutable: str = "tesseract", lang: str = "spa+eng", psm: int = 6, timeout_s: int = 120
    ) -> None:
        self.ejecutable, self.lang, self.psm, self.timeout_s = ejecutable, lang, psm, timeout_s

    def disponible(self) -> bool:
        return shutil.which(self.ejecutable) is not None

    def orientacion(self, imagen: Image.Image) -> int | None:
        """Grados que hay que girar (0/90/180/270) según el OSD de Tesseract, o None si no lo sabe."""
        if not self.disponible():
            return None
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "img.png"
            imagen.save(ruta, "PNG")
            try:
                salida = subprocess.run(
                    [self.ejecutable, str(ruta), "stdout", "--psm", "0"],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                ).stdout
            except (subprocess.TimeoutExpired, OSError):
                return None
        for linea in salida.splitlines():
            if linea.startswith("Rotate:"):
                try:
                    return int(linea.split(":")[1].strip())
                except ValueError:
                    return None
        return None

    def reconocer(self, imagen: Image.Image) -> ResultadoOCR:
        if not self.disponible():
            return ResultadoOCR(
                texto="", motor=self.nombre, error=f"'{self.ejecutable}' no está instalado o no está en el PATH"
            )
        inicio = time.perf_counter()
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "img.png"
            imagen.save(ruta, "PNG")
            try:
                proceso = subprocess.run(
                    [self.ejecutable, str(ruta), "stdout", "-l", self.lang, "--psm", str(self.psm), "tsv"],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return ResultadoOCR(texto="", motor=self.nombre, error=f"tesseract superó {self.timeout_s}s")
            except OSError as exc:
                return ResultadoOCR(texto="", motor=self.nombre, error=str(exc))
        if proceso.returncode != 0:
            return ResultadoOCR(texto="", motor=self.nombre, error=proceso.stderr.strip()[-300:] or "tesseract falló")
        palabras, texto = _desde_tsv(proceso.stdout)
        return ResultadoOCR(
            texto=texto, motor=self.nombre, palabras=palabras, tiempo_s=round(time.perf_counter() - inicio, 2)
        )


def _desde_tsv(tsv: str) -> tuple[list[PalabraOCR], str]:
    """Reconstruye líneas de texto a partir del TSV de Tesseract (level 5 = palabra), en orden de lectura."""
    palabras: list[PalabraOCR] = []
    lineas: dict[tuple[int, int, int, int], list[PalabraOCR]] = {}
    for fila in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if fila.get("level") != "5" or not (fila.get("text") or "").strip():
            continue
        clave = (int(fila["page_num"]), int(fila["block_num"]), int(fila["par_num"]), int(fila["line_num"]))
        try:
            conf = float(fila["conf"])
        except ValueError:
            conf = 0.0
        palabra = PalabraOCR(
            fila["text"].strip(),
            max(conf, 0.0),
            int(fila["left"]),
            int(fila["top"]),
            int(fila["width"]),
            int(fila["height"]),
            len(lineas),
        )
        lineas.setdefault(clave, []).append(palabra)
        palabras.append(palabra)
    # Orden de lectura: por posición vertical de la línea, luego horizontal
    ordenadas = sorted(lineas.values(), key=lambda ps: (min(p.y for p in ps), min(p.x for p in ps)))
    texto = "\n".join(" ".join(p.texto for p in sorted(ps, key=lambda p: p.x)) for ps in ordenadas)
    return palabras, texto


def reconstruir_filas(palabras: list[PalabraOCR], tolerancia: float = 0.6) -> list[str]:
    """Agrupa palabras por su centro vertical (con tolerancia relativa a la altura mediana) y las ordena por x.
    Recupera filas de tablas que Tesseract parte en bloques distintos (texto a la izquierda, importes a la derecha)."""
    if not palabras:
        return []
    alturas = sorted(p.alto for p in palabras)
    mediana = alturas[len(alturas) // 2] or 1
    umbral = max(mediana * tolerancia, 4)
    ordenadas = sorted(palabras, key=lambda p: p.y + p.alto / 2)
    filas: list[list[PalabraOCR]] = []
    centros: list[float] = []
    for p in ordenadas:
        centro = p.y + p.alto / 2
        if filas and abs(centro - centros[-1]) <= umbral:
            filas[-1].append(p)
            centros[-1] = (centros[-1] * (len(filas[-1]) - 1) + centro) / len(filas[-1])
        else:
            filas.append([p])
            centros.append(centro)
    return [" ".join(w.texto for w in sorted(fila, key=lambda w: w.x)) for fila in filas]


def motor_por_nombre(nombre: str, **opciones) -> MotorOCR:
    nombre = (nombre or "ninguno").strip().lower()
    if nombre == "tesseract":
        return MotorTesseract(**opciones)
    return MotorNulo()
