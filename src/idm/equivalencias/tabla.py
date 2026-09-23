"""Tabla de equivalencias (proveedor, código del proveedor) → código IDM, con resolución y aprendizaje.
Resuelve por código exacto, por código normalizado (sin guiones/espacios) o no resuelve; siempre dice el método.
No inventa códigos: lo que no está en la tabla ni en lo aprendido queda como ARTICULO_NO_RESUELTO."""

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from idm.dominio.modelos import Equivalencia


def normalizar_codigo_proveedor(codigo: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", codigo.upper())


@dataclass
class Resolucion:
    codigo_idm: str | None
    metodo: str  # "equivalencia", "equivalencia_normalizada", "aprendida", "no_resuelto"


@dataclass
class TablaEquivalencias:
    exactas: dict[tuple[str, str], str] = field(default_factory=dict)
    normalizadas: dict[tuple[str, str], str] = field(default_factory=dict)
    aprendidas: dict[tuple[str, str], str] = field(default_factory=dict)

    @classmethod
    def desde(cls, equivalencias: list[Equivalencia], aprendidas: Path | None = None) -> "TablaEquivalencias":
        tabla = cls()
        for e in equivalencias:
            tabla.exactas[(e.proveedor, e.codigo_proveedor.strip().upper())] = e.codigo_idm
            tabla.normalizadas[(e.proveedor, normalizar_codigo_proveedor(e.codigo_proveedor))] = e.codigo_idm
        if aprendidas and aprendidas.exists():
            with aprendidas.open(encoding="utf-8", newline="") as f:
                for fila in csv.DictReader(f, delimiter=";"):
                    tabla.aprendidas[(fila["proveedor"], fila["codigo_proveedor"].strip().upper())] = fila["codigo_idm"]
        return tabla

    def resolver(self, proveedor: str, codigo_proveedor: str | None) -> Resolucion:
        if not codigo_proveedor:
            return Resolucion(None, "no_resuelto")
        clave = (proveedor, codigo_proveedor.strip().upper())
        if clave in self.exactas:
            return Resolucion(self.exactas[clave], "equivalencia")
        if clave in self.aprendidas:
            return Resolucion(self.aprendidas[clave], "aprendida")
        clave_n = (proveedor, normalizar_codigo_proveedor(codigo_proveedor))
        if clave_n in self.normalizadas:
            return Resolucion(self.normalizadas[clave_n], "equivalencia_normalizada")
        return Resolucion(None, "no_resuelto")

    def aprender(self, proveedor: str, codigo_proveedor: str, codigo_idm: str, fichero: Path) -> None:
        """Guarda una equivalencia confirmada por una persona en la bandeja (CSV con ; en datos/)."""
        self.aprendidas[(proveedor, codigo_proveedor.strip().upper())] = codigo_idm
        nuevo = not fichero.exists()
        fichero.parent.mkdir(parents=True, exist_ok=True)
        with fichero.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            if nuevo:
                w.writerow(["proveedor", "codigo_proveedor", "codigo_idm"])
            w.writerow([proveedor, codigo_proveedor.strip().upper(), codigo_idm])
