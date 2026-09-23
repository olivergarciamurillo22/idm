"""Genera fixtures/siddex/escandallo_ficticio.xls en BIFF2 (Excel 2.0), el formato real del export de Siddex.
Escritor mínimo: BOF, LABEL y NUMBER, EOF; suficiente para que xlrd lo lea como el original.
Datos completamente ficticios. Ejecutar: PYTHONPATH=src .venv/bin/python fixtures/siddex/generar_biff2.py"""

import struct
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# nivel, cabecera, sec, código, descripción, cantidad, unidad, precio, importe, tipo
FILAS = [
    ("", " Articulo: M91.000.001   *MAQUINA-FICTICIA-1", "", "", "", None, "", None, None, ""),
    ("", "", "", "", "", None, "", None, None, ""),
    ("1.0", "", "1", "M91.000.001", "MAQUINA FICTICIA 1", 1, "UD", None, 1234.50, "Producto"),
    (".2", "", "1", "C10.000.001", "CONJUNTO CHASIS", 1, "UD", None, 600.00, "Conjunto"),
    ("..3", "", "1", "P20.000.010", "CORTE TUBO 80x80x3 L=1200", 4, "UD", 12.50, 50.00, "MP"),
    ("..3", "", "2", "P20.000.011", "CHAPA KG 3MM", 25, "KG", 1.20, 30.00, "MP"),
    ("..3", "", "3", "T30.000.100", "TORNILLO M10x30 DIN933", 40, "UD", 0.08, 3.20, "Comercial"),
    ("..3", "", "4", "R40.000.001", "RUEDA 400x8 LISA", 4, "UD", 38.00, 152.00, "Comercial"),
    ("..3", "", "5", "O00.000.001", "SOLDADURA CHASIS", 90, "MIN", None, None, "Operacion"),
    (".2", "", "2", "C10.000.002", "CONJUNTO HIDRAULICO", 1, "UD", None, 400.00, "Conjunto"),
    ("..3", "", "1", "H50.000.020", "BOMBA HIDRAULICA 20L", 1, "UD", 210.00, 210.00, "Comercial"),
    ("..3", "", "2", "M37.000.012", "MANG. HIDR. 1/2 (x2)", 2, "M", 6.40, 12.80, "Conjunto"),
    ("...4", "", "1", "I37.000.012", "MANGUERA HIDRAULICA 1/2", 4, "M", 6.40, 25.60, "Comercial"),
    ("...4", "", "2", "I37.000.099", "RACOR 1/2 MACHO", 4, "UD", 1.10, 4.40, "Comercial"),
    ("..3", "", "3", "t30.000.100", "TORNILLO M10x30 DIN933", 8, "UD", 0.08, 0.64, "Comercial"),
    ("..3", "", "4", "M37.000.050", "MANGUERA RETORNO", 1, "UD", None, None, "Conjunto"),
    (".2", "", "3", "E60.000.005", "CABLEADO 24V", 1, "UD", None, 60.00, "Conjunto"),
    ("..3", "", "1", "I34.000.842", "TERMINAL FASTON 9,4", 50, "UD", 0.30, 15.00, "Comercial"),
    ("..3", "", "2", "I34.000.900", "RELE 24V 40A", 2, "UD", None, None, "Comercial"),
    ("..3", "", "3", "L70.000.001", "CHAPA CORTADA LASER", 1, "UD", 8.00, 8.00, "Material"),
]


def registro(tipo: int, datos: bytes) -> bytes:
    return struct.pack("<HH", tipo, len(datos)) + datos


def label(fila: int, col: int, texto: str) -> bytes:
    cuerpo = texto.encode("latin-1")[:255]
    return registro(0x0004, struct.pack("<HH3sB", fila, col, b"\x00\x00\x00", len(cuerpo)) + cuerpo)


def number(fila: int, col: int, valor: float) -> bytes:
    return registro(0x0003, struct.pack("<HH3sd", fila, col, b"\x00\x00\x00", float(valor)))


def escribir(ruta: Path) -> None:
    columnas = [0, 1, 3, 4, 5, 11, 12, 15, 16, 17]
    salida = registro(0x0009, struct.pack("<HH", 0x0000, 0x0010))  # BOF: BIFF2, hoja
    for r, fila in enumerate(FILAS):
        for col, valor in zip(columnas, fila, strict=True):
            if valor is None or valor == "":
                continue
            if isinstance(valor, int | float):
                salida += number(r, col, valor)
            else:
                salida += label(r, col, valor)
    salida += registro(0x000A, b"")  # EOF
    ruta.write_bytes(salida)


FILAS_L = [
    ("", " Articulo: M91.000.002   *MAQUINA-FICTICIA-1 L", "", "", "", None, "", None, None, ""),
    ("1.0", "", "1", "M91.000.002", "MAQUINA FICTICIA 1 L (RUEDAS LISAS)", 1, "UD", None, 1300.00, "Producto"),
    (".2", "", "1", "C10.000.001", "CONJUNTO CHASIS", 1, "UD", None, 600.00, "Conjunto"),
    ("..3", "", "1", "P20.000.010", "CORTE TUBO 80x80x3 L=1200", 4, "UD", 12.50, 50.00, "MP"),
    ("..3", "", "2", "T30.000.100", "TORNILLO M10x30 DIN933", 40, "UD", 0.08, 3.20, "Comercial"),
    ("..3", "", "3", "R40.000.002", "RUEDA 400x8 LISA REFORZADA", 4, "UD", 45.00, 180.00, "Comercial"),
    (".2", "", "2", "C10.000.002", "CONJUNTO HIDRAULICO", 1, "UD", None, 400.00, "Conjunto"),
    ("..3", "", "1", "H50.000.020", "BOMBA HIDRAULICA 20L", 1, "UD", 210.00, 210.00, "Comercial"),
]


def escribir_filas(ruta: Path, filas: list) -> None:
    global FILAS
    original = FILAS
    FILAS = filas
    try:
        escribir(ruta)
    finally:
        FILAS = original


if __name__ == "__main__":
    escribir(AQUI / "escandallo_ficticio.xls")
    escribir_filas(AQUI / "escandallo_ficticio_L.xls", FILAS_L)
    print("escritos escandallo_ficticio.xls y escandallo_ficticio_L.xls en", AQUI)
