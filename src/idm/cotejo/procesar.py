"""Procesa un documento entrante de principio a fin: idempotencia, lectura, interpretación, cotejo o factura, traza,
registro en el repositorio con sus eventos de negocio, y archivo del fichero en procesados/<sha256>.
Es el único sitio que une lector + gateway + equivalencias + repositorio; no contiene reglas de negocio."""

import shutil
import traceback
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from idm.albaranes.buzon import DocumentoEntrante
from idm.albaranes.lector import LectorDocumentos
from idm.almacen.documentos import (
    ArticuloTrazado,
    ConflictoDuplicado,
    DocumentoRegistrado,
    Evento,
    ReglaTrazada,
    Repositorio,
    Traza,
)
from idm.cotejo import facturas
from idm.cotejo.cotejar import cotejar_documento
from idm.cotejo.interpretar import interpretar_factura
from idm.dominio.estados import CodigoError, EstadoDocumento, RelacionPedido, ResultadoLectura, Semaforo, TipoDocumento
from idm.dominio.modelos import DocumentoLeido, ErrorProcesamiento
from idm.dominio.reglas import REGLAS_POR_DEFECTO, ReglasCotejo
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.gateway import SiddexGateway

# Se cambia cuando cambia algo que altera el resultado (reglas de cotejo, lector, normalización). Queda en cada traza.
VERSION_PROCESAMIENTO = "2026.09.24"


class Motivo(StrEnum):
    PROCESADO = "procesado"
    REPROCESADO = "reprocesado"
    DUPLICADO_SHA = "duplicado_sha"
    DUPLICADO_NUMERO = "duplicado_numero"
    NO_PROCESABLE = "no_procesable"
    REQUIERE_OCR = "requiere_ocr"
    ERROR = "error"
    REPROCESO_NO_PERMITIDO = "reproceso_no_permitido"


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


class Registrador:
    """Repositorio + id de ejecución: todos los eventos de esta pasada llevan el mismo ejecucion_id."""

    def __init__(self, repo: Repositorio, ejecucion_id: str | None) -> None:
        self.repo, self.ejecucion_id = repo, ejecucion_id

    def evento(self, tipo: str, doc_id: str | None, datos: dict) -> None:
        self.repo.registrar_evento(Evento(tipo=tipo, documento_id=doc_id, ejecucion_id=self.ejecucion_id, datos=datos))


def archivar(entrante: DocumentoEntrante, carpeta_procesados: Path | None) -> str:
    if carpeta_procesados is None:
        return str(entrante.ruta)
    carpeta_procesados.mkdir(parents=True, exist_ok=True)
    destino = carpeta_procesados / f"{entrante.sha256}{entrante.ruta.suffix.lower()}"
    if entrante.ruta == destino:
        return str(destino)
    if not destino.exists():
        shutil.move(str(entrante.ruta), destino)
    elif entrante.ruta.exists():
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
    ejecucion_id: str | None = None,
    reprocesar: bool = False,
) -> Procesado:
    """Idempotente: el mismo contenido (sha256) o el mismo (proveedor, tipo, número) no crea dos documentos.
    reprocesar=True procesa de nuevo un documento registrado (mismo id, reprocesos+1), salvo si está APROBADO."""
    reg = Registrador(repo, ejecucion_id)
    previo = repo.existe_sha(entrante.sha256)
    if previo is not None and not reprocesar:
        reg.evento("documento.duplicado", previo.id, {"sha256": entrante.sha256, "ruta": str(entrante.ruta)})
        archivar(entrante, carpeta_procesados)
        return Procesado(previo, False, Motivo.DUPLICADO_SHA)
    if previo is not None and previo.estado == EstadoDocumento.APROBADO:
        reg.evento("documento.reprocesado", previo.id, {"rechazado": True, "motivo": "el documento está APROBADO"})
        return Procesado(previo, False, Motivo.REPROCESO_NO_PERMITIDO)

    try:
        return _procesar(entrante, lector, gateway, tabla, reg, carpeta_procesados, reglas, previo)
    except ConflictoDuplicado as exc:
        # Otro proceso guardó el mismo documento entre nuestra comprobación y nuestro guardado (carrera).
        existente = repo.existe_sha(entrante.sha256) if exc.campo == "sha256" else None
        if existente is None:
            existente = _por_numero(repo, exc.valor)
        archivar(entrante, carpeta_procesados)
        if existente is not None:
            reg.evento(
                "documento.duplicado", existente.id, {"sha256": entrante.sha256, "carrera": True, "campo": exc.campo}
            )
            motivo = Motivo.DUPLICADO_SHA if exc.campo == "sha256" else Motivo.DUPLICADO_NUMERO
            return Procesado(existente, False, motivo)
        return _registrar_error(entrante, exc, reg, carpeta_procesados, CodigoError.CONFLICTO_DUPLICADO)
    except Exception as exc:  # noqa: BLE001 - un fallo inesperado se registra como ERROR y no tumba el lote
        return _registrar_error(entrante, exc, reg, carpeta_procesados, CodigoError.INESPERADO)


