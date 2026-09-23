"""benchmark_lector: aciertos por campo del lector sobre fixtures/documentos (o la carpeta que se indique).
Uso: ejecutar.bat benchmark_lector [--carpeta ruta] [--sin-imagenes] [--detalle]
Sirve para comparar lectores (texto, OCR local, servicio externo) sobre los mismos documentos."""

import argparse
from pathlib import Path

from idm.albaranes import benchmark
from idm.config import RAIZ


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Mide los aciertos por campo del lector de documentos.")
    p.add_argument("--carpeta", type=Path, default=RAIZ / "fixtures" / "documentos")
    p.add_argument("--sin-imagenes", action="store_true")
    p.add_argument("--detalle", action="store_true", help="muestra cada fallo")
    args = p.parse_args(argv)
    r = benchmark.ejecutar(args.carpeta, incluir_imagenes=not args.sin_imagenes)
    print(r.tabla())
    if args.detalle:
        print()
        for linea in r.detalle:
            print(" -", linea)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
