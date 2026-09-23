"""Parser del export "Simulación de Costos" (escandallo) de Siddex, que sale en BIFF2 (Excel 2.0).
Lee con xlrd (openpyxl no abre BIFF2), agrega lo que se compra (Comercial y MP) por código y lista incidencias.
No calcula necesidades ni conoce el planning: solo devuelve filas y agregados del escandallo."""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import xlrd

from idm.dominio.dinero import CERO, a_decimal, redondear

# Columnas 0-based del export, verificadas sobre el fichero real (ver CONTEXTO §7).
COL_NIVEL, COL_CABECERA, COL_SEC, COL_CODIGO, COL_DESCRIPCION = 0, 1, 3, 4, 5
COL_CANTIDAD, COL_UNIDAD, COL_PRECIO, COL_IMPORTE, COL_TIPO = 11, 12, 15, 16, 17

TIPOS_COMPRA = ("Comercial", "MP")
TIPOS_CONOCIDOS = ("Producto", "Conjunto", "Material", "Comercial", "MP", "Operacion")

_RE_CABECERA = re.compile(r"Articulo:\s*(?P<codigo>\S+)\s+\*?(?P<nombre>.*)", re.IGNORECASE)


@dataclass
class FilaEscandallo:
    nivel: int
    codigo: str
    descripcion: str
    cantidad: Decimal
    unidad: str
    precio: Decimal | None
    importe: Decimal | None
    tipo: str
    fila: int  # fila del Excel (1-based) para poder señalar incidencias


@dataclass
class Escandallo:
    ruta: str
    codigo_maquina: str | None
    nombre_maquina: str | None
    filas: list[FilaEscandallo] = field(default_factory=list)


@dataclass
class Compra:
    codigo: str
    descripcion: str
    unidad: str
    tipo: str
    cantidad: Decimal  # por máquina, ya sumada si el código aparece en varias ramas
    precio: Decimal | None
    importe: Decimal


def abrir(ruta: Path | str) -> xlrd.sheet.Sheet:
    """Abre el .xls BIFF2 con latin-1 (Siddex no declara codepage) y devuelve la primera hoja."""
    libro = xlrd.open_workbook(str(ruta), encoding_override="latin-1")
    return libro.sheet_by_index(0)


def nivel_desde_texto(texto: str) -> int | None:
    """'1.0' → 1, '.2' → 2, '..3' → 3, '...4' → 4. Otro texto → None."""
    limpio = str(texto).strip()
    if not limpio:
        return None
    m = re.fullmatch(r"\.*(\d+)(?:\.0)?", limpio)
    return int(m.group(1)) if m else None


def normalizar_codigo(codigo: str) -> str:
    """'i33.000.786' y 'I33.000.786' son el mismo artículo."""
    return str(codigo).strip().upper()


def leer_escandallo(ruta: Path | str) -> Escandallo:
    hoja = abrir(ruta)
    escandallo = Escandallo(ruta=str(ruta), codigo_maquina=None, nombre_maquina=None)
    for indice in range(hoja.nrows):
        fila = [hoja.cell_value(indice, c) if c < hoja.ncols else "" for c in range(COL_TIPO + 1)]
        cabecera = str(fila[COL_CABECERA]).strip()
        if escandallo.codigo_maquina is None and (m := _RE_CABECERA.search(cabecera)):
            escandallo.codigo_maquina = normalizar_codigo(m.group("codigo"))
            escandallo.nombre_maquina = m.group("nombre").strip()
        nivel = nivel_desde_texto(fila[COL_NIVEL])
        tipo = str(fila[COL_TIPO]).strip()
        codigo = str(fila[COL_CODIGO]).strip()
        if nivel is None or not codigo or tipo not in TIPOS_CONOCIDOS:
            continue
        escandallo.filas.append(
            FilaEscandallo(
                nivel=nivel,
                codigo=normalizar_codigo(codigo),
                descripcion=str(fila[COL_DESCRIPCION]).strip(),
                cantidad=a_decimal(fila[COL_CANTIDAD]) or CERO,
                unidad=str(fila[COL_UNIDAD]).strip() or "UD",
                precio=a_decimal(fila[COL_PRECIO]) if fila[COL_PRECIO] not in ("", None) else None,
                importe=a_decimal(fila[COL_IMPORTE]) if fila[COL_IMPORTE] not in ("", None) else None,
                tipo=tipo,
                fila=indice + 1,
            )
        )
    return escandallo


def agregar_compras(escandallo: Escandallo) -> dict[str, Compra]:
    """Suma por código lo que se compra (Comercial y MP). Las cantidades ya vienen explotadas por máquina."""
    compras: dict[str, Compra] = {}
    for f in escandallo.filas:
        if f.tipo not in TIPOS_COMPRA:
            continue
        if f.codigo in compras:
            c = compras[f.codigo]
            c.cantidad += f.cantidad
            c.importe = redondear(c.importe + (f.importe or CERO))
            if c.precio is None:
                c.precio = f.precio
        else:
            compras[f.codigo] = Compra(
                codigo=f.codigo,
                descripcion=f.descripcion,
                unidad=f.unidad,
                tipo=f.tipo,
                cantidad=f.cantidad,
                precio=f.precio,
                importe=redondear(f.importe or CERO),
            )
    return compras


def incidencias(escandallo: Escandallo) -> dict[str, list[str]]:
    """Sin precio, conjuntos sin despiece (nivel sin hijos) y códigos en minúscula en el fichero original."""
    resultado: dict[str, list[str]] = defaultdict(list)
    filas = escandallo.filas
    for i, f in enumerate(filas):
        if f.tipo in TIPOS_COMPRA and (f.precio is None or f.precio == CERO):
            resultado["sin_precio"].append(f"{f.codigo} {f.descripcion} (fila {f.fila})")
        if f.tipo == "Conjunto":
            siguiente = filas[i + 1] if i + 1 < len(filas) else None
            if siguiente is None or siguiente.nivel <= f.nivel:
                resultado["conjunto_sin_despiece"].append(f"{f.codigo} {f.descripcion} (fila {f.fila})")
    hoja = abrir(escandallo.ruta)
    for indice in range(hoja.nrows):
        crudo = str(hoja.cell_value(indice, COL_CODIGO)).strip()
        if crudo and crudo != crudo.upper() and nivel_desde_texto(hoja.cell_value(indice, COL_NIVEL)):
            resultado["codigo_minuscula"].append(f"{crudo} (fila {indice + 1})")
    return dict(resultado)


def total_materiales(compras: dict[str, Compra]) -> Decimal:
    return redondear(sum((c.importe for c in compras.values()), CERO))
