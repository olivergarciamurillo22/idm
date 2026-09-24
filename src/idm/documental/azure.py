"""AzureDocumentIntelligenceProvider: API REST oficial de Azure AI Document Intelligence v4 (api-version 2024-11-30).
Por defecto prebuilt-layout con features=keyValuePairs: texto, palabras con polígono y confianza, tablas y pares;
con un modelo prebuilt con campos (prebuilt-invoice) los traduce a CampoExtraido. Sin SDK: urllib inyectable."""

import base64
import json
import time
from collections.abc import Callable
from decimal import Decimal

from idm.documental.base import DocumentoEntrada, ErrorPermanente, ErrorTransitorio, ProveedorExternoBase
from idm.documental.costes import Tarifas, estimar
from idm.documental.http import ClienteHTTP, ClienteUrllib
from idm.documental.modelo import (
    Caja,
    CampoExtraido,
    Celda,
    LineaExtraida,
    LineaTexto,
    MetadatosMotor,
    Pagina,
    Palabra,
    ParClaveValor,
    ResultadoDocumental,
    Tabla,
)
from idm.documental.privacidad import PoliticaEnvioExterno
from idm.documental.reintentos import llamar, request_id

API_VERSION = "2024-11-30"
MODELO_POR_DEFECTO = "prebuilt-layout"

# Campos de modelos prebuilt (invoice) → nombres neutros de IDM. Solo se usan para completar huecos.
CAMPOS_CABECERA = {
    "InvoiceId": "numero",
    "InvoiceDate": "fecha",
    "VendorTaxId": "cif",
    "VendorName": "proveedor",
    "PurchaseOrder": "nuestro_pedido",
    "SubTotal": "base",
    "TotalTax": "iva",
    "InvoiceTotal": "total",
}
CAMPOS_LINEA = {
    "ProductCode": "codigo_proveedor",
    "Description": "descripcion",
    "Quantity": "cantidad",
    "UnitPrice": "precio_bruto",
    "Discount": "descuento_pct",
    "Amount": "importe",
}


def _valor_campo(campo: dict) -> str | None:
    """Valor de un campo v4 según su tipo (valueString, valueNumber, valueDate, valueCurrency…) o su texto."""
    for clave in ("valueString", "valueDate", "valueNumber", "valueInteger", "valuePhoneNumber"):
        if clave in campo and campo[clave] is not None:
            return str(campo[clave])
    if (moneda := campo.get("valueCurrency")) and moneda.get("amount") is not None:
        return str(moneda["amount"])
    return campo.get("content")


def _caja_de(regiones: list[dict] | None, unidades: dict[int, str]) -> Caja | None:
    if not regiones:
        return None
    r = regiones[0]
    pagina = int(r.get("pageNumber", 1))
    return Caja.desde_poligono(r.get("polygon"), pagina, unidades.get(pagina, "px"))


def convertir(analisis: dict, metadatos: MetadatosMotor) -> ResultadoDocumental:
    """analyzeResult de Azure v4 → ResultadoDocumental. Función pura (los tests la usan con respuestas grabadas)."""
    unidades = {int(p.get("pageNumber", i + 1)): p.get("unit", "px") for i, p in enumerate(analisis.get("pages", []))}
    paginas = []
    for i, p in enumerate(analisis.get("pages", [])):
        numero = int(p.get("pageNumber", i + 1))
        unidad = p.get("unit", "px")
        paginas.append(
            Pagina(
                numero=numero,
                ancho=p.get("width"),
                alto=p.get("height"),
                unidad=unidad,
                angulo=p.get("angle"),
                palabras=[
                    Palabra(
                        texto=w.get("content", ""),
                        confianza=w.get("confidence"),
                        caja=Caja.desde_poligono(w.get("polygon"), numero, unidad),
                    )
                    for w in p.get("words", [])
                ],
                lineas=[
                    LineaTexto(texto=ln.get("content", ""), caja=Caja.desde_poligono(ln.get("polygon"), numero, unidad))
                    for ln in p.get("lines", [])
                ],
            )
        )
    tablas = []
    for t in analisis.get("tables", []):
        caja_tabla = _caja_de(t.get("boundingRegions"), unidades)
        tablas.append(
            Tabla(
                filas=int(t.get("rowCount", 0)),
                columnas=int(t.get("columnCount", 0)),
                pagina=caja_tabla.pagina if caja_tabla else None,
                celdas=[
                    Celda(
                        fila=int(c.get("rowIndex", 0)),
                        columna=int(c.get("columnIndex", 0)),
                        texto=c.get("content", ""),
                        cabecera=c.get("kind") in ("columnHeader", "rowHeader", "stubHead"),
                        extension_filas=int(c.get("rowSpan", 1)),
                        extension_columnas=int(c.get("columnSpan", 1)),
                        caja=_caja_de(c.get("boundingRegions"), unidades),
                    )
                    for c in t.get("cells", [])
                ],
            )
        )
    pares = [
        ParClaveValor(
            clave=(kv.get("key") or {}).get("content", ""),
            valor=(kv.get("value") or {}).get("content"),
            confianza=kv.get("confidence"),
            caja=_caja_de((kv.get("value") or kv.get("key") or {}).get("boundingRegions"), unidades),
        )
        for kv in analisis.get("keyValuePairs", [])
    ]
    campos: dict[str, CampoExtraido] = {}
    lineas: list[LineaExtraida] = []
    for documento in analisis.get("documents", []):
        for nombre_azure, campo in (documento.get("fields") or {}).items():
            if nombre_azure in CAMPOS_CABECERA and campo:
                nombre = CAMPOS_CABECERA[nombre_azure]
                campos[nombre] = CampoExtraido(
                    nombre=nombre,
                    valor=_valor_campo(campo),
                    confianza=campo.get("confidence"),
                    caja=_caja_de(campo.get("boundingRegions"), unidades),
                )
        items = (documento.get("fields") or {}).get("Items") or {}
        for item in items.get("valueArray", []) or []:
            objeto = item.get("valueObject") or {}
            lineas.append(
                LineaExtraida(
                    campos={
                        CAMPOS_LINEA[k]: CampoExtraido(
                            nombre=CAMPOS_LINEA[k], valor=_valor_campo(v), confianza=v.get("confidence")
                        )
                        for k, v in objeto.items()
                        if k in CAMPOS_LINEA and v
                    }
                )
            )
    metadatos.paginas_procesadas = len(paginas) or metadatos.paginas_procesadas
    return ResultadoDocumental(
        texto=analisis.get("content", ""),
        paginas=paginas,
        tablas=tablas,
        pares=pares,
        campos=campos,
        lineas=lineas,
        metadatos=metadatos,
    )


