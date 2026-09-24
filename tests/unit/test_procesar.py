"""Tests de cotejo/procesar.py con RepositorioMemoria: pipeline completo, idempotencia por SHA-256 y por número,
factura contra los albaranes ya registrados, archivo en procesados/<sha>."""

import shutil

from idm.albaranes.buzon import CarpetaEntrada
from idm.albaranes.lector import LectorAutomatico
from idm.almacen.documentos import RepositorioMemoria
from idm.cotejo.procesar import Motivo, procesar
from idm.dominio.estados import CodigoError, EstadoDocumento, RelacionPedido, Semaforo, TipoDocumento
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
    assert [r.motivo for r in resultados] == [Motivo.PROCESADO] * 4 + [Motivo.REQUIERE_OCR]
    vega, recambios, electro, factura, foto = (r.documento for r in resultados)

    assert vega.semaforo == Semaforo.VERDE and vega.pedido == "20261060" and vega.estado == EstadoDocumento.EN_REVISION
    assert recambios.relacion == RelacionPedido.PEDIDO_PROPUESTO and recambios.pedido_propuesto is not None
    assert electro.semaforo == Semaforo.AMBAR and electro.numero == "2026/1234"
    assert factura.tipo == TipoDocumento.FACTURA
    cf = factura.cotejo_factura
    assert cf["albaranes_encontrados"] == ["B26 0100005283"] and cf["albaranes_no_encontrados"] == ["B26 0100005301"]
    assert factura.semaforo == Semaforo.AMBAR
    assert foto.leido.metodo == "imagen_nulo" and foto.semaforo == Semaforo.AMBAR and foto.proveedor == "DESCONOCIDO"
    assert foto.estado == EstadoDocumento.EN_REVISION and foto.errores[0].codigo == CodigoError.LECTURA_REQUIERE_OCR

    assert vega.ruta == str(procesados / f"{vega.sha256}.pdf") and not (entrada / ORDEN[0]).exists()
    tipos = [e.tipo for e in repo.eventos(vega.id)]
    assert tipos[:2] == ["documento.recibido", "documento.leido"] and "precio.comparado" in tipos
    assert len(repo.listar()) == 5

    # Mismo fichero otra vez: duplicado por SHA, no se crea registro
    shutil.copy(fixtures / "documentos" / ORDEN[0], entrada / "otra_copia.pdf")
    r = procesar(CarpetaEntrada(entrada).pendientes()[0], lector, g, tabla, repo, procesados)
    assert not r.nuevo and r.motivo == Motivo.DUPLICADO_SHA and r.documento.id == vega.id
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
    assert not r.nuevo and r.motivo == Motivo.DUPLICADO_NUMERO and r.documento.id == primero.documento.id


def test_no_procesables_quedan_registrados_sin_tumbar_el_lote(fixtures, fixtures_raiz, tmp_path):
    entrada, g, tabla, repo, lector = _preparar(fixtures, tmp_path)
    for nombre in ("corrupto.pdf", "vacio.pdf", "hoja.xlsx", "texto.txt"):
        shutil.copy(fixtures_raiz / "no_procesables" / nombre, entrada / nombre)
    procesados = tmp_path / "procesados"
    resultados = {
        e.ruta.name: procesar(e, lector, g, tabla, repo, procesados) for e in CarpetaEntrada(entrada).pendientes()
    }
    # CarpetaEntrada solo admite pdf/imágenes: hoja.xlsx y texto.txt no entran por el buzón (quedan en la carpeta)
    assert (entrada / "hoja.xlsx").exists() and (entrada / "texto.txt").exists()
    for nombre in ("corrupto.pdf", "vacio.pdf"):
        r = resultados[nombre]
        assert r.nuevo and r.motivo == Motivo.NO_PROCESABLE and r.documento.estado == EstadoDocumento.NO_PROCESABLE
        assert r.documento.errores and not r.documento.errores[0].recuperable
        assert not (entrada / nombre).exists()  # archivado igualmente, con su sha
    assert [e.tipo for e in repo.eventos(resultados["corrupto.pdf"].documento.id)][-1] == "documento.no_procesable"
    assert len(repo.listar(estado=EstadoDocumento.NO_PROCESABLE)) == 2


class _LectorQueRevienta:
    def leer(self, ruta):
        raise RuntimeError("fallo simulado del lector")


def test_error_inesperado_queda_como_documento_en_error(fixtures, tmp_path):
    entrada, g, tabla, repo, _ = _preparar(fixtures, tmp_path)
    entrante = next(e for e in CarpetaEntrada(entrada).pendientes() if e.ruta.name == ORDEN[0])
    r = procesar(entrante, _LectorQueRevienta(), g, tabla, repo, tmp_path / "procesados")
    assert r.motivo == Motivo.ERROR and r.documento.estado == EstadoDocumento.ERROR
    assert r.documento.errores[0].codigo == CodigoError.INESPERADO and r.documento.errores[0].recuperable
    assert "fallo simulado" in r.documento.errores[0].mensaje and "traceback" in r.documento.errores[0].detalle
    assert repo.eventos(r.documento.id)[-1].tipo == "documento.error"
    # Al reintentar con un lector que funciona, el sha ya existe: hoy es duplicado (el reproceso explícito llega aparte)
    assert repo.existe_sha(entrante.sha256) is not None
