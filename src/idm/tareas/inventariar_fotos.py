"""inventariar_fotos: inventario (nombre, tamaño, formato, sha256, dimensiones, orientación, fecha EXIF, duplicados) de
una carpeta de fotos y derivados JPEG locales con la orientación aplicada. Nunca modifica los originales.
Uso: ejecutar.bat inventariar_fotos --carpeta datos/material_real/fotos_2026-09-24 [--derivados ruta] [--lado 1600]"""

import argparse
from pathlib import Path

from idm.albaranes.imagenes import ImagenNoLegible, derivado_jpeg, escribir_inventario, inventariar
from idm.tareas import _consola


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    p = argparse.ArgumentParser(description="Inventaría fotos de documentos y genera derivados JPEG locales.")
    p.add_argument("--carpeta", type=Path, required=True)
    p.add_argument(
        "--derivados", type=Path, default=None, help="carpeta de derivados (por defecto <carpeta>/derivados)"
    )
    p.add_argument("--lado", type=int, default=None, help="lado máximo del derivado (vacío = tamaño original)")
    p.add_argument("--sin-derivados", action="store_true")
    args = p.parse_args(argv)
    datos_lista = inventariar(args.carpeta)
    ruta_json, ruta_md = escribir_inventario(args.carpeta, datos_lista)
    print(
        f"{len(datos_lista)} imágenes · {sum(1 for d in datos_lista if d.duplicado_de)} duplicadas · "
        f"{sum(1 for d in datos_lista if not d.legible)} ilegibles → {ruta_md}"
    )
    if args.sin_derivados:
        return 0
    carpeta_derivados = args.derivados or args.carpeta / "derivados"
    for d in datos_lista:
        if not d.legible or d.duplicado_de:
            continue
        try:
            destino = derivado_jpeg(args.carpeta / d.fichero, carpeta_derivados, args.lado)
            print(f"  {d.fichero} → {destino.name}")
        except ImagenNoLegible as exc:
            print(f"  {d.fichero}: NO LEGIBLE ({exc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
