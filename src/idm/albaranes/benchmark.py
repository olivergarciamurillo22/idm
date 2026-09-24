"""Benchmark del lector: por cada <nombre>.json de verdad busca el documento del mismo nombre (pdf, jpg, png, heic) y
mide aciertos por campo (tipo, cif, número, fecha, pedido, nº líneas; por línea código, cantidad, precio, dto, importe).
Cuenta documentos completamente procesables. Imprime una tabla; no decide nada ni guarda resultados."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from idm.albaranes.extraer import EXTENSIONES_IMAGEN, EXTENSIONES_PDF
from idm.albaranes.lector import LectorAutomatico, LectorDocumentos
from idm.dominio.dinero import a_decimal
from idm.dominio.estados import ResultadoLectura

CAMPOS_CABECERA = ("tipo", "cif", "numero", "fecha", "nuestro_pedido", "n_lineas")
CAMPOS_LINEA = ("codigo_proveedor", "cantidad", "precio_bruto", "descuento_pct", "importe")
CAMPOS_COMPLETO = ("numero", "fecha", "n_lineas")  # con estos bien y todas las líneas bien, el documento es "completo"


@dataclass
class ResultadoDocumento:
    nombre: str
    resultado_lectura: ResultadoLectura
    confianza: float
    aciertos: int = 0
    total: int = 0
    completo: bool = False
    tiempo_s: float = 0.0


@dataclass
class Resultado:
    aciertos: dict[str, int] = field(default_factory=dict)
    totales: dict[str, int] = field(default_factory=dict)
    detalle: list[str] = field(default_factory=list)
    documentos: list[ResultadoDocumento] = field(default_factory=list)

    def anotar(self, campo: str, ok: bool, documento: str, esperado, obtenido) -> bool:
        self.totales[campo] = self.totales.get(campo, 0) + 1
        if ok:
            self.aciertos[campo] = self.aciertos.get(campo, 0) + 1
        else:
            self.detalle.append(f"{documento} · {campo}: esperado {esperado!r}, obtenido {obtenido!r}")
        return ok

    def tabla(self) -> str:
        filas = ["campo                 aciertos  total  %"]
        for campo in list(CAMPOS_CABECERA) + [f"linea.{c}" for c in CAMPOS_LINEA]:
            t = self.totales.get(campo, 0)
            a = self.aciertos.get(campo, 0)
            filas.append(f"{campo:<22}{a:>8}{t:>7}  {100 * a / t if t else 0:5.1f}")
        n = len(self.documentos)
        if n:
            filas.append("")
            filas.append(
                f"documentos: {n} · completamente procesables: {sum(1 for d in self.documentos if d.completo)} · "
                + " · ".join(
                    f"{r.value}: {sum(1 for d in self.documentos if d.resultado_lectura == r)}"
                    for r in ResultadoLectura
                    if any(d.resultado_lectura == r for d in self.documentos)
                )
            )
        return "\n".join(filas)

    def resumen(self) -> dict:
        return {
            "documentos": len(self.documentos),
            "completos": sum(1 for d in self.documentos if d.completo),
            "por_campo": {c: [self.aciertos.get(c, 0), self.totales.get(c, 0)] for c in self.totales},
            "por_documento": [
                {
                    "nombre": d.nombre,
                    "lectura": d.resultado_lectura,
                    "confianza": d.confianza,
                    "aciertos": f"{d.aciertos}/{d.total}",
                    "completo": d.completo,
                }
                for d in self.documentos
            ],
        }


def _igual_decimal(esperado, obtenido) -> bool:
    e, o = a_decimal(esperado) if esperado is not None else None, obtenido
    if e is None and o is None:
        return True
    if e is None or o is None:
        return False
    return e == o


def documentos_de(carpeta: Path, incluir_imagenes: bool = True) -> list[tuple[Path, Path]]:
    """Parejas (documento, json de verdad): <nombre>.<ext> junto a <nombre>.json, más <nombre>_foto.* si se piden."""
    parejas = []
    for verdad in sorted(Path(carpeta).glob("*.json")):
        if verdad.name in ("inventario.json",):
            continue
        candidatos = [
            p
            for p in sorted(carpeta.iterdir())
            if p.stem == verdad.stem and p.suffix.lower() in EXTENSIONES_PDF | EXTENSIONES_IMAGEN
        ]
        if incluir_imagenes:
            candidatos += sorted(
                p for p in carpeta.glob(f"{verdad.stem}_foto.*") if p.suffix.lower() in EXTENSIONES_IMAGEN
            )
        elif candidatos:
            candidatos = [p for p in candidatos if p.suffix.lower() in EXTENSIONES_PDF] or candidatos[:1]
        parejas += [(c, verdad) for c in candidatos]
    return parejas


def ejecutar(carpeta: Path, lector: LectorDocumentos | None = None, incluir_imagenes: bool = True) -> Resultado:
    import time

    lector = lector or LectorAutomatico()
    resultado = Resultado()
    for documento, verdad in documentos_de(Path(carpeta), incluir_imagenes):
        esperado = json.loads(verdad.read_text(encoding="utf-8"))
        inicio = time.perf_counter()
        doc = lector.leer(documento)
        rd = ResultadoDocumento(
            documento.name, doc.resultado, doc.confianza, tiempo_s=round(time.perf_counter() - inicio, 2)
        )
        nombre = documento.name
        oks = {
            "tipo": resultado.anotar("tipo", doc.tipo == esperado["tipo"], nombre, esperado["tipo"], doc.tipo),
            "cif": resultado.anotar("cif", doc.cif == esperado.get("cif"), nombre, esperado.get("cif"), doc.cif),
            "numero": resultado.anotar(
                "numero", doc.numero == esperado["numero"], nombre, esperado["numero"], doc.numero
            ),
            "fecha": resultado.anotar(
                "fecha",
                doc.fecha is not None and doc.fecha.isoformat() == esperado["fecha"],
                nombre,
                esperado["fecha"],
                doc.fecha,
            ),
            "nuestro_pedido": resultado.anotar(
                "nuestro_pedido",
                doc.nuestro_pedido == esperado.get("nuestro_pedido"),
                nombre,
                esperado.get("nuestro_pedido"),
                doc.nuestro_pedido,
            ),
            "n_lineas": resultado.anotar(
                "n_lineas", len(doc.lineas) == len(esperado["lineas"]), nombre, len(esperado["lineas"]), len(doc.lineas)
            ),
        }
        lineas_ok = True
        for i, linea_esperada in enumerate(esperado["lineas"]):
            obtenida = doc.lineas[i] if i < len(doc.lineas) else None
            for campo in CAMPOS_LINEA:
                valor = getattr(obtenida, campo) if obtenida else None
                if campo == "codigo_proveedor":
                    ok = (valor or None) == (linea_esperada.get(campo) or None)
                else:
                    ok = _igual_decimal(linea_esperada.get(campo), valor)
                lineas_ok &= resultado.anotar(f"linea.{campo}", ok, f"{nombre}[{i}]", linea_esperada.get(campo), valor)
        rd.aciertos = sum(oks.values()) + sum(1 for c in resultado.detalle if False)  # cabecera
        rd.total = len(oks)
        rd.completo = all(oks[c] for c in CAMPOS_COMPLETO) and lineas_ok
        resultado.documentos.append(rd)
    return resultado
