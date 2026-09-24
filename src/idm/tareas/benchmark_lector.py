"""benchmark_lector: aciertos por campo del lector sobre una carpeta con <nombre>.json de verdad y su documento.
Uso: ejecutar.bat benchmark_lector [--carpeta ruta] [--lector auto|ocr|nulo] [--tuberia X] [--psm 6] [--detalle]
Compara lectores y preprocesados sobre los mismos documentos (ficticios o reales en datos/, nunca en git)."""

import argparse
import json
from pathlib import Path

from idm import config
from idm.albaranes import benchmark
from idm.albaranes.lector import (
    LectorAutomatico,
    LectorImagenNulo,
    LectorImagenOCR,
    LectorTextoPDF,
    tuberias_desde_texto,
)
from idm.albaranes.ocr import MotorTesseract
from idm.albaranes.preprocesado import TUBERIAS
from idm.config import RAIZ
from idm.equivalencias import proveedores
from idm.tareas import _consola


def construir_lector(
    nombre: str, tuberia: str, psms: tuple[int, ...], cifs_propios: set[str], lang: str, orientar: bool
):
    texto = LectorTextoPDF(cifs_propios)
    if nombre == "ocr":
        tuberias = tuberias_desde_texto(tuberia)
        return LectorAutomatico(
            texto,
            LectorImagenOCR(MotorTesseract(lang=lang), tuberias[0], cifs_propios, orientar, psms, tuberias[1:]),
        )
    return LectorAutomatico(texto, LectorImagenNulo())


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    cfg = config.cargar()
    proveedores.cargar_locales(cfg.ruta_datos / proveedores.NOMBRE_CSV_LOCAL)
    p = argparse.ArgumentParser(description="Mide los aciertos por campo del lector de documentos.")
    p.add_argument("--carpeta", type=Path, default=RAIZ / "fixtures" / "ficticios" / "documentos")
    p.add_argument("--lector", choices=("auto", "ocr", "nulo"), default="auto", help="auto = según OCR_MOTOR del .env")
    p.add_argument("--tuberia", default=None, help="tuberías separadas por coma: " + ", ".join(TUBERIAS))
    p.add_argument("--psm", default="4,6,11", help="modos de segmentación de Tesseract, separados por coma (se unen)")
    p.add_argument("--sin-orientar", action="store_true", help="no usar el OSD de Tesseract para girar")
    p.add_argument("--sin-imagenes", action="store_true")
    p.add_argument("--detalle", action="store_true", help="muestra cada fallo")
    p.add_argument("--json", type=Path, default=None, help="guarda el resumen en este fichero")
    args = p.parse_args(argv)
    nombre = args.lector if args.lector != "auto" else ("ocr" if cfg.ocr_motor == "tesseract" else "nulo")
    tuberia = args.tuberia or cfg.ocr_tuberia
    psms = tuple(int(x) for x in str(args.psm).split(",") if x.strip())
    lector = construir_lector(nombre, tuberia, psms, cfg.cifs_propios, cfg.ocr_lang, not args.sin_orientar)
    r = benchmark.ejecutar(args.carpeta, lector, incluir_imagenes=not args.sin_imagenes)
    print(f"lector={nombre} tubería={tuberia} psm={psms} carpeta={args.carpeta}")
    print(r.tabla())
    if args.detalle:
        print()
        for linea in r.detalle:
            print(" -", linea)
    if args.json:
        args.json.write_text(
            json.dumps(
                {"lector": nombre, "tuberia": tuberia, "psm": psms, **r.resumen()}, indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
