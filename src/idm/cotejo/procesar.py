"""Procesa un documento entrante de principio a fin: idempotencia, lectura, interpretación, cotejo o factura,
registro en el repositorio con sus eventos de negocio, y archivo del fichero en procesados/<sha256>.
Es el único sitio que une lector + gateway + equivalencias + repositorio; no contiene reglas de negocio."""

import shutil
import traceback
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from idm.albaranes.buzon import DocumentoEntrante
from idm.albaranes.lector import LectorDocumentos
from idm.almacen.documentos import DocumentoRegistrado, Evento, Repositorio
from idm.cotejo import facturas
from idm.cotejo.cotejar import cotejar_documento
from idm.cotejo.interpretar import interpretar_factura
from idm.dominio.estados import CodigoError, EstadoDocumento, RelacionPedido, ResultadoLectura, Semaforo, TipoDocumento
from idm.dominio.modelos import ErrorProcesamiento
from idm.dominio.reglas import REGLAS_POR_DEFECTO, ReglasCotejo
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.gateway import SiddexGateway


class Motivo(StrEnum):
    PROCESADO = "procesado"
    DUPLICADO_SHA = "duplicado_sha"
    DUPLICADO_NUMERO = "duplicado_numero"
    NO_PROCESABLE = "no_procesable"
    REQUIERE_OCR = "requiere_ocr"
    ERROR = "error"


@dataclass
class Procesado:
    documento: DocumentoRegistrado
    nuevo: bool
    motivo: Motivo


# Resultados de lectura que no dan lugar a cotejo: el documento queda NO_PROCESABLE (alguien tiene que mirar el fichero)
NO_PROCESABLES = {
    ResultadoLectura.CORRUPTO,
    ResultadoLectura.VACIO,
    ResultadoLectura.EXCEL,
    ResultadoLectura.NO_SOPORTADO,
}


def _evento(repo: Repositorio, tipo: str, doc_id: str | None, datos: dict) -> None:
    repo.registrar_evento(Evento(tipo=tipo, documento_id=doc_id, datos=datos))


def archivar(entrante: DocumentoEntrante, carpeta_procesados: Path | None) -> str:
    if carpeta_procesados is None:
        return str(entrante.ruta)
    carpeta_procesados.mkdir(parents=True, exist_ok=True)
    destino = carpeta_procesados / f"{entrante.sha256}{entrante.ruta.suffix.lower()}"
    if not destino.exists():
        shutil.move(str(entrante.ruta), destino)
    elif entrante.ruta.exists() and entrante.ruta != destino:
        entrante.ruta.unlink()
    return str(destino)


def procesar(
    entrante: DocumentoEntrante,
    lector: LectorDocumentos,
    gateway: SiddexGateway,
    tabla: TablaEquivalencias,
    repo: Repositorio,
    carpeta_procesados: Path | None = None,
    reglas: ReglasCotejo = REGLAS_POR_DEFECTO,
) -> Procesado:
    if (previo := repo.existe_sha(entrante.sha256)) is not None:
        _evento(repo, "documento.duplicado", previo.id, {"sha256": entrante.sha256, "ruta": str(entrante.ruta)})
        archivar(entrante, carpeta_procesados)
        return Procesado(previo, False, Motivo.DUPLICADO_SHA)

    try:
        return _procesar_nuevo(entrante, lector, gateway, tabla, repo, carpeta_procesados, reglas)
    except Exception as exc:  # noqa: BLE001 - un fallo inesperado se registra como ERROR y no tumba el lote
        return _registrar_error(entrante, exc, repo, carpeta_procesados)


def _registrar_error(
    entrante: DocumentoEntrante, exc: Exception, repo: Repositorio, carpeta_procesados: Path | None
) -> Procesado:
    error = ErrorProcesamiento(
        codigo=CodigoError.INESPERADO,
        mensaje=f"{type(exc).__name__}: {str(exc)[:300]}",
        recuperable=True,
        detalle={"traceback": "".join(traceback.format_exception(exc))[-2000:]},
    )
    doc = DocumentoRegistrado(
        sha256=entrante.sha256,
        tipo=TipoDocumento.DESCONOCIDO,
        proveedor="DESCONOCIDO",
        numero=f"ERROR-{entrante.sha256[:8]}",
        numero_original="",
        ruta=str(entrante.ruta),
        origen=entrante.origen,
        estado=EstadoDocumento.ERROR,
        semaforo=Semaforo.AMBAR,
        errores=[error],
        avisos=[error.mensaje],
    )
    doc.ruta = archivar(entrante, carpeta_procesados)
    repo.guardar(doc)
    _evento(repo, "documento.error", doc.id, {"codigo": error.codigo, "mensaje": error.mensaje})
    return Procesado(doc, True, Motivo.ERROR)


