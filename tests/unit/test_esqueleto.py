"""Test de humo de la Fase 0: el paquete importa y la estructura existe.
Comprueba que datos/ está ignorada y que las carpetas del reparto están.
No prueba lógica de negocio."""

import importlib


def test_paquete_importa():
    assert importlib.import_module("idm") is not None


def test_datos_ignorada(raiz):
    gitignore = (raiz / ".gitignore").read_text(encoding="utf-8")
    assert "datos/" in gitignore
    assert ".env" in gitignore


def test_estructura_reparto(raiz):
    for carpeta in [
        "dominio",
        "necesidades",
        "encargos",
        "pedidos",
        "albaranes",
        "cotejo",
        "siddex",
        "equivalencias",
        "bandeja",
        "almacen",
        "tareas",
    ]:
        assert (raiz / "src" / "idm" / carpeta / "__init__.py").exists(), carpeta
