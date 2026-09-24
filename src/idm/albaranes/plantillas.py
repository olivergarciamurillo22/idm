"""Plantillas de lectura por proveedor: formas del número de albarán, etiquetas (en la misma línea o en la siguiente),
cabeceras de tabla, regex de línea según el orden de columnas del proveedor y ruido de pie a descartar.
Las plantillas describen LAYOUT (orden de columnas, forma del número), nunca datos de negocio ni de clientes."""

import re
from dataclasses import dataclass, field

# Cabeceras de tabla (normalizadas: minúsculas sin acentos) → campo de LineaLeida
CABECERAS_GENERICAS: dict[str, tuple[str, ...]] = {
    "albaran": ("albaran", "n albaran", "num albaran", "nº albaran"),
    "codigo_proveedor": ("referencia", "ref", "ref.", "codigo", "articulo", "cod", "cod.", "codigo articulo"),
    "descripcion": ("descripcion", "concepto", "denominacion", "articulo descripcion", "detalle"),
    "cantidad": ("cantidad", "cant", "cant.", "uds", "uds.", "unidades", "cantidad servida"),
    "unidad": ("ud", "ud.", "unidad", "u.m.", "um", "medida"),
    "precio_bruto": ("precio", "p. unit", "p.unit", "precio unitario", "pvp", "p/u", "precio ud", "precio u."),
    "descuento_pct": ("dto", "dto %", "dto%", "% dto", "descuento", "desc", "desc.", "dto.", "% descuentos"),
    "importe": ("importe", "total", "total linea", "neto", "importe neto", "imp. linea", "precio total"),
}

NUM = r"\d{1,3}(?:\.\d{3})*,\d+|\d+,\d+|\d+"  # 1.234,56 · 9,14 · 100
ETIQUETA_NUMERO = (
    r"(?:TIPO\s*/\s*SERIE\s*/\s*)?N[ºo°.]?\s*ALBAR[AÁ]N(?:ES)?(?:\s+SALIDA)?|ALBAR[AÁ]N\s*N[ºo°.]?|FACTURA\s*N[ºo°.]?"
)


@dataclass(frozen=True)
class Plantilla:
    clave: str
    # 1) Etiqueta y valor en la misma línea: "ALBARÁN Nº: AC B26 0100005283"
    numero: tuple[str, ...] = (
        r"(?:ALBAR[AÁ]N|FACTURA|ALBARAN)\s*(?:N[ºo°.]*|NUM\.?|N[ÚU]MERO)?\s*:?\s*"
        r"(?P<numero>[A-Z0-9][A-Z0-9 ./\-]{2,}?)\s*$",
    )
    # 2) Formas del número buscadas en todo el texto (útil con OCR, donde la etiqueta y el valor se separan)
    formas_numero: tuple[str, ...] = ()
    # 3) Etiqueta en una línea y valor en una de las 2 siguientes (recuadros de cabecera de muchos albaranes)
    etiqueta_numero: str = ETIQUETA_NUMERO
    fecha: tuple[str, ...] = (
        r"FECHA[^\d\n]{0,20}(?P<fecha>\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
        r"(?<![\d/])(?P<fecha>\d{2}/\d{2}/\d{4})(?![\d/])",  # primera fecha completa del documento
    )
    nuestro_pedido: tuple[str, ...] = (
        r"(?:SU PEDIDO|S/PEDIDO|S\.PEDIDO|PEDIDO CLIENTE|VUESTRO PEDIDO|N/PEDIDO|SU REF\.? PEDIDO"
        r"|S/REFERENCIA|SU DOC\.?)"
        r"\s*:?\s*(?P<pedido>\d{6,})",
    )
    albaranes_referenciados: tuple[str, ...] = (r"ALBARANES?\s*:?\s*(?P<lista>[A-Z0-9][A-Z0-9 ./,\-]+)",)
    base: tuple[str, ...] = (r"B(?:ASE)?\.?\s*(?:IMPONIBLE)?\s*:?\s*(?P<importe>[\d.]+,\d{2})",)
    iva: tuple[str, ...] = (r"(?:IMPORTE\s+)?IVA[^\n:]*:?\s*(?P<importe>[\d.]+,\d{2})",)
    total: tuple[str, ...] = (r"(?:IMPORTE\s+)?TOTAL(?: FACTURA| ALBAR[AÁ]N)?\s*:?\s*(?P<importe>[\d.]+,\d{2})",)
    cabeceras: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(CABECERAS_GENERICAS))
    # Regex por línea de texto (sin tabla con rejilla). Grupos con nombre como LineaLeida. Se prueban en orden.
    linea_texto: tuple[str, ...] = (
        r"^(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{2,})\s+(?P<descripcion>.+?)\s+(?P<cantidad>" + NUM + r")\s+"
        r"(?P<unidad>UD|UDS|M|ML|KG|L|LT|PZ|CAJA|ROLLO|BOLSA)\s+(?P<precio_bruto>" + NUM + r")\s+"
        r"(?P<descuento_pct>" + NUM + r")\s+(?P<importe>[\d.]+,\d{2})\s*$",
        r"^(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{2,})\s+(?P<descripcion>.+?)\s+(?P<cantidad>" + NUM + r")\s+"
        r"(?P<unidad>UD|UDS|M|ML|KG|L|LT|PZ|CAJA|ROLLO|BOLSA)\s*$",
    )
    # Layouts donde el OCR separa el bloque de texto del numérico (o van desalineados en el papel): dos regex, una para
    # la parte de texto (familia/referencia/descripción) y otra para la numérica; se emparejan por orden de aparición.
    linea_partes: tuple[str, str] | None = None
    # Líneas del texto que son ruido (pies legales, horarios, listas de familias) y no deben parecer líneas de artículo
    ruido: tuple[str, ...] = (
        r"^\s*-\[",
        r"\bHORARIO\b",
        r"\bPREPARADO POR\b",
        r"\bSIN ASIGNAR\b",
        r"\bFIRMA(?:DO)?\b",
        r"\bFORMA DE PAGO\b",
        r"\bAVISO LEGAL\b",
        r"\bP[AÁ]G\.?:?\s*\d",
        r"\bCOPIA\b",
        r"\bCIF\b",
        r"\bN\.?I\.?F\b",
        r"\bTEL[EÉ]?F?\b\.?:?",
        r"\bTLF\b",
        r"@",
        r"\bWWW\.",
        r"^\s*(?:C/|AV\.?|AVDA\b)",
    )


