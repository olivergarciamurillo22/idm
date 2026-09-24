"""MistralDocumentAIProvider sin llamadas reales: cuerpo de la petición (image_url / document_url en data URI,
tablas, confianza, anotación), conversión de la respuesta grabada, tablas markdown/HTML, errores y normalización."""

import base64
import json
from decimal import Decimal

import pytest

from idm.documental.base import ErrorTransitorio
from idm.documental.costes import Tarifas
from idm.documental.entrada import preparar
from idm.documental.lector import LectorDocumental
from idm.documental.mistral import ESQUEMA_ANOTACION, MistralDocumentAIProvider, convertir, tabla_html, tablas_markdown
from idm.documental.modelo import MetadatosMotor
from idm.documental.privacidad import PoliticaEnvioExterno
from idm.documental.registro import RegistroMemoria
from idm.dominio.estados import ResultadoLectura, TipoDocumento

POLITICA = PoliticaEnvioExterno(True, frozenset({"mistral"}))


def _proveedor(http, **kw):
    return MistralDocumentAIProvider(
        "clave", POLITICA, http=http, esperar=lambda s: None, tarifas=Tarifas.cargar(), **kw
    )


def _json(respuestas_documentales, nombre):
    return json.loads((respuestas_documentales / nombre).read_text(encoding="utf-8"))


def test_cuerpo_imagen_y_pdf(fixtures, tmp_path):
    p = _proveedor(None)
    img = preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path)
    cuerpo = p.cuerpo(img)
    assert cuerpo["model"] == "mistral-ocr-latest" and cuerpo["document"]["type"] == "image_url"
    assert cuerpo["document"]["image_url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(cuerpo["document"]["image_url"].split(",", 1)[1]) == img.contenido
    assert cuerpo["table_format"] == "markdown" and cuerpo["confidence_scores_granularity"] == "word"
    assert cuerpo["include_image_base64"] is False and "document_annotation_format" not in cuerpo
    pdf = preparar(fixtures / "documentos" / "albaran_vega_bruto_descuento.pdf", tmp_path)
    cuerpo = p.cuerpo(pdf)
    assert cuerpo["document"]["type"] == "document_url"
    assert cuerpo["document"]["document_url"].startswith("data:application/pdf;base64,")
    anot = _proveedor(None, anotacion=True, confianza="none").cuerpo(img)
    assert anot["document_annotation_format"]["json_schema"]["schema"] == ESQUEMA_ANOTACION
    assert "confidence_scores_granularity" not in anot


def test_convertir(respuestas_documentales):
    r = convertir(
        _json(respuestas_documentales, "mistral_ocr_albaran.json"),
        MetadatosMotor(proveedor="mistral", modelo="mistral-ocr-latest", externo=True),
    )
    assert "tbl-1" not in r.texto and "AC B26 0100009999" in r.texto
    assert len(r.tablas) == 1  # con tablas aparte, las que quedan en el markdown no se reinterpretan como tablas
    assert r.metadatos.modelo == "mistral-ocr-2512" and r.metadatos.paginas_procesadas == 1
    assert r.palabras[1].texto == "B00000001" and r.palabras[1].caja is None
    assert r.tablas[-1].como_filas()[1][:2] == ["TORN", "REF-A1"]


def test_tablas_markdown_y_html():
    md = "texto\n| a | b |\n|---|:---:|\n| 1 | 2 |\n\nfin"
    assert tablas_markdown(md) == [[["a", "b"], ["1", "2"]]]
    assert tabla_html("<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td> 2 </td></tr></table>") == [
        ["a", "b"],
        ["1", "2"],
    ]


def test_normalizacion_completa(http_falso, respuestas_documentales, fixtures, tmp_path):
    http_falso.encolar(200, _json(respuestas_documentales, "mistral_ocr_albaran.json"), {"x-request-id": "m-1"})
    registro = RegistroMemoria()
    doc = LectorDocumental(_proveedor(http_falso), {"B99999999"}, tmp_path, registro).leer(
        fixtures / "imagenes" / "albaran_sintetico.jpg"
    )
    peticion = http_falso.peticiones[0]
    assert (
        peticion["url"] == "https://api.mistral.ai/v1/ocr" and peticion["cabeceras"]["Authorization"] == "Bearer clave"
    )
    assert (
        doc.resultado == ResultadoLectura.IMAGEN_OCR and doc.motor == "mistral:mistral-ocr-2512"
    )  # la versión concreta que devolvió, no el alias
    assert doc.tipo == TipoDocumento.ALBARAN and doc.cif == "B00000001" and doc.numero == "AC B26 0100009999"
    assert str(doc.fecha) == "2026-09-20"
    assert [(li.codigo_proveedor, li.precio_bruto) for li in doc.lineas] == [
        ("REF-A1", Decimal("0.12")),
        ("REF-B22", Decimal("0.04")),
    ]
    assert "linea[1].precio_bruto" in doc.campos_dudosos  # "0,04" con confianza 0,51
    assert doc.coste_estimado_eur == Decimal("0.0018") and doc.metadatos_motor["request_id"] == "m-1"
    assert registro.llamadas[0].paginas == 1


def test_anotacion_completa_huecos(http_falso, respuestas_documentales, fixtures, tmp_path):
    http_falso.encolar(200, _json(respuestas_documentales, "mistral_ocr_anotacion.json"))
    doc = LectorDocumental(_proveedor(http_falso, anotacion=True), {"B99999999"}, tmp_path).leer(
        fixtures / "imagenes" / "albaran_sintetico.jpg"
    )
    assert doc.numero == "AC B26 0100009999" and doc.cif == "B00000001" and str(doc.fecha) == "2026-09-20"
    assert doc.lineas[0].precio_bruto == Decimal("0.12") and doc.lineas[0].importe == Decimal("6.60")
    assert doc.coste_estimado_eur == Decimal("0.0046")  # (2 + 3 anotación) USD/1.000 × 0,92
    assert doc.campos_dudosos == []  # sin confianza por palabra no se marca nada por esta vía


def test_cuota_cero_es_permanente_y_no_reintenta(http_falso, fixtures, tmp_path):
    """Caso real observado: cuenta sin OCR habilitado responde 429 con x-ratelimit-limit-req-minute: 0."""
    from idm.documental.base import ErrorPermanente

    http_falso.encolar(
        429,
        {"object": "error", "message": "Rate limit exceeded", "type": "rate_limited", "code": "1300"},
        {"x-ratelimit-limit-req-minute": "0", "x-ratelimit-remaining-req-minute": "0", "mistral-correlation-id": "c-1"},
    )
    with pytest.raises(ErrorPermanente, match="límite 0") as exc:
        _proveedor(http_falso).analizar(preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path))
    assert len(http_falso.peticiones) == 1 and exc.value.request_id == "c-1"


def test_error_servidor_transitorio(http_falso, fixtures, tmp_path):
    for _ in range(3):
        http_falso.encolar(500, {"message": "internal"})
    with pytest.raises(ErrorTransitorio, match="500"):
        _proveedor(http_falso).analizar(preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path))
