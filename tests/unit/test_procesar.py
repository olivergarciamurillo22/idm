"""Tests de cotejo/procesar.py con RepositorioMemoria: pipeline completo, idempotencia por SHA-256 y por número,
factura contra los albaranes ya registrados, archivo en procesados/<sha>."""

import shutil

from idm.albaranes.buzon import CarpetaEntrada
from idm.albaranes.lector import LectorAutomatico
from idm.almacen.documentos import RepositorioMemoria
from idm.cotejo.procesar import procesar
from idm.dominio.estados import EstadoDocumento, RelacionPedido, Semaforo, TipoDocumento
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel

ORDEN = [
    "albaran_vega_bruto_descuento.pdf",
    "albaran_recambios_sin_precio.pdf",
    "albaran_electro_puntos_prefijo.pdf",
    "factura_vega_agrupa.pdf",
    "albaran_recambios_sin_precio_foto.png",
]


def _preparar(fixtures, tmp_path):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    for nombre in ORDEN:
        shutil.copy(fixtures / "documentos" / nombre, entrada / nombre)
    g = SiddexDesdeExcel(fixtures / "siddex")
    return entrada, g, TablaEquivalencias.desde(g.equivalencias()), RepositorioMemoria(), LectorAutomatico()


def test_pipeline_completo_e_idempotente(fixtures, tmp_path):
    entrada, g, tabla, repo, lector = _preparar(fixtures, tmp_path)
    procesados = tmp_path / "procesados"
    entrantes = {e.ruta.name: e for e in CarpetaEntrada(entrada).pendientes()}
    resultados = [procesar(entrantes[n], lector, g, tabla, repo, procesados) for n in ORDEN]
    assert all(r.nuevo for r in resultados)
    vega, recambios, electro, factura, foto = (r.documento for r in resultados)

    assert vega.semaforo == Semaforo.VERDE and vega.pedido == "20261060" and vega.estado == EstadoDocumento.EN_REVISION
    assert recambios.relacion == RelacionPedido.PEDIDO_PROPUESTO and recambios.pedido_propuesto is not None
    assert electro.semaforo == Semaforo.AMBAR and electro.numero == "2026/1234"
    assert factura.tipo == TipoDocumento.FACTURA
    cf = factura.cotejo_factura
    assert cf["albaranes_encontrados"] == ["B26 0100005283"] and cf["albaranes_no_encontrados"] == ["B26 0100005301"]
    assert factura.semaforo == Semaforo.AMBAR
    assert foto.leido.metodo == "imagen_nulo" and foto.semaforo == Semaforo.AMBAR and foto.proveedor == "DESCONOCIDO"

    assert vega.ruta == str(procesados / f"{vega.sha256}.pdf") and not (entrada / ORDEN[0]).exists()
    tipos = [e.tipo for e in repo.eventos(vega.id)]
    assert tipos[:2] == ["documento.recibido", "documento.leido"] and "precio.comparado" in tipos
    assert len(repo.listar()) == 5

    # Mismo fichero otra vez: duplicado por SHA, no se crea registro
    shutil.copy(fixtures / "documentos" / ORDEN[0], entrada / "otra_copia.pdf")
    r = procesar(CarpetaEntrada(entrada).pendientes()[0], lector, g, tabla, repo, procesados)
    assert not r.nuevo and r.motivo == "duplicado_sha" and r.documento.id == vega.id
    assert len(repo.listar()) == 5 and not (entrada / "otra_copia.pdf").exists()


def test_duplicado_por_numero(fixtures, tmp_path):
    entrada, g, tabla, repo, lector = _preparar(fixtures, tmp_path)
    ruta = entrada / "albaran_vega_bruto_descuento.pdf"
    entrante_vega = next(e for e in CarpetaEntrada(entrada).pendientes() if e.ruta == ruta)
    primero = procesar(entrante_vega, lector, g, tabla, repo)
    assert primero.documento.ruta == str(ruta)
    # Mismo albarán (mismo proveedor, tipo y número) pero fichero distinto (un byte más al final)
    copia = entrada / "reenviado.pdf"
    copia.write_bytes(ruta.read_bytes() + b"\n%reenviado")
    entrante = next(e for e in CarpetaEntrada(entrada).pendientes() if e.ruta == copia)
    r = procesar(entrante, lector, g, tabla, repo)
    assert not r.nuevo and r.motivo == "duplicado_numero" and r.documento.id == primero.documento.id
