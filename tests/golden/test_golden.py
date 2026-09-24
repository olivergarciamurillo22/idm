"""Ejecuta todos los casos de fixtures/golden/ y falla si alguno se desvía de esperado.json.
Cada caso es un test parametrizado con el nombre de su carpeta. Los casos con documento.pdf pasan por el lector real
y por interpretar_albaran con las equivalencias de los exports ficticios de fixtures/ficticios/siddex."""

from pathlib import Path

import pytest

from idm.albaranes.lector import leer
from idm.cotejo.interpretar import interpretar_albaran
from idm.dominio.golden import ejecutar_caso
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN = FIXTURES / "golden"
CASOS = sorted(p for p in GOLDEN.iterdir() if p.is_dir() and (p / "esperado.json").exists())


def _interpretar():
    gateway = SiddexDesdeExcel(FIXTURES / "ficticios" / "siddex")
    tabla = TablaEquivalencias.desde(gateway.equivalencias())
    proveedores = gateway.proveedores()
    return lambda doc: interpretar_albaran(doc, tabla, proveedores).albaran


@pytest.mark.parametrize("caso", CASOS, ids=[c.name for c in CASOS])
def test_caso_golden(caso: Path):
    diferencias = ejecutar_caso(caso, leer, _interpretar())
    assert diferencias == [], "\n".join(diferencias)
