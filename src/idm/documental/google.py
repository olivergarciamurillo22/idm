"""GoogleDocumentAIProvider: hueco preparado para Google Cloud Document AI (Enterprise Document OCR / Layout Parser).
No implementado todavía: el router lo reconoce y responde con un error claro. Pasos para implementarlo en
docs/DOCUMENT-PROVIDERS.md ("Cómo añadir otro proveedor"); debe heredar de ProveedorExternoBase como Azure y Mistral."""

from idm.documental.base import DocumentoEntrada, ErrorPermanente, ProveedorExternoBase
from idm.documental.modelo import ResultadoDocumental
from idm.documental.privacidad import PoliticaEnvioExterno


class GoogleDocumentAIProvider(ProveedorExternoBase):
    nombre = "google"
    modelo = "document-ai (no implementado)"

    def __init__(self, politica: PoliticaEnvioExterno) -> None:
        super().__init__(politica)

    def disponible(self) -> bool:
        return False

    def _analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental:
        raise ErrorPermanente("GoogleDocumentAIProvider está preparado pero no implementado")
