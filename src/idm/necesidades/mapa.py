"""Mapa nombre de planning (texto libre) → código de escandallo en Siddex, con las reglas de variante L y E.
Primero busca el nombre exacto normalizado; si no, separa familia y detecta tokens L (ruedas lisas) y E/ED
(dirección eléctrica); el resto de variantes (alto, ancho, escalón) no cambian lo que se compra."""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from idm.equivalencias.proveedores import normalizar_nombre

RUTA_MAPA_POR_DEFECTO = Path(__file__).with_name("mapa_productos.csv")


@dataclass(frozen=True)
class EntradaMapa:
    nombre: str  # normalizado
    codigo: str | None
    variante: str
    notas: str = ""


@dataclass(frozen=True)
class Resultado:
    codigo: str | None
    variante: str
    familia: str
    metodo: str  # exacto, familia+variante, sin_codigo, no_mapeado


def cargar_mapa(ruta: Path = RUTA_MAPA_POR_DEFECTO) -> dict[str, EntradaMapa]:
    mapa: dict[str, EntradaMapa] = {}
    with ruta.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f, delimiter=";"):
            nombre = normalizar_nombre(fila["nombre_planning"])
            mapa[nombre] = EntradaMapa(nombre, (fila.get("codigo_siddex") or "").strip().upper() or None,
                                       (fila.get("variante") or "base").strip(), fila.get("notas", ""))
    return mapa


def variante_desde_tokens(tokens: list[str]) -> str:
    """'L' → L; 'E' o 'ED' → E; ambos → LE. Los números (2250, 2500 900) y 'CON ESCALON' no cuentan."""
    tiene_l = any(t == "L" for t in tokens)
    tiene_e = any(t in ("E", "ED") for t in tokens)
    if tiene_l and tiene_e:
        return "LE"
    if tiene_l:
        return "L"
    if tiene_e:
        return "E"
    return "base"


def resolver(nombre_planning: str, mapa: dict[str, EntradaMapa]) -> Resultado:
    nombre = normalizar_nombre(nombre_planning)
    if nombre in mapa:
        e = mapa[nombre]
        return Resultado(e.codigo, e.variante, nombre, "exacto" if e.codigo else "sin_codigo")
    tokens = re.split(r"\s+", nombre)
    # Familia = tokens iniciales hasta el primero que sea variante o número.
    familia_tokens: list[str] = []
    for t in tokens:
        if t in ("L", "E", "ED") or t.isdigit():
            break
        familia_tokens.append(t)
    familia = " ".join(familia_tokens)
    variante = variante_desde_tokens(tokens[len(familia_tokens):])
    # Prueba familia + variante, después familia sola si la variante es base.
    candidatos = [f"{familia} {variante}".strip()] if variante != "base" else [familia]
    # Para A4R el planning escribe "A4R-2000-820", "A4R ED", "A4R L 2250": la familia es el primer token.
    if familia_tokens:
        primero = familia_tokens[0]
        candidatos += [f"{primero} {variante}".strip()] if variante != "base" else [primero]
    for c in candidatos:
        if c in mapa:
            e = mapa[c]
            return Resultado(e.codigo, variante, familia, "familia+variante" if e.codigo else "sin_codigo")
    return Resultado(None, variante, familia, "no_mapeado")
