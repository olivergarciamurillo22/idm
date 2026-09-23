"""procesar_buzon: descarga adjuntos de los buzones IMAP (o lee datos/entrada), procesa cada documento y lo guarda.
Uso: ejecutar.bat procesar_buzon [--carpeta ruta] [--sin-imap]      (pensado para la Tarea programada cada 10 min)
Imprime un resumen por documento; los detalles quedan en la bandeja y en la tabla de eventos."""

import argparse
from pathlib import Path

from idm import config
from idm.albaranes.buzon import BuzonIMAP, CarpetaEntrada, DocumentoEntrante, FuenteDocumentos, RegistroProcesados
from idm.albaranes.lector import LectorAutomatico
from idm.almacen.documentos import Repositorio
from idm.almacen.sesion import abrir
from idm.cotejo.procesar import procesar
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.siddex.gateway import SiddexGateway


def ejecutar(
    entrantes: list[DocumentoEntrante], gateway: SiddexGateway, repo: Repositorio, cfg: config.Config
) -> list[str]:
    tabla = TablaEquivalencias.desde(gateway.equivalencias(), cfg.ruta_datos / "equivalencias_aprendidas.csv")
    lector = LectorAutomatico(
        texto=__import__("idm.albaranes.lector", fromlist=["LectorTextoPDF"]).LectorTextoPDF(
            cifs_propios={cfg.empresa.get("cif", "")} if cfg.empresa.get("cif") else None
        )
    )
    informe = []
    for entrante in entrantes:
        r = procesar(entrante, lector, gateway, tabla, repo, cfg.ruta_procesados)
        d = r.documento
        informe.append(
            f"{r.motivo:<18} {d.tipo:<8} {d.proveedor:<16} {d.numero:<22} {d.semaforo or '-':<6} "
            f"avisos={d.n_avisos} ({entrante.ruta.name})"
        )
    return informe


def fuentes(cfg: config.Config, carpeta: Path | None, sin_imap: bool) -> list[FuenteDocumentos]:
    resultado: list[FuenteDocumentos] = [CarpetaEntrada(carpeta or cfg.ruta_entrada)]
    if not sin_imap:
        registro = RegistroProcesados(cfg.ruta_datos / "correos_procesados.jsonl")
        resultado += [BuzonIMAP(b, cfg.ruta_entrada, registro) for b in cfg.buzones]
    return resultado


def main(argv: list[str] | None = None) -> int:
    cfg = config.cargar()
    p = argparse.ArgumentParser(description="Procesa los documentos que han llegado.")
    p.add_argument("--carpeta", type=Path, default=None, help="carpeta de entrada (por defecto RUTA_ENTRADA)")
    p.add_argument("--sin-imap", action="store_true", help="no consulta los buzones, solo la carpeta")
    args = p.parse_args(argv)
    cfg.crear_carpetas()
    entrantes: list[DocumentoEntrante] = []
    imap_primero = [f for f in fuentes(cfg, args.carpeta, args.sin_imap) if isinstance(f, BuzonIMAP)]
    for fuente in imap_primero:  # descargan a la carpeta de entrada
        try:
            fuente.pendientes()
        except Exception as exc:  # noqa: BLE001 - un buzón caído no debe parar la carpeta
            print(f"AVISO buzón {fuente.buzon.usuario}: {exc}")
    entrantes = CarpetaEntrada(args.carpeta or cfg.ruta_entrada).pendientes()
    if not entrantes:
        print("Nada nuevo.")
        return 0
    sesion, repo, _ = abrir(cfg)
    try:
        for linea in ejecutar(entrantes, SiddexDesdeExcel(cfg.ruta_siddex), repo, cfg):
            print(linea)
    finally:
        sesion.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
