"""Interfaz LectorDocumentos: leer(ruta) -> DocumentoLeido. LectorTextoPDF (pdfplumber), LectorImagenOCR (motor OCR
local + preprocesado + mismo intérprete de texto) y LectorImagenNulo (REQUIERE_OCR). LectorAutomatico despacha.
Solo extrae lo que dice el documento; no normaliza números ni decide nada (eso es cotejo/)."""

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from PIL import Image

from idm.albaranes import plantillas as pl
from idm.albaranes.extraer import EXTENSIONES_EXCEL, Extraccion, es_excel, es_imagen, es_pdf, extraer, sha256_fichero
from idm.albaranes.imagenes import ImagenNoLegible, abrir
from idm.albaranes.ocr import MotorNulo, MotorOCR, MotorTesseract, ResultadoOCR
from idm.albaranes.preprocesado import TUBERIAS, preparar
from idm.dominio.dinero import CERO, a_decimal, redondear
from idm.dominio.estados import CodigoError, ResultadoLectura, TipoDocumento
from idm.dominio.modelos import DocumentoLeido, ErrorProcesamiento, LineaLeida
from idm.dominio.reglas import es_linea_portes
from idm.equivalencias.proveedores import identificar

RE_CIF = re.compile(r"\b([ABCDEFGHJKLMNPQRSUVW][\s.]?\d{8}|[ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]|\d{8}[A-Z])\b")
CONFIANZA_OCR_MINIMA = 60.0  # media de confianza de palabras por debajo de la cual el documento se marca para revisar


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
    """FACTURA solo si hay un rótulo (FACTURA Nº / FACTURA:); un albarán puede mencionar 'la factura' en el pie."""
    t = _sin_acentos(texto).upper()
    if re.search(r"\bFACTURA\s*(?:N[ºo°O.]|NUM|N[UÚ]MERO|:)", t):
        return TipoDocumento.FACTURA
    if re.search(r"\bALBARAN", t):
        return TipoDocumento.ALBARAN
    if re.search(r"^\s*FACTURA\b", t, re.MULTILINE):
        return TipoDocumento.FACTURA
    return TipoDocumento.DESCONOCIDO


RE_JUNK_BORDES = re.compile(r"^[\s|¦\[\]{}()<>\\/'\"`´¿?¡!*_:;,.\-—–=+~]+|[\s|¦\[\]{}()<>\\/'\"`´¿?¡!*_:;,\-—–=+~]+$")


def limpiar_texto_ocr(texto: str) -> str:
    """Quita barras de tabla y restos de bordes que el OCR pega al principio y al final de cada línea."""
    lineas = []
    for linea in texto.splitlines():
        limpia = RE_JUNK_BORDES.sub("", linea.replace("|", " ").replace("¦", " "))
        limpia = re.sub(r"[ \t]{2,}", " ", limpia).strip()
        if limpia:
            lineas.append(limpia)
    return "\n".join(lineas)


def _cif(texto: str, excluir: set[str]) -> str | None:
    for m in RE_CIF.finditer(texto.upper()):
        cif = re.sub(r"[\s.]", "", m.group(1))
        if cif not in excluir:
            return cif
    return None


# Un número de documento empieza por pocas letras y un dígito cerca ("AC B26 0100…", "F26/000731", "5526/2.063")
RE_FORMA_NUMERO = re.compile(r"^[A-Z]{0,4}[ .\-/]{0,2}[A-Z]?\d", re.IGNORECASE)


def _numero(texto: str, plantilla: pl.Plantilla, es_factura: bool = False) -> str | None:
    """Albarán: forma conocida del proveedor → etiqueta+valor en la misma línea → etiqueta y valor en las 2 líneas
    siguientes. Factura: la etiqueta primero (las formas del proveedor son de albarán y la factura los cita)."""
    etiquetado = _primero(plantilla.numero, texto, "numero")
    if es_factura and etiquetado and RE_FORMA_NUMERO.match(etiquetado):
        return etiquetado
    for patron in pl.compilar(plantilla.formas_numero):  # la forma conocida del proveedor manda
        if m := patron.search(texto):
            return m.group(0).strip()
    if etiquetado and RE_FORMA_NUMERO.match(etiquetado):
        return etiquetado
    etiqueta = re.compile(plantilla.etiqueta_numero, re.IGNORECASE)
    lineas = texto.splitlines()
    for i, linea in enumerate(lineas):
        if etiqueta.search(_sin_acentos(linea)):
            for siguiente in lineas[i + 1 : i + 3]:
                if (
                    m := re.search(r"([A-Z]{0,3}\s?[A-Z]?\d[\dA-Z ./\-]{3,})", siguiente.strip())
                ) and RE_FORMA_NUMERO.match(m.group(1)):
                    return m.group(1).strip()
    return None


