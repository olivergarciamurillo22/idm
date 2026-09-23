"""Reglas de negocio parametrizables del cotejo: tolerancia, portes pactados, exceso.
Los valores por defecto son los que dijo IDM: tolerancia cero y exceso siempre a revisión.
No decide nada por sí mismo: cotejar() las lee."""

from decimal import Decimal

from pydantic import BaseModel, Field

from idm.dominio.dinero import CERO


class ReglasCotejo(BaseModel):
    tolerancia_precio: Decimal = CERO  # Fernando: "tiene que cuadrar al céntimo"
    tolerancia_descuento_pct: Decimal = CERO
    aceptar_exceso: bool = False  # más cantidad de la pedida siempre avisa
    # portes pactados por proveedor (clave → importe fijo aceptado sin aviso)
    portes_pactados: dict[str, Decimal] = Field(default_factory=dict)
    # palabras que identifican una línea de portes en la descripción
    palabras_portes: tuple[str, ...] = ("PORTES", "PORTE", "TRANSPORTE", "ENVIO", "ENVÍO")
    # palabras que identifican hierro (fuera del circuito por ahora)
    palabras_hierro: tuple[str, ...] = ("CORTE TUBO", "CHAPA KG")


REGLAS_POR_DEFECTO = ReglasCotejo()


def es_linea_portes(descripcion: str, reglas: ReglasCotejo = REGLAS_POR_DEFECTO) -> bool:
    texto = descripcion.upper()
    return any(palabra in texto for palabra in reglas.palabras_portes)


def es_hierro(descripcion: str, reglas: ReglasCotejo = REGLAS_POR_DEFECTO) -> bool:
    texto = descripcion.upper()
    return any(palabra in texto for palabra in reglas.palabras_hierro)
