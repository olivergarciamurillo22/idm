"""Normaliza el número de albarán/factura como lo teclea Fernando en Siddex: reglas por proveedor, no generales.
RECACOR imprime 5526/2.063 y en Siddex va 5526/2063; La Cepa imprime AC B26 0100005206 y va B26 0100005206.
No identifica al proveedor (eso es equivalencias/proveedores.py): recibe la clave y el número tal cual."""

import re
from collections.abc import Callable

Regla = Callable[[str], str]


def quitar_puntos(numero: str) -> str:
    return numero.replace(".", "")


def quitar_prefijo(prefijo: str) -> Regla:
    def regla(numero: str) -> str:
        patron = re.compile(r"^\s*" + re.escape(prefijo) + r"\s*", re.IGNORECASE)
        return patron.sub("", numero, count=1)

    return regla


def espacios_simples(numero: str) -> str:
    return " ".join(numero.split())


def mayusculas(numero: str) -> str:
    return numero.upper()


# Tabla de reglas por proveedor (clave del registro de proveedores). Las reales se completan con Fernando.
REGLAS_NUMERO: dict[str, tuple[Regla, ...]] = {
    "RECACOR": (quitar_puntos,),
    "LA_CEPA": (quitar_prefijo("AC"),),
    "FICT_RECAMBIOS": (quitar_puntos,),
    "FICT_VEGA": (quitar_prefijo("AC"),),
    "FICT_ELECTRO": (quitar_prefijo("ALB."), quitar_prefijo("ALB"), quitar_puntos),
}

REGLAS_COMUNES: tuple[Regla, ...] = (espacios_simples, mayusculas)


def normalizar_numero(proveedor: str | None, numero: str) -> str:
    """Aplica las reglas del proveedor (si las hay) y después las comunes (espacios simples, mayúsculas)."""
    resultado = numero.strip()
    for regla in REGLAS_NUMERO.get(proveedor or "", ()):
        resultado = regla(resultado)
    for regla in REGLAS_COMUNES:
        resultado = regla(resultado)
    return resultado.strip()
