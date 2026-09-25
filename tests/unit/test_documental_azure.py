"""AzureDocumentIntelligenceProvider sin llamadas reales: petición (URL, versión, modelo, features, cabecera, base64),
sondeo con Retry-After, conversión del analyzeResult grabado, reintentos y errores, HEIC convertido a JPEG,
campos de prebuilt-invoice y normalización completa a DocumentoLeido con coste y campos dudosos."""

import base64
import json
from decimal import Decimal

import pytest

from idm.documental.azure import AzureDocumentIntelligenceProvider, convertir
from idm.documental.base import ErrorPermanente, ErrorTransitorio
from idm.documental.costes import Tarifas
from idm.documental.entrada import preparar
from idm.documental.http import ErrorRed
from idm.documental.lector import LectorDocumental
from idm.documental.modelo import MetadatosMotor
from idm.documental.privacidad import PoliticaEnvioExterno
from idm.documental.registro import RegistroMemoria
from idm.dominio.estados import CodigoError, ResultadoLectura, TipoDocumento

POLITICA = PoliticaEnvioExterno(True, frozenset({"azure"}))
OP = "https://ficticio.cognitiveservices.azure.com/documentintelligence/documentModels/prebuilt-layout/analyzeResults/abc"


def _proveedor(http, esperas=None, **kw):
    return AzureDocumentIntelligenceProvider(
        "https://ficticio.cognitiveservices.azure.com/",
        "clave",
        POLITICA,
        http=http,
        esperar=(esperas.append if esperas is not None else (lambda s: None)),
        tarifas=Tarifas.cargar(),
        **kw,
    )


def _respuesta(respuestas_documentales, nombre="azure_layout_albaran.json"):
    return json.loads((respuestas_documentales / nombre).read_text(encoding="utf-8"))


def _encolar_ok(http, respuestas_documentales, nombre="azure_layout_albaran.json"):
    http.encolar(202, {}, {"Operation-Location": OP, "apim-request-id": "req-123"})
    http.encolar(200, {"status": "running"}, {"Retry-After": "2"})
    http.encolar(200, _respuesta(respuestas_documentales, nombre))


def test_peticion_y_sondeo(http_falso, respuestas_documentales, fixtures, tmp_path):
    esperas = []
    _encolar_ok(http_falso, respuestas_documentales)
    documento = preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path)
    r = _proveedor(http_falso, esperas).analizar(documento)
    post, get1, get2 = http_falso.peticiones
    assert post["metodo"] == "POST" and post["url"] == (
        "https://ficticio.cognitiveservices.azure.com/documentintelligence/documentModels/prebuilt-layout:analyze"
        "?api-version=2024-11-30&features=keyValuePairs"
    )
    assert post["cabeceras"]["Ocp-Apim-Subscription-Key"] == "clave"
    assert base64.b64decode(json.loads(post["cuerpo"])["base64Source"]) == documento.contenido
    assert get1["metodo"] == get2["metodo"] == "GET" and get1["url"] == OP and get1["cuerpo"] is None
    assert esperas == [2.0]  # respeta Retry-After
    assert r.metadatos.request_id == "req-123" and r.metadatos.externo and r.metadatos.paginas_procesadas == 1
    assert r.metadatos.coste_estimado_eur == Decimal("0.0092")  # 10 USD/1.000 págs × 0,92


def test_convertir_estructura(respuestas_documentales):
    r = convertir(
        _respuesta(respuestas_documentales)["analyzeResult"],
        MetadatosMotor(proveedor="azure", modelo="m", externo=True),
    )
    assert len(r.palabras) == 16 and r.palabras[0].caja.x0 == 120 and r.palabras[0].caja.unidad == "pixel"
    assert r.tablas[0].como_filas()[0][:3] == ["Familia", "Referencia", "Denominacion"]
    assert r.tablas[0].celdas[0].cabecera and r.tablas[0].pagina == 1
    assert r.pares[0].clave == "Tipo / Serie / No Albaran" and r.pares[0].valor == "AC B26 0100009999"
    assert 0.9 < r.confianza_media < 1
    assert r.resumen_campos() == {
        "paginas": 1,
        "palabras": 16,
        "tablas": 1,
        "pares": 3,
        "campos": 0,
        "lineas": 0,
        "caracteres": len(r.texto),
    }


