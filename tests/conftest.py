"""Configuración común de pytest: rutas a fixtures y utilidades compartidas.
Solo expone fixtures de pytest; no contiene lógica de negocio.
No lee datos/ ni .env: los tests son independientes del entorno."""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = RAIZ / "fixtures"


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