class AzureDocumentIntelligenceProvider(ProveedorExternoBase):
    nombre = "azure"

    def __init__(
        self,
        endpoint: str,
        clave: str,
        politica: PoliticaEnvioExterno,
        modelo: str = MODELO_POR_DEFECTO,
        version_api: str = API_VERSION,
        caracteristicas: tuple[str, ...] = ("keyValuePairs",),
        http: ClienteHTTP | None = None,
        esperar: Callable[[float], None] = time.sleep,
        intentos: int = 3,
        timeout_s: float = 60.0,
        espera_max_s: float = 180.0,
        tarifas: Tarifas | None = None,
    ) -> None:
        super().__init__(politica)
        if not endpoint or not clave:
            raise ErrorPermanente("Faltan AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT y/o AZURE_DOCUMENT_INTELLIGENCE_KEY")
        self._endpoint = endpoint.rstrip("/")
        self.__clave = clave  # nunca se registra ni se incluye en errores
        self.modelo = modelo
        self.version_api = version_api
        self.caracteristicas = tuple(c for c in caracteristicas if c)
        self._http = http or ClienteUrllib()
        self._esperar = esperar
        self._intentos = intentos
        self._timeout_s = timeout_s
        self._espera_max_s = espera_max_s
        self._tarifas = tarifas

    def __repr__(self) -> str:
        return f"AzureDocumentIntelligenceProvider(endpoint={self._endpoint!r}, modelo={self.modelo!r})"

    def disponible(self) -> bool:
        return bool(self._endpoint and self.__clave)

    def url_analisis(self) -> str:
        url = (
            f"{self._endpoint}/documentintelligence/documentModels/{self.modelo}:analyze?api-version={self.version_api}"
        )
        if self.caracteristicas:
            url += "&features=" + ",".join(self.caracteristicas)
        return url

    def _analizar(self, documento: DocumentoEntrada) -> ResultadoDocumental:
        cabeceras = {"Ocp-Apim-Subscription-Key": self.__clave, "Content-Type": "application/json"}
        cuerpo = json.dumps({"base64Source": base64.b64encode(documento.contenido).decode("ascii")}).encode()
        respuesta = llamar(
            self._http,
            "POST",
            self.url_analisis(),
            cabeceras,
            cuerpo,
            self._timeout_s,
            self._intentos,
            self._esperar,
            esperados=(202,),
        )
        rid = request_id(respuesta)
        operacion = respuesta.cabecera("operation-location")
        if not operacion:
            raise ErrorPermanente("Azure no devolvió Operation-Location", rid, respuesta.status)
        resultado = self._sondear(operacion, rid)
        metadatos = MetadatosMotor(
            proveedor=self.nombre, modelo=self.modelo, externo=True, version_api=self.version_api, request_id=rid
        )
        convertido = convertir(resultado.get("analyzeResult") or {}, metadatos)
        if self._tarifas:
            extras = tuple(self.caracteristicas)
            if coste := estimar(
                self._tarifas, self.nombre, self.modelo, convertido.metadatos.paginas_procesadas or 1, extras
            ):
                convertido.metadatos.coste_estimado_usd, convertido.metadatos.coste_estimado_eur = coste.usd, coste.eur
        return convertido

    def _sondear(self, operacion: str, rid: str | None) -> dict:
        cabeceras = {"Ocp-Apim-Subscription-Key": self.__clave}
        esperado = 0.0
        while True:
            r = llamar(
                self._http,
                "GET",
                operacion,
                cabeceras,
                None,
                self._timeout_s,
                self._intentos,
                self._esperar,
                esperados=(200,),
            )
            datos = r.json()
            estado = str(datos.get("status", "")).lower()
            if estado == "succeeded":
                return datos
            if estado == "failed":
                error = datos.get("error") or {}
                raise ErrorPermanente(f"Azure: análisis fallido ({error.get('code')}: {error.get('message')})", rid)
            pausa = Decimal(r.cabecera("retry-after") or "1")
            pausa_s = float(min(max(pausa, Decimal("0.5")), Decimal(10)))
            if esperado + pausa_s > self._espera_max_s:
                raise ErrorTransitorio(f"Azure no terminó en {self._espera_max_s:.0f} s (estado {estado})", rid)
            self._esperar(pausa_s)
            esperado += pausa_s
