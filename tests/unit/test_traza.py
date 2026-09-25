"""Trazabilidad por ejecución (BLOQUE 4): cada documento procesado lleva una Traza completa y los eventos comparten
ejecucion_id; las reglas de cotejo quedan escritas con su resultado, también en la función pura."""

import shutil

from idm.albaranes.buzon import CarpetaEntrada
from idm.albaranes.lector import LectorAutomatico
from idm.almacen.documentos import Ejecucion, RepositorioMemoria
from idm.cotejo.procesar import VERSION_PROCESAMIENTO, procesar
from idm.dominio.estados import EstadoDocumento, Semaforo, TipoDocumento
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel


def _procesar_todo(fixtures, tmp_path, nombres, ejecucion_id="ej-1"):
    entrada = tmp_path / "entrada"
    entrada.mkdir(exist_ok=True)
    for n in nombres:
        shutil.copy(fixtures / "documentos" / n, entrada / n)
    g = SiddexDesdeExcel(fixtures / "siddex")
    repo = RepositorioMemoria()
    repo.guardar_ejecucion(Ejecucion(id=ejecucion_id, version=VERSION_PROCESAMIENTO))
    docs = {}
    for e in CarpetaEntrada(entrada).pendientes():
        r = procesar(
            e,
            LectorAutomatico(),
            g,
            TablaEquivalencias.desde(g.equivalencias()),
            repo,
            tmp_path / "p",
            ejecucion_id=ejecucion_id,
        )
        docs[e.ruta.name] = r.documento
    return docs, repo


def test_traza_albaran_con_pedido(fixtures, tmp_path):
    docs, repo = _procesar_todo(fixtures, tmp_path, ["albaran_electro_puntos_prefijo.pdf"])
    d = docs["albaran_electro_puntos_prefijo.pdf"]
    t = d.traza
    assert t.ejecucion_id == "ej-1" and t.version == VERSION_PROCESAMIENTO and t.fin is not None and t.fin >= t.inicio
    assert t.sha256 == d.sha256 and t.fichero.endswith("albaran_electro_puntos_prefijo.pdf") and t.origen == "carpeta"
    assert t.resultado_lectura == "PDF_TEXTO" and t.tipo == TipoDocumento.ALBARAN
    assert t.proveedor == "FICT_ELECTRO" and t.proveedor_metodo == "cif"
    assert t.campos_extraidos["numero"] == "ALB. 2026/1.234" and t.campos_extraidos["nuestro_pedido"] == "20269061"
    assert t.normalizaciones == ["número: 'ALB. 2026/1.234' → '2026/1234'"]
    assert [(a.linea, a.codigo_idm, a.metodo) for a in t.articulos] == [
        (0, None, "no_resuelto"),
        (1, "I34.000.900", "equivalencia"),
        (2, None, "no_resuelto"),
        (3, None, None),
    ]
    assert t.pedido == "20269061" and t.pedido_metodo == "nuestro_pedido" and t.pedido_propuesto is None
    reglas = {(r.linea, r.regla): r.resultado for r in t.reglas}
    assert reglas[(0, "ARTICULO_EN_PEDIDO")] == "AVISO"
    assert reglas[(1, "ARTICULO_EN_PEDIDO")] == "OK" and reglas[(1, "PRECIO_BRUTO")] == "OK"
    assert reglas[(1, "DESCUENTO")] == "OK" and reglas[(1, "CANTIDAD")] == "OK"
    assert reglas[(3, "PORTES_PACTADOS")] == "AVISO"
    assert any(d.startswith("LINEA_SIN_PEDIDO") for d in t.diferencias)
    assert any(d.startswith("ARTICULO_NO_RESUELTO") for d in t.diferencias)
    assert t.estado_final == EstadoDocumento.EN_REVISION and t.semaforo == Semaforo.AMBAR and t.errores == []
    assert all(e.ejecucion_id == "ej-1" for e in repo.eventos(d.id))
    assert d.ejecucion_id == "ej-1" and d.version_procesamiento == VERSION_PROCESAMIENTO


def test_traza_sin_precio_y_factura(fixtures, tmp_path):
    docs, _ = _procesar_todo(
        fixtures,
        tmp_path,
        ["albaran_recambios_sin_precio.pdf", "albaran_vega_bruto_descuento.pdf", "factura_vega_agrupa.pdf"],
    )
    t = docs["albaran_recambios_sin_precio.pdf"].traza
    assert t.pedido is None and t.pedido_metodo == "ninguno" and t.pedido_propuesto == "PP-4410/3172"
    assert {r.regla for r in t.reglas} == {"ARTICULO_EN_PEDIDO"}
    tf = docs["factura_vega_agrupa.pdf"].traza
    assert tf.tipo == TipoDocumento.FACTURA and tf.factura == "F26/000731"
    assert tf.albaranes_relacionados == ["B26 0100008881"] and tf.albaranes_no_encontrados == ["B26 0100005301"]
    assert "albarán referenciado 'AC B26 0100008881' → 'B26 0100008881'" in tf.normalizaciones
    reglas = {r.regla: r.resultado for r in tf.reglas}
    assert reglas["ALBARANES_RECIBIDOS"] == "AVISO" and reglas["PORTES_PACTADOS"] == "AVISO"
    # El rodamiento a 9,40 va en el albarán 5301, que no está recibido: no se compara con el maestro (queda en el aviso
    # ALBARAN_NO_ENCONTRADO). Las líneas del albarán recibido coinciden con el maestro.
    assert reglas["PRECIO_COMPRA_MAESTRO"] == "OK"


def test_traza_serializa_con_el_documento(fixtures, tmp_path):
    docs, _ = _procesar_todo(fixtures, tmp_path, ["albaran_vega_bruto_descuento.pdf"])
    d = docs["albaran_vega_bruto_descuento.pdf"]
    datos = d.model_dump(mode="json")
    assert datos["traza"]["version"] == VERSION_PROCESAMIENTO and len(datos["traza"]["reglas"]) == 12
    assert datos["cotejo"]["lineas"][0]["reglas"][0]["regla"] == "ARTICULO_EN_PEDIDO"
