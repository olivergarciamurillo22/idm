"""servir_bandeja: arranca la bandeja de revisión con uvicorn en la red local (BANDEJA_HOST:BANDEJA_PUERTO).
Uso: ejecutar.bat servir_bandeja [--host 0.0.0.0] [--puerto 8000]
Usa la base de datos de .env; hay que haber ejecutado 'migrar' antes."""

import argparse

import uvicorn

from idm import config
from idm.almacen.sesion import abrir
from idm.bandeja.app import crear_app
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.tareas import _consola


def crear() -> "uvicorn.Config | object":
    cfg = config.cargar()
    cfg.crear_carpetas()
    _, repo, encargos = abrir(cfg)
    gateway = SiddexDesdeExcel(cfg.ruta_siddex)
    tabla = TablaEquivalencias.desde(gateway.equivalencias(), cfg.ruta_datos / "equivalencias_aprendidas.csv")
    return crear_app(repo, encargos, cfg, tabla, {p.clave: p for p in gateway.proveedores()})


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    cfg = config.cargar()
    p = argparse.ArgumentParser(description="Bandeja de revisión en la red local.")
    p.add_argument("--host", default=cfg.bandeja_host)
    p.add_argument("--puerto", type=int, default=cfg.bandeja_puerto)
    args = p.parse_args(argv)
    uvicorn.run(crear(), host=args.host, port=args.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
