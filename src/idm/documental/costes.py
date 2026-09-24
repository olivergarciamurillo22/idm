"""Estimación de coste por documento a partir de un fichero de tarifas fechado (tarifas.json o DOCUMENT_PRICING_FILE).
Devuelve coste por documento, por 100, por 1.000 y mensual para el volumen indicado; nunca inventa el volumen de IDM.
Las tarifas cambian: el resultado siempre lleva la fecha de referencia y el aviso del fichero."""

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).with_name("tarifas.json")


@dataclass(frozen=True)
class Tarifas:
    datos: dict

    @classmethod
    def cargar(cls, ruta: Path | None = None) -> "Tarifas":
        ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
        return cls(json.loads(ruta.read_text(encoding="utf-8")))

    @property
    def fecha(self) -> str:
        return self.datos.get("fecha_referencia", "?")

    @property
    def usd_a_eur(self) -> Decimal:
        return Decimal(str(self.datos.get("usd_a_eur", 1)))

    def por_1000_paginas(self, proveedor: str, modelo: str, extras: tuple[str, ...] = ()) -> Decimal | None:
        info = self.datos.get("proveedores", {}).get(proveedor)
        if info is None:
            return None
        modelos = info.get("modelos", {})
        base = modelos.get(modelo) or modelos.get("*")
        if base is None:
            return None
        total = Decimal(str(base["usd_por_1000_paginas"]))
        for extra in extras:
            if e := info.get("extras", {}).get(extra):
                total += Decimal(str(e["usd_por_1000_paginas"]))
        return total


def _r(valor: Decimal, decimales: str = "0.0001") -> Decimal:
    return valor.quantize(Decimal(decimales), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Coste:
    usd: Decimal
    eur: Decimal
    fecha_tarifa: str


def estimar(tarifas: Tarifas, proveedor: str, modelo: str, paginas: int, extras: tuple[str, ...] = ()) -> Coste | None:
    por_mil = tarifas.por_1000_paginas(proveedor, modelo, extras)
    if por_mil is None:
        return None
    usd = por_mil * Decimal(paginas) / Decimal(1000)
    return Coste(_r(usd), _r(usd * tarifas.usd_a_eur), tarifas.fecha)


@dataclass(frozen=True)
class Proyeccion:
    proveedor: str
    modelo: str
    eur_por_documento: Decimal
    eur_por_100: Decimal
    eur_por_1000: Decimal
    eur_mes: Decimal | None
    documentos_mes: int | None
    paginas_por_documento: Decimal
    fecha_tarifa: str

    def texto(self) -> str:
        mes = (
            f"{self.eur_mes} € al mes para {self.documentos_mes} documentos"
            if self.eur_mes is not None
            else "mensual: indicar --documentos-mes (no hay dato de volumen de IDM)"
        )
        return (
            f"{self.proveedor} ({self.modelo}), {self.paginas_por_documento} pág./doc, tarifa del {self.fecha_tarifa}: "
            f"{self.eur_por_documento} €/doc · {self.eur_por_100} €/100 · {self.eur_por_1000} €/1.000 · {mes}"
        )


def proyectar(
    tarifas: Tarifas,
    proveedor: str,
    modelo: str,
    paginas_por_documento: Decimal = Decimal(1),
    documentos_mes: int | None = None,
    extras: tuple[str, ...] = (),
) -> Proyeccion | None:
    por_mil = tarifas.por_1000_paginas(proveedor, modelo, extras)
    if por_mil is None:
        return None
    eur_doc = por_mil * paginas_por_documento / Decimal(1000) * tarifas.usd_a_eur
    return Proyeccion(
        proveedor,
        modelo,
        _r(eur_doc),
        _r(eur_doc * 100, "0.01"),
        _r(eur_doc * 1000, "0.01"),
        _r(eur_doc * documentos_mes, "0.01") if documentos_mes is not None else None,
        documentos_mes,
        paginas_por_documento,
        tarifas.fecha,
    )
