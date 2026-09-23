"""Ejecución de un caso golden: carga albaran/pedido/reglas, coteja y compara con esperado.json.
Solo compara los campos presentes en esperado; devuelve una lista de diferencias legibles.
No lee PDFs: la parte de lectura la añade albaranes/ a través de un lector inyectado."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from idm.dominio.cotejar import cotejar
from idm.dominio.modelos import Albaran, DocumentoLeido, Pedido
from idm.dominio.reglas import REGLAS_POR_DEFECTO, ReglasCotejo

Lector = Callable[[Path], DocumentoLeido]
Interpretador = Callable[[DocumentoLeido], Albaran]


def cargar_json(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def ejecutar_caso(
    carpeta: Path,
    lector: Lector | None = None,
    interpretar: Interpretador | None = None,
) -> list[str]:
    """Devuelve [] si el caso pasa; si no, una diferencia por línea ('campo: esperado ≠ obtenido')."""
    esperado = cargar_json(carpeta / "esperado.json")
    diferencias: list[str] = []

    albaran = _cargar_albaran(carpeta, esperado, lector, interpretar, diferencias)
    if albaran is None:
        return diferencias

    pedido = Pedido(**cargar_json(carpeta / "pedido.json")) if (carpeta / "pedido.json").exists() else None
    reglas = (
        ReglasCotejo(**cargar_json(carpeta / "reglas.json"))
        if (carpeta / "reglas.json").exists()
        else REGLAS_POR_DEFECTO
    )
    if "cotejo" in esperado:
        cotejo = cotejar(albaran, pedido, reglas).model_dump(mode="json")
        _comparar(esperado["cotejo"], _resumen_cotejo(cotejo), "cotejo", diferencias)
    return diferencias


def _cargar_albaran(carpeta, esperado, lector, interpretar, diferencias) -> Albaran | None:
    if (carpeta / "albaran.json").exists():
        return Albaran(**cargar_json(carpeta / "albaran.json"))
    documento = next(iter(carpeta.glob("documento.*")), None)
    if documento is None:
        diferencias.append("caso sin albaran.json ni documento.*")
        return None
    if lector is None or interpretar is None:
        diferencias.append("caso con documento pero sin lector: se salta la lectura")
        return None
    leido = lector(documento)
    if "lectura" in esperado:
        _comparar(esperado["lectura"], leido.model_dump(mode="json"), "lectura", diferencias)
    return interpretar(leido)


def _resumen_cotejo(cotejo: dict) -> dict:
    """Reduce el cotejo a lo que se fija en el golden: estados, totales y tipos de aviso."""
    return {
        **{
            k: cotejo[k]
            for k in ("semaforo", "relacion", "entrega", "precio", "total_albaran", "total_cotejado_pedido")
        },
        "lineas": [
            {
                "semaforo": linea["semaforo"],
                "entrega": linea["entrega"],
                "precio": linea["precio"],
                "avisos": [a["tipo"] for a in linea["avisos"]],
            }
            for linea in cotejo["lineas"]
        ],
        "avisos": [a["tipo"] for a in cotejo["avisos"]],
    }


def _comparar(esperado: Any, obtenido: Any, camino: str, diferencias: list[str]) -> None:
    """Compara solo lo que hay en esperado; listas por posición; dicts por clave."""
    if isinstance(esperado, dict):
        if not isinstance(obtenido, dict):
            diferencias.append(f"{camino}: esperado objeto, obtenido {obtenido!r}")
            return
        for clave, valor in esperado.items():
            _comparar(valor, obtenido.get(clave), f"{camino}.{clave}", diferencias)
    elif isinstance(esperado, list):
        if not isinstance(obtenido, list) or len(obtenido) != len(esperado):
            diferencias.append(f"{camino}: esperado {len(esperado)} elementos, obtenido {obtenido!r}")
            return
        for i, (e, o) in enumerate(zip(esperado, obtenido, strict=True)):
            _comparar(e, o, f"{camino}[{i}]", diferencias)
    elif esperado != obtenido:
        diferencias.append(f"{camino}: esperado {esperado!r} ≠ obtenido {obtenido!r}")
