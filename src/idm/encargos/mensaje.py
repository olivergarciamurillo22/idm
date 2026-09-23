"""Interpreta un mensaje con formato fijo (WhatsApp, correo o SMS reenviado) y lo convierte en encargos.
Formato por línea: "proveedor ; artículo ; cantidad [; unidad]". Devuelve encargos y errores por línea.
No usa ningún modelo: el formato es fijo a propósito para que se registre sin ambigüedad."""

from dataclasses import dataclass, field

from idm.dominio.dinero import a_decimal
from idm.dominio.estados import OrigenEncargo
from idm.encargos.registro import Encargo

SEPARADORES = (";", "|", "\t")
FORMATO = "proveedor ; artículo ; cantidad [; unidad]   (una línea por encargo)"


@dataclass
class ResultadoMensaje:
    encargos: list[Encargo] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def interpretar(texto: str, quien: str = "") -> ResultadoMensaje:
    resultado = ResultadoMensaje()
    for numero, linea in enumerate(texto.splitlines(), start=1):
        limpio = linea.strip()
        if not limpio or limpio.startswith("#"):
            continue
        separador = next((s for s in SEPARADORES if s in limpio), None)
        if separador is None:
            resultado.errores.append(f"Línea {numero}: falta el separador. Formato: {FORMATO}")
            continue
        partes = [p.strip() for p in limpio.split(separador)]
        if len(partes) < 3:
            resultado.errores.append(f"Línea {numero}: hacen falta proveedor, artículo y cantidad. Formato: {FORMATO}")
            continue
        cantidad = a_decimal(partes[2])
        if cantidad is None or cantidad <= 0:
            resultado.errores.append(f"Línea {numero}: cantidad no válida '{partes[2]}'")
            continue
        resultado.encargos.append(Encargo(
            proveedor=partes[0], articulo=partes[1], cantidad=cantidad,
            unidad=partes[3].upper() if len(partes) > 3 and partes[3] else "UD",
            quien=quien, origen=OrigenEncargo.MENSAJE,
        ))
    return resultado
