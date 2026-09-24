"""Interfaz LectorDocumentos: leer(ruta) -> DocumentoLeido; LectorTextoPDF (pdfplumber + plantillas) y LectorImagenNulo.
leer(ruta) despacha: PDF con más de 80 caracteres → texto; si no (escaneo o foto) → lector de imagen.
Solo extrae lo que dice el documento; no normaliza números ni decide nada (eso es cotejo/)."""

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from idm.albaranes import plantillas as pl
from idm.albaranes.extraer import EXTENSIONES_EXCEL, Extraccion, es_excel, es_imagen, es_pdf, extraer, sha256_fichero
from idm.dominio.dinero import CERO, a_decimal, redondear
from idm.dominio.estados import CodigoError, ResultadoLectura, TipoDocumento
from idm.dominio.modelos import DocumentoLeido, ErrorProcesamiento, LineaLeida
from idm.dominio.reglas import es_linea_portes
from idm.equivalencias.proveedores import identificar

RE_CIF = re.compile(r"\b([ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]|\d{8}[A-Z])\b")


class LectorDocumentos(Protocol):
    def leer(self, ruta: Path) -> DocumentoLeido: ...


def _sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def _primero(patrones: tuple[str, ...], texto: str, grupo: str) -> str | None:
    for patron in pl.compilar(patrones):
        if m := patron.search(texto):
            return m.group(grupo).strip()
    return None


def _fecha(texto: str | None) -> date | None:
    if not texto:
        return None
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _tipo(texto: str) -> TipoDocumento:
    t = _sin_acentos(texto).upper()
    if re.search(r"\bFACTURA\s*(N|NUM|Nº|N°|:)", t):
        return TipoDocumento.FACTURA
    if re.search(r"\bALBARAN", t):
        return TipoDocumento.ALBARAN
    if "FACTURA" in t:
        return TipoDocumento.FACTURA
    return TipoDocumento.DESCONOCIDO


def _cif(texto: str, excluir: set[str]) -> str | None:
    for m in RE_CIF.finditer(texto.upper()):
        if m.group(1) not in excluir:
            return m.group(1)
    return None


def _mapear_cabeceras(fila: list[str | None], cabeceras: dict[str, tuple[str, ...]]) -> dict[str, int] | None:
    normalizadas = [" ".join(_sin_acentos(str(c or "")).lower().split()) for c in fila]
    indices: dict[str, int] = {}
    for campo, nombres in cabeceras.items():
        for i, cab in enumerate(normalizadas):
            if cab in nombres and i not in indices.values():
                indices[campo] = i
                break
    return indices if "descripcion" in indices and "cantidad" in indices else None


def _linea_desde_valores(valores: dict[str, str | None]) -> LineaLeida | None:
    descripcion = (valores.get("descripcion") or "").strip()
    cantidad = a_decimal(valores.get("cantidad"))
    if not descripcion or cantidad is None:
        return None
    codigo = (valores.get("codigo_proveedor") or "").strip() or None
    precio = a_decimal(valores.get("precio_bruto"))
    return LineaLeida(
        codigo_proveedor=codigo,
        descripcion=descripcion,
        cantidad=cantidad,
        unidad=(valores.get("unidad") or "").strip().upper() or None,
        precio_bruto=precio,
        descuento_pct=a_decimal(valores.get("descuento_pct")) if precio is not None else None,
        importe=a_decimal(valores.get("importe")),
        albaran=(valores.get("albaran") or "").strip() or None,
        es_portes=es_linea_portes(descripcion) and not codigo,
    )


def _lineas_desde_tablas(tablas, plantilla: pl.Plantilla) -> list[LineaLeida]:
    lineas: list[LineaLeida] = []
    for tabla in tablas:
        indices = _mapear_cabeceras(tabla[0], plantilla.cabeceras)
        if indices is None:
            continue
        for fila in tabla[1:]:
            valores = {campo: (fila[i] if i < len(fila) else None) for campo, i in indices.items()}
            if (linea := _linea_desde_valores(valores)) is not None:
                lineas.append(linea)
    return lineas


