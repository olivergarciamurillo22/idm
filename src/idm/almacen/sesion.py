"""Motor y sesión de SQLAlchemy a partir de DATABASE_URL, y aplicación de migraciones Alembic desde código.
abrir(cfg) devuelve (sesion, RepositorioSQL, EncargosSQL): la sesión es una por hilo (la bandeja atiende peticiones en
varios hilos) y SQLite va en modo WAL con espera ante bloqueos (la bandeja y la tarea programada escriben a la vez)."""

from pathlib import Path

from alembic import command
from alembic.config import Config as ConfigAlembic
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from idm.almacen.sql import EncargosSQL, RepositorioSQL
from idm.config import RAIZ, Config

ESPERA_BLOQUEO_S = 30  # SQLite: cuánto espera una escritura si otro proceso tiene la base bloqueada


def motor(url: str) -> Engine:
    if url.startswith("sqlite:///"):
        ruta = url.removeprefix("sqlite:///")
        if ruta and ruta != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, future=True, connect_args={"timeout": ESPERA_BLOQUEO_S, "check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _pragmas(conexion, _registro):  # noqa: ANN001 - firma de SQLAlchemy
            cursor = conexion.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")  # lectores y un escritor a la vez sin bloquearse
            cursor.execute(f"PRAGMA busy_timeout={ESPERA_BLOQUEO_S * 1000}")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, future=True, pool_pre_ping=True)


def migrar(url: str, destino: str = "head") -> None:
    """Aplica las migraciones de migrations/ hasta 'head'. Equivale a 'alembic upgrade head' con esa URL."""
    cfg = ConfigAlembic(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, destino)


def abrir(cfg: Config) -> tuple[Session, RepositorioSQL, EncargosSQL]:
    """scoped_session: cada hilo tiene su propia sesión y los repositorios la usan sin enterarse."""
    sesion = scoped_session(sessionmaker(bind=motor(cfg.database_url), future=True))
    return sesion, RepositorioSQL(sesion), EncargosSQL(sesion)
