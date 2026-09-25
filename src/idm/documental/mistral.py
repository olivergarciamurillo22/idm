"""MistralDocumentAIProvider: API oficial de Mistral OCR (POST /v1/ocr, modelo mistral-ocr-latest). Devuelve markdown
por página, tablas aparte (table_format markdown/html), confianza por palabra opcional y, si se activa, anotación JSON
con campos del albarán según un esquema fijo. No da cajas por palabra. Sin SDK: urllib inyectable."""

import base64
import json
import re
import time
from collections.abc import Callable
from html.parser import HTMLParser

from idm.documental.base import DocumentoEntrada, ErrorPermanente, ProveedorExternoBase
from idm.documental.costes import Tarifas, estimar
from idm.documental.http import ClienteHTTP, ClienteUrllib
from idm.documental.modelo import (
    CampoExtraido,
    Celda,
    LineaExtraida,
    MetadatosMotor,
    Pagina,
    Palabra,
    ResultadoDocumental,
    Tabla,
)
from idm.documental.privacidad import PoliticaEnvioExterno
from idm.documental.reintentos import llamar, request_id

ENDPOINT = "https://api.mistral.ai/v1/ocr"
MODELO_POR_DEFECTO = "mistral-ocr-latest"

# Esquema neutro de campos de un albarán/factura para la anotación de documento (opcional, coste aparte).
ESQUEMA_ANOTACION = {
    "type": "object",
    "properties": {
        "numero": {"type": ["string", "null"], "description": "Número del albarán o factura tal como está impreso"},
        "fecha": {"type": ["string", "null"], "description": "Fecha del documento, formato dd/mm/aaaa"},
        "cif": {"type": ["string", "null"], "description": "CIF/NIF del emisor (no el del cliente)"},
        "proveedor": {"type": ["string", "null"], "description": "Razón social del emisor"},
        "nuestro_pedido": {"type": ["string", "null"], "description": "Número de pedido del cliente si aparece"},
        "lineas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "codigo_proveedor": {"type": ["string", "null"]},
                    "descripcion": {"type": ["string", "null"]},
                    "cantidad": {"type": ["string", "null"]},
                    "precio_bruto": {"type": ["string", "null"]},
                    "descuento_pct": {"type": ["string", "null"]},
                    "importe": {"type": ["string", "null"]},
                },
            },
        },
    },
}

# Parámetros que mejoran la lectura pero no son imprescindibles: si el modelo los rechaza, se reintenta sin ellos
OPCIONALES = ("confidence_scores_granularity", "table_format")

RE_MARCADOR_TABLA = re.compile(r"\[(tbl-\d+\.(?:md|html))\]\([^)]*\)")


def tablas_markdown(texto: str) -> list[list[list[str]]]:
    """Tablas markdown ('| a | b |' + separador '|---|') → filas de celdas. Tolera tablas sin barras exteriores."""
    tablas: list[list[list[str]]] = []
    actual: list[list[str]] = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.count("|") >= 2:
            celdas = [c.strip() for c in limpia.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in celdas if c):
                continue  # separador de cabecera
            actual.append(celdas)
        elif actual:
            tablas.append(actual)
            actual = []
    if actual:
        tablas.append(actual)
    return [t for t in tablas if len(t) >= 2]


class _TablaHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.filas: list[list[str]] = []
        self._fila: list[str] | None = None
        self._celda: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._fila is not None and self._celda is not None:
            self._fila.append(" ".join("".join(self._celda).split()))
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            self.filas.append(self._fila)
            self._fila = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def tabla_html(texto: str) -> list[list[str]]:
    p = _TablaHTML()
    p.feed(texto)
    return p.filas


def _a_tabla(filas: list[list[str]], pagina: int) -> Tabla:
    columnas = max((len(f) for f in filas), default=0)
    celdas = [
        Celda(fila=i, columna=j, texto=valor, cabecera=i == 0)
        for i, fila in enumerate(filas)
        for j, valor in enumerate(fila)
    ]
    return Tabla(filas=len(filas), columnas=columnas, celdas=celdas, pagina=pagina)


def convertir(respuesta: dict, metadatos: MetadatosMotor) -> ResultadoDocumental:
    """Respuesta de /v1/ocr → ResultadoDocumental. Función pura (los tests la usan con respuestas grabadas)."""
    paginas, tablas, textos = [], [], []
    for p in respuesta.get("pages", []):
        numero = int(p.get("index", 0)) + 1
        markdown = p.get("markdown", "") or ""
        separadas = p.get("tables") or []
        for t in separadas:
            contenido = t.get("content", "") or ""
            filas = tabla_html(contenido) if t.get("format") == "html" else (tablas_markdown(contenido) or [[]])[0]
            if filas:
                tablas.append(_a_tabla(filas, numero))
        if not separadas:  # tablas en línea dentro del markdown (table_format nulo)
            tablas += [_a_tabla(f, numero) for f in tablas_markdown(markdown)]
        textos.append(RE_MARCADOR_TABLA.sub("", markdown))
        confianzas = (p.get("confidence_scores") or {}).get("word_confidence_scores") or []
        dimensiones = p.get("dimensions") or {}
        paginas.append(
            Pagina(
                numero=numero,
                ancho=dimensiones.get("width"),
                alto=dimensiones.get("height"),
                unidad="px",
                palabras=[
                    Palabra(texto=str(w.get("text", "")).strip(), confianza=w.get("confidence"))
                    for w in confianzas
                    if str(w.get("text", "")).strip()
                ],
            )
        )
    campos: dict[str, CampoExtraido] = {}
    lineas: list[LineaExtraida] = []
    anotacion = respuesta.get("document_annotation")
    if anotacion:
        datos = json.loads(anotacion) if isinstance(anotacion, str) else anotacion
        for nombre in ("numero", "fecha", "cif", "proveedor", "nuestro_pedido"):
            if datos.get(nombre):
                campos[nombre] = CampoExtraido(nombre=nombre, valor=str(datos[nombre]))
        for li in datos.get("lineas") or []:
            lineas.append(
                LineaExtraida(campos={k: CampoExtraido(nombre=k, valor=str(v)) for k, v in li.items() if v is not None})
            )
    uso = respuesta.get("usage_info") or {}
    metadatos.paginas_procesadas = int(uso.get("pages_processed") or len(paginas))
    metadatos.modelo = respuesta.get("model") or metadatos.modelo
    return ResultadoDocumental(
        texto="\n".join(textos), paginas=paginas, tablas=tablas, campos=campos, lineas=lineas, metadatos=metadatos
    )


