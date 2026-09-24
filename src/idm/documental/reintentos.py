"""Llamadas HTTP con reintentos acotados para errores transitorios (red, 408, 429, 5xx) respetando Retry-After.
Traduce el resultado a ErrorTransitorio / ErrorPermanente con el request id del proveedor si lo hay.
No cambia de proveedor: si se agotan los reintentos el documento queda pendiente, no se manda a otro tercero."""

import time
from collections.abc import Callable

from idm.documental.base import ErrorPermanente, ErrorTransitorio
from idm.documental.http import ClienteHTTP, ErrorRed, RespuestaHTTP

TRANSITORIOS = {408, 429, 500, 502, 503, 504}
CABECERAS_REQUEST_ID = ("apim-request-id", "x-request-id", "x-ms-request-id", "mistral-correlation-id", "request-id")


def request_id(respuesta: RespuestaHTTP | None) -> str | None:
    if respuesta is None:
        return None
    for nombre in CABECERAS_REQUEST_ID:
        if valor := respuesta.cabecera(nombre):
            return valor
    return None


def _espera(respuesta: RespuestaHTTP | None, intento: int) -> float:
    if respuesta is not None and (ra := respuesta.cabecera("retry-after")):
        try:
            return min(float(ra), 30.0)
        except ValueError:
            pass
    return min(2.0**intento, 30.0)


def cuota_cero(respuesta: RespuestaHTTP) -> bool:
    """429 con un límite anunciado de 0 peticiones (x-ratelimit-limit-*: 0): la cuenta no tiene esta API habilitada
    (p. ej. sin facturación activa). Reintentar no sirve: es un error permanente de configuración de la cuenta."""
    return respuesta.status == 429 and any(
        k.startswith("x-ratelimit-limit") and v.strip() == "0" for k, v in respuesta.cabeceras.items()
    )


def _detalle(respuesta: RespuestaHTTP) -> str:
    """Mensaje de error del proveedor, recortado. El cuerpo de error no contiene el documento."""
    try:
        datos = respuesta.json()
        error = datos.get("error", datos)
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or error)[:300]
        return str(error)[:300]
    except (ValueError, UnicodeDecodeError):
        return respuesta.cuerpo[:200].decode("utf-8", "replace")


def llamar(
    http: ClienteHTTP,
    metodo: str,
    url: str,
    cabeceras: dict[str, str],
    cuerpo: bytes | None,
    timeout_s: float,
    intentos: int = 3,
    esperar: Callable[[float], None] = time.sleep,
    esperados: tuple[int, ...] = (200, 202),
) -> RespuestaHTTP:
    ultima: RespuestaHTTP | None = None
    for intento in range(max(intentos, 1)):
        try:
            ultima = http.enviar(metodo, url, cabeceras, cuerpo, timeout_s)
        except ErrorRed as exc:
            if intento + 1 >= intentos:
                raise ErrorTransitorio(f"Sin conexión con el proveedor: {exc}") from exc
            esperar(_espera(None, intento))
            continue
        if ultima.status in esperados:
            return ultima
        if cuota_cero(ultima):
            raise ErrorPermanente(
                "HTTP 429 con límite 0 peticiones/minuto: la cuenta del proveedor no tiene esta API habilitada "
                "(revisar plan y facturación en la consola del proveedor). No se reintenta.",
                request_id(ultima),
                ultima.status,
            )
        if ultima.status in TRANSITORIOS:
            if intento + 1 >= intentos:
                break
            esperar(_espera(ultima, intento))
            continue
        tipo = "credenciales o permisos" if ultima.status in (401, 403) else "petición rechazada"
        raise ErrorPermanente(f"HTTP {ultima.status} ({tipo}): {_detalle(ultima)}", request_id(ultima), ultima.status)
    assert ultima is not None
    raise ErrorTransitorio(
        f"HTTP {ultima.status} tras {intentos} intentos: {_detalle(ultima)}", request_id(ultima), ultima.status
    )
