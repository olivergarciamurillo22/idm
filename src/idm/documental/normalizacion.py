"""Normalización IDM: de ResultadoDocumental (cualquier proveedor) a DocumentoLeido del dominio. Reutiliza el intérprete
de texto y tablas de albaranes/lector.py (plantillas por layout); los campos estructurados del proveedor solo rellenan
huecos. Marca los campos dudosos por confianza. No decide nada: el cotejo sigue siendo determinista y en otro sitio."""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from idm.albaranes.lector import interpretar_texto, limpiar_texto_ocr
from idm.documental.modelo import ResultadoDocumental
from idm.dominio.dinero import a_decimal
from idm.dominio.estados import ResultadoLectura
from idm.dominio.modelos import DocumentoLeido, LineaLeida

UMBRAL_DUDOSO = 0.80  # confianza de palabra por debajo de la cual un campo se marca para revisar
CONFIANZA_BAJA_DOCUMENTO = 0.60


def _norm(texto: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(texto).upper())


def _formas(valor) -> set[str]:
    """Formas normalizadas en que un valor puede aparecer impreso ('9.14' → '914', '9140'; fecha ISO → ddmmaaaa)."""
    if valor is None:
        return set()
    if isinstance(valor, date):
        return {_norm(valor.strftime("%d/%m/%Y")), _norm(valor.strftime("%d/%m/%y"))}
    if isinstance(valor, Decimal):
        formas = {_norm(str(valor))}
        for d in range(0, 5):
            formas.add(_norm(f"{valor:.{d}f}"))
        return {f for f in formas if f}
    return {_norm(valor)} - {""}


def confianza_de(valor, resultado: ResultadoDocumental) -> float | None:
    """Mínima confianza de las palabras que forman el valor (hasta 4 palabras seguidas). None si no se encuentra
    o si el proveedor no da confianza por palabra."""
    formas = _formas(valor)
    if not formas:
        return None
    palabras = [p for p in resultado.palabras if p.confianza is not None]
    textos = [_norm(p.texto) for p in palabras]
    mejor: float | None = None
    for i in range(len(textos)):
        acumulado = ""
        for j in range(i, min(i + 4, len(textos))):
            acumulado += textos[j]
            if acumulado in formas:
                conf = min(p.confianza for p in palabras[i : j + 1])
                mejor = conf if mejor is None else max(mejor, conf)
                break
            if not any(f.startswith(acumulado) for f in formas):
                break
    return mejor


def _texto_pares(resultado: ResultadoDocumental) -> str:
    """Pares clave-valor como líneas 'clave: valor' para que las mismas expresiones de las plantillas los lean."""
    return "\n".join(f"{p.clave}: {p.valor}" for p in resultado.pares if p.clave and p.valor)


def _completar_con_campos(doc: DocumentoLeido, resultado: ResultadoDocumental) -> list[str]:
    """Campos estructurados del proveedor solo donde el intérprete no sacó nada. Devuelve qué se completó."""
    completados = []
    c = resultado.campos
    if not doc.numero and (v := c.get("numero")) and v.valor:
        doc.numero = v.valor.strip()
        completados.append("numero")
    if not doc.fecha and (v := c.get("fecha")) and v.valor:
        from idm.albaranes.lector import _fecha

        fecha = _fecha(v.valor.strip()) or _fecha_iso(v.valor)
        if fecha:
            doc.fecha = fecha
            completados.append("fecha")
    if not doc.cif and (v := c.get("cif")) and v.valor:
        doc.cif = re.sub(r"[^A-Z0-9]", "", v.valor.upper())
        completados.append("cif")
    if not doc.nuestro_pedido and (v := c.get("nuestro_pedido")) and v.valor:
        doc.nuestro_pedido = v.valor.strip()
        completados.append("nuestro_pedido")
    if not doc.lineas and resultado.lineas:
        for linea in resultado.lineas:
            g = {k: (v.valor if v else None) for k, v in linea.campos.items()}
            cantidad = a_decimal(g.get("cantidad"))
            if cantidad is None or not (g.get("descripcion") or g.get("codigo_proveedor")):
                continue
            precio = a_decimal(g.get("precio_bruto"))
            doc.lineas.append(
                LineaLeida(
                    codigo_proveedor=(g.get("codigo_proveedor") or "").strip() or None,
                    descripcion=(g.get("descripcion") or "").strip(),
                    cantidad=cantidad,
                    precio_bruto=precio,
                    descuento_pct=a_decimal(g.get("descuento_pct")) if precio is not None else None,
                    importe=a_decimal(g.get("importe")),
                )
            )
        if doc.lineas:
            completados.append("lineas")
    return completados


