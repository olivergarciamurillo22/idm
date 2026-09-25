"""LectorDocumental: implementa albaranes.lector.LectorDocumentos con cualquier DocumentProvider. Prepara la entrada
(HEIC → JPEG), llama al proveedor, registra la llamada (también si falla) y normaliza a DocumentoLeido.
Los fallos técnicos quedan como PROVEEDOR_NO_DISPONIBLE (reintentable): nunca se prueba otro proveedor por su cuenta."""

from pathlib import Path

from idm.albaranes.imagenes import ImagenNoLegible, sha256_fichero
from idm.documental import entrada
from idm.documental.base import (
    DocumentProvider,
    ErrorPermanente,
    ErrorProveedorDocumental,
    ErrorTransitorio,
    ProcesamientoExternoNoAutorizado,
)
from idm.documental.modelo import ResultadoDocumental
from idm.documental.normalizacion import a_documento_leido
from idm.documental.registro import LlamadaDocumental, RegistroLlamadas, RegistroMemoria
from idm.dominio.estados import CodigoError, ResultadoLectura
from idm.dominio.modelos import DocumentoLeido, ErrorProcesamiento

RESULTADO_POR_ERROR = {
    ProcesamientoExternoNoAutorizado: (
        ResultadoLectura.REQUIERE_OCR,
        CodigoError.PROCESAMIENTO_EXTERNO_NO_AUTORIZADO,
        False,
    ),
    ErrorTransitorio: (ResultadoLectura.PROVEEDOR_NO_DISPONIBLE, CodigoError.PROVEEDOR_DOCUMENTAL_NO_DISPONIBLE, True),
    ErrorPermanente: (ResultadoLectura.PROVEEDOR_NO_DISPONIBLE, CodigoError.PROVEEDOR_DOCUMENTAL_ERROR, False),
}
ESTADO_REGISTRO = {
    ProcesamientoExternoNoAutorizado: "rechazado_privacidad",
    ErrorTransitorio: "error_transitorio",
    ErrorPermanente: "error_permanente",
}


class LectorDocumental:
    def __init__(
        self,
        proveedor: DocumentProvider,
        cifs_propios: set[str] | None = None,
        carpeta_derivados: Path = Path("datos/derivados_documentales"),
        registro: RegistroLlamadas | None = None,
        respaldo: DocumentProvider | None = None,
    ) -> None:
        """respaldo: segundo proveedor EXPLÍCITO (configurado) para fallos transitorios del primero. Si es externo, su
        propia política vuelve a comprobar la autorización."""
        self.proveedor = proveedor
        self.respaldo = respaldo
        self.cifs_propios = {c.upper() for c in (cifs_propios or set())} | {"B99999999"}
        self.carpeta_derivados = Path(carpeta_derivados)
        self.registro = registro or RegistroMemoria()
        self.ultimo: ResultadoDocumental | None = None
        self.ejecucion_id: str | None = None

    def _llamar(self, proveedor: DocumentProvider, documento) -> ResultadoDocumental:
        try:
            resultado = proveedor.analizar(documento)
        except ErrorProveedorDocumental as exc:
            estado = next((v for k, v in ESTADO_REGISTRO.items() if isinstance(exc, k)), "error_permanente")
            self.registro.registrar(
                LlamadaDocumental(
                    proveedor=proveedor.nombre,
                    modelo=getattr(proveedor, "modelo", ""),
                    externo=proveedor.externo,
                    sha256_documento=documento.sha256_original,
                    sha256_enviado=None if estado == "rechazado_privacidad" else documento.sha256_enviado,
                    estado=estado,
                    error=str(exc)[:300],
                    request_id=exc.request_id,
                    ejecucion_id=self.ejecucion_id,
                )
            )
            raise
        llamada = LlamadaDocumental.desde_resultado(resultado, documento.sha256_original)
        llamada.ejecucion_id = self.ejecucion_id
        self.registro.registrar(llamada)
        return resultado

    def leer(self, ruta: Path) -> DocumentoLeido:
        """Cada proveedor recibe su propia entrada: el local, el original; el externo, el derivado JPEG."""
        ruta = Path(ruta)
        self.ultimo = None
        entradas: dict[bool, object] = {}

        def entrada_para(proveedor):
            if proveedor.externo not in entradas:
                entradas[proveedor.externo] = entrada.preparar(
                    ruta,
                    self.carpeta_derivados,
                    convertir=proveedor.externo,
                    max_bytes=getattr(proveedor, "max_bytes", None),
                )
            return entradas[proveedor.externo]

        try:
            documento = entrada_para(self.proveedor)
            resultado = self._llamar(self.proveedor, documento)
        except ImagenNoLegible as exc:
            return _no_leido(ruta, ResultadoLectura.CORRUPTO, CodigoError.LECTURA_CORRUPTO, str(exc), False)
        except entrada.FormatoNoAdmitido as exc:
            return _no_leido(ruta, ResultadoLectura.NO_SOPORTADO, CodigoError.LECTURA_NO_SOPORTADA, str(exc), False)
        except ErrorTransitorio as exc:
            if self.respaldo is None:
                return self._error(ruta, exc)
            try:
                documento = entrada_para(self.respaldo)
                resultado = self._llamar(self.respaldo, documento)
            except ErrorProveedorDocumental as exc2:
                return self._error(ruta, exc2, previo=exc)
        except ErrorProveedorDocumental as exc:
            return self._error(ruta, exc)
        self.ultimo = resultado
        doc = a_documento_leido(resultado, ruta, documento.sha256_original, self.cifs_propios)
        if documento.nota:
            doc.avisos.append(f"Imagen enviada {documento.nota}")
        return doc

    def _error(self, ruta: Path, exc: ErrorProveedorDocumental, previo: ErrorProveedorDocumental | None = None):
        resultado, codigo, recuperable = next(v for k, v in RESULTADO_POR_ERROR.items() if isinstance(exc, k))
        mensaje = f"{self.proveedor.nombre}: {exc}" + (f" (antes: {previo})" if previo else "")
        doc = _no_leido(ruta, resultado, codigo, mensaje, recuperable)
        if exc.request_id:
            doc.metadatos_motor["request_id"] = exc.request_id
        doc.motor = f"{self.proveedor.nombre}:{getattr(self.proveedor, 'modelo', '')}"
        return doc


def _no_leido(ruta: Path, resultado: ResultadoLectura, codigo: CodigoError, mensaje: str, recuperable: bool):
    try:
        sha = sha256_fichero(ruta)
    except OSError:
        sha = ""
    return DocumentoLeido(
        ruta=str(ruta),
        sha256=sha,
        metodo="no_leido",
        resultado=resultado,
        confianza=0.0,
        avisos=[mensaje],
        errores=[ErrorProcesamiento(codigo=codigo, mensaje=mensaje, recuperable=recuperable)],
    )