def _lineas_desde_texto(texto: str, plantilla: pl.Plantilla) -> list[LineaLeida]:
    lineas: list[LineaLeida] = []
    patrones = pl.compilar(plantilla.linea_texto)
    for linea_texto in texto.splitlines():
        for patron in patrones:
            if m := patron.match(linea_texto.strip()):
                if (linea := _linea_desde_valores(m.groupdict())) is not None:
                    lineas.append(linea)
                break
    return lineas


def _albaranes_referenciados(texto: str, plantilla: pl.Plantilla, lineas: list[LineaLeida]) -> list[str]:
    referencias: list[str] = []
    if lista := _primero(plantilla.albaranes_referenciados, texto, "lista"):
        referencias += [t.strip() for t in lista.split(",") if t.strip()]
    for li in lineas:
        if li.albaran and li.albaran not in referencias:
            referencias.append(li.albaran)
    return referencias


def _confianza(doc: DocumentoLeido) -> float:
    puntos = [
        doc.tipo != TipoDocumento.DESCONOCIDO,
        bool(doc.numero),
        bool(doc.fecha),
        bool(doc.lineas),
        doc.cif is not None or doc.proveedor_texto is not None,
    ]
    base = sum(puntos) / len(puntos)
    if doc.lineas and doc.base is not None:
        suma = redondear(sum((li.importe or CERO for li in doc.lineas), CERO))
        if suma != redondear(doc.base):
            doc.avisos.append(f"La suma de líneas ({suma}) no cuadra con la base ({doc.base})")
            return round(base * 0.8, 2)
    return round(base, 2)


class LectorTextoPDF:
    """Lee PDF con capa de texto: tablas con rejilla primero, líneas por regex si no hay tablas."""

    def __init__(self, cifs_propios: set[str] | None = None) -> None:
        self.cifs_propios = {c.upper() for c in (cifs_propios or set())} | {"B99999999"}  # el del cliente ficticio

    def leer(self, ruta: Path, extraccion: Extraccion | None = None) -> DocumentoLeido:
        ex = extraccion or extraer(ruta)
        texto = ex.texto
        cif = _cif(texto, self.cifs_propios)
        proveedor, _ = identificar(nombre=texto.split("\n", 1)[0] if texto else None, cif=cif)
        if proveedor is None:
            proveedor, _ = identificar(nombre=texto[:400])
        plantilla = pl.plantilla_para(proveedor)
        lineas = _lineas_desde_tablas(ex.tablas, plantilla) or _lineas_desde_texto(texto, plantilla)
        doc = DocumentoLeido(
            ruta=str(ruta),
            sha256=sha256_fichero(ruta),
            tipo=_tipo(texto),
            proveedor_texto=texto.strip().split("\n", 1)[0].strip() if texto.strip() else None,
            cif=cif,
            numero=_primero(plantilla.numero, texto, "numero"),
            fecha=_fecha(_primero(plantilla.fecha, texto, "fecha")),
            nuestro_pedido=_primero(plantilla.nuestro_pedido, texto, "pedido"),
            lineas=lineas,
            base=a_decimal(_primero(plantilla.base, texto, "importe")),
            iva=a_decimal(_primero(plantilla.iva, texto, "importe")),
            total=a_decimal(_primero(plantilla.total, texto, "importe")),
            metodo="pdf_texto",
            resultado=ResultadoLectura.PDF_TEXTO,
            texto=texto,
        )
        if doc.tipo == TipoDocumento.FACTURA:
            doc.albaranes_referenciados = _albaranes_referenciados(texto, plantilla, lineas)
        if not lineas:
            doc.avisos.append("No se han reconocido líneas")
        doc.confianza = _confianza(doc)
        return doc


class LectorImagenNulo:
    """Implementación mínima para escaneos y fotos: no lee nada y lo dice con REQUIERE_OCR. Detrás irá OCR local
    o un servicio externo según IDM decida si los documentos pueden salir de la empresa (DECISIONES.md)."""

    def leer(self, ruta: Path) -> DocumentoLeido:
        mensaje = "Documento sin capa de texto: requiere lectura de imagen (OCR/modelo) o tecleo manual"
        return DocumentoLeido(
            ruta=str(ruta),
            sha256=sha256_fichero(ruta),
            metodo="imagen_nulo",
            resultado=ResultadoLectura.REQUIERE_OCR,
            confianza=0.0,
            avisos=[mensaje],
            errores=[ErrorProcesamiento(codigo=CodigoError.LECTURA_REQUIERE_OCR, mensaje=mensaje, recuperable=False)],
        )


