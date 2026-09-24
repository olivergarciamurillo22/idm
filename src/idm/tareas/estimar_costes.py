"""estimar_costes: coste por documento, por 100, por 1.000 y mensual de cada proveedor con las tarifas fechadas.
Uso: ejecutar.bat estimar_costes [--documentos-mes 300] [--paginas-por-documento 1] [--provider azure]
El volumen mensual de IDM no se conoce: se pasa como argumento; sin él solo se dan costes unitarios."""

import argparse
from decimal import Decimal

from idm import config
from idm.documental.costes import Tarifas, proyectar
from idm.tareas import _consola


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    cfg = config.cargar()
    p = argparse.ArgumentParser(description="Estima costes de lectura documental.")
    p.add_argument("--documentos-mes", type=int, default=None)
    p.add_argument("--paginas-por-documento", type=Decimal, default=Decimal(1))
    p.add_argument("--provider", default=None, help="por defecto: tesseract, azure y mistral con su modelo configurado")
    args = p.parse_args(argv)
    tarifas = Tarifas.cargar(cfg.document_pricing_file)
    modelos = {"tesseract": "*", "azure": cfg.azure_model, "mistral": cfg.mistral_model}
    extras = {"azure": tuple(cfg.azure_features), "mistral": ("document_annotation",) if cfg.mistral_annotation else ()}
    print(f"Tarifas del {tarifas.fecha}: ORIENTATIVAS, verificar en la web de cada proveedor antes de presupuestar.")
    for nombre in [args.provider] if args.provider else list(modelos):
        pr = proyectar(
            tarifas,
            nombre,
            modelos.get(nombre, "*"),
            args.paginas_por_documento,
            args.documentos_mes,
            extras.get(nombre, ()),
        )
        print(" ", pr.texto() if pr else f"{nombre}: sin tarifa en el fichero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
