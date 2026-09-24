"""Benchmark A/B con un proveedor falso sobre fixtures ficticios: métricas de cabecera, líneas (referencia, descripción,
cantidad, precio, descuento, importe), estructura, operación y tabla comparada; la tarea rechaza externos sin
autorización explícita y no envía nada."""

import json
import shutil
from decimal import Decimal

from idm.documental import benchmark
from idm.documental.azure import convertir as convertir_azure
from idm.documental.lector import LectorDocumental
from idm.documental.modelo import MetadatosMotor
from idm.documental.registro import RegistroMemoria


class _ProveedorGrabado:
    """Devuelve siempre la respuesta grabada de Azure (sin red)."""

    nombre, modelo, externo = "grabado", "azure-layout-grabado", False

    def __init__(self, respuesta):
        self.respuesta = respuesta

    def disponible(self):
        return True

    def analizar(self, documento):
        m = MetadatosMotor(proveedor="grabado", modelo=self.modelo, externo=False, coste_estimado_eur=Decimal("0.0092"))
        return convertir_azure(self.respuesta["analyzeResult"], m)


def _carpeta(fixtures, tmp_path):
    carpeta = tmp_path / "bench"
    carpeta.mkdir()
    shutil.copy(fixtures / "imagenes" / "albaran_sintetico.jpg", carpeta / "a.jpg")
    verdad = json.loads((fixtures / "imagenes" / "albaran_sintetico.json").read_text())
    verdad["proveedor"] = "FICT_VEGA"
    (carpeta / "a.json").write_text(json.dumps(verdad))
    return carpeta


def test_metricas_con_proveedor_grabado(fixtures, respuestas_documentales, tmp_path):
    respuesta = json.loads((respuestas_documentales / "azure_layout_albaran.json").read_text())
    lector = LectorDocumental(_ProveedorGrabado(respuesta), {"B99999999"}, tmp_path / "d", RegistroMemoria())
    r = benchmark.ejecutar(_carpeta(fixtures, tmp_path), lector, "grabado")
    s = r.resumen()
    assert s["cabecera"] == {"proveedor": (1, 1), "cif": (1, 1), "numero": (1, 1), "fecha": (1, 1)}
    assert all(v == (2, 2) for v in s["lineas"].values()), s["lineas"]
    assert s["lineas_5_campos"] == (10, 10)
    assert s["estructura"] == {"filas": (1, 1), "tablas": (1, 1), "columnas": (1, 1), "asociaciones": (2, 2)}
    assert s["operacion"]["completos"] == (1, 1) and s["operacion"]["coste_medio_eur_doc"] == "0.0092"
    assert s["operacion"]["campos_baja_confianza"] == 1  # el precio "0,12" con confianza 0,42
    texto = benchmark.tabla_comparada([r], benchmark.cargar_baseline())
    assert "grabado" in texto and "BASELINE CONGELADA tesseract" in texto and "33/50" in texto


def test_campos_de_linea_y_emparejado():
    from idm.dominio.modelos import LineaLeida

    assert benchmark.campo_linea_ok("codigo_proveedor", "REF-A1", "ref a1")
    assert benchmark.campo_linea_ok("descripcion", "TORNILLO M8X30", "TORNILLO M8X3O")
    assert not benchmark.campo_linea_ok("descripcion", "TORNILLO M8X30", "TUERCA")
    assert benchmark.campo_linea_ok("precio_bruto", "0.12", Decimal("0.120"))
    obtenidas = [
        LineaLeida(codigo_proveedor="B", descripcion="Y", cantidad=1),
        LineaLeida(codigo_proveedor="A", descripcion="X", cantidad=1),
    ]
    pares = benchmark.emparejar([{"codigo_proveedor": "A"}, {"codigo_proveedor": "B"}], obtenidas)
    assert [p.codigo_proveedor for p in pares] == ["A", "B"]


def test_tarea_rechaza_externo_sin_autorizacion(monkeypatch, tmp_path, capsys):
    from idm.tareas import benchmark_documentos

    monkeypatch.setenv("RUTA_DATOS", str(tmp_path))
    monkeypatch.setenv("ALLOW_EXTERNAL_DOCUMENT_PROCESSING", "true")
    monkeypatch.setenv("EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert benchmark_documentos.main(["--provider", "mistral", "--carpeta", str(tmp_path)]) == 3
    assert "--autorizo-envio-externo" in capsys.readouterr().out
    monkeypatch.setenv("ALLOW_EXTERNAL_DOCUMENT_PROCESSING", "false")
    assert (
        benchmark_documentos.main(["--provider", "mistral", "--carpeta", str(tmp_path), "--autorizo-envio-externo"])
        == 3
    )
    assert not (tmp_path / "llamadas_documentales.jsonl").exists()  # ni un intento registrado
