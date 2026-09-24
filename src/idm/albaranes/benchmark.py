"""Benchmark del lector: aciertos por campo sobre cada documento con su .json de verdad (fixtures/ficticios/documentos).
Campos: tipo, cif, número, fecha, nuestro pedido, nº de líneas; por línea código, cantidad, precio, descuento, importe.
Imprime una tabla; no decide nada ni guarda resultados."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from idm.albaranes.lector import LectorAutomatico, LectorDocumentos
from idm.dominio.dinero import a_decimal

CAMPOS_CABECERA = ("tipo", "cif", "numero", "fecha", "nuestro_pedido", "n_lineas")
CAMPOS_LINEA = ("codigo_proveedor", "cantidad", "precio_bruto", "descuento_pct", "importe")


@dataclass
class Resultado:
    aciertos: dict[str, int] = field(default_factory=dict)
    totales: dict[str, int] = field(default_factory=dict)
    detalle: list[str] = field(default_factory=list)

    def anotar(self, campo: str, ok: bool, documento: str, esperado, obtenido) -> None:
        self.totales[campo] = self.totales.get(campo, 0) + 1
        if ok:
            self.aciertos[campo] = self.aciertos.get(campo, 0) + 1
        else:
            self.detalle.append(f"{documento} · {campo}: esperado {esperado!r}, obtenido {obtenido!r}")

    def tabla(self) -> str:
        filas = ["campo                 aciertos  total  %"]
        for campo in list(CAMPOS_CABECERA) + [f"linea.{c}" for c in CAMPOS_LINEA]:
            t = self.totales.get(campo, 0)
            a = self.aciertos.get(campo, 0)
            filas.append(f"{campo:<22}{a:>8}{t:>7}  {100 * a / t if t else 0:5.1f}")
        return "\n".join(filas)


def _igual_decimal(esperado, obtenido) -> bool:
    e, o = a_decimal(esperado) if esperado is not None else None, obtenido
    if e is None and o is None:
        return True
    if e is None or o is None:
        return False
    return e == o


def ejecutar(carpeta: Path, lector: LectorDocumentos | None = None, incluir_imagenes: bool = True) -> Resultado:
    lector = lector or LectorAutomatico()
    resultado = Resultado()
    for verdad in sorted(carpeta.glob("*.json")):
        esperado = json.loads(verdad.read_text(encoding="utf-8"))
        candidatos = [verdad.with_suffix(".pdf")]
        if incluir_imagenes:
            candidatos += sorted(carpeta.glob(f"{verdad.stem}_foto.*"))
        for documento in candidatos:
            if not documento.exists():
                continue
            doc = lector.leer(documento)
            nombre = documento.name
            resultado.anotar("tipo", doc.tipo == esperado["tipo"], nombre, esperado["tipo"], doc.tipo)
            resultado.anotar("cif", doc.cif == esperado["cif"], nombre, esperado["cif"], doc.cif)
            resultado.anotar("numero", doc.numero == esperado["numero"], nombre, esperado["numero"], doc.numero)
            resultado.anotar(
                "fecha",
                doc.fecha is not None and doc.fecha.isoformat() == esperado["fecha"],
                nombre,
                esperado["fecha"],
                doc.fecha,
            )
            resultado.anotar(
                "nuestro_pedido",
                doc.nuestro_pedido == esperado.get("nuestro_pedido"),
                nombre,
                esperado.get("nuestro_pedido"),
                doc.nuestro_pedido,
            )
            resultado.anotar(
                "n_lineas", len(doc.lineas) == len(esperado["lineas"]), nombre, len(esperado["lineas"]), len(doc.lineas)
            )
            for i, linea_esperada in enumerate(esperado["lineas"]):
                obtenida = doc.lineas[i] if i < len(doc.lineas) else None
                for campo in CAMPOS_LINEA:
                    valor = getattr(obtenida, campo) if obtenida else None
                    if campo == "codigo_proveedor":
                        ok = (valor or None) == (linea_esperada.get(campo) or None)
                    else:
                        ok = _igual_decimal(linea_esperada.get(campo), valor)
                    resultado.anotar(f"linea.{campo}", ok, f"{nombre}[{i}]", linea_esperada.get(campo), valor)
    return resultado