def test_normalizacion_a_documento_leido(http_falso, respuestas_documentales, fixtures, tmp_path):
    _encolar_ok(http_falso, respuestas_documentales)
    registro = RegistroMemoria()
    lector = LectorDocumental(_proveedor(http_falso), {"B99999999"}, tmp_path, registro)
    doc = lector.leer(fixtures / "imagenes" / "albaran_sintetico.jpg")
    assert doc.resultado == ResultadoLectura.IMAGEN_OCR and doc.motor == "azure:prebuilt-layout"
    assert doc.tipo == TipoDocumento.ALBARAN and doc.cif == "B00000001"
    assert doc.numero == "AC B26 0100009999" and str(doc.fecha) == "2026-09-20"
    assert [li.codigo_proveedor for li in doc.lineas] == ["REF-A1", "REF-B22"]
    li = doc.lineas[0]
    assert (li.cantidad, li.precio_bruto, li.descuento_pct, li.importe) == (
        Decimal("100.00"),
        Decimal("0.12"),
        Decimal("45"),
        Decimal("6.60"),
    )
    assert "linea[0].precio_bruto" in doc.campos_dudosos  # la palabra "0,12" vino con confianza 0,42
    assert doc.coste_estimado_eur == Decimal("0.0092") and doc.metadatos_motor["request_id"] == "req-123"
    assert registro.llamadas[0].estado == "ok" and registro.llamadas[0].campos_recibidos["tablas"] == 1


def test_heic_se_envia_como_jpeg(http_falso, respuestas_documentales, fixtures, tmp_path):
    _encolar_ok(http_falso, respuestas_documentales)
    lector = LectorDocumental(_proveedor(http_falso), carpeta_derivados=tmp_path, registro=RegistroMemoria())
    doc = lector.leer(fixtures / "imagenes" / "albaran_sintetico_exif6.heic")
    enviado = base64.b64decode(json.loads(http_falso.peticiones[0]["cuerpo"])["base64Source"])
    assert enviado[:2] == b"\xff\xd8"  # JPEG
    assert doc.metadatos_motor["sha256_enviado"] != doc.sha256  # se envió el derivado, el original queda en la traza


def test_reintenta_429_y_luego_funciona(http_falso, respuestas_documentales, fixtures, tmp_path):
    http_falso.encolar(429, {"error": {"code": "429"}}, {"Retry-After": "1"})
    _encolar_ok(http_falso, respuestas_documentales)
    r = _proveedor(http_falso).analizar(preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path))
    assert len(http_falso.peticiones) == 4 and r.tablas


def test_credenciales_malas_no_reintenta(http_falso, fixtures, tmp_path):
    http_falso.encolar(401, {"error": {"code": "401", "message": "Access denied"}}, {"apim-request-id": "r1"})
    with pytest.raises(ErrorPermanente) as exc:
        _proveedor(http_falso).analizar(preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path))
    assert exc.value.estado_http == 401 and exc.value.request_id == "r1" and len(http_falso.peticiones) == 1


def test_servicio_caido_deja_documento_pendiente(http_falso, fixtures, tmp_path):
    for _ in range(3):
        http_falso.encolar(503, {"error": {"message": "Service unavailable"}})
    doc = LectorDocumental(_proveedor(http_falso), carpeta_derivados=tmp_path).leer(
        fixtures / "imagenes" / "albaran_sintetico.jpg"
    )
    assert doc.resultado == ResultadoLectura.PROVEEDOR_NO_DISPONIBLE
    assert doc.errores[0].codigo == CodigoError.PROVEEDOR_DOCUMENTAL_NO_DISPONIBLE and doc.errores[0].recuperable


