"""Registro de proveedores conocidos: clave estable, código en Siddex, CIF y nombres con los que aparecen.
Es la única tabla que une lo que dice un documento (nombre, CIF) con la clave que usan reglas y plantillas.
No decide nada sobre precios ni pedidos; los datos reales (códigos, CIF) se completan desde el Maestro."""

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from idm.dominio.modelos import Proveedor

# Datos reales (códigos Siddex, CIF, correos) de los proveedores: NUNCA en git. Van en datos/proveedores_conocidos.csv
# con columnas clave;codigo_siddex;cif;nombre;patrones_nombre (separados por |);email. Se funden con CONOCIDOS.
NOMBRE_CSV_LOCAL = "proveedores_conocidos.csv"
_locales: dict[str, "ProveedorConocido"] = {}


@dataclass(frozen=True)
class ProveedorConocido:
    clave: str
    nombre: str
    codigo_siddex: str | None = None
    cif: str | None = None
    patrones_nombre: tuple[str, ...] = field(default_factory=tuple)  # regex sobre el nombre normalizado
    email: str | None = None


# Reales (códigos y CIF se rellenan desde el Maestro de Proveedores; los nombres vienen del AS-IS).
# Ficticios (FICT_*) solo para fixtures y tests.
CONOCIDOS: tuple[ProveedorConocido, ...] = (
    ProveedorConocido("LA_CEPA", "Recambios La Cepa", patrones_nombre=(r"LA CEPA",)),
    ProveedorConocido("RECACOR", "RECACOR", patrones_nombre=(r"RECACOR",)),
    ProveedorConocido("CRUZ", "Complementos y Suministros Cruz", patrones_nombre=(r"SUMINISTROS CRUZ",)),
    ProveedorConocido("MEYRAS", "Grupo Electro Meyras", patrones_nombre=(r"MEYRAS",)),
    ProveedorConocido("BONDIOLI", "Bondioli", patrones_nombre=(r"BONDIOLI",)),
    ProveedorConocido("JUCAMP", "Jucamp", patrones_nombre=(r"JUCAMP",)),
    ProveedorConocido("HIERROS_TURIA", "Hierros Turia", patrones_nombre=(r"HIERROS TURIA",)),
    ProveedorConocido("ALSIMET", "Alsimet", patrones_nombre=(r"ALSIMET",)),
    ProveedorConocido("HIERROS_VELEZ", "Hierros Vélez", patrones_nombre=(r"HIERROS VELEZ",)),
    ProveedorConocido(
        "FICT_VEGA",
        "Suministros Ficticios La Vega S.L.",
        codigo_siddex="9001",
        cif="B00000001",
        patrones_nombre=(r"FICTICIOS LA VEGA",),
    ),
    ProveedorConocido(
        "FICT_RECAMBIOS",
        "Recambios Ejemplo S.A.",
        codigo_siddex="9002",
        cif="A00000002",
        patrones_nombre=(r"RECAMBIOS EJEMPLO",),
    ),
    ProveedorConocido(
        "FICT_ELECTRO",
        "Electro Ficticio S.L.",
        codigo_siddex="9003",
        cif="B00000003",
        patrones_nombre=(r"ELECTRO FICTICIO",),
    ),
)


def cargar_locales(ruta: Path | None) -> int:
    """Carga (o recarga) los proveedores del CSV local. Devuelve cuántos. Sin fichero → 0, sin error."""
    _locales.clear()
    if ruta is None or not Path(ruta).exists():
        return 0
    with Path(ruta).open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f, delimiter=";"):
            clave = (fila.get("clave") or "").strip().upper()
            if not clave:
                continue
            patrones = tuple(p.strip() for p in (fila.get("patrones_nombre") or "").split("|") if p.strip())
            _locales[clave] = ProveedorConocido(
                clave,
                (fila.get("nombre") or clave).strip(),
                (fila.get("codigo_siddex") or "").strip() or None,
                (fila.get("cif") or "").strip() or None,
                patrones,
                (fila.get("email") or "").strip() or None,
            )
    return len(_locales)


def conocidos() -> tuple[ProveedorConocido, ...]:
    """CONOCIDOS (versionado, sin datos sensibles) completado con lo local: el local manda si repite clave."""
    base = {p.clave: p for p in CONOCIDOS}
    for clave, local in _locales.items():
        previo = base.get(clave)
        base[clave] = ProveedorConocido(
            clave,
            local.nombre or (previo.nombre if previo else clave),
            local.codigo_siddex or (previo.codigo_siddex if previo else None),
            local.cif or (previo.cif if previo else None),
            tuple(dict.fromkeys((previo.patrones_nombre if previo else ()) + local.patrones_nombre)),
            local.email or (previo.email if previo else None),
        )
    return tuple(base.values())


def normalizar_nombre(texto: str) -> str:
    """Mayúsculas, sin acentos ni puntuación, espacios simples: 'Hierros Vélez, S.L.' → 'HIERROS VELEZ S L'."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", sin_acentos.upper()).strip()


def normalizar_cif(cif: str | None) -> str | None:
    if not cif:
        return None
    return re.sub(r"[^A-Z0-9]", "", cif.upper()) or None


def clave_por_codigo_siddex(codigo: str) -> str | None:
    for p in conocidos():
        if p.codigo_siddex == str(codigo).strip():
            return p.clave
    return None


def identificar(
    nombre: str | None = None, cif: str | None = None, proveedores: list[Proveedor] | None = None
) -> tuple[str | None, str]:
    """Devuelve (clave, metodo). Orden: CIF, nombre en el registro, nombre en la lista del gateway, nada."""
    cif_n = normalizar_cif(cif)
    if cif_n:
        for p in conocidos():
            if normalizar_cif(p.cif) == cif_n:
                return p.clave, "cif"
        for p in proveedores or []:
            if normalizar_cif(p.cif) == cif_n:
                return p.clave, "cif"
    if nombre:
        nombre_n = normalizar_nombre(nombre)
        for p in conocidos():
            if any(re.search(patron, nombre_n) for patron in p.patrones_nombre):
                return p.clave, "nombre"
        for p in proveedores or []:
            candidatos = [p.nombre, *p.alias]
            if any(normalizar_nombre(c) and normalizar_nombre(c) in nombre_n for c in candidatos):
                return p.clave, "nombre"
    return None, "no_resuelto"


def clave_para(codigo_siddex: str | None, nombre: str) -> str:
    """Clave de un proveedor que viene del Maestro: la del registro si se conoce, si no S<código> o el nombre."""
    if codigo_siddex and (clave := clave_por_codigo_siddex(codigo_siddex)):
        return clave
    clave, _ = identificar(nombre=nombre)
    if clave:
        return clave
    if codigo_siddex:
        return f"S{str(codigo_siddex).strip()}"
    return normalizar_nombre(nombre).replace(" ", "_")
