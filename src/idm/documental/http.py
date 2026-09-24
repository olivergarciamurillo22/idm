"""Cliente HTTP mínimo e inyectable para los proveedores cloud (urllib de la biblioteca estándar, sin SDK).
Los tests inyectan un cliente falso que registra peticiones y devuelve respuestas grabadas: ninguna llamada real.
No registra cabeceras ni cuerpos (llevan la clave y el documento): solo devuelve la respuesta al llamador."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RespuestaHTTP:
    status: int
    cabeceras: dict[str, str] = field(default_factory=dict)  # en minúsculas
    cuerpo: bytes = b""

    def json(self) -> dict:
        return json.loads(self.cuerpo.decode("utf-8") or "{}")

    def cabecera(self, nombre: str) -> str | None:
        return self.cabeceras.get(nombre.lower())


class ErrorRed(Exception):
    """Fallo de red o tiempo agotado antes de recibir respuesta."""


class ClienteHTTP(Protocol):
    def enviar(
        self, metodo: str, url: str, cabeceras: dict[str, str], cuerpo: bytes | None, timeout_s: float
    ) -> RespuestaHTTP: ...


class ClienteUrllib:
    def enviar(
        self, metodo: str, url: str, cabeceras: dict[str, str], cuerpo: bytes | None, timeout_s: float
    ) -> RespuestaHTTP:
        peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(peticion, timeout=timeout_s) as r:  # noqa: S310 - URL de configuración (https)
                return RespuestaHTTP(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
        except urllib.error.HTTPError as exc:
            return RespuestaHTTP(exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read() or b"")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ErrorRed(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
