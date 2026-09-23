"""Plantillas de lectura por proveedor: expresiones para número, fecha, pedido y cabeceras de la tabla de líneas.
Hay una plantilla GENERICA (vale para los PDF de fixtures) y una entrada por proveedor real a afinar con sus documentos.
No lee ficheros: solo describe dónde está cada cosa."""

import re
from dataclasses import dataclass, field

# Cabeceras de tabla (normalizadas: minúsculas sin acentos) → campo de LineaLeida
CABECERAS_GENERICAS: dict[str, tuple[str, ...]] = {
    "albaran": ("albaran", "n albaran", "num albaran", "nº albaran"),
    "codigo_proveedor": ("referencia", "ref", "ref.", "codigo", "articulo", "cod", "cod.", "codigo articulo"),
    "descripcion": ("descripcion", "concepto", "denominacion", "articulo descripcion", "detalle"),
    "cantidad": ("cantidad", "cant", "cant.", "uds", "unidades", "cantidad servida"),
    "unidad": ("ud", "ud.", "unidad", "u.m.", "um", "medida"),
    "precio_bruto": ("precio", "p. unit", "p.unit", "precio unitario", "pvp", "p/u", "precio ud"),
    "descuento_pct": ("dto", "dto %", "dto%", "% dto", "descuento", "desc", "desc.", "dto."),
    "importe": ("importe", "total", "total linea", "neto", "importe neto"),
}


@dataclass(frozen=True)
class Plantilla:
    clave: str
    numero: tuple[str, ...] = (
        r"(?:ALBAR[AÁ]N|FACTURA|ALBARAN)\s*(?:N[ºo°.]*|NUM\.?|N[ÚU]MERO)?\s*:?\s*"
        r"(?P<numero>[A-Z0-9][A-Z0-9 ./\-]{2,}?)\s*$",
    )
    fecha: tuple[str, ...] = (r"FECHA[^\d\n]{0,20}(?P<fecha>\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",)
    nuestro_pedido: tuple[str, ...] = (
        r"(?:SU PEDIDO|S/PEDIDO|S\.PEDIDO|PEDIDO CLIENTE|VUESTRO PEDIDO|N/PEDIDO|SU REF\.? PEDIDO)"
        r"\s*:?\s*(?P<pedido>\d{6,})",
    )
    albaranes_referenciados: tuple[str, ...] = (r"ALBARANES?\s*:?\s*(?P<lista>[A-Z0-9][A-Z0-9 ./,\-]+)",)
    base: tuple[str, ...] = (r"BASE(?: IMPONIBLE)?\s*:?\s*(?P<importe>[\d.]+,\d{2})",)
    iva: tuple[str, ...] = (r"IVA[^\n:]*:?\s*(?P<importe>[\d.]+,\d{2})",)
    total: tuple[str, ...] = (r"TOTAL(?: FACTURA| ALBAR[AÁ]N)?\s*:?\s*(?P<importe>[\d.]+,\d{2})",)
    cabeceras: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(CABECERAS_GENERICAS))
    # Líneas sin tabla con rejilla: regex sobre cada línea de texto (grupos con nombre como LineaLeida)
    linea_texto: tuple[str, ...] = (
        r"^(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{2,})\s+(?P<descripcion>.+?)\s+(?P<cantidad>\d+(?:[.,]\d+)?)\s+"
        r"(?P<unidad>UD|UDS|M|ML|KG|L|LT|PZ|CAJA|ROLLO|BOLSA)\s+(?P<precio_bruto>[\d.]+,\d+)\s+"
        r"(?P<descuento_pct>\d+(?:[.,]\d+)?)\s+(?P<importe>[\d.]+,\d{2})\s*$",
        r"^(?P<codigo_proveedor>[A-Z0-9][A-Z0-9\-./]{2,})\s+(?P<descripcion>.+?)\s+(?P<cantidad>\d+(?:[.,]\d+)?)\s+"
        r"(?P<unidad>UD|UDS|M|ML|KG|L|LT|PZ|CAJA|ROLLO|BOLSA)\s*$",
    )


GENERICA = Plantilla("GENERICA")

# Por proveedor real: heredan la genérica hasta que tengamos sus PDF y las afinemos (docs/reglas-proveedor/).
PLANTILLAS: dict[str, Plantilla] = {
    "LA_CEPA": Plantilla("LA_CEPA"),
    "RECACOR": Plantilla("RECACOR"),
    "CRUZ": Plantilla("CRUZ"),
    "MEYRAS": Plantilla("MEYRAS"),
    "BONDIOLI": Plantilla("BONDIOLI"),
    "JUCAMP": Plantilla("JUCAMP"),
}


def plantilla_para(proveedor: str | None) -> Plantilla:
    return PLANTILLAS.get(proveedor or "", GENERICA)


def compilar(patrones: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patrones]