def _por_numero(repo: Repositorio, valor: str) -> DocumentoRegistrado | None:
    try:
        proveedor, tipo, numero = valor.split("/", 2)
        return repo.existe_numero(proveedor, TipoDocumento(tipo), numero)
    except ValueError:
        return None


def _registrar_error(
    entrante: DocumentoEntrante, exc: Exception, reg: Registrador, carpeta_procesados: Path | None, codigo: CodigoError
) -> Procesado:
    error = ErrorProcesamiento(
        codigo=codigo,
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
        ejecucion_id=reg.ejecucion_id,
        version_procesamiento=VERSION_PROCESAMIENTO,
    )
    doc.traza = Traza(
        ejecucion_id=reg.ejecucion_id,
        version=VERSION_PROCESAMIENTO,
        inicio=datetime.now(),
        fin=datetime.now(),
        fichero=str(entrante.ruta),
        sha256=entrante.sha256,
        origen=entrante.origen,
        errores=[error.mensaje],
        estado_final=EstadoDocumento.ERROR,
        semaforo=Semaforo.AMBAR,
    )
    doc.ruta = archivar(entrante, carpeta_procesados)
    try:
        reg.repo.guardar(doc)
    except ConflictoDuplicado:
        existente = reg.repo.existe_sha(entrante.sha256)
        if existente is not None:
            return Procesado(existente, False, Motivo.DUPLICADO_SHA)
        raise
    reg.evento("documento.error", doc.id, {"codigo": error.codigo, "mensaje": error.mensaje})
    return Procesado(doc, True, Motivo.ERROR)