def _procesar_nuevo(entrante, lector, gateway, tabla, repo, carpeta_procesados, reglas) -> Procesado:
    leido = lector.leer(entrante.ruta)
    doc = DocumentoRegistrado(
        sha256=entrante.sha256,
        tipo=leido.tipo,
        proveedor="DESCONOCIDO",
        numero=leido.numero or f"SIN-NUMERO-{entrante.sha256[:8]}",
        numero_original=leido.numero or "",
        ruta=str(entrante.ruta),
        origen=entrante.origen,
        leido=leido,
        avisos=list(leido.avisos),
    )
    _evento(
        repo,
        "documento.recibido",
        doc.id,
        {"sha256": doc.sha256, "origen": entrante.origen, "ruta": str(entrante.ruta)},
    )
    _evento(
        repo,
        "documento.leido",
        doc.id,
        {
            "metodo": leido.metodo,
            "resultado": leido.resultado,
            "confianza": leido.confianza,
            "lineas": len(leido.lineas),
        },
    )
    doc.errores = list(leido.errores)

    if leido.resultado in NO_PROCESABLES:
        doc.estado, doc.semaforo = EstadoDocumento.NO_PROCESABLE, Semaforo.AMBAR
        doc.ruta = archivar(entrante, carpeta_procesados)
        repo.guardar(doc)
        _evento(repo, "documento.no_procesable", doc.id, {"resultado": leido.resultado})
        return Procesado(doc, True, Motivo.NO_PROCESABLE)
    doc.estado = EstadoDocumento.LEIDO

    if leido.resultado == ResultadoLectura.REQUIERE_OCR:
        doc.estado, doc.semaforo = EstadoDocumento.EN_REVISION, Semaforo.AMBAR
        doc.ruta = archivar(entrante, carpeta_procesados)
        repo.guardar(doc)
        return Procesado(doc, True, Motivo.REQUIERE_OCR)

    if leido.tipo == TipoDocumento.FACTURA:
        _procesar_factura(doc, leido, gateway, repo, reglas)
    else:
        _procesar_albaran(doc, leido, gateway, tabla, repo, reglas)

    if (previo := repo.existe_numero(doc.proveedor, doc.tipo, doc.numero)) is not None and previo.sha256 != doc.sha256:
        _evento(repo, "documento.duplicado", previo.id, {"numero": doc.numero, "sha256_nuevo": doc.sha256})
        archivar(entrante, carpeta_procesados)
        return Procesado(previo, False, Motivo.DUPLICADO_NUMERO)

    doc.ruta = archivar(entrante, carpeta_procesados)
    doc.estado = EstadoDocumento.EN_REVISION
    repo.guardar(doc)
    return Procesado(doc, True, Motivo.PROCESADO)


def _procesar_albaran(doc, leido, gateway, tabla, repo, reglas) -> None:
    r = cotejar_documento(leido, gateway, tabla, reglas)
    doc.tipo = TipoDocumento.ALBARAN
    doc.proveedor, doc.numero, doc.numero_original = r.albaran.proveedor, r.albaran.numero, r.albaran.numero_original
    doc.albaran, doc.cotejo, doc.pedido_propuesto = r.albaran, r.cotejo, r.pedido_propuesto
    doc.pedido = r.pedido.numero if r.pedido else None
    doc.relacion = RelacionPedido.PEDIDO_PROPUESTO if r.pedido_propuesto else r.cotejo.relacion
    doc.precio, doc.entrega, doc.semaforo = r.cotejo.precio, r.cotejo.entrega, r.cotejo.semaforo
    doc.avisos += [a.mensaje for a in r.avisos]
    if doc.avisos:
        doc.semaforo = Semaforo.AMBAR
    for e in r.eventos:
        _evento(repo, e.tipo, doc.id, e.datos)
    doc.estado = EstadoDocumento.COTEJADO


def _procesar_factura(doc, leido, gateway, repo, reglas) -> None:
    fi = interpretar_factura(leido, gateway.proveedores())
    doc.tipo = TipoDocumento.FACTURA
    doc.proveedor, doc.numero, doc.numero_original = fi.factura.proveedor, fi.factura.numero, fi.factura.numero
    doc.factura = fi.factura
    doc.avisos += [a.mensaje for a in fi.avisos]
    for e in fi.eventos:
        _evento(repo, e.tipo, doc.id, e.datos)
    cf = facturas.cotejar_factura(fi.factura, repo.albaranes_de(doc.proveedor), gateway.articulos(), reglas)
    doc.cotejo_factura = cf.model_dump(mode="json")
    doc.semaforo = Semaforo.AMBAR if (cf.semaforo == Semaforo.AMBAR or doc.avisos) else Semaforo.VERDE
    doc.relacion = RelacionPedido.CON_PEDIDO if cf.albaranes_encontrados else RelacionPedido.SIN_PEDIDO
    _evento(
        repo,
        "factura.cotejada",
        doc.id,
        {
            "albaranes": cf.albaranes_encontrados,
            "no_encontrados": cf.albaranes_no_encontrados,
            "precios_completados": len(cf.precios_completados),
            "precios_cambiados": len(cf.precios_cambiados),
            "avisos": [a.tipo for a in cf.avisos],
        },
    )
    doc.estado = EstadoDocumento.COTEJADO
