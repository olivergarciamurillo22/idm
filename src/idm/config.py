"""Configuración del programa: lee .env (rutas, buzones, correo, modo simulación) y expone un objeto Config.
Nada de configuración escondida: todo lo que cambia entre el PC de desarrollo y el servidor de IDM está aquí.
No contiene secretos: los valores vienen del .env, que no entra en git."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Buzon:
    host: str
    usuario: str
    clave: str
    carpeta: str = "INBOX"


@dataclass(frozen=True)
class Config:
    ruta_datos: Path
    ruta_entrada: Path
    ruta_procesados: Path
    ruta_siddex: Path
    ruta_planning: Path
    ruta_pedidos_pdf: Path
    ruta_salida: Path
    ruta_pedidos_transmitidos: Path | None
    database_url: str
    modo_simulacion: bool
    empresa: dict[str, str] = field(default_factory=dict)
    smtp_host: str = ""
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_clave: str = ""
    smtp_remitente: str = ""
    buzones: tuple[Buzon, ...] = ()
    bandeja_host: str = "0.0.0.0"
    bandeja_puerto: int = 8000

    def crear_carpetas(self) -> None:
        for ruta in (self.ruta_datos, self.ruta_entrada, self.ruta_procesados, self.ruta_siddex,
                     self.ruta_pedidos_pdf, self.ruta_salida):
            ruta.mkdir(parents=True, exist_ok=True)


def _ruta(valor: str) -> Path:
    ruta = Path(valor)
    return ruta if ruta.is_absolute() else RAIZ / ruta


def _bool(valor: str) -> bool:
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes")


def _buzones(valor: str) -> tuple[Buzon, ...]:
    """IMAP_BUZONES=host|usuario|clave|carpeta;host|usuario|clave"""
    resultado = []
    for trozo in filter(None, (t.strip() for t in valor.split(";"))):
        partes = trozo.split("|")
        if len(partes) < 3:
            raise ValueError(f"IMAP_BUZONES: entrada incompleta '{trozo}'")
        resultado.append(Buzon(partes[0], partes[1], partes[2], partes[3] if len(partes) > 3 else "INBOX"))
    return tuple(resultado)


def cargar(ruta_env: Path | None = None) -> Config:
    """Carga .env (o el fichero indicado) sobre las variables de entorno y construye Config."""
    load_dotenv(ruta_env or RAIZ / ".env", override=False)
    g = os.environ.get
    return Config(
        ruta_datos=_ruta(g("RUTA_DATOS", "datos")),
        ruta_entrada=_ruta(g("RUTA_ENTRADA", "datos/entrada")),
        ruta_procesados=_ruta(g("RUTA_PROCESADOS", "datos/procesados")),
        ruta_siddex=_ruta(g("RUTA_SIDDEX", "datos/siddex")),
        ruta_planning=_ruta(g("RUTA_PLANNING", "datos/planning/PLANNING_IDM_MENSUAL.xlsx")),
        ruta_pedidos_pdf=_ruta(g("RUTA_PEDIDOS_PDF", "datos/pedidos")),
        ruta_salida=_ruta(g("RUTA_SALIDA", "datos/salida")),
        ruta_pedidos_transmitidos=_ruta(g("RUTA_PEDIDOS_TRANSMITIDOS")) if g("RUTA_PEDIDOS_TRANSMITIDOS") else None,
        database_url=g("DATABASE_URL", f"sqlite:///{RAIZ / 'datos' / 'idm.db'}"),
        modo_simulacion=_bool(g("MODO_SIMULACION", "true")),
        empresa={
            "nombre": g("EMPRESA_NOMBRE", "IDM"),
            "direccion": g("EMPRESA_DIRECCION", ""),
            "cif": g("EMPRESA_CIF", ""),
            "telefono": g("EMPRESA_TELEFONO", ""),
            "email_pedidos": g("EMPRESA_EMAIL_PEDIDOS", ""),
        },
        smtp_host=g("SMTP_HOST", ""),
        smtp_puerto=int(g("SMTP_PUERTO", "587")),
        smtp_usuario=g("SMTP_USUARIO", ""),
        smtp_clave=g("SMTP_CLAVE", ""),
        smtp_remitente=g("SMTP_REMITENTE", ""),
        buzones=_buzones(g("IMAP_BUZONES", "")),
        bandeja_host=g("BANDEJA_HOST", "0.0.0.0"),
        bandeja_puerto=int(g("BANDEJA_PUERTO", "8000")),
    )
