"""Genera ficheros que el lector debe rechazar con un resultado claro: corrupto, vacío, Excel, texto y PDF escaneado
(solo imagen, sin capa de texto). Ejecutar: PYTHONPATH=src .venv/bin/python fixtures/no_procesables/generar.py"""

from pathlib import Path

import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

AQUI = Path(__file__).resolve().parent


def main() -> None:
    (AQUI / "corrupto.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nesto no es un pdf de verdad\n")
    (AQUI / "vacio.pdf").write_bytes(b"")
    (AQUI / "texto.txt").write_text("esto es un fichero de texto, no un documento", encoding="utf-8")
    libro = openpyxl.Workbook()
    libro.active.append(["Un Excel que alguien dejó en la carpeta de entrada"])
    libro.save(AQUI / "hoja.xlsx")
    foto = AQUI.parent / "ficticios" / "documentos" / "albaran_recambios_sin_precio_foto.png"
    c = canvas.Canvas(str(AQUI / "escaneado_sin_texto.pdf"), pagesize=A4)
    c.drawImage(str(foto), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    print("generados en", AQUI)


if __name__ == "__main__":
    main()
