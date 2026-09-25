"""Configuración central de las columnas de los exports de Siddex: campo interno, alias de cabecera, si es requerida
y si está VERIFICADA con un export real. Lee alias extra de datos/siddex/columnas.json y produce un informe por fichero.
No lee filas de negocio: solo localiza la cabecera y dice qué columna es qué; cero pérdida silenciosa."""

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl


@dataclass(frozen=True)
class Columna:
    campo: str
    alias: tuple[str, ...]
    requerida: bool = False
    descripcion: str = ""


# PROVISIONAL hasta tener los exports reales (docs/PENDIENTE-IDM.md). Solo el escandallo (lectura.py) está verificado.
TABLAS: dict[str, tuple[Columna, ...]] = {
    "articulos": (
        Columna("codigo", ("codigo", "articulo", "codigo articulo", "cod articulo", "referencia"), True, "código IDM"),
        Columna("descripcion", ("descripcion", "denominacion", "nombre"), False, "descripción interna"),
        Columna("unidad", ("unidad", "ud", "unidad medida", "um"), False, "UD, M, KG, LT"),
        Columna(
            "proveedor",
            ("proveedor", "proveedor habitual", "codigo proveedor", "cod proveedor"),
            False,
            "código del proveedor habitual (PROVEEDR)",
        ),
        Columna(
            "precio", ("precio", "precio compra", "ultimo precio", "precio coste", "coste"), False, "precio de compra"
        ),
        Columna("descuento", ("descuento", "dto", "dto %", "% dto", "descuento compra"), False, "descuento habitual"),
        Columna(
            "multiplo",
            ("multiplo", "multiplo compra", "unidades caja", "caja", "lote compra", "minimo compra"),
            False,
            "múltiplo de compra: caja, rollo, bolsa",
        ),
        Columna("tipo", ("tipo", "tipo articulo", "familia"), False, "Comercial, MP, Conjunto..."),
    ),
    "proveedores": (
        Columna(
            "codigo",
            ("codigo", "codigo proveedor", "cod proveedor", "proveedor"),
            True,
            "código en PROVEEDR (p. ej. 9001)",
        ),
        Columna("nombre", ("nombre", "razon social", "nombre comercial"), True, "razón social"),
        Columna("cif", ("cif", "nif", "cif nif", "nif cif"), False, "CIF"),
        Columna("email", ("email", "e-mail", "correo", "correo electronico", "mail"), False, "correo para pedidos"),
    ),
    "fabricantes": (
        Columna("codigo", ("codigo", "articulo", "codigo articulo", "cod articulo"), True, "código IDM"),
        Columna(
            "proveedor", ("proveedor", "codigo proveedor", "fabricante", "cod proveedor"), True, "código del proveedor"
        ),
        Columna(
            "codigo_proveedor",
            (
                "codigo alternativo",
                "referencia proveedor",
                "codigo proveedor articulo",
                "referencia",
                "ref proveedor",
                "codigo fabricante",
            ),
            True,
            "referencia con la que el proveedor lo llama",
        ),
        Columna(
            "descripcion",
            ("descripcion proveedor", "denominacion proveedor", "descripcion"),
            False,
            "descripción del proveedor",
        ),
    ),
    "pedidos": (
        Columna(
            "numero",
            ("pedido", "numero pedido", "nuestro pedido", "numero", "n pedido"),
            True,
            "número de pedido (20269060)",
        ),
        Columna("proveedor", ("proveedor", "codigo proveedor", "cod proveedor"), True, "código del proveedor"),
        Columna("fecha", ("fecha", "fecha pedido"), False, "fecha del pedido"),
        Columna("codigo", ("articulo", "codigo", "codigo articulo", "cod articulo"), True, "código IDM de la línea"),
        Columna("descripcion", ("descripcion", "denominacion"), False, "descripción"),
        Columna("cantidad", ("cantidad", "pedido cantidad", "cant", "cantidad pedida"), True, "cantidad pedida"),
        Columna("unidad", ("unidad", "ud", "um"), False, "unidad"),
        Columna("precio", ("precio", "precio compra", "precio unitario"), True, "precio bruto pactado"),
        Columna("descuento", ("descuento", "dto", "dto %", "% dto"), False, "descuento de la línea"),
        Columna(
            "recibida",
            ("recibida", "cantidad recibida", "servida", "cantidad servida", "entregada"),
            False,
            "cantidad ya recibida (para el pendiente)",
        ),
        Columna(
            "codigo_proveedor",
            ("codigo alternativo", "referencia proveedor", "referencia", "ref proveedor"),
            False,
            "referencia del proveedor en la línea",
        ),
    ),
    "stock": (
        Columna("codigo", ("codigo", "articulo", "codigo articulo", "cod articulo"), True, "código IDM"),
        Columna("stock", ("stock", "existencias", "stock actual", "stock real", "disponible"), True, "existencias"),
    ),
}

