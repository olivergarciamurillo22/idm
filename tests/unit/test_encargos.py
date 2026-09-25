"""Tests de encargos/: repositorio JSONL (guardar, listar, marcar) y mensaje con formato fijo.
No usa web ni base de datos."""

from decimal import Decimal

from idm.dominio.estados import EstadoEncargo, OrigenEncargo
from idm.encargos import mensaje
from idm.encargos.registro import Encargo, EncargosJSONL


def test_jsonl_guarda_lista_y_marca(tmp_path):
    repo = EncargosJSONL(tmp_path / "encargos.jsonl")
    e1 = repo.guardar(Encargo(proveedor="La Cepa", articulo="Z33.000.786", cantidad=Decimal("5"), quien="Fernandillo"))
    repo.guardar(Encargo(proveedor="Meyras", articulo="rele 24v", cantidad=Decimal("12")))
    assert len(repo.listar()) == 2
    assert repo.marcar([e1.id], EstadoEncargo.EN_PEDIDO, pedido="P-20260923-01") == 1
    assert [e.proveedor for e in repo.listar(EstadoEncargo.PENDIENTE)] == ["Meyras"]
    assert repo.obtener(e1.id).pedido == "P-20260923-01"
    assert len(repo.listar()) == 2  # el estado nuevo sustituye, no duplica


def test_mensaje_formato_fijo():
    texto = "La Cepa ; Z33.000.786 ; 5\nMeyras | rele 24v | 12 | ud\n# comentario\nsin separador\nX;Y;cero"
    r = mensaje.interpretar(texto, quien="Fernandillo")
    assert [(e.proveedor, e.articulo, e.cantidad, e.unidad) for e in r.encargos] == [
        ("La Cepa", "Z33.000.786", Decimal("5"), "UD"),
        ("Meyras", "rele 24v", Decimal("12"), "UD"),
    ]
    assert r.encargos[0].origen == OrigenEncargo.MENSAJE and r.encargos[0].quien == "Fernandillo"
    assert len(r.errores) == 2
    assert "Línea 4" in r.errores[0] and "Línea 5" in r.errores[1]
