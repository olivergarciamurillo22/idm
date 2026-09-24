"""Router y respaldo: cambiar de motor por configuración, faltan credenciales, proveedor desconocido o sin implementar,
modo benchmark, compatibilidad con OCR_MOTOR, y fallback controlado (sin respaldo el documento queda pendiente; el
respaldo solo se usa si está configurado y, si es externo, autorizado)."""

import pytest

from idm import config
from idm.albaranes.lector import LectorImagenNulo
from idm.documental.base import ConfiguracionDocumentalInvalida, ErrorTransitorio
from idm.documental.lector import LectorDocumental
from idm.documental.modelo import MetadatosMotor, ResultadoDocumental
from idm.documental.registro import RegistroMemoria
from idm.documental.router import ProveedorComparativo, crear_proveedor, lector_desde_config
from idm.documental.tesseract import TesseractProvider
from idm.dominio.estados import ResultadoLectura


def _cfg(tmp_path, **extra):
    base = dict(
        ruta_datos=tmp_path,
        ruta_entrada=tmp_path,
        ruta_procesados=tmp_path,
        ruta_siddex=tmp_path,
        ruta_planning=tmp_path / "x.xlsx",
        ruta_pedidos_pdf=tmp_path,
        ruta_salida=tmp_path,
        ruta_pedidos_transmitidos=None,
        database_url="sqlite://",
        modo_simulacion=True,
    )
    base.update(extra)
    return config.Config(**base)


AUTORIZADO = dict(allow_external_document_processing=True, external_document_providers_allowed=("azure", "mistral"))


def test_ninguno_y_tesseract(tmp_path):
    assert isinstance(lector_desde_config(_cfg(tmp_path)).imagen, LectorImagenNulo)
    lector = lector_desde_config(_cfg(tmp_path, document_provider="tesseract"))
    assert isinstance(lector.imagen, LectorDocumental) and isinstance(lector.imagen.proveedor, TesseractProvider)
    assert lector.imagen.respaldo is None


def test_externos_con_autorizacion_y_credenciales(tmp_path):
    cfg = _cfg(tmp_path, azure_endpoint="https://x", azure_key="k", mistral_key="k", **AUTORIZADO)
    assert crear_proveedor("azure", cfg).nombre == "azure"
    assert crear_proveedor("mistral", cfg).modelo == "mistral-ocr-latest"
    with pytest.raises(ConfiguracionDocumentalInvalida, match="AZURE_DOCUMENT_INTELLIGENCE"):
        crear_proveedor("azure", _cfg(tmp_path, **AUTORIZADO))
    with pytest.raises(ConfiguracionDocumentalInvalida, match="MISTRAL_API_KEY"):
        crear_proveedor("mistral", _cfg(tmp_path, **AUTORIZADO))


def test_desconocido_y_google(tmp_path):
    with pytest.raises(ConfiguracionDocumentalInvalida, match="desconocido"):
        crear_proveedor("paddle", _cfg(tmp_path))
    with pytest.raises(ConfiguracionDocumentalInvalida, match="no implementado"):
        crear_proveedor(
            "google",
            _cfg(tmp_path, allow_external_document_processing=True, external_document_providers_allowed=("google",)),
        )


def test_respaldo_configuracion(tmp_path):
    cfg = _cfg(
        tmp_path, document_provider="mistral", mistral_key="k", document_provider_fallback="tesseract", **AUTORIZADO
    )
    assert isinstance(lector_desde_config(cfg).imagen.respaldo, TesseractProvider)
    with pytest.raises(ConfiguracionDocumentalInvalida, match="mismo"):
        lector_desde_config(_cfg(tmp_path, document_provider="tesseract", document_provider_fallback="tesseract"))
    # un respaldo externo no autorizado se rechaza al arrancar, aunque el principal sea local
    with pytest.raises(ConfiguracionDocumentalInvalida, match="ALLOW_EXTERNAL"):
        lector_desde_config(
            _cfg(
                tmp_path,
                document_provider="tesseract",
                document_provider_fallback="azure",
                azure_endpoint="https://x",
                azure_key="k",
            )
        )


def test_modo_benchmark(tmp_path):
    lector = lector_desde_config(
        _cfg(tmp_path, document_provider="benchmark", document_providers_benchmark=("tesseract",))
    )
    assert isinstance(lector.imagen.proveedor, ProveedorComparativo)


def test_ocr_motor_antiguo_sigue_funcionando(monkeypatch, tmp_path):
    monkeypatch.delenv("DOCUMENT_PROVIDER", raising=False)
    monkeypatch.setenv("OCR_MOTOR", "tesseract")
    monkeypatch.setenv("RUTA_DATOS", str(tmp_path))
    cfg = config.cargar(tmp_path / "no_existe.env")
    assert cfg.document_provider == "tesseract" and cfg.allow_external_document_processing is False


class _Falla:
    nombre, modelo, externo = "falla", "x", False

    def __init__(self):
        self.llamadas = 0

    def disponible(self):
        return True

    def analizar(self, documento):
        self.llamadas += 1
        raise ErrorTransitorio("servicio caído")


class _Funciona:
    nombre, modelo, externo = "local", "y", False

    def __init__(self):
        self.llamadas = 0

    def disponible(self):
        return True

    def analizar(self, documento):
        self.llamadas += 1
        return ResultadoDocumental(
            texto="ALBARAN Nº: X-1", metadatos=MetadatosMotor(proveedor="local", modelo="y", externo=False)
        )


def test_sin_respaldo_queda_pendiente_y_no_se_prueba_otro(fixtures, tmp_path):
    otro = _Funciona()
    registro = RegistroMemoria()
    doc = LectorDocumental(_Falla(), carpeta_derivados=tmp_path, registro=registro).leer(
        fixtures / "imagenes" / "albaran_sintetico.jpg"
    )
    assert doc.resultado == ResultadoLectura.PROVEEDOR_NO_DISPONIBLE and doc.errores[0].recuperable
    assert otro.llamadas == 0 and [c.estado for c in registro.llamadas] == ["error_transitorio"]


def test_con_respaldo_explicito_se_usa(fixtures, tmp_path):
    respaldo = _Funciona()
    registro = RegistroMemoria()
    doc = LectorDocumental(_Falla(), carpeta_derivados=tmp_path, registro=registro, respaldo=respaldo).leer(
        fixtures / "imagenes" / "albaran_sintetico.jpg"
    )
    assert respaldo.llamadas == 1 and doc.resultado == ResultadoLectura.IMAGEN_OCR and doc.motor == "local:y"
    assert [c.estado for c in registro.llamadas] == ["error_transitorio", "ok"]
