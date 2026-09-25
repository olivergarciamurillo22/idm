"""Configuración común de pytest: rutas a fixtures y utilidades compartidas.
Solo expone fixtures de pytest; no contiene lógica de negocio.
No lee datos/ ni .env: los tests son independientes del entorno."""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = RAIZ / "fixtures"

# Variables que el programa lee del .env. En los tests NO deben venir del .env del desarrollador (puede tener claves
# reales de Mistral/Azure o la bandera de envío externo activada): cada test parte de la configuración por defecto.
PREFIJOS_CONFIG = (
    "RUTA_",
    "DATABASE_URL",
    "MODO_SIMULACION",
    "EMPRESA_",
    "SMTP_",
    "IMAP_",
    "BANDEJA_",
    "OCR_",
    "DOCUMENT_",
    "ALLOW_EXTERNAL",
    "EXTERNAL_DOCUMENT",
    "AZURE_DOCUMENT",
    "MISTRAL_",
    "TESSERACT_",
)


@pytest.fixture(autouse=True)
def _aislar_de_env_local(monkeypatch, tmp_path_factory):
    import os

    for nombre in list(os.environ):
        if nombre.startswith(PREFIJOS_CONFIG):
            monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv("IDM_ENV_FILE", str(tmp_path_factory.getbasetemp() / "sin_env_de_desarrollo.env"))


@pytest.fixture
def fixtures() -> Path:
    """Carpeta de fixtures FICTICIOS (documentos, siddex, planning). Los reales anonimizados van en fixtures/reales."""
    return FIXTURES / "ficticios"


@pytest.fixture
def fixtures_raiz() -> Path:
    return FIXTURES


@pytest.fixture
def raiz() -> Path:
    return RAIZ


# ------------------------------------------------------------------ cliente HTTP falso para proveedores documentales


class HTTPFalso:
    """Cliente HTTP de pruebas: devuelve respuestas encoladas y registra cada petición. Nunca abre la red."""

    def __init__(self, respuestas=None):
        from idm.documental.http import RespuestaHTTP

        self._R = RespuestaHTTP
        self.respuestas = list(respuestas or [])
        self.peticiones: list[dict] = []

    def encolar(self, status, cuerpo=None, cabeceras=None):
        import json as _json

        datos = cuerpo if isinstance(cuerpo, bytes) else _json.dumps(cuerpo or {}).encode()
        self.respuestas.append(self._R(status, {k.lower(): v for k, v in (cabeceras or {}).items()}, datos))
        return self

    def enviar(self, metodo, url, cabeceras, cuerpo, timeout_s):
        self.peticiones.append({"metodo": metodo, "url": url, "cabeceras": dict(cabeceras), "cuerpo": cuerpo})
        if not self.respuestas:
            raise AssertionError(f"petición inesperada {metodo} {url}")
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def http_falso():
    return HTTPFalso()


@pytest.fixture
def respuestas_documentales(fixtures) -> Path:
    return fixtures / "proveedores_documentales"
