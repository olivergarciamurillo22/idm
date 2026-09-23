"""calcular_mes: planning × escandallos → Excel de necesidades (fila por artículo: cantidad, precio, importe, máquinas).
Uso: ejecutar.bat calcular_mes --hoja SEPT_26 [--planning ruta] [--siddex carpeta] [--salida ruta] [--descontar-stock]
No genera pedidos: eso es generar_pedidos."""

import argparse
from pathlib import Path

from idm import config
from idm.necesidades import mapa as mapa_mod
from idm.necesidades.calculo import calcular
from idm.necesidades.planning import hojas, leer_planning
from idm.necesidades.salida import escribir_excel
from idm.siddex.desde_excel import SiddexDesdeExcel


def ejecutar(hoja: str, planning: Path, siddex: Path, salida: Path, mapa: Path, descontar_stock: bool) -> Path:
    lineas = leer_planning(planning, hoja)
    gateway = SiddexDesdeExcel(siddex)
    resultado = calcular(lineas, gateway, mapa_mod.cargar_mapa(mapa), hoja=hoja, descontar_stock=descontar_stock)
    ruta = escribir_excel(resultado, salida)
    print(f"Planning {hoja}: {len(lineas)} líneas, {sum(resultado.maquinas.values())} máquinas")
    print(f"Necesidades: {len(resultado.necesidades)} artículos, total {resultado.total} €")
    print(f"Fuera de circuito (hierro): {len(resultado.fuera_circuito)} artículos")
    for texto in resultado.incidencias:
        print("  AVISO:", texto)
    print("Excel:", ruta)
    return ruta


def main(argv: list[str] | None = None) -> int:
    cfg = config.cargar()
    p = argparse.ArgumentParser(description="Calcula las necesidades de compra del mes.")
    p.add_argument("--hoja", help="hoja del planning (p. ej. SEPT_26); sin ella, lista las hojas")
    p.add_argument("--planning", type=Path, default=cfg.ruta_planning)
    p.add_argument("--siddex", type=Path, default=cfg.ruta_siddex, help="carpeta con los exports de Siddex")
    p.add_argument("--salida", type=Path, default=None)
    p.add_argument("--mapa", type=Path, default=mapa_mod.RUTA_MAPA_POR_DEFECTO)
    p.add_argument("--descontar-stock", action="store_true", help="descuenta stock y pendiente de recibir")
    args = p.parse_args(argv)
    if not args.planning.exists():
        print(f"No existe el planning: {args.planning}")
        return 1
    if not args.hoja:
        print("Hojas disponibles:", ", ".join(hojas(args.planning)))
        return 0
    salida = args.salida or cfg.ruta_salida / f"necesidades_{args.hoja}.xlsx"
    ejecutar(args.hoja, args.planning, args.siddex, salida, args.mapa, args.descontar_stock)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
