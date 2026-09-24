"""ejecutar_golden: corre todos los casos de fixtures/golden/ y muestra cuáles pasan y qué difiere en los que no.
Uso: ejecutar.bat ejecutar_golden [--carpeta ruta]
Es lo mismo que pytest tests/golden, pero legible para quien no usa pytest."""

import argparse
from pathlib import Path

from idm.albaranes.lector import leer
from idm.config import RAIZ
from idm.cotejo.interpretar import interpretar_albaran
from idm.dominio.golden import ejecutar_caso
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.tareas import _consola


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    p = argparse.ArgumentParser(description="Ejecuta el golden dataset.")
    p.add_argument("--carpeta", type=Path, default=RAIZ / "fixtures" / "golden")
    p.add_argument("--siddex", type=Path, default=RAIZ / "fixtures" / "siddex")
    args = p.parse_args(argv)
    gateway = SiddexDesdeExcel(args.siddex)
    tabla = TablaEquivalencias.desde(gateway.equivalencias())
    proveedores = gateway.proveedores()
    fallos = 0
    for caso in sorted(c for c in args.carpeta.iterdir() if c.is_dir() and (c / "esperado.json").exists()):
        diferencias = ejecutar_caso(caso, leer, lambda d: interpretar_albaran(d, tabla, proveedores).albaran)
        print(("OK   " if not diferencias else "FALLA") + " " + caso.name)
        for d in diferencias:
            print("      -", d)
        fallos += bool(diferencias)
    print(f"\n{fallos} caso(s) con diferencias")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
