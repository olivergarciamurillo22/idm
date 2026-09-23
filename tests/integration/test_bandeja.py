"""Test de integración de la bandeja con TestClient: lista con filtros, documento, aprobar con nº de registro,
equivalencia aprendida, pedido propuesto confirmado y formulario de encargos."""

import shutil

from fastapi.testclient import TestClient

from idm import config
from idm.albaranes.buzon import CarpetaEntrada
from idm.albaranes.lector import LectorAutomatico
from idm.almacen.documentos import RepositorioMemoria
from idm.bandeja.app import crear_app
from idm.cotejo.procesar import procesar
from idm.dominio.estados import EstadoDocumento, RelacionPedido
from idm.encargos.registro import EncargosJSONL
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel


def _cliente(fixtures, tmp_path):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    for n in ("albaran_vega_bruto_descuento.pdf", "albaran_recambios_sin_precio.pdf"):
        shutil.copy(fixtures / "documentos" / n, entrada / n)
    g = SiddexDesdeExcel(fixtures / "siddex")
    tabla = TablaEquivalencias.desde(g.equivalencias())
    repo = RepositorioMemoria()
    for e in CarpetaEntrada(entrada).pendientes():
        procesar(e, LectorAutomatico(), g, tabla, repo)
    cfg = config.Config(
        ruta_datos=tmp_path,
        ruta_entrada=entrada,
        ruta_procesados=tmp_path / "p",
        ruta_siddex=fixtures / "siddex",
        ruta_planning=fixtures / "planning_ficticio.xlsx",
        ruta_pedidos_pdf=tmp_path / "pdf",
        ruta_salida=tmp_path / "salida",
        ruta_pedidos_transmitidos=None,
        database_url="sqlite://",
        modo_simulacion=True,
    )
    app = crear_app(repo, EncargosJSONL(tmp_path / "encargos.jsonl"), cfg, tabla, {p.clave: p for p in g.proveedores()})
    return TestClient(app), repo, tabla


def test_lista_y_filtros(fixtures, tmp_path):
    c, repo, _ = _cliente(fixtures, tmp_path)
    r = c.get("/")
    assert r.status_code == 200 and "B26 0100005283" in r.text and "5526/2063" in r.text
    assert "5526/2063" not in c.get("/?semaforo=VERDE").text
    assert "B26 0100005283" not in c.get("/?proveedor=FICT_RECAMBIOS").text


def test_documento_aprobar_y_equivalencia(fixtures, tmp_path):
    c, repo, tabla = _cliente(fixtures, tmp_path)
    doc = next(d for d in repo.listar() if d.proveedor == "FICT_RECAMBIOS")
    r = c.get(f"/documentos/{doc.id}")
    assert r.status_code == 200 and "PENDIENTE_FACTURA" in r.text and "PP-5526/2063" in r.text
    assert c.get(f"/documentos/{doc.id}/fichero").headers["content-type"] == "application/pdf"

    r = c.post(
        f"/documentos/{doc.id}/equivalencia", data={"linea": "1", "codigo_idm": "i99.000.001"}, follow_redirects=False
    )
    assert r.status_code == 303
    assert doc.albaran.lineas[1].codigo_idm == "I99.000.001"
    assert tabla.resolver("FICT_RECAMBIOS", "FL-2240").metodo == "aprendida"
    assert (tmp_path / "equivalencias_aprendidas.csv").exists()

    r = c.post(
        f"/documentos/{doc.id}/aprobar",
        data={"numero_registro_siddex": "20262921", "quien": "Fernando"},
        follow_redirects=True,
    )
    assert "20262921" in r.text and doc.estado == EstadoDocumento.APROBADO
    assert repo.eventos(doc.id)[-1].tipo == "decision.tomada"
    assert "Aprobar" not in r.text.split("Decisión")[-1][:200]


def test_pedido_propuesto_confirmar(fixtures, tmp_path):
    c, repo, _ = _cliente(fixtures, tmp_path)
    doc = next(d for d in repo.listar() if d.pedido_propuesto is not None)
    assert "PP-5526/2063" in c.get("/pedidos").text
    r = c.post(f"/pedidos/{doc.id}/confirmar", data={"quien": "Fernandillo"}, follow_redirects=True)
    assert r.status_code == 200 and doc.relacion == RelacionPedido.CON_PEDIDO and doc.pedido == "PP-5526/2063"
    assert list((tmp_path / "salida").glob("pedido_propuesto_*.xlsx"))
    assert "PP-5526/2063" not in c.get("/pedidos").text


def test_encargos_web(fixtures, tmp_path):
    c, _, _ = _cliente(fixtures, tmp_path)
    assert c.get("/encargos").status_code == 200
    r = c.post(
        "/encargos",
        data={"proveedor": "La Cepa", "articulo": "I33.000.786", "cantidad": "5", "quien": "F"},
        follow_redirects=True,
    )
    assert "I33.000.786" in r.text
    r = c.post("/encargos", data={"texto": "Meyras ; rele ; 12\nmal", "quien": "F"}, follow_redirects=True)
    assert "rele" in r.text and "Línea 2" in r.text
    r = c.post("/encargos", data={"proveedor": "", "articulo": "x", "cantidad": "1"}, follow_redirects=True)
    assert "Faltan" in r.text