class MistralDocumentAIProvider(ProveedorExternoBase):
    nombre = "mistral"

    def __init__(
        self,
        clave: str,
        politica: PoliticaEnvioExterno,
        modelo: str = MODELO_POR_DEFECTO,
        endpoint: str = ENDPOINT,
        anotacion: bool = False,
        confianza: str = "word",
        formato_tablas: str = "markdown",
        http: ClienteHTTP | None = None,
        esperar: Callable[[float], None] = time.sleep,
        intentos: int = 3,
        timeout_s: float = 120.0,
        tarifas: Tarifas | None = None,
        max_bytes: int = 50_000_000,
    ) -> None:
        super().__init__(politica)
        self.max_bytes = max_bytes  # límite documentado de Mistral OCR: 50 MB
        if not clave:
            raise ErrorPermanente("Falta MISTRAL_API_KEY")
        self.__clave = clave  # nunca se registra ni se incluye en errores
        self.modelo = modelo
        self._endpoint = endpoint
        self.anotacion = anotacion
        self.confianza = confianza if confianza in ("word", "page") else None
        self.formato_tablas = formato_tablas if formato_tablas in ("markdown", "html") else None
        self._http = http or ClienteUrllib()
        self._esperar = esperar
        self._intentos = intentos
        self._timeout_s = timeout_s
        self._tarifas = tarifas

    def __repr__(self) -> str:
        return f"MistralDocumentAIProvider(modelo={self.modelo!r}, anotacion={self.anotacion})"

    def disponible(self) -> bool:
        return bool(self.__clave)

    def _enviar(self, cabeceras: dict, cuerpo: dict):
        return llamar(
            self._http,
            "POST",
            self._endpoint,
            cabeceras,
            json.dumps(cuerpo).encode(),
            self._timeout_s,
            self._intentos,
            self._esperar,
            esperados=(200,),
        )

    def cuerpo(self, documento: DocumentoEntrada) -> dict:
        datos = base64.b64encode(documento.contenido).decode("ascii")
        uri = f"data:{documento.tipo_mime};base64,{datos}"
        if documento.tipo_mime.startswith("image/"):
            fuente = {"type": "image_url", "image_url": uri}
        else:
            fuente = {"type": "document_url", "document_url": uri}
        cuerpo: dict = {"model": self.modelo, "document": fuente, "include_image_base64": False}
        if self.formato_tablas:
            cuerpo["table_format"] = self.formato_tablas
        if self.confianza:
            cuerpo["confidence_scores_granularity"] = self.confianza
        if self.anotacion:
            cuerpo["document_annotation_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "documento_compra", "schema": ESQUEMA_ANOTACION, "strict": False},
            }
        return cuerpo

    def _analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental:
        cabeceras = {"Authorization": f"Bearer {self.__clave}", "Content-Type": "application/json"}
        avisos: list[str] = []
        cuerpo = self.cuerpo(documento)
        try:
            r = self._enviar(cabeceras, cuerpo)
        except ErrorPermanente as exc:
            opcionales = [k for k in OPCIONALES if k in cuerpo and k in str(exc)]
            if exc.estado_http not in (400, 422) or not opcionales:
                raise
            # El modelo no admite un parámetro opcional: se repite una vez sin él y se deja anotado
            for k in opcionales:
                cuerpo.pop(k)
            avisos.append(f"Mistral no admitió {', '.join(opcionales)} con {self.modelo}: leído sin ello")
            r = self._enviar(cabeceras, cuerpo)
        metadatos = MetadatosMotor(proveedor=self.nombre, modelo=self.modelo, externo=True, request_id=request_id(r))
        resultado = convertir(r.json(), metadatos)
        resultado.avisos += avisos
        if self._tarifas:
            extras = ("document_annotation",) if self.anotacion else ()
            modelo_tarifa = self.modelo  # la tarifa se busca por el alias configurado (p. ej. mistral-ocr-latest)
            paginas = resultado.metadatos.paginas_procesadas or 1
            if coste := estimar(self._tarifas, self.nombre, modelo_tarifa, paginas, extras):
                resultado.metadatos.coste_estimado_usd, resultado.metadatos.coste_estimado_eur = coste.usd, coste.eur
        return resultado