FICHEROS: dict[str, str] = {
    "articulos": "articulos.xlsx",
    "proveedores": "proveedores.xlsx",
    "fabricantes": "fabricantes.xlsx",
    "pedidos": "pedidos.xlsx",
    "stock": "stock.xlsx",
}

NOMBRE_ALIAS_EXTRA = "columnas.json"  # en la carpeta de exports: {"articulos": {"multiplo": ["Uds/Caja"]}, ...}


def normalizar_cabecera(texto: object) -> str:
    """'Código Artículo ' → 'codigo articulo'; tolera acentos, mayúsculas, puntos, guiones bajos y espacios dobles."""
    sin_acentos = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().replace("_", " ").replace(".", " ").replace("-", " ").replace("/", " ").split())


def cargar_alias_extra(carpeta: Path) -> dict[str, dict[str, list[str]]]:
    ruta = Path(carpeta) / NOMBRE_ALIAS_EXTRA
    if not ruta.exists():
        return {}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta}: se esperaba un objeto {{tabla: {{campo: [alias]}}}}")
    return datos


def columnas_de(tabla: str, alias_extra: dict[str, dict[str, list[str]]] | None = None) -> list[Columna]:
    if tabla not in TABLAS:
        raise KeyError(f"Tabla desconocida '{tabla}'. Conocidas: {', '.join(TABLAS)}")
    extra = (alias_extra or {}).get(tabla, {})
    resultado = []
    for col in TABLAS[tabla]:
        nuevos = tuple(normalizar_cabecera(a) for a in extra.get(col.campo, []))
        resultado.append(Columna(col.campo, col.alias + nuevos, col.requerida, col.descripcion))
    desconocidos = set(extra) - {c.campo for c in TABLAS[tabla]}
    if desconocidos:
        raise ValueError(f"{NOMBRE_ALIAS_EXTRA}: campos desconocidos en '{tabla}': {', '.join(sorted(desconocidos))}")
    return resultado


@dataclass
class InformeColumnas:
    tabla: str
    fichero: str
    fila_cabecera: int | None = None  # 1-based
    encontradas: dict[str, str] = field(default_factory=dict)  # campo → cabecera tal como está en el fichero
    faltantes_requeridas: list[str] = field(default_factory=list)
    faltantes_opcionales: list[str] = field(default_factory=list)
    desconocidas: list[str] = field(default_factory=list)  # cabeceras del fichero que no se usan
    filas: int = 0
    cabeceras_vistas: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.fila_cabecera is not None and not self.faltantes_requeridas

    def texto(self) -> str:
        lineas = [
            f"[{self.tabla}] {self.fichero}: "
            + ("OK" if self.ok else "INCOMPLETO")
            + (f" · cabecera en fila {self.fila_cabecera} · {self.filas} filas" if self.fila_cabecera else "")
        ]
        for campo, cab in self.encontradas.items():
            lineas.append(f"    {campo:<18} ← '{cab}'")
        for campo in self.faltantes_requeridas:
            lineas.append(f"    {campo:<18} FALTA (requerida)")
        for campo in self.faltantes_opcionales:
            lineas.append(f"    {campo:<18} falta (opcional: se usará el valor por defecto)")
        if self.desconocidas:
            lineas.append(f"    columnas del fichero sin uso: {', '.join(self.desconocidas)}")
        if self.fila_cabecera is None:
            lineas.append(f"    cabeceras vistas: {', '.join(self.cabeceras_vistas) or '(ninguna)'}")
        return "\n".join(lineas)


