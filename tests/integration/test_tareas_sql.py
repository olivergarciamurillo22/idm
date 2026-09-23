"""Integración de las tareas con la base de datos real (SQLite temporal): migrar, procesar_buzon sobre fixtures,
generar_pedidos guardando pedidos y eventos, y la bandeja servida sobre RepositorioSQL."""

import shutil
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from idm import config
from idm.albaranes.buzon import CarpetaEntrada
from idm.almacen.sesion import abrir, migrar
from idm.bandeja.app import crear_app
from idm.dominio.estados import EstadoEncargo
from idm.encargos.registro import Encargo
from idm.pedidos.enviar import CorreoSimulado
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.tareas import generar_pedidos, procesar_buzon


def _cfg(tmp_path, fixtures):
    return config.Config(
        ruta_datos=tmp_path,
        ruta_entrada=tmp_path / "entrada",
        ruta_procesados=tmp_path / "procesados",
        ruta_siddex=fixtures / "siddex",
        ruta_planning=fixtures / "planning_ficticio.xlsx",
        ruta_pedidos_pdf=tmp_path / "pedidos",
        ruta_salida=tmp_path / "salida",
        ruta_pedidos_transmitidos=None,
        database_url=f"sqlite:///{tmp_path / 'idm.db'}",
        modo_simulacion=True,
        empresa={"nombre": "FICTICIA"},
    )


def test_migrar_procesar_y_bandeja_con_sql(tmp_path, fixtures):
    cfg = _cfg(tmp_path, fixtures)
    cfg.crear_carpetas()
    migrar(cfg.database_url)
    for n in ("albaran_vega_bruto_descuento.pdf", "factura_vega_agrupa.pdf"):
        shutil.copy(fixtures / "documentos" / n, cfg.ruta_entrada / n)
    sesion, repo, encargos = abrir(cfg)
    entrantes = CarpetaEntrada(cfg.ruta_entrada).pendientes()
    informe = procesar_buzon.ejecutar(entrantes, SiddexDesdeExcel(cfg.ruta_siddex), repo, cfg)
    assert len(informe) == 2 and all(li.startswith("procesado") for li in informe)
    assert not list(cfg.ruta_entrada.iterdir()) and len(list(cfg.ruta_procesados.iterdir())) == 2
    assert len(repo.listar()) == 2 and len(repo.eventos()) >= 8

    # Segunda pasada con los mismos ficheros: duplicados, sin registros nuevos
    for n in ("albaran_vega_bruto_descuento.pdf",):
        shutil.copy(fixtures / "documentos" / n, cfg.ruta_entrada / n)
    informe = procesar_buzon.ejecutar(
        CarpetaEntrada(cfg.ruta_entrada).pendientes(), SiddexDesdeExcel(cfg.ruta_siddex), repo, cfg
    )
    assert informe[0].startswith("duplicado_sha") and len(repo.listar()) == 2

    encargos.guardar(Encargo(proveedor="FICT_VEGA", articulo="I33.000.786", cantidad=Decimal("5")))
    informe = generar_pedidos.ejecutar(
        cfg,
        SiddexDesdeExcel(cfg.ruta_siddex),
        encargos,
        CorreoSimulado(tmp_path / "correo"),
        hoja=None,
        fecha=date(2026, 9, 23),
        almacen=repo,
    )
    assert any("P-20260923-01 FICT_VEGA" in li for li in informe)
    assert repo.pedidos()[0].numero == "P-20260923-01"
    assert {e.tipo for e in repo.eventos()} >= {"pedido.generado", "correo.enviado"}
    assert encargos.listar(EstadoEncargo.PENDIENTE) == []

    app = crear_app(repo, encargos, cfg)
    c = TestClient(app)
    assert "B26 0100005283" in c.get("/").text and "F26/000731" in c.get("/?tipo=FACTURA").text
    doc = repo.listar(tipo=None)[-1]
    r = c.post(
        f"/documentos/{doc.id}/aprobar",
        data={"numero_registro_siddex": "20262921", "quien": "Fernando"},
        follow_redirects=True,
    )
    assert "20262921" in r.text and repo.obtener(doc.id).numero_registro_siddex == "20262921"
    sesion.close()
