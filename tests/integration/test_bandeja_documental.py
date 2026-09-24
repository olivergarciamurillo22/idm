"""La bandeja enseña quién leyó el documento (motor, local o externo, coste, petición), los campos dudosos marcados en
las líneas y las correcciones hechas a mano. Documento leído con un proveedor grabado, sin red."""

import json
import shutil

from fastapi.testclient import TestClient

from idm import config
from idm.albaranes.buzon import CarpetaEntrada
from idm.albaranes.lector import LectorAutomatico, LectorTextoPDF
from idm.almacen.documentos import RepositorioMemoria
from idm.bandeja.app import crear_app
from idm.cotejo.procesar import procesar
from idm.documental.azure import convertir
from idm.documental.lector import LectorDocumental
from idm.documental.modelo import MetadatosMotor
from idm.encargos.registro import EncargosJSONL
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel


class _Grabado:
    nombre, modelo, externo = "azure", "prebuilt-layout", True

    def __init__(self, respuesta):
        self.respuesta = respuesta

    def disponible(self):
        return True

    def analizar(self, documento):
        from decimal import Decimal

        m = MetadatosMotor(
            proveedor="azure",
            modelo="prebuilt-layout",
            externo=True,
            request_id="req-9",
            coste_estimado_eur=Decimal("0.0092"),
            tiempo_s=2.5,
            paginas_procesadas=1,
        )
        return convertir(self.respuesta["analyzeResult"], m)


def test_bandeja_muestra_motor_coste_dudosos_y_correcciones(fixtures, respuestas_documentales, tmp_path):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    shutil.copy(fixtures / "imagenes" / "albaran_sintetico.jpg", entrada / "foto.jpg")
    grabado = _Grabado(json.loads((respuestas_documentales / "azure_layout_albaran.json").read_text()))
    lector = LectorAutomatico(LectorTextoPDF(), LectorDocumental(grabado, {"B99999999"}, tmp_path / "d"))
    g = SiddexDesdeExcel(fixtures / "siddex")
    repo = RepositorioMemoria()
    doc = procesar(
        CarpetaEntrada(entrada).pendientes()[0],
        lector,
        g,
        TablaEquivalencias.desde(g.equivalencias()),
        repo,
        tmp_path / "p",
    ).documento
    cfg = config.Config(
        ruta_datos=tmp_path,
        ruta_entrada=entrada,
        ruta_procesados=tmp_path / "p",
        ruta_siddex=tmp_path,
        ruta_planning=tmp_path / "x",
        ruta_pedidos_pdf=tmp_path,
        ruta_salida=tmp_path,
        ruta_pedidos_transmitidos=None,
        database_url="sqlite://",
        modo_simulacion=True,
    )
    c = TestClient(crear_app(repo, EncargosJSONL(tmp_path / "e.jsonl"), cfg))
    html = c.get(f"/documentos/{doc.id}").text
    assert "Motor: <b>azure:prebuilt-layout</b>" in html and "(servicio externo)" in html
    assert "coste estimado 0.0092 €" in html and "petición req-9" in html
    assert "Campos dudosos" in html and "linea[0].precio_bruto" in html and 'class="num dudoso"' in html
    c.post(f"/documentos/{doc.id}/corregir", data={"numero": "AC B26 0100009998", "quien": "Fernando"})
    html = c.get(f"/documentos/{doc.id}").text
    assert "Correcciones hechas a mano" in html and "B26 0100009999 → B26 0100009998" in html
