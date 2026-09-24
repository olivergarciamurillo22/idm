"""Integración REAL con proveedores cloud. Solo corre con IDM_RUN_CLOUD_TESTS=1 y la clave del proveedor en el entorno.
Envía únicamente la imagen SINTÉTICA ficticia del repositorio (fixtures/ficticios/imagenes/albaran_sintetico.jpg),
nunca documentos de IDM; por eso construye su propia política en vez de usar ALLOW_EXTERNAL_DOCUMENT_PROCESSING."""

import os
from pathlib import Path

import pytest

from idm.documental.azure import AzureDocumentIntelligenceProvider
from idm.documental.costes import Tarifas
from idm.documental.lector import LectorDocumental
from idm.documental.mistral import MistralDocumentAIProvider
from idm.documental.privacidad import PoliticaEnvioExterno
from idm.dominio.estados import ResultadoLectura

pytestmark = pytest.mark.cloud
RAIZ = Path(__file__).resolve().parents[2]
SINTETICA = RAIZ / "fixtures" / "ficticios" / "imagenes" / "albaran_sintetico.jpg"
ACTIVO = os.environ.get("IDM_RUN_CLOUD_TESTS") == "1"


def _cargar_env():
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env", override=False)


def _leer(proveedor, tmp_path):
    assert SINTETICA.is_relative_to(RAIZ / "fixtures" / "ficticios")  # salvaguarda: solo material ficticio
    return LectorDocumental(proveedor, {"B99999999"}, tmp_path).leer(SINTETICA)


@pytest.mark.skipif(not ACTIVO, reason="IDM_RUN_CLOUD_TESTS=1 para ejecutar llamadas reales")
def test_mistral_real_con_imagen_sintetica(tmp_path):
    _cargar_env()
    clave = os.environ.get("MISTRAL_API_KEY")
    if not clave:
        pytest.skip("falta MISTRAL_API_KEY")
    proveedor = MistralDocumentAIProvider(
        clave,
        PoliticaEnvioExterno(True, frozenset({"mistral"})),
        confianza=os.environ.get("MISTRAL_OCR_CONFIDENCE", "word"),
        tarifas=Tarifas.cargar(),
    )
    doc = _leer(proveedor, tmp_path)
    assert doc.resultado == ResultadoLectura.IMAGEN_OCR, doc.avisos
    assert doc.numero == "AC B26 0100009999"
    assert doc.metadatos_motor.get("paginas") == "1"


@pytest.mark.skipif(not ACTIVO, reason="IDM_RUN_CLOUD_TESTS=1 para ejecutar llamadas reales")
def test_azure_real_con_imagen_sintetica(tmp_path):
    _cargar_env()
    endpoint, clave = (
        os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
        os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY"),
    )
    if not endpoint or not clave:
        pytest.skip("faltan AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT/KEY")
    proveedor = AzureDocumentIntelligenceProvider(
        endpoint, clave, PoliticaEnvioExterno(True, frozenset({"azure"})), tarifas=Tarifas.cargar()
    )
    doc = _leer(proveedor, tmp_path)
    assert doc.resultado == ResultadoLectura.IMAGEN_OCR, doc.avisos
    assert doc.numero == "AC B26 0100009999" and doc.metadatos_motor.get("request_id")
