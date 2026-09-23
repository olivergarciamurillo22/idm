"""Motor y sesión de SQLAlchemy a partir de DATABASE_URL, y aplicación de migraciones Alembic desde código.
abrir(cfg) devuelve (sesion, RepositorioSQL, EncargosSQL) listos para las tareas y la bandeja.
No define tablas: están en almacen/sql.py; el esquema lo crea 'ejecutar.bat migrar'."""

from pathlib import Path

from alembic import command
from alembic.config import Config as ConfigAlembic
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from idm.almacen.sql import EncargosSQL, RepositorioSQL
from idm.config import RAIZ, Config


def motor(url: str) -> Engine:
    if url.startswith("sqlite:///"):
        ruta = url.removeprefix("sqlite:///")
        if ruta and ruta != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, future=True)


def migrar(url: str, destino: str = "head") -> None:
    """Aplica las migraciones de migrations/ hasta 'head'. Equivale a 'alembic upgrade head' con esa URL."""
    cfg = ConfigAlembic(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, destino)


def abrir(cfg: Config) -> tuple[Session, RepositorioSQL, EncargosSQL]:
    sesion = Session(motor(cfg.database_url), future=True)
    return sesion, RepositorioSQL(sesion), EncargosSQL(sesion)
