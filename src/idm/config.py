"""Configuración del programa: lee .env (rutas, buzones, correo, modo simulación) y expone un objeto Config.
Nada de configuración escondida: todo lo que cambia entre el PC de desarrollo y el servidor de IDM está aquí.
No contiene secretos: los valores vienen del .env, que no entra en git."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Buzon:
    host: str
    usuario: str
    clave: str = field(repr=False)  # nunca en logs ni trazas
    carpeta: str = "INBOX"


@dataclass(frozen=True)
class Config:
    ruta_datos: Path
    ruta_entrada: Path
    ruta_procesados: Path
    ruta_siddex: Path
    ruta_planning: Path
    ruta_pedidos_pdf: Path
    ruta_salida: Path
    ruta_pedidos_transmitidos: Path | None
    database_url: str
    modo_simulacion: bool
    empresa: dict[str, str] = field(default_factory=dict)
    smtp_host: str = ""
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_clave: str = field(default="", repr=False)
    smtp_remitente: str = ""
    buzones: tuple[Buzon, ...] = ()
    bandeja_host: str = "0.0.0.0"
    bandeja_puerto: int = 8000
    ocr_motor: str = "ninguno"  # obsoleto: se usa si DOCUMENT_PROVIDER no está definido
    ocr_tuberia: str = "contraste_3200,recorte_3200"  # tuberías de albaranes.preprocesado.TUBERIAS, se unen
    ocr_lang: str = "spa+eng"
    # Lectura documental (documental/). Los secretos no salen en repr(): un print(cfg) no los filtra.
    document_provider: str = "ninguno"  # ninguno | tesseract | azure | mistral | google | benchmark
    document_provider_fallback: str = ""  # vacío = sin respaldo automático
    document_providers_benchmark: tuple[str, ...] = ("tesseract",)
    allow_external_document_processing: bool = False
    external_document_providers_allowed: tuple[str, ...] = ()
    azure_endpoint: str = ""
    azure_key: str = field(default="", repr=False)
    azure_model: str = "prebuilt-layout"
    azure_api_version: str = "2024-11-30"
    azure_features: tuple[str, ...] = ("keyValuePairs",)
    mistral_key: str = field(default="", repr=False)
    mistral_model: str = "mistral-ocr-latest"
    mistral_endpoint: str = "https://api.mistral.ai/v1/ocr"
    mistral_annotation: bool = False
    mistral_confidence: str = "word"
    document_pricing_file: Path | None = None
    document_provider_timeout_s: float = 120.0
    document_provider_max_retries: int = 3
    tesseract_cmd: str = (
        "tesseract"  # en Windows, si no está en el PATH: C:\\Program Files\\Tesseract-OCR\\tesseract.exe
    )
    azure_max_bytes: int = 4_000_000  # límite del plan gratuito F0 (el S0 admite 500 MB): cabe en ambos

    @property
    def cifs_propios(self) -> set[str]:
        cif = (self.empresa.get("cif") or "").replace(" ", "").replace("-", "").upper()
        return {cif} if cif else set()

    def crear_carpetas(self) -> None:
        for ruta in (
            self.ruta_datos,
            self.ruta_entrada,
            self.ruta_procesados,
            self.ruta_siddex,
            self.ruta_pedidos_pdf,
            self.ruta_salida,
        ):
            ruta.mkdir(parents=True, exist_ok=True)


def _ruta(valor: str) -> Path:
    ruta = Path(valor)
    return ruta if ruta.is_absolute() else RAIZ / ruta


VERDADEROS = ("1", "true", "si", "sí", "yes")
FALSOS = ("", "0", "false", "no")


def _bool(valor: str) -> bool:
    """true/false (y sí/no, 1/0). Cualquier otra cosa es un error: una errata en ALLOW_EXTERNAL_DOCUMENT_PROCESSING
    no debe convertirse en silencio en un valor distinto del que se quería."""
    limpio = (valor or "").strip().lower()
    if limpio in VERDADEROS:
        return True
    if limpio in FALSOS:
        return False
    raise ConfiguracionInvalida(f"Valor {valor!r} en .env: se esperaba true o false")


class ConfiguracionInvalida(ValueError):
    """Un valor del .env no se puede interpretar. El mensaje dice qué variable y qué valor."""


def _numero(nombre: str, defecto: str, tipo=int):
    """Número del entorno; vacío = valor por defecto; texto no numérico = error claro (no un traceback de int())."""
    valor = (os.environ.get(nombre) or "").strip() or defecto
    try:
        return tipo(valor.replace(",", "."))
    except ValueError as exc:
        raise ConfiguracionInvalida(f"{nombre}={valor!r} en .env no es un número válido") from exc


def _lista(valor: str, minusculas: bool = True) -> tuple[str, ...]:
    partes = (p.strip() for p in (valor or "").split(","))
    return tuple(p.lower() if minusculas else p for p in partes if p)


def _buzones(valor: str) -> tuple[Buzon, ...]:
    """IMAP_BUZONES=host|usuario|clave|carpeta;host|usuario|clave"""
    resultado = []
    for trozo in filter(None, (t.strip() for t in valor.split(";"))):
        partes = trozo.split("|")
        if len(partes) < 3:
            raise ValueError(f"IMAP_BUZONES: entrada incompleta '{trozo}'")
        resultado.append(Buzon(partes[0], partes[1], partes[2], partes[3] if len(partes) > 3 else "INBOX"))
    return tuple(resultado)


def cargar(ruta_env: Path | None = None) -> Config:
    """Carga .env (o el fichero indicado) sobre las variables de entorno y construye Config."""
    # IDM_ENV_FILE permite apuntar a otro fichero (los tests lo usan para no leer el .env del desarrollador)
    load_dotenv(ruta_env or Path(os.environ.get("IDM_ENV_FILE") or RAIZ / ".env"), override=False)
    g = os.environ.get
    return Config(
        ruta_datos=_ruta(g("RUTA_DATOS", "datos")),
        ruta_entrada=_ruta(g("RUTA_ENTRADA", "datos/entrada")),
        ruta_procesados=_ruta(g("RUTA_PROCESADOS", "datos/procesados")),
        ruta_siddex=_ruta(g("RUTA_SIDDEX", "datos/siddex")),
        ruta_planning=_ruta(g("RUTA_PLANNING", "datos/planning/PLANNING_IDM_MENSUAL.xlsx")),
        ruta_pedidos_pdf=_ruta(g("RUTA_PEDIDOS_PDF", "datos/pedidos")),
        ruta_salida=_ruta(g("RUTA_SALIDA", "datos/salida")),
        ruta_pedidos_transmitidos=_ruta(g("RUTA_PEDIDOS_TRANSMITIDOS")) if g("RUTA_PEDIDOS_TRANSMITIDOS") else None,
        database_url=g("DATABASE_URL", f"sqlite:///{RAIZ / 'datos' / 'idm.db'}"),
        modo_simulacion=_bool(g("MODO_SIMULACION", "true")),
        empresa={
            "nombre": g("EMPRESA_NOMBRE", "IDM"),
            "direccion": g("EMPRESA_DIRECCION", ""),
            "cif": g("EMPRESA_CIF", ""),
            "telefono": g("EMPRESA_TELEFONO", ""),
            "email_pedidos": g("EMPRESA_EMAIL_PEDIDOS", ""),
        },
        smtp_host=g("SMTP_HOST", ""),
        smtp_puerto=_numero("SMTP_PUERTO", "587"),
        smtp_usuario=g("SMTP_USUARIO", ""),
        smtp_clave=g("SMTP_CLAVE", ""),
        smtp_remitente=g("SMTP_REMITENTE", ""),
        buzones=_buzones(g("IMAP_BUZONES", "")),
        bandeja_host=g("BANDEJA_HOST", "0.0.0.0"),
        bandeja_puerto=_numero("BANDEJA_PUERTO", "8000"),
        ocr_motor=g("OCR_MOTOR", "ninguno").strip().lower(),
        ocr_tuberia=g("OCR_TUBERIA", "contraste_3200,recorte_3200").strip().lower(),
        ocr_lang=g("OCR_LANG", "spa+eng").strip(),
        document_provider=(g("DOCUMENT_PROVIDER") or g("OCR_MOTOR") or "ninguno").strip().lower(),
        document_provider_fallback=g("DOCUMENT_PROVIDER_FALLBACK", "").strip().lower(),
        document_providers_benchmark=_lista(g("DOCUMENT_PROVIDERS_BENCHMARK", "tesseract")),
        allow_external_document_processing=_bool(g("ALLOW_EXTERNAL_DOCUMENT_PROCESSING", "false")),
        external_document_providers_allowed=_lista(g("EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED", "")),
        azure_endpoint=g("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "").strip(),
        azure_key=g("AZURE_DOCUMENT_INTELLIGENCE_KEY", "").strip(),
        azure_model=g("AZURE_DOCUMENT_INTELLIGENCE_MODEL", "prebuilt-layout").strip(),
        azure_api_version=g("AZURE_DOCUMENT_INTELLIGENCE_API_VERSION", "2024-11-30").strip(),
        azure_features=_lista(g("AZURE_DOCUMENT_INTELLIGENCE_FEATURES", "keyValuePairs"), minusculas=False),
        mistral_key=g("MISTRAL_API_KEY", "").strip(),
        mistral_model=g("MISTRAL_OCR_MODEL", "mistral-ocr-latest").strip(),
        mistral_endpoint=g("MISTRAL_OCR_ENDPOINT", "https://api.mistral.ai/v1/ocr").strip(),
        mistral_annotation=_bool(g("MISTRAL_DOCUMENT_ANNOTATION", "false")),
        mistral_confidence=g("MISTRAL_OCR_CONFIDENCE", "word").strip().lower(),
        document_pricing_file=_ruta(g("DOCUMENT_PRICING_FILE")) if g("DOCUMENT_PRICING_FILE") else None,
        document_provider_timeout_s=_numero("DOCUMENT_PROVIDER_TIMEOUT_S", "120", float),
        document_provider_max_retries=_numero("DOCUMENT_PROVIDER_MAX_RETRIES", "3"),
        tesseract_cmd=(g("TESSERACT_CMD") or "").strip() or "tesseract",
        azure_max_bytes=_numero("AZURE_DOCUMENT_INTELLIGENCE_MAX_BYTES", "4000000"),
    )
