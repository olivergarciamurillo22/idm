"""SiddexDesdeExcel: implementación de SiddexGateway sobre los exports a Excel de las pantallas de Siddex.
Lee por nombre de cabecera (tabla COLUMNAS al principio) los ficheros de una carpeta: articulos, proveedores,
fabricantes, pedidos, stock y escandallos .xls. No escribe nada y no conoce la base de datos de Siddex."""

import unicodedata
from decimal import Decimal
from pathlib import Path

import openpyxl

from idm.dominio.dinero import CERO, a_decimal
from idm.dominio.estados import RelacionPedido
from idm.dominio.modelos import Articulo, Equivalencia, LineaPedido, Pedido, Proveedor
from idm.equivalencias.proveedores import clave_para
from idm.siddex.lectura import Escandallo, leer_escandallo, normalizar_codigo

# PROVISIONAL: nombres de cabecera aceptados por cada campo. Se ajustan cuando lleguen los exports reales
# (Maestro de Artículos, Proveedores, Fabricantes, Pedidos, Stocks). Ver DECISIONES.md.
COLUMNAS: dict[str, dict[str, tuple[str, ...]]] = {
    "articulos": {
        "codigo": ("codigo", "articulo", "codigo articulo"),
        "descripcion": ("descripcion", "denominacion"),
        "unidad": ("unidad", "ud", "unidad medida"),
        "proveedor": ("proveedor", "proveedor habitual", "codigo proveedor"),
        "precio": ("precio", "precio compra", "ultimo precio"),
        "descuento": ("descuento", "dto", "dto %"),
        "multiplo": ("multiplo", "multiplo compra", "unidades caja", "caja"),
        "tipo": ("tipo", "tipo articulo"),
    },
    "proveedores": {
        "codigo": ("codigo", "codigo proveedor"),
        "nombre": ("nombre", "razon social"),
        "cif": ("cif", "nif"),
        "email": ("email", "e-mail", "correo"),
    },
    "fabricantes": {
        "codigo": ("codigo", "articulo", "codigo articulo"),
        "proveedor": ("proveedor", "codigo proveedor", "fabricante"),
        "codigo_proveedor": ("codigo alternativo", "referencia proveedor", "codigo proveedor articulo", "referencia"),
        "descripcion": ("descripcion proveedor", "denominacion proveedor", "descripcion"),
    },
    "pedidos": {
        "numero": ("pedido", "numero pedido", "nuestro pedido", "numero"),
        "proveedor": ("proveedor", "codigo proveedor"),
        "fecha": ("fecha", "fecha pedido"),
        "codigo": ("articulo", "codigo", "codigo articulo"),
        "descripcion": ("descripcion", "denominacion"),
        "cantidad": ("cantidad", "pedido cantidad", "cant"),
        "unidad": ("unidad", "ud"),
        "precio": ("precio", "precio compra"),
        "descuento": ("descuento", "dto", "dto %"),
        "recibida": ("recibida", "cantidad recibida", "servida"),
        "codigo_proveedor": ("codigo alternativo", "referencia proveedor", "referencia"),
    },
    "stock": {
        "codigo": ("codigo", "articulo", "codigo articulo"),
        "stock": ("stock", "existencias", "stock actual"),
    },
}

FICHEROS = {
    "articulos": "articulos.xlsx",
    "proveedores": "proveedores.xlsx",
    "fabricantes": "fabricantes.xlsx",
    "pedidos": "pedidos.xlsx",
    "stock": "stock.xlsx",
}


def _normalizar_cabecera(texto) -> str:
    sin_acentos = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().replace("_", " ").replace(".", " ").split())


def leer_tabla(ruta: Path, columnas: dict[str, tuple[str, ...]]) -> list[dict[str, object]]:
    """Devuelve una lista de dicts campo→valor usando la primera fila con cabeceras reconocidas."""
    libro = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    hoja = libro.worksheets[0]
    filas = list(hoja.iter_rows(values_only=True))
    libro.close()
    for i, fila in enumerate(filas):
        cabeceras = [_normalizar_cabecera(c) for c in fila]
        indices = {
            campo: next((k for k, cab in enumerate(cabeceras) if cab in nombres), None)
            for campo, nombres in columnas.items()
        }
        if indices.get("codigo") is not None or indices.get("numero") is not None:
            return [
                {
                    campo: (fila_datos[k] if k is not None and k < len(fila_datos) else None)
                    for campo, k in indices.items()
                }
                for fila_datos in filas[i + 1 :]
                if any(c not in (None, "") for c in fila_datos)
            ]
    raise ValueError(f"{ruta.name}: no se reconoce ninguna fila de cabeceras (ver COLUMNAS en desde_excel.py)")


