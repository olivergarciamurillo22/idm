"""Casos de fixtures/problematicos: representan situaciones reales sin regla de IDM todavía. Están xfail(strict=True):
si un día pasan, pytest avisa (XPASS): hay que moverlos a fixtures/golden y cerrar el punto en docs/PENDIENTE-IDM.md."""

from pathlib import Path

import pytest

from idm.dominio.golden import ejecutar_caso

PROBLEMATICOS = Path(__file__).resolve().parents[2] / "fixtures" / "problematicos"
CASOS = sorted(p for p in PROBLEMATICOS.iterdir() if p.is_dir() and (p / "esperado.json").exists())


@pytest.mark.parametrize("caso", CASOS, ids=[c.name for c in CASOS])
@pytest.mark.xfail(strict=True, reason="pendiente de regla de IDM: ver PENDIENTE.md del caso y docs/PENDIENTE-IDM.md")
def test_caso_problematico(caso: Path):
    assert (caso / "PENDIENTE.md").exists(), "cada caso problemático explica qué falta"
    diferencias = ejecutar_caso(caso)
    assert diferencias == [], "\n".join(diferencias)


def test_todo_caso_problematico_tiene_pendiente():
    for caso in CASOS:
        texto = (caso / "PENDIENTE.md").read_text(encoding="utf-8")
        assert "Qué necesitamos de IDM" in texto, caso.name
