"""Test de integración de generar_pedidos con config apuntando a tmp_path y gateway sobre fixtures.
No envía correo (CorreoSimulado) ni toca datos/."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from idm import config
from idm.dominio.estados import EstadoEncargo
from idm.encargos.registro import Encargo, EncargosJSONL
from idm.pedidos.enviar import CorreoSimulado
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.tareas import generar_pedidos


def _config(tmp_path: Path, fixtures: Path) -> config.Config:
    return config.Config(
        ruta_datos=tmp_path, ruta_entrada=tmp_path / "entrada", ruta_procesados=tmp_path / "procesados",
        ruta_siddex=fixtures / "siddex", ruta_planning=fixtures / "planning_ficticio.xlsx",
        ruta_pedidos_pdf=tmp_path / "pedidos", ruta_salida=tmp_path / "salida",
        ruta_pedidos_transmitidos=tmp_path / "transmitidos", database_url=f"sqlite:///{tmp_path / 'idm.db'}",
        modo_simulacion=True, empresa={"nombre": "EMPRESA FICTICIA"},
    )


def test_generar_pedidos_desde_encargos_y_planning(tmp_path, fixtures):
    cfg = _config(tmp_path, fixtures)
    repo = EncargosJSONL(tmp_path / "encargos.jsonl")
    repo.guardar(Encargo(proveedor="Recambios Ejemplo", articulo="H50.000.020", cantidad=Decimal("1")))
    correo = CorreoSimulado(tmp_path / "correo")
    informe = generar_pedidos.ejecutar(cfg, SiddexDesdeExcel(cfg.ruta_siddex), repo, correo,
                                       hoja="SEPT_26", fecha=date(2026, 9, 23),
                                       mapa=fixtures / "siddex" / "mapa_productos_ficticio.csv")
    texto = "\n".join(informe)
    assert "P-20260923-01 FICT_ELECTRO" in texto and "FICT_RECAMBIOS" in texto and "FICT_VEGA" in texto
    assert "Hoja para Siddex" in texto
    assert len(list((tmp_path / "pedidos").glob("*.pdf"))) == 3
    assert len(list((tmp_path / "transmitidos").glob("*.pdf"))) == 3
    assert len(list((tmp_path / "correo").glob("*.eml"))) == 3
    assert repo.listar(EstadoEncargo.PENDIENTE) == []
    assert repo.listar()[0].estado == EstadoEncargo.EN_PEDIDO