def _procesar(entrante, lector, gateway, tabla, reg, carpeta_procesados, reglas, previo) -> Procesado:
    inicio = datetime.now()
    leido: DocumentoLeido = lector.leer(entrante.ruta)
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
        errores=list(leido.errores),
        ejecucion_id=reg.ejecucion_id,
        version_procesamiento=VERSION_PROCESAMIENTO,
    )
    if previo is not None:  # reproceso: se conserva la identidad y la fecha de recepción
        doc.id, doc.recibido, doc.reprocesos = previo.id, previo.recibido, previo.reprocesos + 1
        doc.origen = previo.origen
    traza = Traza(
        ejecucion_id=reg.ejecucion_id,
        version=VERSION_PROCESAMIENTO,
        inicio=inicio,
        fichero=str(entrante.ruta),
        sha256=entrante.sha256,
        origen=doc.origen,
        resultado_lectura=leido.resultado,
        metodo_lectura=leido.metodo,
        confianza=leido.confianza,
        tipo=leido.tipo,
        reproceso=doc.reprocesos,
        campos_extraidos={
            "numero": leido.numero,
            "fecha": leido.fecha.isoformat() if leido.fecha else None,
            "nuestro_pedido": leido.nuestro_pedido,
            "cif": leido.cif,
            "proveedor_texto": leido.proveedor_texto,
            "n_lineas": str(len(leido.lineas)),
            "base": str(leido.base) if leido.base is not None else None,
            "total": str(leido.total) if leido.total is not None else None,
        },
        errores=[e.mensaje for e in leido.errores],
    )
    doc.traza = traza
    reg.evento(
        "documento.recibido" if previo is None else "documento.reprocesado",
        doc.id,
        {"sha256": doc.sha256, "origen": entrante.origen, "ruta": str(entrante.ruta), "reproceso": doc.reprocesos},
    )
    reg.evento(
        "documento.leido",
        doc.id,
        {
            "metodo": leido.metodo,
            "resultado": leido.resultado,
            "confianza": leido.confianza,
            "lineas": len(leido.lineas),
        },
    )
    motivo = Motivo.PROCESADO if previo is None else Motivo.REPROCESADO

    if leido.resultado in NO_PROCESABLES:
        doc.estado, doc.semaforo = EstadoDocumento.NO_PROCESABLE, Semaforo.AMBAR
        reg.evento("documento.no_procesable", doc.id, {"resultado": leido.resultado})
        return _cerrar(doc, entrante, reg, carpeta_procesados, Motivo.NO_PROCESABLE)
    if leido.motor:
        reg.evento(
            "documento.proveedor_documental",
            doc.id,
            {
                "motor": leido.motor,
                "resultado": leido.resultado,
                "coste_estimado_eur": str(leido.coste_estimado_eur) if leido.coste_estimado_eur is not None else None,
                "campos_dudosos": leido.campos_dudosos,
                **leido.metadatos_motor,
            },
        )
    if leido.resultado == ResultadoLectura.PROVEEDOR_NO_DISPONIBLE:
        # Fallo técnico del servicio de lectura: queda en ERROR y se reintenta después (--reintentar-pendientes).
        # No se manda el documento a ningún otro proveedor por su cuenta.
        doc.estado, doc.semaforo = EstadoDocumento.ERROR, Semaforo.AMBAR
        return _cerrar(doc, entrante, reg, carpeta_procesados, Motivo.ERROR)
    doc.estado = EstadoDocumento.LEIDO
    if leido.resultado == ResultadoLectura.REQUIERE_OCR:
        doc.estado, doc.semaforo = EstadoDocumento.EN_REVISION, Semaforo.AMBAR
        return _cerrar(doc, entrante, reg, carpeta_procesados, Motivo.REQUIERE_OCR)

    if leido.tipo == TipoDocumento.FACTURA:
        _procesar_factura(doc, leido, gateway, reg, reglas)
    else:
        _procesar_albaran(doc, leido, gateway, tabla, reg, reglas)

    otro = reg.repo.existe_numero(doc.proveedor, doc.tipo, doc.numero)
    if otro is not None and otro.id != doc.id:
        reg.evento("documento.duplicado", otro.id, {"numero": doc.numero, "sha256_nuevo": doc.sha256})
        archivar(entrante, carpeta_procesados)
        return Procesado(otro, False, Motivo.DUPLICADO_NUMERO)
    if leido.resultado == ResultadoLectura.IMAGEN_OCR:
        doc.semaforo = Semaforo.AMBAR  # lo leído por OCR nunca se da por verde sin que alguien lo mire
    doc.estado = EstadoDocumento.EN_REVISION
    return _cerrar(doc, entrante, reg, carpeta_procesados, motivo)


def _cerrar(doc, entrante, reg, carpeta_procesados, motivo: Motivo) -> Procesado:
    doc.ruta = archivar(entrante, carpeta_procesados)
    assert doc.traza is not None
    doc.traza.fin = datetime.now()
    doc.traza.estado_final, doc.traza.semaforo = doc.estado, doc.semaforo
    doc.traza.errores = [e.mensaje for e in doc.errores]
    reg.repo.guardar(doc)
    return Procesado(doc, True, motivo)


