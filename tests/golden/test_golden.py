"""Ejecuta todos los casos de fixtures/golden/ y falla si alguno se desvía de esperado.json.
Cada caso es un test parametrizado con el nombre de su carpeta.
Los casos con documento.pdf usan el lector real de albaranes/ si existe."""

from pathlib import Path

import pytest

from idm.dominio.golden import ejecutar_caso

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
CASOS = sorted(p for p in GOLDEN.iterdir() if p.is_dir() and (p / "esperado.json").exists())


def _lector_e_interprete():
    try:
        from idm.albaranes.lector import leer
        from idm.cotejo.interpretar import interpretar_albaran_fixture
    except ImportError:  # antes de la Fase 4/5 no hay lector
        return None, None
    return leer, interpretar_albaran_fixture


@pytest.mark.parametrize("caso", CASOS, ids=[c.name for c in CASOS])
def test_caso_golden(caso: Path):
    lector, interpretar = _lector_e_interprete()
    diferencias = ejecutar_caso(caso, lector, interpretar)
    assert diferencias == [], "\n".join(diferencias)