RE_CODIGO_VALIDO = re.compile(r"^(?=.*[0-9])[A-Z0-9][A-Z0-9\-./]*$|^[A-Z]{4,}$")


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
    if codigo is not None and not RE_CODIGO_VALIDO.match(codigo):
        return None  # "etree", "Hadas": restos de OCR que no son una referencia (mayúsculas y/o dígitos)
    precio = a_decimal(valores.get("precio_bruto"))
    importe = a_decimal(valores.get("importe"))
    dto = a_decimal(valores.get("descuento_pct")) if precio is not None else None
    if importe is not None and precio is not None and "," not in str(valores.get("importe") or ""):
        # OCR que pierde la coma ("2,56" → "256"): se corrige solo si la aritmética de la línea lo confirma
        from idm.dominio.dinero import importe_linea

        esperado = importe_linea(cantidad, precio, dto or CERO)
        if esperado == importe / 100:
            importe = esperado
    return LineaLeida(
        codigo_proveedor=codigo,
        descripcion=descripcion,
        cantidad=cantidad,
        unidad=(valores.get("unidad") or "").strip().upper() or None,
        precio_bruto=precio,
        descuento_pct=dto,
        importe=importe,
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


def _es_ruido(linea: str, plantilla: pl.Plantilla) -> bool:
    t = _sin_acentos(linea).upper()
    return any(re.search(p, t) for p in plantilla.ruido)


def _lineas_desde_texto(texto: str, plantilla: pl.Plantilla) -> list[LineaLeida]:
    """Una línea por coincidencia; si el texto viene de varias pasadas de OCR, la misma línea se queda una sola vez."""
    lineas: list[LineaLeida] = []
    vistas: set[tuple] = set()
    patrones = pl.compilar(plantilla.linea_texto)
    for linea_texto in texto.splitlines():
        candidata = linea_texto.strip()
        if not candidata or _es_ruido(candidata, plantilla):
            continue
        for patron in patrones:
            if m := patron.match(candidata):
                if (linea := _linea_desde_valores(m.groupdict())) is not None:
                    # Varias pasadas de OCR leen la misma línea varias veces: la primera lectura de la referencia gana.
                    # Límite conocido: un albarán con la misma referencia en dos líneas se quedaría con una.
                    clave = linea.codigo_proveedor or (linea.descripcion, linea.cantidad, linea.precio_bruto)
                    if clave not in vistas and not _repetida(linea, lineas):
                        vistas.add(clave)
                        lineas.append(linea)
                break
    return lineas


def _lineas_por_partes(texto: str, plantilla: pl.Plantilla) -> list[LineaLeida]:
    """Filas de texto y filas numéricas por separado, emparejadas por orden. Solo si el layout lo declara y cuadran."""
    if plantilla.linea_partes is None:
        return []
    re_texto, re_numeros = (re.compile(p, re.IGNORECASE) for p in plantilla.linea_partes)
    textos: list[dict] = []
    numeros: list[dict] = []
    vistos_t: set[str] = set()
    vistos_n: set[str] = set()
    for linea in texto.splitlines():
        candidata = linea.strip()
        if not candidata or _es_ruido(candidata, plantilla):
            continue
        if (m := re_texto.match(candidata)) and m.group("codigo_proveedor") not in vistos_t:
            vistos_t.add(m.group("codigo_proveedor"))
            textos.append(m.groupdict())
        elif (m := re_numeros.match(candidata)) and candidata not in vistos_n:
            vistos_n.add(candidata)
            numeros.append(m.groupdict())
    if not textos or len(textos) != len(numeros):
        return []
    lineas = []
    for t, n in zip(textos, numeros, strict=True):
        if (linea := _linea_desde_valores({**t, **n})) is not None:
            lineas.append(linea)
    return lineas


def _repetida(nueva: LineaLeida, lineas: list[LineaLeida]) -> bool:
    """La misma línea leída dos veces (varias pasadas de OCR) con la descripción recortada: mismos números y una
    descripción contenida en la otra. Dos artículos distintos con los mismos números no se confunden: difieren."""
    for otra in lineas:
        mismos_numeros = (nueva.cantidad, nueva.precio_bruto, nueva.descuento_pct, nueva.importe) == (
            otra.cantidad,
            otra.precio_bruto,
            otra.descuento_pct,
            otra.importe,
        )
        a, b = nueva.descripcion.upper(), otra.descripcion.upper()
        if mismos_numeros and (a in b or b in a):
            return True
    return False


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


def interpretar_texto(
    ruta: Path,
    sha256: str,
    texto: str,
    tablas: list,
    cifs_propios: set[str],
    metodo: str,
    resultado: ResultadoLectura,
    texto_secundario: str = "",
) -> DocumentoLeido:
    """Núcleo compartido por PDF con texto y por OCR: del texto (y tablas si las hay) a DocumentoLeido.
    texto_secundario (filas geométricas del OCR) completa la cabecera y solo aporta líneas si el principal no da."""
    completo = texto + ("\n" + texto_secundario if texto_secundario else "")
    cif = _cif(completo, cifs_propios)
    primera_linea = texto.strip().split("\n", 1)[0].strip() if texto.strip() else None
    proveedor, _ = identificar(nombre=primera_linea, cif=cif)
    if proveedor is None:
        proveedor, _ = identificar(nombre=texto[:600])
    plantilla = pl.plantilla_para(proveedor)
    lineas = (
        _lineas_desde_tablas(tablas, plantilla)
        or _lineas_desde_texto(texto, plantilla)
        or _lineas_desde_texto(texto_secundario, plantilla)
        or _lineas_por_partes(completo, plantilla)  # último recurso: texto y números en filas separadas, por orden
    )
    tipo = _tipo(completo)
    numero = _numero(completo, plantilla, es_factura=tipo == TipoDocumento.FACTURA)
    if tipo == TipoDocumento.DESCONOCIDO and numero and plantilla.formas_numero:
        # El OCR ha perdido la palabra "Albarán" pero el número tiene la forma de albarán de este proveedor
        if any(re.fullmatch(f, numero, re.IGNORECASE) for f in plantilla.formas_numero):
            tipo = TipoDocumento.ALBARAN
    doc = DocumentoLeido(
        ruta=str(ruta),
        sha256=sha256,
        tipo=tipo,
        proveedor_texto=primera_linea,
        cif=cif,
        numero=numero,
        fecha=_fecha(_primero(plantilla.fecha, completo, "fecha")),
        nuestro_pedido=_primero(plantilla.nuestro_pedido, completo, "pedido"),
        lineas=lineas,
        base=a_decimal(_primero(plantilla.base, completo, "importe")),
        iva=a_decimal(_primero(plantilla.iva, completo, "importe")),
        total=a_decimal(_primero(plantilla.total, completo, "importe")),
        metodo=metodo,
        resultado=resultado,
        texto=texto,
    )
    if doc.tipo == TipoDocumento.FACTURA:
        doc.albaranes_referenciados = _albaranes_referenciados(completo, plantilla, lineas)
    if not lineas:
        doc.avisos.append("No se han reconocido líneas")
    doc.confianza = _confianza(doc)
    return doc


class LectorTextoPDF:
    """Lee PDF con capa de texto: tablas con rejilla primero, líneas por regex si no hay tablas."""

    def __init__(self, cifs_propios: set[str] | None = None) -> None:
        self.cifs_propios = {c.upper() for c in (cifs_propios or set())} | {"B99999999"}  # el del cliente ficticio

    def leer(self, ruta: Path, extraccion: Extraccion | None = None) -> DocumentoLeido:
        ex = extraccion or extraer(ruta)
        return interpretar_texto(
            ruta, sha256_fichero(ruta), ex.texto, ex.tablas, self.cifs_propios, "pdf_texto", ResultadoLectura.PDF_TEXTO
        )


class LectorImagenNulo:
    """Sin motor OCR: no lee nada y lo dice con REQUIERE_OCR. El documento queda en la bandeja para teclear."""

    def leer(self, ruta: Path) -> DocumentoLeido:
        mensaje = "Documento sin capa de texto: requiere lectura de imagen (OCR) o tecleo manual"
        return DocumentoLeido(
            ruta=str(ruta),
            sha256=sha256_fichero(ruta),
            metodo="imagen_nulo",
            resultado=ResultadoLectura.REQUIERE_OCR,
            confianza=0.0,
            avisos=[mensaje],
            errores=[ErrorProcesamiento(codigo=CodigoError.LECTURA_REQUIERE_OCR, mensaje=mensaje, recuperable=False)],
        )


class LectorImagenOCR:
    """imagen/HEIC → preprocesado → orientación (la de mayor confianza entre 0/90/180/270) → OCR en uno o varios modos
    de segmentación (psm) cuyos textos se unen → intérprete de texto (el mismo que el PDF). Todo local.
    Si el motor no está disponible se comporta como LectorImagenNulo. La confianza media del OCR va en avisos."""

    def __init__(
        self,
        motor: MotorOCR | None = None,
        pasos: tuple[str, ...] = TUBERIAS["recorte_3200"],
        cifs_propios: set[str] | None = None,
        orientar: bool = True,
        psms: tuple[int, ...] = (4, 6, 11),
        pasos_extra: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        self.motor = motor or MotorTesseract()
        self.pasos = pasos
        self.pasos_extra = pasos_extra  # otras tuberías cuyo texto se une al principal (cada una ve cosas distintas)
        self.cifs_propios = {c.upper() for c in (cifs_propios or set())} | {"B99999999"}
        self.orientar = orientar
        self.psms = psms
        self.ultimo: ResultadoOCR | None = None
        self.ultima_orientacion: int = 0

    def _mejor_orientacion(self, imagen: Image.Image) -> int:
        """Prueba las cuatro orientaciones en pequeño y se queda con la de mayor confianza media (el OSD falla)."""
        if not isinstance(self.motor, MotorTesseract):
            return 0
        pequena = imagen.copy()
        pequena.thumbnail((1400, 1400))
        motor = MotorTesseract(self.motor.ejecutable, self.motor.lang, psm=6, timeout_s=self.motor.timeout_s)
        mejor, mejor_puntos = 0, -1.0
        for grados in (0, 90, 180, 270):
            r = motor.reconocer(pequena.rotate(-grados, expand=True) if grados else pequena)
            puntos = r.puntuacion_orientacion() if r.disponible else -1.0
            if puntos > mejor_puntos:
                mejor, mejor_puntos = grados, puntos
        return mejor

    def _reconocer_varios(self, imagen: Image.Image) -> ResultadoOCR:
        """Une el texto de cada psm (cada modo ve cosas distintas: 4 respeta columnas, 6 lee bloques)."""
        resultados = []
        for psm in self.psms:
            motor = self.motor
            if isinstance(self.motor, MotorTesseract):
                motor = MotorTesseract(self.motor.ejecutable, self.motor.lang, psm=psm, timeout_s=self.motor.timeout_s)
            resultados.append(motor.reconocer(imagen))
            if not isinstance(self.motor, MotorTesseract):
                break
        fallidos = [r for r in resultados if not r.disponible]
        if len(fallidos) == len(resultados):
            return resultados[0]
        buenos = [r for r in resultados if r.disponible]
        palabras = [p for r in buenos for p in r.palabras]
        # Texto de Tesseract (bloques) y, aparte, filas reconstruidas por geometría (recuperan tablas partidas en
        # columnas, pero en layouts con columnas desalineadas pueden emparejar mal: por eso van como respaldo)
        return ResultadoOCR(
            texto="\n".join(r.texto for r in buenos),
            motor=buenos[0].motor,
            palabras=palabras,
            tiempo_s=round(sum(r.tiempo_s for r in buenos), 2),
            texto_filas="\n".join(r.texto_por_filas for r in buenos),
        )

    def leer(self, ruta: Path) -> DocumentoLeido:
        ruta = Path(ruta)
        if not self.motor.disponible():
            doc = LectorImagenNulo().leer(ruta)
            doc.avisos.append(f"Motor OCR '{self.motor.nombre}' no disponible")
            return doc
        try:
            imagen = abrir(ruta) if es_imagen(ruta) else _pdf_a_imagen(ruta)
        except ImagenNoLegible as exc:
            return _no_leido(ruta, ResultadoLectura.CORRUPTO, CodigoError.LECTURA_CORRUPTO, str(exc))
        original = imagen
        resultados: list[ResultadoOCR] = []
        for i, pasos in enumerate((self.pasos, *self.pasos_extra)):
            imagen = preparar(original, pasos)
            orientacion = self._mejor_orientacion(imagen) if self.orientar else 0
            if i == 0:
                self.ultima_orientacion = orientacion
            if orientacion:
                imagen = imagen.rotate(-orientacion, expand=True)
            resultados.append(self._reconocer_varios(imagen))
        buenos = [r for r in resultados if r.disponible]
        resultado = (
            ResultadoOCR(
                texto="\n".join(r.texto for r in buenos),
                motor=buenos[0].motor,
                palabras=[p for r in buenos for p in r.palabras],
                tiempo_s=round(sum(r.tiempo_s for r in buenos), 2),
                texto_filas="\n".join(r.texto_filas for r in buenos),
            )
            if buenos
            else resultados[0]
        )
        self.ultimo = resultado
        if not resultado.disponible:
            doc = LectorImagenNulo().leer(ruta)
            doc.avisos.append(f"OCR falló: {resultado.error}")
            return doc
        doc = interpretar_texto(
            ruta,
            sha256_fichero(ruta),
            limpiar_texto_ocr(resultado.texto),
            [],
            self.cifs_propios,
            f"ocr_{resultado.motor}",
            ResultadoLectura.IMAGEN_OCR,
            texto_secundario=limpiar_texto_ocr(resultado.texto_filas),
        )
        if self.ultima_orientacion:
            doc.avisos.append(f"Foto girada {self.ultima_orientacion}° para leerla")
        doc.avisos.insert(
            0,
            f"Leído por OCR ({resultado.motor}, confianza media {resultado.confianza_media} %): "
            "revisar los campos antes de aprobar",
        )
        doc.confianza = round(doc.confianza * min(resultado.confianza_media, 100.0) / 100.0, 2)
        if resultado.confianza_media < CONFIANZA_OCR_MINIMA:
            doc.avisos.append(f"Confianza OCR baja (< {CONFIANZA_OCR_MINIMA:.0f} %): posible foto borrosa o girada")
        return doc


def _pdf_a_imagen(ruta: Path) -> Image.Image:
    """Primera página de un PDF escaneado como imagen (pdfplumber/pypdfium2), para pasarla por OCR."""
    import pdfplumber

    with pdfplumber.open(str(ruta)) as pdf:
        return pdf.pages[0].to_image(resolution=200).original.convert("RGB")


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
    PDF con texto → LectorTextoPDF; PDF sin texto o imagen (jpg/png/tif/HEIC) → lector de imagen (OCR o nulo);
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
            try:
                abrir(ruta)  # valida que la imagen (incluido HEIC) se puede abrir antes de pasarla al lector
            except ImagenNoLegible as exc:
                return _no_leido(ruta, ResultadoLectura.CORRUPTO, CodigoError.LECTURA_CORRUPTO, str(exc))
            return self.imagen.leer(ruta)
        if es_pdf(ruta):
            return self._leer_pdf(ruta)
        return _no_leido(
            ruta,
            ResultadoLectura.NO_SOPORTADO,
            CodigoError.LECTURA_NO_SOPORTADA,
            f"Extensión no soportada: '{ruta.suffix}'. Se admiten PDF e imágenes (jpg, png, tif, heic)",
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


def tuberias_desde_texto(nombres: str) -> tuple[tuple[str, ...], ...]:
    """'contraste_3200,recorte_3200' → tuplas de pasos. Nombres desconocidos lanzan KeyError con la lista válida."""
    resultado = []
    for nombre in (n.strip().lower() for n in nombres.split(",") if n.strip()):
        if nombre not in TUBERIAS:
            raise KeyError(f"Tubería OCR desconocida '{nombre}'. Válidas: {', '.join(TUBERIAS)}")
        resultado.append(TUBERIAS[nombre])
    return tuple(resultado) or (TUBERIAS["contraste_3200"],)


def lector_por_defecto(
    cifs_propios: set[str] | None = None,
    motor_ocr: str = "ninguno",
    pasos: tuple[str, ...] = TUBERIAS["contraste_3200"],
    pasos_extra: tuple[tuple[str, ...], ...] = (TUBERIAS["recorte_3200"],),
) -> LectorAutomatico:
    """Despachador según configuración: motor 'tesseract' activa el OCR local; 'ninguno' deja REQUIERE_OCR."""
    if motor_ocr == "tesseract":
        imagen: LectorDocumentos = LectorImagenOCR(MotorTesseract(), pasos, cifs_propios, pasos_extra=pasos_extra)
    else:
        imagen = LectorImagenNulo()
    return LectorAutomatico(LectorTextoPDF(cifs_propios), imagen)


LECTOR_POR_DEFECTO = LectorAutomatico()


def leer(ruta: Path) -> DocumentoLeido:
    return LECTOR_POR_DEFECTO.leer(Path(ruta))


__all__ = [
    "LectorAutomatico",
    "LectorDocumentos",
    "LectorImagenNulo",
    "LectorImagenOCR",
    "LectorTextoPDF",
    "MotorNulo",
    "interpretar_texto",
    "lector_por_defecto",
    "leer",
]
