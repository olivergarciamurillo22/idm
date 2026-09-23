"""Test de integración del comando calcular_mes sobre fixtures: produce el Excel de necesidades.
No lee .env ni datos/: pasa todas las rutas por argumentos."""

from idm.tareas import calcular_mes


def test_calcular_mes_produce_excel(fixtures, tmp_path):
    salida = tmp_path / "necesidades_SEPT_26.xlsx"
    ruta = calcular_mes.ejecutar(
        "SEPT_26", fixtures / "planning_ficticio.xlsx", fixtures / "siddex", salida,
        fixtures / "siddex" / "mapa_productos_ficticio.csv", descontar_stock=False,
    )
    assert ruta.exists() and ruta.stat().st_size > 0
