"""Genera los PDF (con texto) y una foto simulada (PNG) de los documentos ficticios a partir de sus .json.
Imita la estructura de un albarán/factura de proveedor: cabecera, número, fecha, su pedido, tabla con rejilla, totales.
Ejecutar: PYTHONPATH=src .venv/bin/python fixtures/ficticios/documentos/generar_pdfs.py"""

import json
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

AQUI = Path(__file__).resolve().parent

DIRECCIONES = {
    "B00000001": "Polígono Ficticio, nave 1 · 04000 Almería · Tel. 950 000 001",
    "A00000002": "Calle Inventada 22 · 04000 Almería · Tel. 950 000 002",
    "B00000003": "Avenida de Prueba 3 · 04000 Almería · Tel. 950 000 003",
}


def num(v):
    if v is None:
        return ""
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cant(v):
    return "" if v is None else (str(int(float(v))) if float(v).is_integer() else num(v))


def fecha_es(iso):
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def pdf(datos: dict, ruta: Path) -> None:
    est = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(ruta), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm)
    es_factura = datos["tipo"] == "FACTURA"
    cuerpo = [
        Paragraph(f"<b>{datos['proveedor_texto']}</b>", est["Title"]),
        Paragraph(f"CIF {datos['cif']} · {DIRECCIONES[datos['cif']]}", est["Normal"]),
        Spacer(1, 5 * mm),
        Paragraph("Cliente: EMPRESA CLIENTE FICTICIA S.L. · CIF B99999999", est["Normal"]),
        Spacer(1, 5 * mm),
        Paragraph(f"<b>{'FACTURA' if es_factura else 'ALBARÁN'} Nº: {datos['numero']}</b>", est["Heading2"]),
        Paragraph(f"Fecha: {fecha_es(datos['fecha'])}", est["Normal"]),
    ]
    if datos.get("nuestro_pedido"):
        cuerpo.append(Paragraph(f"Su pedido: {datos['nuestro_pedido']}", est["Normal"]))
    if es_factura:
        cuerpo.append(Paragraph("Albaranes: " + ", ".join(datos["albaranes_referenciados"]), est["Normal"]))
    cuerpo.append(Spacer(1, 5 * mm))

    sin_precio = all(li.get("precio_bruto") is None for li in datos["lineas"])
    cab = (["Albarán"] if es_factura else []) + ["Referencia", "Descripción", "Cantidad", "Ud"]
    if not sin_precio:
        cab += ["Precio", "Dto %", "Importe"]
    filas = [cab]
    for li in datos["lineas"]:
        fila = ([li.get("albaran") or ""] if es_factura else []) + [
            li.get("codigo_proveedor") or "",
            li["descripcion"],
            cant(li["cantidad"]),
            li.get("unidad") or "UD",
        ]
        if not sin_precio:
            dto = li.get("descuento_pct")
            fila += [num(li.get("precio_bruto")), cant(dto) if dto is not None else "", num(li.get("importe"))]
        filas.append(fila)
    tabla = Table(filas, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (-3, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    cuerpo.append(tabla)
    cuerpo.append(Spacer(1, 6 * mm))
    if not sin_precio:
        for etiqueta, clave in (("Base imponible", "base"), ("IVA 21%", "iva"), ("TOTAL", "total")):
            cuerpo.append(Paragraph(f"{etiqueta}: {num(datos[clave])} €", est["Normal"]))
    else:
        cuerpo.append(Paragraph("Precios según factura.", est["Normal"]))
    doc.build(cuerpo)


def foto(datos: dict, ruta: Path) -> None:
    """Simula la foto de un albarán en papel: imagen sin capa de texto."""
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    y = 80
    lineas = [
        datos["proveedor_texto"],
        f"CIF {datos['cif']}",
        "",
        f"ALBARAN N: {datos['numero']}",
        f"Fecha: {fecha_es(datos['fecha'])}",
        "",
    ]
    lineas += [
        f"{li.get('codigo_proveedor') or ''}  {li['descripcion']}  {cant(li['cantidad'])} {li.get('unidad') or ''}"
        for li in datos["lineas"]
    ]
    for linea in lineas:
        d.text((80, y), linea, fill="black")
        y += 40
    img.save(ruta)


def main() -> None:
    for json_ruta in sorted(AQUI.glob("*.json")):
        datos = json.loads(json_ruta.read_text(encoding="utf-8"))
        pdf(datos, json_ruta.with_suffix(".pdf"))
        print("pdf", json_ruta.with_suffix(".pdf").name)
    recambios = json.loads((AQUI / "albaran_recambios_sin_precio.json").read_text(encoding="utf-8"))
    foto(recambios, AQUI / "albaran_recambios_sin_precio_foto.png")
    print("png albaran_recambios_sin_precio_foto.png")


if __name__ == "__main__":
    main()