GENERICA = Plantilla("GENERICA")

# ------------------------------------------------ layouts observados en documentos reales (solo estructura, sin datos)

# Layout A: recuadros "Tipo / Serie / Nº Albarán" con el valor en la línea siguiente; número "XX Y00 0000000000";
# columnas Familia | Referencia | Denominación | Precio | %Dto (hasta 3) | Cantidad | Imp. Línea; "Pedido" propio = 0.
LAYOUT_A = Plantilla(
    "LAYOUT_A",
    formas_numero=(r"\b[A-Z]{2}\s?[A-Z]\d{2}\s?\d{10}\b", r"\b[A-Z]\d{2}\s?\d{10}\b"),
    linea_partes=(
        r"^(?P<familia>[A-Z]{2,8})\s+(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{2,})\s+(?P<descripcion>[^\d,]{3,}?)\s*$",
        r"^(?P<precio_bruto>" + NUM + r")\s+(?P<descuento_pct>\d{1,2})(?:\s+[0-9O]{1,2}){0,2}\s+"
        r"(?P<cantidad>\d+,\d{2})\s+(?P<importe>[\d.]+,\d{2})\s*$",
    ),
    linea_texto=(
        r"^(?P<familia>[A-Z]{2,8})\s+(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{2,})\s+(?P<descripcion>.+?)\s+"
        r"(?P<precio_bruto>" + NUM + r")\s+(?P<descuento_pct>\d{1,2})(?:\s+\d{1,2}){0,2}\s+"
        r"(?P<cantidad>" + NUM + r")\s+(?P<importe>[\d.]+,\d{2}|\d{3,})(?:\s+\S{1,4}){0,6}\s*$",
        r"^(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{2,})\s+(?P<descripcion>.+?)\s+"
        r"(?P<precio_bruto>" + NUM + r")\s+(?P<descuento_pct>\d{1,2})(?:\s+\d{1,2}){0,2}\s+"
        r"(?P<cantidad>" + NUM + r")\s+(?P<importe>[\d.]+,\d{2}|\d{3,})(?:\s+\S{1,4}){0,6}\s*$",
    ),
)

# Layout B: cabecera de tabla "ALBARAN Nº" con el valor debajo, número con punto de millar "20.0xxxxx";
# columnas REFERENCIA | DESCRIPCION | CANTIDAD | PRECIO (4 decimales) | DTO. | IMPORTE; pie con PORTES y CANON.
LAYOUT_B = Plantilla(
    "LAYOUT_B",
    formas_numero=(r"\b\d{2}\.\d{6}\b",),
    linea_texto=(
        r"^(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{3,})\s+(?P<descripcion>.+?)\s+(?P<cantidad>" + NUM + r")\s+"
        r"(?P<precio_bruto>\d+,\d{2,4})\s+(?P<descuento_pct>"
        + NUM
        + r")\s+(?P<importe>[\d.]+,\d{2}|\d{3,})(?:\s+\S{1,4}){0,6}\s*$",
    ),
)

# Layout C: tabla "Fecha | Nº Albaranes Salida | SU DOC. | Nº PÁGINA" con valores debajo, número "5526/2.063";
# columnas CÓDIGO | CONCEPTO | UDS. | PRECIO U. | DTO | PRECIO TOTAL, a menudo SIN precio.
LAYOUT_C = Plantilla(
    "LAYOUT_C",
    formas_numero=(r"\b\d{4}/\d{1,2}\.\d{3}\b", r"\b\d{4}/\d{1,5}\b"),
    linea_texto=(
        r"^(?P<codigo_proveedor>[A-Z]{2}\d{5,}|[A-Z0-9][A-Z0-9\-./]{3,})\s+(?P<descripcion>.+?)\s+(?P<cantidad>\d+,\d{2})"
        r"(?:\s+(?P<precio_bruto>"
        + NUM
        + r")\s+(?P<descuento_pct>"
        + NUM
        + r")\s+(?P<importe>[\d.]+,\d{2}))?(?:\s+\S{1,4}){0,6}\s*$",
    ),
)

# Qué layout usa cada proveedor conocido (clave del registro de proveedores). Los reales se asignan por observación.
PLANTILLAS: dict[str, Plantilla] = {
    "LA_CEPA": LAYOUT_A,
    "MEYRAS": LAYOUT_B,
    "RECACOR": LAYOUT_C,
    "FICT_VEGA": LAYOUT_A,  # fixtures ficticios que imitan cada layout
    "FICT_RECAMBIOS": LAYOUT_C,
    "CRUZ": GENERICA,
    "BONDIOLI": GENERICA,
    "JUCAMP": GENERICA,
}


def plantilla_para(proveedor: str | None) -> Plantilla:
    return PLANTILLAS.get(proveedor or "", GENERICA)


def compilar(patrones: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patrones]
