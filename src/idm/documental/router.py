"""Router de proveedores documentales: de la configuración (DOCUMENT_PROVIDER, DOCUMENT_PROVIDER_FALLBACK, credenciales,
política de envío externo) a un lector listo. Rechaza al arrancar cualquier proveedor externo no autorizado o sin
credenciales, con un mensaje claro. Cambiar de motor es cambiar el .env, nunca el código."""

from pathlib import Path

from idm.albaranes.lector import LectorAutomatico, LectorImagenNulo, LectorTextoPDF, tuberias_desde_texto
from idm.documental.azure import AzureDocumentIntelligenceProvider
from idm.documental.base import (
    ConfiguracionDocumentalInvalida,
    DocumentoEntrada,
    DocumentProvider,
    ErrorPermanente,
    ErrorProveedorDocumental,
)
from idm.documental.costes import Tarifas
from idm.documental.http import ClienteHTTP
from idm.documental.lector import LectorDocumental
from idm.documental.mistral import MistralDocumentAIProvider
from idm.documental.modelo import ResultadoDocumental
from idm.documental.privacidad import PoliticaEnvioExterno
from idm.documental.registro import LlamadaDocumental, RegistroJSONL, RegistroLlamadas
from idm.documental.tesseract import TesseractProvider

LOCALES = ("tesseract",)
EXTERNOS = ("azure", "mistral", "google")
VALIDOS = ("ninguno", *LOCALES, *EXTERNOS, "benchmark")


def _tarifas(cfg) -> Tarifas:
    return Tarifas.cargar(cfg.document_pricing_file)


def crear_proveedor(nombre: str, cfg, http: ClienteHTTP | None = None) -> DocumentProvider:
    """Un proveedor concreto. Externo sin autorización o sin credenciales → ConfiguracionDocumentalInvalida."""
    nombre = (nombre or "").strip().lower()
    if nombre not in (*LOCALES, *EXTERNOS):
        raise ConfiguracionDocumentalInvalida(
            f"Proveedor documental desconocido '{nombre}'. Válidos: {', '.join(VALIDOS)}"
        )
    politica = PoliticaEnvioExterno.desde_config(cfg)
    if nombre in EXTERNOS and (motivo := politica.motivo_rechazo(nombre)):
        raise ConfiguracionDocumentalInvalida(motivo)
    try:
        if nombre == "tesseract":
            tuberias = tuberias_desde_texto(cfg.ocr_tuberia)
            return TesseractProvider(tuberias[0], tuberias[1:], lang=cfg.ocr_lang, ejecutable=cfg.tesseract_cmd)
        if nombre == "azure":
            return AzureDocumentIntelligenceProvider(
                cfg.azure_endpoint,
                cfg.azure_key,
                politica,
                modelo=cfg.azure_model,
                version_api=cfg.azure_api_version,
                caracteristicas=cfg.azure_features,
                http=http,
                intentos=cfg.document_provider_max_retries,
                timeout_s=cfg.document_provider_timeout_s,
                tarifas=_tarifas(cfg),
                max_bytes=cfg.azure_max_bytes,
            )
        if nombre == "mistral":
            return MistralDocumentAIProvider(
                cfg.mistral_key,
                politica,
                modelo=cfg.mistral_model,
                endpoint=cfg.mistral_endpoint,
                anotacion=cfg.mistral_annotation,
                confianza=cfg.mistral_confidence,
                http=http,
                intentos=cfg.document_provider_max_retries,
                timeout_s=cfg.document_provider_timeout_s,
                tarifas=_tarifas(cfg),
            )
    except ErrorPermanente as exc:  # credenciales ausentes
        raise ConfiguracionDocumentalInvalida(f"{nombre}: {exc}") from exc
    # google: preparado, no implementado
    raise ConfiguracionDocumentalInvalida(
        "El proveedor 'google' está preparado pero no implementado (docs/DOCUMENT-PROVIDERS.md)"
    )


class ProveedorComparativo:
    """DOCUMENT_PROVIDER=benchmark: el primero de la lista lee el documento; los demás se ejecutan sobre el mismo
    documento solo para comparar (quedan en el registro de llamadas). Cada externo pasa su propia autorización."""

    nombre = "benchmark"
    externo = False

    def __init__(self, proveedores: list[DocumentProvider], registro: RegistroLlamadas) -> None:
        if not proveedores:
            raise ConfiguracionDocumentalInvalida("DOCUMENT_PROVIDERS_BENCHMARK está vacío")
        self.proveedores = proveedores
        self.registro = registro
        self.modelo = "+".join(p.nombre for p in proveedores)
        self.externo = any(p.externo for p in proveedores)

    def disponible(self) -> bool:
        return self.proveedores[0].disponible()

    def analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental:
        principal = self.proveedores[0].analizar(documento)
        for otro in self.proveedores[1:]:
            try:
                r = otro.analizar(documento)
                self.registro.registrar(LlamadaDocumental.desde_resultado(r, documento.sha256_original))
            except ErrorProveedorDocumental as exc:
                self.registro.registrar(
                    LlamadaDocumental(
                        proveedor=otro.nombre,
                        modelo=getattr(otro, "modelo", ""),
                        externo=otro.externo,
                        sha256_documento=documento.sha256_original,
                        estado="error",
                        error=str(exc)[:300],
                    )
                )
        return principal


def registro_desde_config(cfg) -> RegistroJSONL:
    return RegistroJSONL(Path(cfg.ruta_datos) / "llamadas_documentales.jsonl")


def lector_desde_config(cfg, http: ClienteHTTP | None = None, registro: RegistroLlamadas | None = None):
    """LectorAutomatico: PDF con texto → pdfplumber local (gratis y privado); imagen o escaneo → proveedor elegido."""
    registro = registro or registro_desde_config(cfg)
    texto = LectorTextoPDF(cfg.cifs_propios)
    nombre = cfg.document_provider
    if nombre in ("", "ninguno"):
        return LectorAutomatico(texto, LectorImagenNulo())
    if nombre == "benchmark":
        proveedor: DocumentProvider = ProveedorComparativo(
            [crear_proveedor(n, cfg, http) for n in cfg.document_providers_benchmark], registro
        )
    else:
        proveedor = crear_proveedor(nombre, cfg, http)
    respaldo = None
    if cfg.document_provider_fallback:
        if cfg.document_provider_fallback == nombre:
            raise ConfiguracionDocumentalInvalida("DOCUMENT_PROVIDER_FALLBACK no puede ser el mismo proveedor")
        respaldo = crear_proveedor(cfg.document_provider_fallback, cfg, http)
    imagen = LectorDocumental(
        proveedor, cfg.cifs_propios, Path(cfg.ruta_datos) / "derivados_documentales", registro, respaldo
    )
    return LectorAutomatico(texto, imagen)
