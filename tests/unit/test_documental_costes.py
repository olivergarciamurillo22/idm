"""Costes: tarifas fechadas, estimación por páginas y extras, proyección por 100/1.000/mes, proveedor sin tarifa y
fichero de tarifas propio. Sin volumen mensual no se inventa nada."""

import json
from decimal import Decimal

from idm.documental.costes import Tarifas, estimar, proyectar


def test_tarifas_por_defecto_fechadas():
    t = Tarifas.cargar()
    assert t.fecha == "2026-09-24" and "VERIFICAR" in t.datos["_aviso"]
    assert t.por_1000_paginas("azure", "prebuilt-layout") == Decimal("10.0")
    assert t.por_1000_paginas("azure", "modelo-raro") == Decimal("10.0")  # comodín
    assert t.por_1000_paginas("tesseract", "cualquiera") == Decimal("0.0")
    assert t.por_1000_paginas("inventado", "x") is None


def test_estimar_con_extras():
    t = Tarifas.cargar()
    c = estimar(t, "mistral", "mistral-ocr-latest", 3, ("document_annotation",))
    assert c.usd == Decimal("0.0150") and c.eur == Decimal("0.0138") and c.fecha_tarifa == t.fecha


def test_proyeccion():
    p = proyectar(Tarifas.cargar(), "azure", "prebuilt-layout", Decimal("1.5"), 400)
    assert p.eur_por_documento == Decimal("0.0138") and p.eur_por_100 == Decimal("1.38")
    assert p.eur_por_1000 == Decimal("13.80") and p.eur_mes == Decimal("5.52")
    assert "400 documentos" in p.texto()
    sin_volumen = proyectar(Tarifas.cargar(), "azure", "prebuilt-layout")
    assert sin_volumen.eur_mes is None and "--documentos-mes" in sin_volumen.texto()


def test_fichero_de_tarifas_propio(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(
        json.dumps(
            {
                "fecha_referencia": "2027-01-01",
                "usd_a_eur": 1,
                "proveedores": {"azure": {"modelos": {"*": {"usd_por_1000_paginas": 20}}}},
            }
        ),
        encoding="utf-8",
    )
    assert estimar(Tarifas.cargar(f), "azure", "x", 1000).eur == Decimal("20.0000")
