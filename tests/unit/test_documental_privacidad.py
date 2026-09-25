"""Protección técnica del envío externo: con ALLOW_EXTERNAL_DOCUMENT_PROCESSING=false (o sin el proveedor en la lista
permitida) ningún proveedor cloud recibe un byte; el router rechaza al arrancar; procesar_buzon sale con código 3; y
ninguna clave aparece en repr, registros ni errores."""

import json

import pytest

from idm import config
from idm.documental.azure import AzureDocumentIntelligenceProvider
from idm.documental.base import ConfiguracionDocumentalInvalida, ProcesamientoExternoNoAutorizado
from idm.documental.entrada import preparar
from idm.documental.lector import LectorDocumental
from idm.documental.mistral import MistralDocumentAIProvider
from idm.documental.privacidad import PoliticaEnvioExterno
from idm.documental.registro import RegistroJSONL, RegistroMemoria
from idm.documental.router import crear_proveedor, lector_desde_config
from idm.dominio.estados import CodigoError, ResultadoLectura

CLAVE = "SECRETO-DE-PRUEBA-123"


def _cfg(tmp_path, **extra):
    base = dict(
        ruta_datos=tmp_path,
        ruta_entrada=tmp_path / "e",
        ruta_procesados=tmp_path / "p",
        ruta_siddex=tmp_path,
        ruta_planning=tmp_path / "x.xlsx",
        ruta_pedidos_pdf=tmp_path,
        ruta_salida=tmp_path,
        ruta_pedidos_transmitidos=None,
        database_url="sqlite://",
        modo_simulacion=True,
        azure_endpoint="https://ficticio.cognitiveservices.azure.com",
        azure_key=CLAVE,
        mistral_key=CLAVE,
    )
    base.update(extra)
    return config.Config(**base)


def test_politica_por_defecto_deniega():
    p = PoliticaEnvioExterno()
    assert "ALLOW_EXTERNAL_DOCUMENT_PROCESSING=false" in p.motivo_rechazo("azure")
    with pytest.raises(ProcesamientoExternoNoAutorizado):
        p.comprobar("mistral")


def test_politica_exige_lista_explicita():
    p = PoliticaEnvioExterno(True, frozenset({"azure"}))
    assert p.motivo_rechazo("azure") is None
    assert "EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED" in p.motivo_rechazo("mistral")


@pytest.mark.parametrize(
    "fabrica",
    [
        lambda pol, http: AzureDocumentIntelligenceProvider("https://x", CLAVE, pol, http=http),
        lambda pol, http: MistralDocumentAIProvider(CLAVE, pol, http=http),
    ],
)
def test_proveedor_externo_no_envia_nada_sin_autorizacion(fabrica, http_falso, fixtures, tmp_path):
    proveedor = fabrica(PoliticaEnvioExterno(), http_falso)
    documento = preparar(fixtures / "imagenes" / "albaran_sintetico.jpg", tmp_path)
    with pytest.raises(ProcesamientoExternoNoAutorizado):
        proveedor.analizar(documento)
    assert http_falso.peticiones == []  # ni una petición


def test_lector_documental_rechazo_queda_registrado_sin_envio(http_falso, fixtures, tmp_path):
    registro = RegistroMemoria()
    proveedor = MistralDocumentAIProvider(CLAVE, PoliticaEnvioExterno(), http=http_falso)
    doc = LectorDocumental(proveedor, carpeta_derivados=tmp_path, registro=registro).leer(
        fixtures / "imagenes" / "albaran_sintetico.heic"
    )
    assert doc.resultado == ResultadoLectura.REQUIERE_OCR
    assert doc.errores[0].codigo == CodigoError.PROCESAMIENTO_EXTERNO_NO_AUTORIZADO and not doc.errores[0].recuperable
    assert registro.llamadas[0].estado == "rechazado_privacidad" and registro.llamadas[0].sha256_enviado is None
    assert http_falso.peticiones == []


@pytest.mark.parametrize("nombre", ["azure", "mistral"])
def test_router_rechaza_externo_al_arrancar(nombre, tmp_path):
    with pytest.raises(ConfiguracionDocumentalInvalida, match="ALLOW_EXTERNAL_DOCUMENT_PROCESSING"):
        crear_proveedor(nombre, _cfg(tmp_path))
    with pytest.raises(ConfiguracionDocumentalInvalida, match="EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED"):
        crear_proveedor(nombre, _cfg(tmp_path, allow_external_document_processing=True))
    with pytest.raises(ConfiguracionDocumentalInvalida):
        lector_desde_config(_cfg(tmp_path, document_provider=nombre))


def test_procesar_buzon_sale_con_codigo_3_si_la_configuracion_externa_no_esta_autorizada(monkeypatch, tmp_path, capsys):
    from idm.tareas import procesar_buzon

    (tmp_path / "entrada").mkdir()
    (tmp_path / "entrada" / "a.jpg").write_bytes(b"\xff\xd8 no importa")
    monkeypatch.setenv("RUTA_DATOS", str(tmp_path))
    monkeypatch.setenv("RUTA_ENTRADA", str(tmp_path / "entrada"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'idm.db'}")
    monkeypatch.setenv("DOCUMENT_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", CLAVE)
    monkeypatch.setenv("ALLOW_EXTERNAL_DOCUMENT_PROCESSING", "false")
    assert procesar_buzon.main(["--sin-imap"]) == 3
    assert "Configuración documental rechazada" in capsys.readouterr().out
    assert (tmp_path / "entrada" / "a.jpg").exists()  # no se ha tocado nada


def test_secretos_fuera_de_repr_y_registros(http_falso, fixtures, tmp_path):
    cfg = _cfg(tmp_path, allow_external_document_processing=True, external_document_providers_allowed=("azure",))
    assert CLAVE not in repr(cfg)
    proveedor = crear_proveedor("azure", cfg, http=http_falso)
    assert CLAVE not in repr(proveedor)
    http_falso.encolar(401, {"error": {"code": "401", "message": "Access denied due to invalid subscription key."}})
    ruta_log = tmp_path / "llamadas.jsonl"
    doc = LectorDocumental(proveedor, carpeta_derivados=tmp_path, registro=RegistroJSONL(ruta_log)).leer(
        fixtures / "imagenes" / "albaran_sintetico.jpg"
    )
    assert http_falso.peticiones[0]["cabeceras"]["Ocp-Apim-Subscription-Key"] == CLAVE  # se usa…
    volcado = ruta_log.read_text(encoding="utf-8") + json.dumps(doc.model_dump(mode="json"))
    assert CLAVE not in volcado  # …pero no se guarda en ningún sitio
    assert "base64" not in volcado and "albaran_sintetico" not in ruta_log.read_text(encoding="utf-8")
