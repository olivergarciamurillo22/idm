"""Prepara la consola para las tareas: salida UTF-8 (Windows arranca en cp1252 y rompe con acentos y flechas).
Cada main() de tareas/ llama a preparar() antes de imprimir nada.
No hace nada más: sin colores, sin logging."""

import sys


def preparar() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
