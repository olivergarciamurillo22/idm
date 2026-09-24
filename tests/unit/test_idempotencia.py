"""Idempotencia y reproceso (BLOQUE 5): mismo fichero dos veces, mismo contenido con otro nombre, dos documentos,
reproceso explícito (y prohibido si está APROBADO), y carrera entre dos procesos resuelta por el repositorio."""

import shutil

import pytest

from idm.albaranes.buzon import CarpetaEntrada, DocumentoEntrante
from idm.albaranes.extraer import sha256_fichero
from idm.albaranes.lector import LectorAutomatico
from idm.almacen.documentos import ConflictoDuplicado, RepositorioMemoria
from idm.cotejo.procesar import VERSION_PROCESAMIENTO, Motivo, procesar
from idm.dominio.estados import EstadoDocumento
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel

VEGA = "albaran_vega_bruto_descuento.pdf"
ELECTRO = "albaran_electro_puntos_prefijo.pdf"


@pytest.fixture
def entorno(fixtures, tmp_path):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    g = SiddexDesdeExcel(fixtures / "siddex")
    return {
        "entrada": entrada,
        "docs": fixtures / "documentos",
        "gateway": g,
        "tabla": TablaEquivalencias.desde(g.equivalencias()),
        "repo": RepositorioMemoria(),
        "lector": LectorAutomatico(),
        "procesados": tmp_path / "procesados",
    }


def _procesar(e, nombre_destino, origen=VEGA, **kw):
    ruta = e["entrada"] / nombre_destino
    shutil.copy(e["docs"] / origen, ruta)
    entrante = DocumentoEntrante(ruta=ruta, sha256=sha256_fichero(ruta), origen="test")
    return procesar(entrante, e["lector"], e["gateway"], e["tabla"], e["repo"], e["procesados"], **kw)


def test_mismo_fichero_dos_veces(entorno):
    a = _procesar(entorno, VEGA)
    b = _procesar(entorno, VEGA)
    assert a.nuevo and a.motivo == Motivo.PROCESADO
    assert not b.nuevo and b.motivo == Motivo.DUPLICADO_SHA and b.documento.id == a.documento.id
    assert len(entorno["repo"].listar()) == 1
    assert [e.tipo for e in entorno["repo"].eventos(a.documento.id)].count("documento.duplicado") == 1
    assert not (entorno["entrada"] / VEGA).exists()  # el duplicado también se retira de la entrada


def test_mismo_contenido_distinto_nombre(entorno):
    a = _procesar(entorno, "original.pdf")
    b = _procesar(entorno, "reenviado_por_el_proveedor.pdf")
    assert b.motivo == Motivo.DUPLICADO_SHA and b.documento.id == a.documento.id
    assert len(list(entorno["procesados"].iterdir())) == 1  # un solo fichero archivado, por sha


def test_dos_documentos_distintos(entorno):
    a = _procesar(entorno, VEGA)
    b = _procesar(entorno, ELECTRO, origen=ELECTRO)
    assert a.nuevo and b.nuevo and a.documento.id != b.documento.id
    assert len(entorno["repo"].listar()) == 2 and len(list(entorno["procesados"].iterdir())) == 2


def test_reproceso_explicito_conserva_identidad(entorno):
    a = _procesar(entorno, VEGA)
    archivado = entorno["procesados"] / f"{a.documento.sha256}.pdf"
    entrante = DocumentoEntrante(ruta=archivado, sha256=a.documento.sha256, origen="reproceso")
    r = procesar(
        entrante,
        entorno["lector"],
        entorno["gateway"],
        entorno["tabla"],
        entorno["repo"],
        entorno["procesados"],
        reprocesar=True,
        ejecucion_id="ej-2",
    )
    assert r.nuevo and r.motivo == Motivo.REPROCESADO
    assert r.documento.id == a.documento.id and r.documento.recibido == a.documento.recibido
    assert r.documento.reprocesos == 1 and r.documento.traza.reproceso == 1 and r.documento.ejecucion_id == "ej-2"
    assert r.documento.version_procesamiento == VERSION_PROCESAMIENTO
    assert len(entorno["repo"].listar()) == 1 and archivado.exists()
    tipos = [e.tipo for e in entorno["repo"].eventos(a.documento.id)]
    assert "documento.reprocesado" in tipos and tipos.count("documento.recibido") == 1


def test_reproceso_prohibido_si_esta_aprobado(entorno):
    a = _procesar(entorno, VEGA)
    a.documento.estado = EstadoDocumento.APROBADO
    entorno["repo"].guardar(a.documento)
    r = _procesar(entorno, VEGA, reprocesar=True)
    assert not r.nuevo and r.motivo == Motivo.REPROCESO_NO_PERMITIDO
    assert entorno["repo"].obtener(a.documento.id).estado == EstadoDocumento.APROBADO
    assert entorno["repo"].eventos(a.documento.id)[-1].datos["rechazado"] is True


def test_sin_reprocesar_no_se_toca_lo_ya_registrado(entorno):
    a = _procesar(entorno, VEGA)
    a.documento.notas = "revisado por Fernando"
    entorno["repo"].guardar(a.documento)
    _procesar(entorno, VEGA)
    assert entorno["repo"].obtener(a.documento.id).notas == "revisado por Fernando"


class _RepoConCarrera(RepositorioMemoria):
    """Simula otro proceso que guarda el mismo documento justo antes que nosotros."""

    def __init__(self, otro_doc_factory):
        super().__init__()
        self._factory = otro_doc_factory
        self._disparado = False

    def guardar(self, documento):
        if not self._disparado and documento.estado == EstadoDocumento.EN_REVISION:
            self._disparado = True
            super().guardar(self._factory(documento))
        return super().guardar(documento)


def test_carrera_entre_dos_procesos(entorno):
    def otro(doc):
        return doc.model_copy(update={"id": "otroproceso1", "notas": "guardado por el otro proceso"})

    entorno["repo"] = _RepoConCarrera(otro)
    r = _procesar(entorno, VEGA)
    assert not r.nuevo and r.motivo == Motivo.DUPLICADO_SHA and r.documento.id == "otroproceso1"
    assert len(entorno["repo"].listar()) == 1
    assert entorno["repo"].eventos("otroproceso1")[-1].datos.get("carrera") is True


def test_carpeta_no_reprocesa_lo_archivado(entorno):
    _procesar(entorno, VEGA)
    assert CarpetaEntrada(entorno["entrada"]).pendientes() == []


def test_conflicto_duplicado_en_memoria():
    from idm.almacen.documentos import DocumentoRegistrado
    from idm.dominio.estados import TipoDocumento

    repo = RepositorioMemoria()
    repo.guardar(
        DocumentoRegistrado(
            sha256="a" * 64, tipo=TipoDocumento.ALBARAN, proveedor="P", numero="1", numero_original="1", ruta="x"
        )
    )
    with pytest.raises(ConflictoDuplicado):
        repo.guardar(
            DocumentoRegistrado(
                sha256="a" * 64, tipo=TipoDocumento.ALBARAN, proveedor="P", numero="2", numero_original="2", ruta="x"
            )
        )
    with pytest.raises(ConflictoDuplicado):
        repo.guardar(
            DocumentoRegistrado(
                sha256="b" * 64, tipo=TipoDocumento.ALBARAN, proveedor="P", numero="1", numero_original="1", ruta="x"
            )
        )