class SiddexDesdeExcel:
    def __init__(self, carpeta: Path) -> None:
        self.carpeta = Path(carpeta)
        self._escandallos: dict[str, Escandallo] | None = None

    def _ruta(self, nombre: str) -> Path | None:
        ruta = self.carpeta / FICHEROS[nombre]
        return ruta if ruta.exists() else None

    def proveedores(self) -> list[Proveedor]:
        ruta = self._ruta("proveedores")
        if ruta is None:
            return []
        resultado = []
        for f in leer_tabla(ruta, COLUMNAS["proveedores"]):
            codigo = str(f["codigo"]).strip() if f["codigo"] is not None else None
            nombre = str(f["nombre"] or "").strip()
            resultado.append(
                Proveedor(
                    clave=clave_para(codigo, nombre),
                    codigo_siddex=codigo,
                    nombre=nombre,
                    cif=str(f["cif"]).strip() if f["cif"] else None,
                    email=str(f["email"]).strip() if f["email"] else None,
                )
            )
        return resultado

    def _clave_proveedor(self, valor) -> str | None:
        if valor in (None, ""):
            return None
        return clave_para(str(valor).strip(), "")

    def articulos(self) -> dict[str, Articulo]:
        ruta = self._ruta("articulos")
        if ruta is None:
            return {}
        resultado = {}
        for f in leer_tabla(ruta, COLUMNAS["articulos"]):
            if f["codigo"] in (None, ""):
                continue
            codigo = normalizar_codigo(str(f["codigo"]))
            resultado[codigo] = Articulo(
                codigo=codigo,
                descripcion=str(f["descripcion"] or "").strip(),
                unidad=str(f["unidad"] or "UD").strip(),
                proveedor_habitual=self._clave_proveedor(f["proveedor"]),
                precio_compra=a_decimal(f["precio"]) if f["precio"] not in (None, "") else None,
                descuento_pct=a_decimal(f["descuento"]) or CERO,
                multiplo_compra=a_decimal(f["multiplo"]) or Decimal("1"),
                tipo=str(f["tipo"]).strip() if f["tipo"] else None,
            )
        return resultado

    def equivalencias(self) -> list[Equivalencia]:
        ruta = self._ruta("fabricantes")
        if ruta is None:
            return []
        resultado = []
        for f in leer_tabla(ruta, COLUMNAS["fabricantes"]):
            if f["codigo"] in (None, "") or f["codigo_proveedor"] in (None, ""):
                continue
            proveedor = self._clave_proveedor(f["proveedor"])
            if proveedor is None:
                continue
            resultado.append(
                Equivalencia(
                    proveedor=proveedor,
                    codigo_proveedor=str(f["codigo_proveedor"]).strip(),
                    codigo_idm=normalizar_codigo(str(f["codigo"])),
                    descripcion_proveedor=str(f["descripcion"] or "").strip(),
                )
            )
        return resultado

    def _pedidos(self) -> dict[str, Pedido]:
        ruta = self._ruta("pedidos")
        if ruta is None:
            return {}
        pedidos: dict[str, Pedido] = {}
        for f in leer_tabla(ruta, COLUMNAS["pedidos"]):
            if f["numero"] in (None, "") or f["codigo"] in (None, ""):
                continue
            numero = str(f["numero"]).strip()
            if numero.endswith(".0"):
                numero = numero[:-2]
            if numero not in pedidos:
                fecha = f["fecha"]
                pedidos[numero] = Pedido(
                    numero=numero,
                    proveedor=self._clave_proveedor(f["proveedor"]) or "",
                    fecha=fecha.date() if hasattr(fecha, "date") else None,
                    numero_siddex=numero,
                    relacion=RelacionPedido.CON_PEDIDO,
                )
            pedidos[numero].lineas.append(
                LineaPedido(
                    codigo_idm=normalizar_codigo(str(f["codigo"])),
                    descripcion=str(f["descripcion"] or "").strip(),
                    cantidad=a_decimal(f["cantidad"]) or CERO,
                    unidad=str(f["unidad"] or "UD").strip(),
                    precio_bruto=a_decimal(f["precio"]) or CERO,
                    descuento_pct=a_decimal(f["descuento"]) or CERO,
                    cantidad_recibida=a_decimal(f["recibida"]) or CERO,
                    codigo_proveedor=str(f["codigo_proveedor"]).strip() if f["codigo_proveedor"] else None,
                )
            )
        return pedidos

    def pedidos_abiertos(self, proveedor: str | None = None) -> list[Pedido]:
        return [
            p
            for p in self._pedidos().values()
            if (proveedor is None or p.proveedor == proveedor) and any(li.pendiente > CERO for li in p.lineas)
        ]

    def pedido(self, numero: str) -> Pedido | None:
        return self._pedidos().get(str(numero).strip())

    def stock(self) -> dict[str, Decimal]:
        ruta = self._ruta("stock")
        if ruta is None:
            return {}
        return {
            normalizar_codigo(str(f["codigo"])): a_decimal(f["stock"]) or CERO
            for f in leer_tabla(ruta, COLUMNAS["stock"])
            if f["codigo"] not in (None, "")
        }

    def pendiente_recibir(self) -> dict[str, Decimal]:
        pendiente: dict[str, Decimal] = {}
        for p in self._pedidos().values():
            for li in p.lineas:
                if li.pendiente > CERO:
                    pendiente[li.codigo_idm] = pendiente.get(li.codigo_idm, CERO) + li.pendiente
        return pendiente

    def escandallo(self, codigo_maquina: str) -> Escandallo | None:
        if self._escandallos is None:
            self._escandallos = {}
            for ruta in sorted(self.carpeta.glob("*.xls")):
                try:
                    e = leer_escandallo(ruta)
                except Exception:  # noqa: BLE001 - un fichero raro no debe tumbar el resto
                    continue
                if e.codigo_maquina:
                    self._escandallos[e.codigo_maquina] = e
        return self._escandallos.get(normalizar_codigo(codigo_maquina))