def _no_leido(
    ruta: Path, resultado: ResultadoLectura, codigo: CodigoError, mensaje: str, sha256: str = ""
) -> DocumentoLeido:
    return DocumentoLeido(
        ruta=str(ruta),
        sha256=sha256 or _sha_seguro(ruta),
        metodo="no_leido",
        resultado=resultado,
        confianza=0.0,
        avisos=[mensaje],
        errores=[ErrorProcesamiento(codigo=codigo, mensaje=mensaje, recuperable=False)],
    )


def _sha_seguro(ruta: Path) -> str:
    try:
        return sha256_fichero(ruta)
    except OSError:
        return ""


class LectorAutomatico:
    """Despachador. Decide por extensión y contenido y devuelve SIEMPRE un ResultadoLectura explícito:
    PDF con texto → LectorTextoPDF; PDF sin texto o imagen → lector de imagen (REQUIERE_OCR);
    Excel → EXCEL; 0 bytes → VACIO; no se puede abrir → CORRUPTO; otra extensión → NO_SOPORTADO."""

    def __init__(self, texto: LectorTextoPDF | None = None, imagen: LectorDocumentos | None = None) -> None:
        self.texto = texto or LectorTextoPDF()
        self.imagen = imagen or LectorImagenNulo()

    def leer(self, ruta: Path) -> DocumentoLeido:
        ruta = Path(ruta)
        try:
            tamano = ruta.stat().st_size
        except OSError as exc:
            return _no_leido(
                ruta, ResultadoLectura.CORRUPTO, CodigoError.FICHERO_INACCESIBLE, f"No se puede acceder: {exc}"
            )
        if tamano == 0:
            return _no_leido(ruta, ResultadoLectura.VACIO, CodigoError.LECTURA_VACIO, "Fichero vacío (0 bytes)")
        if es_excel(ruta):
            return _no_leido(
                ruta,
                ResultadoLectura.EXCEL,
                CodigoError.LECTURA_EXCEL,
                f"Hoja de cálculo ({ruta.suffix}) en la entrada: no es un documento de proveedor. "
                f"Si es un export de Siddex va en datos/siddex/. Extensiones: {', '.join(sorted(EXTENSIONES_EXCEL))}",
            )
        if es_imagen(ruta):
            return self.imagen.leer(ruta)
        if es_pdf(ruta):
            return self._leer_pdf(ruta)
        return _no_leido(
            ruta,
            ResultadoLectura.NO_SOPORTADO,
            CodigoError.LECTURA_NO_SOPORTADA,
            f"Extensión no soportada: '{ruta.suffix}'. Se admiten PDF e imágenes (jpg, png, tif)",
        )

    def _leer_pdf(self, ruta: Path) -> DocumentoLeido:
        with ruta.open("rb") as f:
            cabecera = f.read(5)
        if not cabecera.startswith(b"%PDF"):
            return _no_leido(
                ruta,
                ResultadoLectura.CORRUPTO,
                CodigoError.LECTURA_CORRUPTO,
                "El fichero tiene extensión .pdf pero no empieza por %PDF (¿descarga incompleta o renombrado?)",
            )
        try:
            ex = extraer(ruta)
        except Exception as exc:  # noqa: BLE001 - pdfplumber/pdfminer lanzan tipos variados; se convierte en CORRUPTO
            return _no_leido(
                ruta,
                ResultadoLectura.CORRUPTO,
                CodigoError.LECTURA_CORRUPTO,
                f"No se puede abrir el PDF: {type(exc).__name__}: {str(exc)[:200]}",
            )
        if ex.paginas == 0:
            return _no_leido(ruta, ResultadoLectura.CORRUPTO, CodigoError.LECTURA_CORRUPTO, "PDF sin páginas")
        if ex.tiene_texto:
            return self.texto.leer(ruta, ex)
        return self.imagen.leer(ruta)


LECTOR_POR_DEFECTO = LectorAutomatico()


def leer(ruta: Path) -> DocumentoLeido:
    return LECTOR_POR_DEFECTO.leer(Path(ruta))