def test_red_caida_es_transitoria(http_falso, fixtures, tmp_path):
    for _ in range(3):
        http_falso.respuestas.append(ErrorRed("timeout"))
    with pytest.raises(ErrorTransitorio):
        _proveedor(http_falso).analizar(preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path))


def test_analisis_fallido_y_sondeo_agotado(http_falso, fixtures, tmp_path):
    documento = preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path)
    http_falso.encolar(202, {}, {"Operation-Location": OP})
    http_falso.encolar(200, {"status": "failed", "error": {"code": "InvalidContent", "message": "corrupto"}})
    with pytest.raises(ErrorPermanente, match="InvalidContent"):
        _proveedor(http_falso).analizar(documento)
    http_falso.encolar(202, {}, {"Operation-Location": OP})
    for _ in range(5):
        http_falso.encolar(200, {"status": "running"}, {"Retry-After": "10"})
    with pytest.raises(ErrorTransitorio, match="no terminó"):
        _proveedor(http_falso, espera_max_s=25).analizar(documento)


def test_prebuilt_invoice_completa_desde_campos(http_falso, respuestas_documentales, fixtures, tmp_path):
    _encolar_ok(http_falso, respuestas_documentales, "azure_invoice_albaran.json")
    lector = LectorDocumental(
        _proveedor(http_falso, modelo="prebuilt-invoice", caracteristicas=()),
        {"B99999999"},
        tmp_path,
        RegistroMemoria(),
    )
    doc = lector.leer(fixtures / "imagenes" / "albaran_sintetico.jpg")
    assert "features" not in http_falso.peticiones[0]["url"]
    assert doc.numero == "AC B26 0100009999" and str(doc.fecha) == "2026-09-20" and doc.cif == "B00000001"
    assert doc.lineas[0].codigo_proveedor == "REF-A1" and doc.lineas[0].precio_bruto == Decimal("0.12")
    assert any("campos estructurados" in a for a in doc.avisos)
    assert lector.ultimo.paginas[0].palabras[0].caja.unidad == "inch"


def test_sin_credenciales_error_permanente():
    with pytest.raises(ErrorPermanente, match="AZURE_DOCUMENT_INTELLIGENCE"):
        AzureDocumentIntelligenceProvider("", "", POLITICA)


def test_imagen_grande_se_recomprime_al_limite_del_proveedor(http_falso, respuestas_documentales, fixtures, tmp_path):
    """Una foto de móvil convertida pesa más que los 4 MB del plan gratuito: se recomprime y se anota."""
    from PIL import Image

    grande = tmp_path / "grande.png"
    Image.effect_noise((3000, 2200), 90).convert("RGB").save(grande)  # ruido: no comprime bien
    _encolar_ok(http_falso, respuestas_documentales)
    proveedor = _proveedor(http_falso, max_bytes=1_500_000)
    doc = LectorDocumental(proveedor, carpeta_derivados=tmp_path / "d", registro=RegistroMemoria()).leer(grande)
    enviado = base64.b64decode(json.loads(http_falso.peticiones[0]["cuerpo"])["base64Source"])
    assert len(enviado) <= 1_500_000 and enviado[:2] == b"\xff\xd8"
    assert any("recomprimida" in a for a in doc.avisos)


def test_pdf_demasiado_grande_se_rechaza_sin_enviar(http_falso, fixtures, tmp_path):
    proveedor = _proveedor(http_falso, max_bytes=1_000)
    doc = LectorDocumental(proveedor, carpeta_derivados=tmp_path).leer(
        fixtures / "documentos" / "albaran_vega_bruto_descuento.pdf"
    )
    assert doc.resultado == ResultadoLectura.NO_SOPORTADO and "admite" in doc.avisos[0]
    assert http_falso.peticiones == []
