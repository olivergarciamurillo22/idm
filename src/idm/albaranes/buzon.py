"""Fuentes de documentos: una carpeta vigilada (datos/entrada) o buzones IMAP (info@, info2@, almacen@).
Descarga adjuntos PDF/imagen a la carpeta de entrada y recuerda los Message-ID procesados para no repetir.
No lee el contenido de los documentos: eso es lector.py."""

import email
import imaplib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from idm.albaranes.extraer import EXTENSIONES_IMAGEN, EXTENSIONES_PDF, sha256_fichero
from idm.config import Buzon

EXTENSIONES_ADMITIDAS = EXTENSIONES_PDF | EXTENSIONES_IMAGEN


@dataclass(frozen=True)
class DocumentoEntrante:
    ruta: Path
    sha256: str
    origen: str  # "carpeta" o "imap:<usuario>"
    remitente: str | None = None
    asunto: str | None = None


class FuenteDocumentos(Protocol):
    def pendientes(self) -> list[DocumentoEntrante]: ...


class CarpetaEntrada:
    """Todo fichero admitido que haya en la carpeta. La idempotencia por SHA-256 la aplica quien procesa."""

    def __init__(self, carpeta: Path) -> None:
        self.carpeta = Path(carpeta)

    def pendientes(self) -> list[DocumentoEntrante]:
        if not self.carpeta.exists():
            return []
        return [
            DocumentoEntrante(ruta=r, sha256=sha256_fichero(r), origen="carpeta")
            for r in sorted(self.carpeta.iterdir())
            if r.is_file() and r.suffix.lower() in EXTENSIONES_ADMITIDAS
        ]


def nombre_seguro(nombre: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)[:120] or "adjunto"


def adjuntos_admitidos(mensaje: EmailMessage) -> list[tuple[str, bytes]]:
    """(nombre, bytes) de cada adjunto PDF o imagen del correo. Función pura, probada sin servidor."""
    resultado = []
    for parte in mensaje.iter_attachments():
        nombre = parte.get_filename() or ""
        if Path(nombre).suffix.lower() in EXTENSIONES_ADMITIDAS:
            resultado.append((nombre_seguro(nombre), parte.get_payload(decode=True) or b""))
    return resultado


class RegistroProcesados:
    """Message-ID ya descargados, uno por línea en un JSONL. Evita bajar dos veces el mismo correo."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = Path(ruta)
        self._ids: set[str] | None = None

    def contiene(self, message_id: str) -> bool:
        if self._ids is None:
            self._ids = set()
            if self.ruta.exists():
                for linea in self.ruta.read_text(encoding="utf-8").splitlines():
                    if linea.strip():
                        self._ids.add(json.loads(linea)["message_id"])
        return message_id in self._ids

    def anotar(self, message_id: str, datos: dict) -> None:
        self.contiene(message_id)
        assert self._ids is not None
        self._ids.add(message_id)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps({"message_id": message_id, "fecha": datetime.now().isoformat(), **datos}, ensure_ascii=False)
                + "\n"
            )


class BuzonIMAP:
    """Descarga a `destino` los adjuntos de los correos no procesados del buzón. Solo lectura del buzón."""

    def __init__(self, buzon: Buzon, destino: Path, registro: RegistroProcesados, criterio: str = "ALL") -> None:
        self.buzon, self.destino, self.registro, self.criterio = buzon, Path(destino), registro, criterio

    def pendientes(self) -> list[DocumentoEntrante]:
        self.destino.mkdir(parents=True, exist_ok=True)
        resultado: list[DocumentoEntrante] = []
        with imaplib.IMAP4_SSL(self.buzon.host) as imap:
            imap.login(self.buzon.usuario, self.buzon.clave)
            imap.select(self.buzon.carpeta, readonly=True)
            _, datos = imap.search(None, self.criterio)
            for uid in datos[0].split():
                _, partes = imap.fetch(uid, "(RFC822)")
                crudo = next((p[1] for p in partes if isinstance(p, tuple)), None)
                if crudo is None:
                    continue
                mensaje = email.message_from_bytes(crudo, policy=policy.default)
                message_id = mensaje.get("Message-ID") or f"sin-id-{uid.decode()}"
                if self.registro.contiene(message_id):
                    continue
                guardados = []
                for nombre, contenido in adjuntos_admitidos(mensaje):
                    ruta = self.destino / f"{datetime.now():%Y%m%d}_{nombre}"
                    contador = 1
                    while ruta.exists():
                        ruta = ruta.with_name(f"{ruta.stem}_{contador}{ruta.suffix}")
                        contador += 1
                    ruta.write_bytes(contenido)
                    guardados.append(str(ruta))
                    resultado.append(
                        DocumentoEntrante(
                            ruta=ruta,
                            sha256=sha256_fichero(ruta),
                            origen=f"imap:{self.buzon.usuario}",
                            remitente=mensaje.get("From"),
                            asunto=mensaje.get("Subject"),
                        )
                    )
                self.registro.anotar(
                    message_id,
                    {
                        "buzon": self.buzon.usuario,
                        "adjuntos": guardados,
                        "de": mensaje.get("From"),
                        "asunto": mensaje.get("Subject"),
                    },
                )
        return resultado
