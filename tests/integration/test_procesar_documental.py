"""Integración del proveedor documental en el procesamiento: un fallo técnico deja el documento en ERROR recuperable,
--reintentar-pendientes lo encuentra, el reproceso con el servicio ya disponible lo lee, y queda el evento
documento.proveedor_documental con motor, coste y request id."""

import json
import shutil

from idm.albaranes.buzon import CarpetaEntrada
from idm.albaranes.lector import LectorAutomatico, LectorTextoPDF
from idm.almacen.documentos import RepositorioMemoria
from idm.cotejo.procesar import Motivo, procesar
from idm.documental.azure import convertir
from idm.documental.base import ErrorTransitorio
from idm.documental.lector import LectorDocumental
from idm.documental.modelo import MetadatosMotor
from idm.documental.registro import RegistroMemoria
from idm.dominio.estados import CodigoError, EstadoDocumento
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.tareas.procesar_buzon import pendientes_de_reintento


class _Servicio:
    nombre, modelo, externo = "servicio", "grabado", False

    def __init__(self, respuesta):
        self.caido = True
        self.respuesta = respuesta

    def disponible(self):
        return True

    def analizar(self, documento):
        if self.caido:
            raise ErrorTransitorio("503 Service unavailable", request_id="r-caido")
        m = MetadatosMotor(proveedor="servicio", modelo="grabado", externo=False, request_id="r-ok")
        return convertir(self.respuesta["analyzeResult"], m)


def test_caida_reintento_y_evento(fixtures, respuestas_documentales, tmp_path):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    shutil.copy(fixtures / "imagenes" / "albaran_sintetico.jpg", entrada / "foto.jpg")
    servicio = _Servicio(json.loads((respuestas_documentales / "azure_layout_albaran.json").read_text()))
    lector = LectorAutomatico(
        LectorTextoPDF(), LectorDocumental(servicio, {"B99999999"}, tmp_path / "d", RegistroMemoria())
    )
    g = SiddexDesdeExcel(fixtures / "siddex")
    tabla = TablaEquivalencias.desde(g.equivalencias())
    repo = RepositorioMemoria()

    r = procesar(CarpetaEntrada(entrada).pendientes()[0], lector, g, tabla, repo, tmp_path / "procesados")
    assert r.motivo == Motivo.ERROR and r.documento.estado == EstadoDocumento.ERROR
    assert (
        r.documento.errores[0].codigo == CodigoError.PROVEEDOR_DOCUMENTAL_NO_DISPONIBLE
        and r.documento.errores[0].recuperable
    )

    pendientes = pendientes_de_reintento(repo)
    assert len(pendientes) == 1 and pendientes[0].origen == "reintento"

    servicio.caido = False
    r2 = procesar(pendientes[0], lector, g, tabla, repo, tmp_path / "procesados", reprocesar=True)
    assert r2.motivo == Motivo.REPROCESADO and r2.documento.id == r.documento.id
    assert r2.documento.estado == EstadoDocumento.EN_REVISION and r2.documento.numero == "B26 0100009999"
    assert pendientes_de_reintento(repo) == []
    eventos = [e for e in repo.eventos(r.documento.id) if e.tipo == "documento.proveedor_documental"]
    assert eventos and eventos[-1].datos["motor"] == "servicio:grabado" and eventos[-1].datos["request_id"] == "r-ok"
