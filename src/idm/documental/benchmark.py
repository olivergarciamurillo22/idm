"""Benchmark A/B de proveedores documentales sobre la misma verdad de referencia (<nombre>.json junto al documento).
Mide cabecera (proveedor, CIF, número, fecha), líneas (referencia, descripción, cantidad, precio, descuento, importe),
estructura (filas, tablas, columnas, asociaciones) y operación (completo, tiempo, coste, campos dudosos). Solo mide."""

import json
import statistics
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

from idm.albaranes.benchmark import documentos_de
from idm.albaranes.lector import _mapear_cabeceras
from idm.albaranes.plantillas import CABECERAS_GENERICAS
from idm.documental.lector import LectorDocumental
from idm.dominio.modelos import DocumentoLeido, LineaLeida
from idm.equivalencias.proveedores import identificar

CABECERA = ("proveedor", "cif", "numero", "fecha")
LINEA = ("codigo_proveedor", "descripcion", "cantidad", "precio_bruto", "descuento_pct", "importe")
LINEA_5 = ("codigo_proveedor", "cantidad", "precio_bruto", "descuento_pct", "importe")  # los de la baseline
UMBRAL_DESCRIPCION = 0.85
RUTA_BASELINE = Path(__file__).with_name("baseline_tesseract.json")


def _norm(texto) -> str:
    return "".join(ch for ch in str(texto or "").upper() if ch.isalnum())