def _fecha_iso(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto.strip()[:10])
    except ValueError:
        return None


def campos_dudosos(doc: DocumentoLeido, resultado: ResultadoDocumental, umbral: float = UMBRAL_DUDOSO) -> list[str]:
    """Campos leídos cuya confianza de palabra es baja. Si el proveedor no da confianzas, no marca nada por esta vía."""
    if resultado.confianza_media is None:
        return []
    dudosos = []
    for nombre, valor in (("numero", doc.numero), ("fecha", doc.fecha), ("cif", doc.cif)):
        if valor is not None and (c := confianza_de(valor, resultado)) is not None and c < umbral:
            dudosos.append(nombre)
    for i, li in enumerate(doc.lineas):
        for campo in ("codigo_proveedor", "cantidad", "precio_bruto", "descuento_pct", "importe"):
            valor = getattr(li, campo)
            if valor is not None and (c := confianza_de(valor, resultado)) is not None and c < umbral:
                dudosos.append(f"linea[{i}].{campo}")
    return dudosos


def a_documento_leido(
    resultado: ResultadoDocumental, ruta: Path, sha256: str, cifs_propios: set[str]
) -> DocumentoLeido:
    m = resultado.metadatos
    secundario = "\n".join(t for t in (limpiar_texto_ocr(resultado.texto_alternativo), _texto_pares(resultado)) if t)
    doc = interpretar_texto(
        Path(ruta),
        sha256,
        limpiar_texto_ocr(resultado.texto),
        [t.como_filas() for t in resultado.tablas],
        cifs_propios,
        f"{m.proveedor}:{m.modelo}",
        ResultadoLectura.IMAGEN_OCR,
        texto_secundario=secundario,
    )
    completados = _completar_con_campos(doc, resultado)
    confianza = resultado.confianza_media
    etiqueta = f"{confianza * 100:.1f} %" if confianza is not None else "sin dato"
    doc.avisos.insert(
        0,
        f"Leído por {m.proveedor} ({m.modelo}), confianza media {etiqueta}: revisar los campos antes de aprobar",
    )
    doc.avisos += resultado.avisos
    if completados:
        doc.avisos.append(f"Completado con campos estructurados del proveedor: {', '.join(completados)}")
    if confianza is not None:
        doc.confianza = round(doc.confianza * min(confianza, 1.0), 2)
        if confianza < CONFIANZA_BAJA_DOCUMENTO:
            doc.avisos.append(
                f"Confianza baja (< {CONFIANZA_BAJA_DOCUMENTO * 100:.0f} %): posible foto borrosa, girada o cortada"
            )
    doc.motor = f"{m.proveedor}:{m.modelo}"
    doc.coste_estimado_eur = m.coste_estimado_eur
    doc.campos_dudosos = campos_dudosos(doc, resultado)
    doc.metadatos_motor = {
        k: str(v)
        for k, v in {
            "proveedor": m.proveedor,
            "modelo": m.modelo,
            "externo": m.externo,
            "version_api": m.version_api,
            "request_id": m.request_id,
            "tiempo_s": m.tiempo_s,
            "paginas": m.paginas_procesadas,
            "sha256_enviado": m.sha256_enviado,
        }.items()
        if v is not None
    }
    return doc
