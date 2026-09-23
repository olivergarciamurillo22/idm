"""Tests de pedidos/: agrupar por proveedor, PDF, correo simulado y hoja para Siddex.
Usa los exports ficticios de fixtures/siddex y escribe solo en tmp_path."""

from datetime import date
from decimal import Decimal
from email import message_from_bytes, policy
from pathlib import Path

import openpyxl

from idm.encargos.registro import Encargo
from idm.necesidades.calculo import Necesidad
from idm.pedidos import enviar, exportar_siddex, generar, pdf
from idm.siddex.desde_excel import SiddexDesdeExcel


def _gateway(fixtures):
    return SiddexDesdeExcel(fixtures / "siddex")


def test_generar_agrupa_por_proveedor(fixtures):
    g = _gateway(fixtures)
    necesidades = [
        Necesidad(
            "T30.000.100",
            "TORNILLO",
            "UD",
            "Comercial",
            "FICT_ELECTRO",
            cantidad_pedir=Decimal("200"),
            precio=Decimal("0.08"),
        ),
        Necesidad(
            "R40.000.001", "RUEDA", "UD", "Comercial", "FICT_VEGA", cantidad_pedir=Decimal("8"), precio=Decimal("38")
        ),
        Necesidad("P20.000.010", "CORTE TUBO", "UD", "MP", None, cantidad_pedir=Decimal("4"), fuera_circuito=True),
        Necesidad("X00.000.001", "SIN PROVEEDOR", "UD", "Comercial", None, cantidad_pedir=Decimal("1")),
    ]
    encargos = [
        Encargo(id="e1", proveedor="Electro Ficticio", articulo="I34.000.900", cantidad=Decimal("12")),
        Encargo(id="e2", proveedor="FICT_VEGA", articulo="R40.000.001", cantidad=Decimal("2")),
        Encargo(id="e3", proveedor="Nadie S.L.", articulo="cosa", cantidad=Decimal("1")),
    ]
    r = generar.generar(necesidades, encargos, g.articulos(), g.proveedores(), date(2026, 9, 23))
    assert [p.numero for p in r.pedidos] == ["P-20260923-01", "P-20260923-02"]
    electro, vega = r.pedidos
    assert electro.proveedor == "FICT_ELECTRO" and vega.proveedor == "FICT_VEGA"
    assert {li.codigo_idm: li.cantidad for li in electro.lineas} == {
        "T30.000.100": Decimal("200"),
        "I34.000.900": Decimal("12"),
    }
    assert {li.codigo_idm: li.cantidad for li in vega.lineas} == {"R40.000.001": Decimal("10")}  # 8 + 2 encargo
    assert electro.lineas[1].descuento_pct == Decimal("10")  # del maestro
    assert r.encargos_por_pedido == {"P-20260923-01": ["e1"], "P-20260923-02": ["e2"]}
    assert len(r.sin_proveedor) == 2  # X00 sin proveedor habitual y encargo de Nadie S.L.


def test_pdf_correo_y_hoja_siddex(fixtures, tmp_path):
    g = _gateway(fixtures)
    provs = {p.clave: p for p in g.proveedores()}
    r = generar.generar(
        [],
        [Encargo(proveedor="FICT_VEGA", articulo="I33.000.786", cantidad=Decimal("5"))],
        g.articulos(),
        g.proveedores(),
        date(2026, 9, 23),
    )
    pedido = r.pedidos[0]
    assert pedido.total == Decimal("25.14")
    ruta_pdf = pdf.generar_pdf(pedido, provs["FICT_VEGA"], {"nombre": "EMPRESA FICTICIA"}, tmp_path / "pedidos")
    assert ruta_pdf.exists() and ruta_pdf.read_bytes()[:4] == b"%PDF"

    correo = enviar.CorreoSimulado(tmp_path / "correo", "pedidos@ficticio.local")
    destino = correo.enviar(enviar.componer(pedido, provs["FICT_VEGA"], {"nombre": "EMPRESA FICTICIA"}, ruta_pdf))
    em = message_from_bytes(Path(destino).read_bytes(), policy=policy.default)
    assert em["To"] == "pedidos@vega.ficticio"
    assert "P-20260923-01" in em["Subject"]
    assert any(p.get_filename() == ruta_pdf.name for p in em.iter_attachments())

    hoja = exportar_siddex.exportar(r.pedidos, provs, tmp_path / "siddex.xlsx")
    libro = openpyxl.load_workbook(hoja)
    filas = list(libro["P-20260923-01"].iter_rows(values_only=True))
    assert filas[1][0] == "9001" and filas[1][3] == "I33.000.786" and filas[1][5] == 5