def _procesar_albaran(doc, leido, gateway, tabla, reg, reglas) -> None:
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
        reg.evento(e.tipo, doc.id, e.datos)
    doc.estado = EstadoDocumento.COTEJADO

    t = doc.traza
    t.tipo, t.proveedor, t.proveedor_metodo = TipoDocumento.ALBARAN, r.albaran.proveedor, r.proveedor_metodo
    if r.albaran.numero_original != r.albaran.numero:
        t.normalizaciones.append(f"número: '{r.albaran.numero_original}' → '{r.albaran.numero}'")
    for i, li in enumerate(r.albaran.lineas):
        t.articulos.append(
            ArticuloTrazado(
                linea=i, codigo_proveedor=li.codigo_proveedor, codigo_idm=li.codigo_idm, metodo=li.metodo_resolucion
            )
        )
        if li.codigo_idm and li.metodo_resolucion == "equivalencia_normalizada":
            t.normalizaciones.append(f"línea {i}: referencia '{li.codigo_proveedor}' normalizada para casar")
    t.pedido, t.pedido_metodo = (r.pedido.numero if r.pedido else None), r.metodo_pedido
    t.pedido_propuesto = r.pedido_propuesto.numero if r.pedido_propuesto else None
    for cl in r.cotejo.lineas:
        t.reglas += [
            ReglaTrazada(linea=cl.indice_albaran, regla=x.regla, resultado=x.resultado, detalle=x.detalle)
            for x in cl.reglas
        ]
    t.diferencias = [f"{a.tipo}: {a.mensaje}" for a in r.cotejo.todos_los_avisos] + [
        f"{a.tipo}: {a.mensaje}" for a in r.avisos
    ]


def _procesar_factura(doc, leido, gateway, reg, reglas) -> None:
    fi = interpretar_factura(leido, gateway.proveedores())
    doc.tipo = TipoDocumento.FACTURA
    doc.proveedor, doc.numero, doc.numero_original = fi.factura.proveedor, fi.factura.numero, fi.factura.numero
    doc.factura = fi.factura
    doc.avisos += [a.mensaje for a in fi.avisos]
    for e in fi.eventos:
        reg.evento(e.tipo, doc.id, e.datos)
    cf = facturas.cotejar_factura(fi.factura, reg.repo.albaranes_de(doc.proveedor), gateway.articulos(), reglas)
    doc.cotejo_factura = cf.model_dump(mode="json")
    doc.semaforo = Semaforo.AMBAR if (cf.semaforo == Semaforo.AMBAR or doc.avisos) else Semaforo.VERDE
    doc.relacion = RelacionPedido.CON_PEDIDO if cf.albaranes_encontrados else RelacionPedido.SIN_PEDIDO
    reg.evento(
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

    t = doc.traza
    t.tipo, t.proveedor, t.proveedor_metodo, t.factura = (
        TipoDocumento.FACTURA,
        fi.factura.proveedor,
        fi.proveedor_metodo,
        fi.factura.numero,
    )
    t.albaranes_relacionados, t.albaranes_no_encontrados = cf.albaranes_encontrados, cf.albaranes_no_encontrados
    t.normalizaciones += [
        f"albarán referenciado '{ref}' → '{n}'"
        for ref, n in zip(fi.factura.albaranes, cf.albaranes_encontrados + cf.albaranes_no_encontrados, strict=False)
        if ref != n
    ]
    t.reglas = [
        ReglaTrazada(
            linea=None,
            regla="ALBARANES_RECIBIDOS",
            resultado="AVISO" if cf.albaranes_no_encontrados else "OK",
            detalle=f"{len(cf.albaranes_encontrados)} encontrados, {len(cf.albaranes_no_encontrados)} no",
        ),
        ReglaTrazada(
            linea=None,
            regla="IMPORTE_LINEAS_VS_ALBARANES",
            resultado="OK" if cf.total_lineas_factura == cf.total_albaranes else "AVISO",
            detalle=f"factura {cf.total_lineas_factura} / albaranes {cf.total_albaranes}",
        ),
        ReglaTrazada(
            linea=None,
            regla="PORTES_PACTADOS",
            resultado="NO_APLICA"
            if cf.portes == 0
            else ("AVISO" if any(a.tipo == "PORTES_NO_PACTADOS" for a in cf.avisos) else "OK"),
            detalle=f"portes {cf.portes}",
        ),
        ReglaTrazada(
            linea=None,
            regla="PRECIO_COMPRA_MAESTRO",
            resultado="AVISO" if cf.precios_cambiados else "OK",
            detalle=f"{len(cf.precios_cambiados)} artículos con precio distinto al maestro",
        ),
    ]
    t.diferencias = [f"{a.tipo}: {a.mensaje}" for a in cf.avisos] + [f"{a.tipo}: {a.mensaje}" for a in fi.avisos]
