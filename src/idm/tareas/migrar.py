"""migrar: crea o actualiza el esquema de la base de datos (Alembic upgrade head) con la URL de .env.
Uso: ejecutar.bat migrar [--url sqlite:///otra.db]
Es lo primero que se ejecuta al instalar; se repite después de cada actualización del programa."""

import argparse

from idm import config
from idm.almacen.sesion import migrar
from idm.tareas import _consola


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    cfg = config.cargar()
    p = argparse.ArgumentParser(description="Aplica las migraciones de la base de datos.")
    p.add_argument("--url", default=cfg.database_url)
    args = p.parse_args(argv)
    cfg.crear_carpetas()
    migrar(args.url)
    print("Base de datos al día:", args.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
