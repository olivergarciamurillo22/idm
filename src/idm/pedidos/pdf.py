"""Genera el PDF de un pedido con reportlab: cabecera de IDM (desde .env), proveedor, líneas y total.
El formato real de IDM (H:\\0_PEDIDOS_TRANSMITIDOS) está PENDIENTE de muestra: este es un formato limpio y provisional.
No envía nada ni toca Siddex."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from idm.dominio.dinero import formatear
from idm.dominio.modelos import Pedido, Proveedor


def nombre_fichero(pedido: Pedido) -> str:
    return f"PEDIDO_{pedido.numero}_{pedido.proveedor}.pdf"


def generar_pdf(pedido: Pedido, proveedor: Proveedor | None, empresa: dict[str, str], carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre_fichero(pedido)
    estilos = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(ruta), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm, title=f"Pedido {pedido.numero}")
    cuerpo = [
        Paragraph(f"<b>{empresa.get('nombre', 'IDM')}</b>", estilos["Title"]),
        Paragraph(" · ".join(filter(None, [empresa.get("direccion"), empresa.get("cif"),
                                            empresa.get("telefono"), empresa.get("email_pedidos")])),
                  estilos["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph(f"<b>PEDIDO DE COMPRA Nº {pedido.numero}</b>", estilos["Heading2"]),
        Paragraph(f"Fecha: {pedido.fecha:%d/%m/%Y}" if pedido.fecha else "", estilos["Normal"]),
        Paragraph(f"Proveedor: <b>{proveedor.nombre if proveedor else pedido.proveedor}</b>"
                  + (f" · CIF {proveedor.cif}" if proveedor and proveedor.cif else ""), estilos["Normal"]),
        Spacer(1, 6 * mm),
    ]
    filas = [["Código", "Descripción", "Cantidad", "Ud.", "Precio", "Dto %", "Importe"]]
    for li in pedido.lineas:
        filas.append([li.codigo_idm, li.descripcion, formatear(li.cantidad), li.unidad,
                      formatear(li.precio_bruto), formatear(li.descuento_pct), formatear(li.importe)])
    filas.append(["", "", "", "", "", "TOTAL", formatear(pedido.total)])
    tabla = Table(filas, colWidths=[28 * mm, 70 * mm, 20 * mm, 12 * mm, 20 * mm, 15 * mm, 22 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -2), 0.4, colors.grey),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    cuerpo += [tabla, Spacer(1, 8 * mm),
               Paragraph("Indicar nuestro número de pedido en albarán y factura.", estilos["Normal"])]
    doc.build(cuerpo)
    return ruta