class ColumnasFaltantes(Exception):
    def __init__(self, informe: InformeColumnas) -> None:
        self.informe = informe
        faltan = ", ".join(informe.faltantes_requeridas) or "no se encontró ninguna fila de cabeceras"
        super().__init__(
            f"{informe.fichero} ({informe.tabla}): faltan columnas requeridas: {faltan}. "
            f"Cabeceras vistas: {', '.join(informe.cabeceras_vistas) or '(ninguna)'}. "
            f"Añade el alias en {NOMBRE_ALIAS_EXTRA} o en siddex/columnas.py."
        )


def _mapear(fila: list, columnas: list[Columna]) -> dict[str, int]:
    normalizadas = [normalizar_cabecera(c) for c in fila]
    indices: dict[str, int] = {}
    for col in columnas:
        for i, cab in enumerate(normalizadas):
            if cab and cab in col.alias and i not in indices.values():
                indices[col.campo] = i
                break
    return indices


def leer_tabla(
    ruta: Path, tabla: str, alias_extra: dict | None = None, max_filas_cabecera: int = 15
) -> tuple[list[dict[str, object]], InformeColumnas]:
    """Busca la fila de cabecera (la que más columnas conocidas tiene en las primeras filas) y devuelve las filas como
    dicts campo→valor más el informe. Lanza ColumnasFaltantes si falta una requerida."""
    columnas = columnas_de(tabla, alias_extra)
    informe = InformeColumnas(tabla=tabla, fichero=Path(ruta).name)
    libro = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    hoja = libro.worksheets[0]
    filas = list(hoja.iter_rows(values_only=True))
    libro.close()

    mejor: tuple[int, int, dict[str, int]] | None = None  # (nº encontradas, índice fila, mapa)
    for i, fila in enumerate(filas[:max_filas_cabecera]):
        indices = _mapear(list(fila), columnas)
        if indices and (mejor is None or len(indices) > mejor[0]):
            mejor = (len(indices), i, indices)
        for c in fila:
            if (
                c not in (None, "")
                and str(c).strip() not in informe.cabeceras_vistas
                and len(informe.cabeceras_vistas) < 40
            ):
                informe.cabeceras_vistas.append(str(c).strip())
    if mejor is None:
        informe.faltantes_requeridas = [c.campo for c in columnas if c.requerida]
        raise ColumnasFaltantes(informe)

    _, fila_cab, indices = mejor
    cabecera = list(filas[fila_cab])
    informe.fila_cabecera = fila_cab + 1
    informe.encontradas = {campo: str(cabecera[i]).strip() for campo, i in indices.items()}
    informe.faltantes_requeridas = [c.campo for c in columnas if c.requerida and c.campo not in indices]
    informe.faltantes_opcionales = [c.campo for c in columnas if not c.requerida and c.campo not in indices]
    informe.desconocidas = [
        str(c).strip() for k, c in enumerate(cabecera) if c not in (None, "") and k not in indices.values()
    ]
    if informe.faltantes_requeridas:
        raise ColumnasFaltantes(informe)

    datos = []
    for fila in filas[fila_cab + 1 :]:
        if not any(c not in (None, "") for c in fila):
            continue
        # Todos los campos de la tabla están siempre presentes: los no encontrados valen None (defecto explícito)
        datos.append(
            {
                col.campo: (
                    fila[indices[col.campo]] if col.campo in indices and indices[col.campo] < len(fila) else None
                )
                for col in columnas
            }
        )
    informe.filas = len(datos)
    return datos, informe