def _decimal(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def _similar(a, b) -> float:
    a, b = " ".join(str(a or "").upper().split()), " ".join(str(b or "").upper().split())
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def campo_linea_ok(campo: str, esperado, obtenido) -> bool:
    if campo == "codigo_proveedor":
        return _norm(esperado) == _norm(obtenido)
    if campo == "descripcion":
        return _similar(esperado, obtenido) >= UMBRAL_DESCRIPCION
    e, o = _decimal(esperado), _decimal(obtenido)
    return e == o


def emparejar(esperadas: list[dict], obtenidas: list[LineaLeida]) -> list[LineaLeida | None]:
    """Cada línea esperada con la obtenida de la misma referencia; si no, la de descripción más parecida; si no, por
    posición. Una obtenida solo se usa una vez."""
    libres = list(range(len(obtenidas)))
    resultado: list[LineaLeida | None] = [None] * len(esperadas)
    for i, e in enumerate(esperadas):
        ref = _norm(e.get("codigo_proveedor"))
        j = next((k for k in libres if ref and _norm(obtenidas[k].codigo_proveedor) == ref), None)
        if j is None and e.get("descripcion"):
            candidatos = [(k, _similar(e["descripcion"], obtenidas[k].descripcion)) for k in libres]
            candidatos = [c for c in candidatos if c[1] >= 0.6]
            j = max(candidatos, key=lambda c: c[1])[0] if candidatos else None
        if j is None and i in libres:
            j = i
        if j is not None:
            resultado[i] = obtenidas[j]
            libres.remove(j)
    return resultado


@dataclass
class DocumentoMedido:
    nombre: str
    tiempo_s: float
    lectura: str
    cabecera: dict[str, bool] = field(default_factory=dict)
    lineas: dict[str, tuple[int, int]] = field(default_factory=dict)
    lineas_completas: tuple[int, int] = (0, 0)
    filas_ok: bool = False
    tablas: int = 0
    tabla_con_columnas: bool = False
    completo: bool = False
    coste_eur: Decimal | None = None
    campos_dudosos: int = 0
    error: str | None = None


def medir_documento(nombre: str, verdad: dict, doc: DocumentoLeido, resultado, tiempo_s: float) -> DocumentoMedido:
    m = DocumentoMedido(nombre, tiempo_s, str(doc.resultado))
    if doc.errores:
        m.error = f"{doc.errores[0].codigo}: {doc.errores[0].mensaje[:120]}"
    clave, _ = identificar(nombre=doc.proveedor_texto, cif=doc.cif)
    if clave is None and doc.texto:
        clave, _ = identificar(nombre=doc.texto[:600])
    obtenidos = {
        "proveedor": clave,
        "cif": doc.cif,
        "numero": doc.numero,
        "fecha": doc.fecha.isoformat() if doc.fecha else None,
    }
    no_visible = set(verdad.get("no_visible", []))
    for c in CABECERA:
        if c in verdad and c not in no_visible:
            m.cabecera[c] = verdad[c] == obtenidos[c]
    esperadas = verdad.get("lineas", [])
    parejas = emparejar(esperadas, doc.lineas)
    for c in LINEA:
        ok = total = 0
        for e, o in zip(esperadas, parejas, strict=True):
            if c not in e:
                continue
            total += 1
            ok += o is not None and campo_linea_ok(c, e.get(c), getattr(o, c))
        m.lineas[c] = (ok, total)
    completas = sum(
        1
        for e, o in zip(esperadas, parejas, strict=True)
        if o is not None and all(campo_linea_ok(c, e.get(c), getattr(o, c)) for c in LINEA if c in e)
    )
    m.lineas_completas = (completas, len(esperadas))
    m.filas_ok = len(doc.lineas) == len(esperadas)
    tablas = getattr(resultado, "tablas", []) or []
    m.tablas = len(tablas)
    m.tabla_con_columnas = any(
        len(_mapear_cabeceras(t.como_filas()[0], CABECERAS_GENERICAS) or {}) >= 4 for t in tablas if t.filas
    )
    cabecera_ok = all(m.cabecera.get(c, True) for c in ("numero", "fecha"))
    m.completo = cabecera_ok and m.filas_ok and completas == len(esperadas) and bool(esperadas)
    m.coste_eur = doc.coste_estimado_eur
    m.campos_dudosos = len(doc.campos_dudosos)
    return m


@dataclass
class ResultadoBenchmark:
    proveedor: str
    documentos: list[DocumentoMedido] = field(default_factory=list)

    def cabecera(self, campo: str) -> tuple[int, int]:
        vals = [d.cabecera[campo] for d in self.documentos if campo in d.cabecera]
        return sum(vals), len(vals)

    def linea(self, campo: str) -> tuple[int, int]:
        return tuple(map(sum, zip(*(d.lineas.get(campo, (0, 0)) for d in self.documentos), strict=True))) or (0, 0)

    def lineas_5(self) -> tuple[int, int]:
        pares = [self.linea(c) for c in LINEA_5]
        return sum(p[0] for p in pares), sum(p[1] for p in pares)

    def contar(self, atributo) -> tuple[int, int]:
        return sum(1 for d in self.documentos if atributo(d)), len(self.documentos)

    def asociaciones(self) -> tuple[int, int]:
        return tuple(map(sum, zip(*(d.lineas_completas for d in self.documentos), strict=True))) or (0, 0)

    def tiempo(self) -> dict[str, float]:
        t = sorted(d.tiempo_s for d in self.documentos) or [0.0]
        return {
            "mediana": round(statistics.median(t), 2),
            "p95": round(t[min(len(t) - 1, round(0.95 * (len(t) - 1)))], 2),
        }

    def coste_medio(self) -> Decimal | None:
        costes = [d.coste_eur for d in self.documentos if d.coste_eur is not None]
        return (sum(costes, Decimal(0)) / len(costes)).quantize(Decimal("0.0001")) if costes else None

    def resumen(self) -> dict:
        return {
            "proveedor": self.proveedor,
            "documentos": len(self.documentos),
            "cabecera": {c: self.cabecera(c) for c in CABECERA},
            "lineas": {c: self.linea(c) for c in LINEA},
            "lineas_5_campos": self.lineas_5(),
            "estructura": {
                "filas": self.contar(lambda d: d.filas_ok),
                "tablas": self.contar(lambda d: d.tablas > 0),
                "columnas": self.contar(lambda d: d.tabla_con_columnas),
                "asociaciones": self.asociaciones(),
            },
            "operacion": {
                "completos": self.contar(lambda d: d.completo),
                "tiempo_s": self.tiempo(),
                "coste_medio_eur_doc": str(self.coste_medio()) if self.coste_medio() is not None else None,
                "campos_baja_confianza": sum(d.campos_dudosos for d in self.documentos),
                "errores": [f"{d.nombre}: {d.error}" for d in self.documentos if d.error],
            },
        }


def ejecutar(carpeta: Path, lector: LectorDocumental, nombre: str) -> ResultadoBenchmark:
    r = ResultadoBenchmark(nombre)
    for documento, verdad in documentos_de(Path(carpeta), incluir_imagenes=True):
        esperado = json.loads(verdad.read_text(encoding="utf-8"))
        inicio = time.perf_counter()
        doc = lector.leer(documento)
        tiempo = round(time.perf_counter() - inicio, 2)
        r.documentos.append(medir_documento(documento.name, esperado, doc, lector.ultimo, tiempo))
    return r


def _f(par) -> str:
    a, t = par
    return f"{a}/{t}" if t else "-"


def tabla_comparada(resultados: list[ResultadoBenchmark], baseline: dict | None = None) -> str:
    """Una columna por proveedor, mismas filas para todos. La baseline congelada va al final como referencia."""
    ancho = 16
    cab = f"{'':<30}" + "".join(f"{r.proveedor:>{ancho}}" for r in resultados)
    filas = [cab, "-" * len(cab)]

    def fila(etiqueta, valores):
        filas.append(f"{etiqueta:<30}" + "".join(f"{v:>{ancho}}" for v in valores))

    fila("DOCUMENTOS", [str(len(r.documentos)) for r in resultados])
    filas.append("CABECERA")
    for c in CABECERA:
        fila(f"  {c}", [_f(r.cabecera(c)) for r in resultados])
    filas.append("LINEAS")
    for c in LINEA:
        fila(f"  {c}", [_f(r.linea(c)) for r in resultados])
    fila("  5 campos (como baseline)", [_f(r.lineas_5()) for r in resultados])
    filas.append("ESTRUCTURA")
    fila("  filas (nº líneas exacto)", [_f(r.contar(lambda d: d.filas_ok)) for r in resultados])
    fila("  tablas devueltas", [_f(r.contar(lambda d: d.tablas > 0)) for r in resultados])
    fila("  columnas reconocidas", [_f(r.contar(lambda d: d.tabla_con_columnas)) for r in resultados])
    fila("  asociaciones (línea entera)", [_f(r.asociaciones()) for r in resultados])
    filas.append("OPERACION")
    fila("  documentos completos", [_f(r.contar(lambda d: d.completo)) for r in resultados])
    fila("  tiempo mediana s", [str(r.tiempo()["mediana"]) for r in resultados])
    fila("  tiempo p95 s", [str(r.tiempo()["p95"]) for r in resultados])
    fila("  coste medio €/doc", [str(r.coste_medio() if r.coste_medio() is not None else "-") for r in resultados])
    fila("  campos baja confianza", [str(sum(d.campos_dudosos for d in r.documentos)) for r in resultados])
    fila("  errores", [str(sum(1 for d in r.documentos if d.error)) for r in resultados])
    if baseline:
        c = baseline["cabecera"]
        filas += [
            "",
            f"BASELINE CONGELADA {baseline['proveedor']} ({baseline['fecha']}, métrica benchmark_lector): "
            f"número {_f(c['numero'])} · fecha {_f(c['fecha'])} · cif {_f(c['cif'])} · "
            f"líneas {_f(baseline['lineas_5_campos'])} · completos {_f(baseline['completos'])}",
        ]
    return "\n".join(filas)


def cargar_baseline(ruta: Path = RUTA_BASELINE) -> dict | None:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
