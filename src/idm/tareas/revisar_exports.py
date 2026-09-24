"""revisar_exports: comprueba los exports de Siddex de una carpeta y dice qué columna se ha reconocido como qué,
qué falta, qué sobra y cuántas filas hay; lista los escandallos con sus incidencias. Para el día que lleguen los reales.
Uso: ejecutar.bat revisar_exports [--carpeta datos/siddex] [--muestra 3]"""

import argparse
from pathlib import Path

from idm import config
from idm.siddex.columnas import FICHEROS, TABLAS, ColumnasFaltantes, cargar_alias_extra, leer_tabla
from idm.siddex.lectura import agregar_compras, incidencias, leer_escandallo
from idm.tareas import _consola


def revisar(carpeta: Path, muestra: int = 3) -> list[str]:
    salida: list[str] = [f"Carpeta: {carpeta}"]
    alias = cargar_alias_extra(carpeta)
    if alias:
        salida.append(f"Alias extra cargados de columnas.json: {', '.join(alias)}")
    for tabla in TABLAS:
        ruta = carpeta / FICHEROS[tabla]
        if not ruta.exists():
            salida.append(f"[{tabla}] {FICHEROS[tabla]}: NO EXISTE")
            continue
        try:
            filas, informe = leer_tabla(ruta, tabla, alias)
        except ColumnasFaltantes as exc:
            salida.append(exc.informe.texto())
            salida.append(f"    → {exc}")
            continue
        salida.append(informe.texto())
        for fila in filas[:muestra]:
            salida.append("    ejemplo: " + " | ".join(f"{k}={v}" for k, v in fila.items() if v not in (None, "")))
    xls = sorted(carpeta.glob("*.xls"))
    salida.append(f"Escandallos (.xls BIFF2): {len(xls)}")
    for ruta in xls:
        try:
            e = leer_escandallo(ruta)
        except Exception as exc:  # noqa: BLE001 - se informa, no se aborta
            salida.append(f"    {ruta.name}: NO SE PUEDE LEER ({type(exc).__name__}: {exc})")
            continue
        compras = agregar_compras(e)
        inc = incidencias(e)
        resumen = f"    {ruta.name}: {e.codigo_maquina or 'SIN CÓDIGO'} {e.nombre_maquina or ''} · {len(e.filas)} filas"
        resumen += f" · {len(compras)} códigos comprados"
        if inc:
            resumen += " · incidencias: " + ", ".join(f"{k}={len(v)}" for k, v in inc.items())
        salida.append(resumen)
    return salida


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    cfg = config.cargar()
    p = argparse.ArgumentParser(description="Revisa los exports de Siddex y sus columnas.")
    p.add_argument("--carpeta", type=Path, default=cfg.ruta_siddex)
    p.add_argument("--muestra", type=int, default=3, help="filas de ejemplo por tabla")
    args = p.parse_args(argv)
    for linea in revisar(args.carpeta, args.muestra):
        print(linea)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
