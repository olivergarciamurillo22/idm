"""benchmark_documentos: compara proveedores documentales (tesseract, azure, mistral…) sobre la misma verdad.
Uso: ejecutar.bat benchmark_documentos --provider azure [--carpeta ruta] [--autorizo-envio-externo] [--json f]
Un externo solo corre con ALLOW_EXTERNAL_DOCUMENT_PROCESSING=true, lista permitida y --autorizo-envio-externo."""

import argparse
import json
from pathlib import Path

from idm import config
from idm.config import RAIZ
from idm.documental import benchmark
from idm.documental.base import ConfiguracionDocumentalInvalida
from idm.documental.lector import LectorDocumental
from idm.documental.router import EXTERNOS, crear_proveedor, registro_desde_config
from idm.equivalencias import proveedores
from idm.tareas import _consola

CARPETA_REAL = RAIZ / "datos" / "analisis_real" / "benchmark"
CARPETA_FICTICIA = RAIZ / "fixtures" / "ficticios" / "imagenes"


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    cfg = config.cargar()
    proveedores.cargar_locales(cfg.ruta_datos / proveedores.NOMBRE_CSV_LOCAL)
    p = argparse.ArgumentParser(description="Benchmark A/B de proveedores documentales.")
    p.add_argument("--provider", required=True, help="tesseract | azure | mistral | google | benchmark")
    p.add_argument("--proveedores", default=None, help="con --provider benchmark: lista separada por comas")
    p.add_argument("--carpeta", type=Path, default=None, help="documentos + <nombre>.json de verdad")
    p.add_argument(
        "--autorizo-envio-externo",
        action="store_true",
        help="confirmación explícita, además de la configuración, para mandar estos documentos fuera",
    )
    p.add_argument("--json", type=Path, default=None, help="guarda el resumen (sin contenido de documentos)")
    args = p.parse_args(argv)

    carpeta = args.carpeta or (CARPETA_REAL if CARPETA_REAL.exists() else CARPETA_FICTICIA)
    if args.provider == "benchmark":
        nombres = [
            n.strip() for n in (args.proveedores or ",".join(cfg.document_providers_benchmark)).split(",") if n.strip()
        ]
    else:
        nombres = [args.provider.strip().lower()]
    externos = [n for n in nombres if n in EXTERNOS]
    if externos and not args.autorizo_envio_externo:
        print(
            f"Rechazado: {', '.join(externos)} recibiría(n) los documentos de {carpeta}. "
            "Hace falta --autorizo-envio-externo además de ALLOW_EXTERNAL_DOCUMENT_PROCESSING=true y "
            "EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED. No se ha enviado nada."
        )
        return 3
    try:
        lectores = [(n, crear_proveedor(n, cfg)) for n in nombres]
    except ConfiguracionDocumentalInvalida as exc:
        print(f"Rechazado: {str(exc).rstrip('.')}. No se ha enviado nada.")
        return 3

    registro = registro_desde_config(cfg)
    resultados = []
    for nombre, proveedor in lectores:
        lector = LectorDocumental(proveedor, cfg.cifs_propios, cfg.ruta_datos / "derivados_documentales", registro)
        print(f"… {nombre} sobre {carpeta}")
        resultados.append(benchmark.ejecutar(carpeta, lector, nombre))
    print()
    print(benchmark.tabla_comparada(resultados, benchmark.cargar_baseline()))
    for r in resultados:
        for e in r.resumen()["operacion"]["errores"]:
            print("  error:", e)
    if args.json:
        args.json.write_text(
            json.dumps([r.resumen() for r in resultados], indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
