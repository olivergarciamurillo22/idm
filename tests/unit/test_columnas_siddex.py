"""Configuración de columnas de Siddex (BLOQUE 8): tolerancia a espacios/acentos/mayúsculas, error claro si falta una
requerida, informe de encontradas/faltantes/desconocidas, alias extra por columnas.json y cero pérdida silenciosa."""

import json

import openpyxl
import pytest

from idm.siddex import columnas
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.tareas.revisar_exports import revisar


def _excel(ruta, cabeceras, filas, filas_previas=2):
    libro = openpyxl.Workbook()
    ws = libro.active
    for _ in range(filas_previas):
        ws.append(["Export de prueba"])
    ws.append(cabeceras)
    for f in filas:
        ws.append(f)
    libro.save(ruta)
    return ruta


def test_normalizar_cabecera_tolerante():
    assert columnas.normalizar_cabecera("  Código_Artículo. ") == "codigo articulo"
    assert columnas.normalizar_cabecera("DTO %") == "dto %"
    assert columnas.normalizar_cabecera("Cód. Proveedor") == "cod proveedor"
    assert columnas.normalizar_cabecera(None) == ""


def test_lee_con_cabeceras_variadas_e_informe(tmp_path):
    ruta = _excel(
        tmp_path / "stock.xlsx", ["  CÓDIGO ARTÍCULO", "Existencias", "Almacén"], [["A1", 5, "P"], ["A2", 0, "P"]]
    )
    filas, informe = columnas.leer_tabla(ruta, "stock")
    assert [f["codigo"] for f in filas] == ["A1", "A2"] and filas[0]["stock"] == 5
    assert informe.ok and informe.fila_cabecera == 3 and informe.filas == 2
    assert informe.encontradas == {"codigo": "CÓDIGO ARTÍCULO", "stock": "Existencias"}
    assert informe.desconocidas == ["Almacén"] and informe.faltantes_requeridas == []
    assert "Almacén" in informe.texto() and "OK" in informe.texto()


def test_falta_requerida_mensaje_claro(tmp_path):
    ruta = _excel(tmp_path / "stock.xlsx", ["Código", "Ubicación"], [["A1", "P"]])
    with pytest.raises(columnas.ColumnasFaltantes) as exc:
        columnas.leer_tabla(ruta, "stock")
    assert "faltan columnas requeridas: stock" in str(exc.value)
    assert "Ubicación" in str(exc.value) and "columnas.json" in str(exc.value)
    assert exc.value.informe.faltantes_requeridas == ["stock"] and exc.value.informe.encontradas == {"codigo": "Código"}


def test_sin_cabecera_reconocible(tmp_path):
    ruta = _excel(tmp_path / "stock.xlsx", ["Uno", "Dos"], [["x", "y"]])
    with pytest.raises(columnas.ColumnasFaltantes) as exc:
        columnas.leer_tabla(ruta, "stock")
    assert exc.value.informe.fila_cabecera is None and "Uno" in exc.value.informe.cabeceras_vistas


def test_alias_extra_desde_columnas_json(tmp_path):
    (tmp_path / "columnas.json").write_text(json.dumps({"stock": {"stock": ["Unidades en almacén"]}}), encoding="utf-8")
    ruta = _excel(tmp_path / "stock.xlsx", ["Código", "Unidades en Almacén"], [["A1", 7]])
    filas, informe = columnas.leer_tabla(ruta, "stock", columnas.cargar_alias_extra(tmp_path))
    assert filas[0]["stock"] == 7 and informe.ok


def test_alias_extra_campo_desconocido_avisa(tmp_path):
    (tmp_path / "columnas.json").write_text(json.dumps({"stock": {"inventado": ["x"]}}), encoding="utf-8")
    with pytest.raises(ValueError, match="campos desconocidos"):
        columnas.columnas_de("stock", columnas.cargar_alias_extra(tmp_path))


def test_columna_opcional_ausente_no_es_silenciosa(tmp_path):
    _excel(tmp_path / "articulos.xlsx", ["Código", "Descripción", "Proveedor"], [["A1", "Cosa", 9001]])
    g = SiddexDesdeExcel(tmp_path)
    arts = g.articulos()
    assert arts["A1"].multiplo_compra == 1 and arts["A1"].precio_compra is None
    assert any("sin columna 'multiplo'" in a for a in g.avisos) and any("sin columna 'precio'" in a for a in g.avisos)
    assert g.informes["articulos"].faltantes_opcionales


def test_gateway_no_estricto_devuelve_vacio_y_avisa(tmp_path):
    _excel(tmp_path / "pedidos.xlsx", ["Pedido", "Artículo"], [[1, "A1"]])  # faltan proveedor, cantidad y precio
    g = SiddexDesdeExcel(tmp_path)
    assert g.pedidos_abiertos() == [] and any("faltan columnas requeridas" in a for a in g.avisos)
    with pytest.raises(columnas.ColumnasFaltantes):
        SiddexDesdeExcel(tmp_path, estricto=True).pedidos_abiertos()


def test_informes_sobre_fixtures(fixtures):
    g = SiddexDesdeExcel(fixtures / "siddex")
    g.articulos(), g.proveedores(), g.equivalencias(), g.pedidos_abiertos(), g.stock()
    assert set(g.informes) == {"articulos", "proveedores", "fabricantes", "pedidos", "stock"}
    assert all(inf.ok for inf in g.informes.values())
    assert "[pedidos] pedidos.xlsx: OK" in g.informe_texto()


def test_cache_de_pedidos_se_invalida_al_cambiar_el_fichero(fixtures, tmp_path):
    import shutil

    for n in ("pedidos.xlsx", "proveedores.xlsx"):
        shutil.copy(fixtures / "siddex" / n, tmp_path / n)
    g = SiddexDesdeExcel(tmp_path)
    assert len(g.pedidos_abiertos()) == 2
    _excel(
        tmp_path / "pedidos.xlsx", ["Pedido", "Proveedor", "Artículo", "Cantidad", "Precio"], [[1, 9001, "A1", 1, 1]]
    )
    import os
    import time

    t = time.time() + 5
    os.utime(tmp_path / "pedidos.xlsx", (t, t))
    assert [p.numero for p in g.pedidos_abiertos()] == ["1"]


def test_revisar_exports_sobre_fixtures(fixtures):
    salida = "\n".join(revisar(fixtures / "siddex", muestra=1))
    assert "[articulos] articulos.xlsx: OK" in salida and "Escandallos (.xls BIFF2): 2" in salida
    assert "M91.000.001" in salida and "codigo_minuscula=1" in salida
