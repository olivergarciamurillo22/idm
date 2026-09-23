"""Tests de almacen/sql.py sobre SQLite temporal creado con las migraciones de Alembic: documentos (idempotencia por
SHA y por número), eventos, pedidos y encargos. Mismo contrato que RepositorioMemoria."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from idm.almacen.documentos import DocumentoRegistrado, Evento
from idm.almacen.sesion import migrar, motor
from idm.almacen.sql import EncargosSQL, RepositorioSQL
from idm.dominio.estados import EstadoDocumento, EstadoEncargo, RelacionPedido, Semaforo, TipoDocumento
from idm.dominio.modelos import LineaPedido, Pedido
from idm.encargos.registro import Encargo


@pytest.fixture
def sesion(tmp_path):
    url = f"sqlite:///{tmp_path / 'idm.db'}"
    migrar(url)
    s = Session(motor(url))
    yield s
    s.close()


def _doc(sha, numero="B26 1", proveedor="FICT_VEGA"):
    return DocumentoRegistrado(
        sha256=sha,
        tipo=TipoDocumento.ALBARAN,
        proveedor=proveedor,
        numero=numero,
        numero_original="AC " + numero,
        ruta="x.pdf",
        semaforo=Semaforo.VERDE,
        estado=EstadoDocumento.EN_REVISION,
    )


def test_documentos_idempotencia_y_filtros(sesion):
    repo = RepositorioSQL(sesion)
    d = repo.guardar(_doc("a" * 64))
    assert repo.existe_sha("a" * 64).id == d.id
    assert repo.existe_numero("FICT_VEGA", TipoDocumento.ALBARAN, "B26 1").id == d.id
    assert repo.existe_numero("FICT_VEGA", TipoDocumento.ALBARAN, "B26 2") is None
    with pytest.raises(IntegrityError):
        repo.guardar(_doc("b" * 64))  # mismo proveedor+tipo+número: la BD lo impide
    sesion.rollback()
    repo.guardar(_doc("c" * 64, numero="B26 2", proveedor="FICT_ELECTRO"))
    assert len(repo.listar()) == 2
    assert [x.proveedor for x in repo.listar(proveedor="FICT_ELECTRO")] == ["FICT_ELECTRO"]
    d.estado = EstadoDocumento.APROBADO
    d.numero_registro_siddex = "20262921"
    repo.guardar(d)
    assert repo.obtener(d.id).numero_registro_siddex == "20262921"
    assert [x.id for x in repo.listar(estado=EstadoDocumento.APROBADO)] == [d.id]


def test_eventos_y_pedidos(sesion):
    repo = RepositorioSQL(sesion)
    repo.registrar_evento(Evento(tipo="documento.recibido", documento_id="doc1", datos={"sha256": "x"}))
    repo.registrar_evento(Evento(tipo="decision.tomada", documento_id="doc1", datos={"decision": "APROBADO"}))
    repo.registrar_evento(Evento(tipo="pedido.generado", datos={"pedido": "P-1"}))
    assert [e.tipo for e in repo.eventos("doc1")] == ["documento.recibido", "decision.tomada"]
    assert len(repo.eventos()) == 3
    pedido = Pedido(
        numero="P-20260923-01",
        proveedor="FICT_VEGA",
        fecha=date(2026, 9, 23),
        lineas=[LineaPedido(codigo_idm="I33.000.786", cantidad=Decimal("5"), precio_bruto=Decimal("9.14"))],
    )
    repo.guardar_pedido(pedido)
    pedido.numero_siddex = "20261099"
    repo.guardar_pedido(pedido)
    guardado = repo.pedidos("FICT_VEGA")[0]
    assert guardado.numero_siddex == "20261099" and guardado.lineas[0].importe == Decimal("45.70")
    assert guardado.relacion == RelacionPedido.CON_PEDIDO


def test_encargos_sql(sesion):
    repo = EncargosSQL(sesion)
    e = repo.guardar(Encargo(proveedor="La Cepa", articulo="I33.000.786", cantidad=Decimal("5"), quien="F"))
    repo.guardar(Encargo(proveedor="Meyras", articulo="rele", cantidad=Decimal("12.5")))
    assert len(repo.listar(EstadoEncargo.PENDIENTE)) == 2
    assert repo.marcar([e.id], EstadoEncargo.EN_PEDIDO, "P-1") == 1
    assert repo.obtener(e.id).pedido == "P-1" and repo.obtener(e.id).estado == EstadoEncargo.EN_PEDIDO
    assert [x.cantidad for x in repo.listar(EstadoEncargo.PENDIENTE)] == [Decimal("12.500")]
