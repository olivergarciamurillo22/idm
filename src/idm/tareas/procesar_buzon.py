"""procesar_buzon: descarga adjuntos de los buzones IMAP (o lee datos/entrada), procesa cada documento y lo guarda.
Uso: ejecutar.bat procesar_buzon [--carpeta ruta | --fichero ruta | --reprocesar-id ID] [--sin-imap] [--reprocesar]
Cada pasada es una Ejecución con su id, y todos los eventos y trazas la llevan. Instancia única por bloqueo."""

import argparse
from datetime import datetime
from pathlib import Path

from idm import config
from idm.albaranes.buzon import BuzonIMAP, CarpetaEntrada, DocumentoEntrante, RegistroProcesados
from idm.albaranes.extraer import sha256_fichero
from idm.albaranes.lector import lector_por_defecto, tuberias_desde_texto
from idm.almacen.documentos import Ejecucion, Repositorio
from idm.almacen.sesion import abrir
from idm.cotejo.procesar import VERSION_PROCESAMIENTO, Motivo, procesar
from idm.equivalencias import proveedores
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.siddex.gateway import SiddexGateway
from idm.tareas import _consola
from idm.tareas.bloqueo import Bloqueo, YaEnEjecucion


def ejecutar(
    entrantes: list[DocumentoEntrante],
    gateway: SiddexGateway,
    repo: Repositorio,
    cfg: config.Config,
    reprocesar: bool = False,
    tarea: str = "procesar_buzon",
) -> list[str]:
    """Procesa la lista dentro de una Ejecución registrada. Devuelve una línea de informe por documento."""
    ejecucion = repo.guardar_ejecucion(Ejecucion(tarea=tarea, version=VERSION_PROCESAMIENTO))
    tabla = TablaEquivalencias.desde(gateway.equivalencias(), cfg.ruta_datos / "equivalencias_aprendidas.csv")
    tuberias = tuberias_desde_texto(cfg.ocr_tuberia)
    lector = lector_por_defecto(cfg.cifs_propios, cfg.ocr_motor, tuberias[0], tuberias[1:])
    informe = [f"Ejecución {ejecucion.id} · versión {VERSION_PROCESAMIENTO} · {len(entrantes)} documento(s)"]
    for entrante in entrantes:
        r = procesar(
            entrante,
            lector,
            gateway,
            tabla,
            repo,
            cfg.ruta_procesados,
            ejecucion_id=ejecucion.id,
            reprocesar=reprocesar,
        )
        d = r.documento
        ejecucion.n_documentos += 1
        if r.motivo in (Motivo.PROCESADO, Motivo.REPROCESADO, Motivo.REQUIERE_OCR):
            ejecucion.n_nuevos += 1
        elif r.motivo in (Motivo.DUPLICADO_SHA, Motivo.DUPLICADO_NUMERO):
            ejecucion.n_duplicados += 1
        elif r.motivo == Motivo.NO_PROCESABLE:
            ejecucion.n_no_procesables += 1
        elif r.motivo == Motivo.ERROR:
            ejecucion.n_errores += 1
        informe.append(
            f"{r.motivo:<22} {d.tipo:<11} {d.proveedor:<16} {d.numero:<22} {d.estado:<14} {d.semaforo or '-':<6} "
            f"avisos={d.n_avisos} ({entrante.ruta.name})"
        )
    ejecucion.fin = datetime.now()
    ejecucion.detalle = {"ficheros": [e.ruta.name for e in entrantes], "reprocesar": reprocesar}
    repo.guardar_ejecucion(ejecucion)
    informe.append(
        f"Fin: nuevos={ejecucion.n_nuevos} duplicados={ejecucion.n_duplicados} "
        f"no_procesables={ejecucion.n_no_procesables} errores={ejecucion.n_errores}"
    )
    return informe


def descargar_buzones(cfg: config.Config) -> list[str]:
    avisos = []
    registro = RegistroProcesados(cfg.ruta_datos / "correos_procesados.jsonl")
    for buzon in cfg.buzones:
        try:
            n = len(BuzonIMAP(buzon, cfg.ruta_entrada, registro).pendientes())
            avisos.append(f"Buzón {buzon.usuario}: {n} adjunto(s) descargado(s)")
        except Exception as exc:  # noqa: BLE001 - un buzón caído no debe parar la carpeta
            avisos.append(f"AVISO buzón {buzon.usuario}: {type(exc).__name__}: {exc}")
    return avisos


def _entrante(ruta: Path, origen: str) -> DocumentoEntrante:
    return DocumentoEntrante(ruta=ruta, sha256=sha256_fichero(ruta), origen=origen)


def main(argv: list[str] | None = None) -> int:
    _consola.preparar()
    cfg = config.cargar()
    proveedores.cargar_locales(cfg.ruta_datos / proveedores.NOMBRE_CSV_LOCAL)
    p = argparse.ArgumentParser(description="Procesa los documentos que han llegado.")
    p.add_argument("--carpeta", type=Path, default=None, help="carpeta de entrada (por defecto RUTA_ENTRADA)")
    p.add_argument("--fichero", type=Path, default=None, help="procesa solo este fichero")
    p.add_argument(
        "--reprocesar-id", default=None, help="vuelve a procesar el documento con este id (fichero archivado)"
    )
    p.add_argument("--reprocesar", action="store_true", help="con --fichero: reprocesa aunque ya esté registrado")
    p.add_argument("--sin-imap", action="store_true", help="no consulta los buzones, solo la carpeta")
    args = p.parse_args(argv)
    cfg.crear_carpetas()
    try:
        with Bloqueo(cfg.ruta_datos / "procesar_buzon.lock"):
            return _correr(cfg, args)
    except YaEnEjecucion as exc:
        print(f"No se ejecuta: {exc}")
        return 2


def _correr(cfg: config.Config, args) -> int:
    sesion, repo, _ = abrir(cfg)
    try:
        reprocesar = args.reprocesar or bool(args.reprocesar_id)
        if args.reprocesar_id:
            doc = repo.obtener(args.reprocesar_id)
            if doc is None or not Path(doc.ruta).exists():
                print(f"No existe el documento {args.reprocesar_id} o su fichero {doc.ruta if doc else ''}")
                return 1
            entrantes = [_entrante(Path(doc.ruta), "reproceso")]
        elif args.fichero:
            if not args.fichero.exists():
                print(f"No existe el fichero {args.fichero}")
                return 1
            entrantes = [_entrante(args.fichero, "fichero")]
        else:
            if not args.sin_imap:
                for aviso in descargar_buzones(cfg):
                    print(aviso)
            entrantes = CarpetaEntrada(args.carpeta or cfg.ruta_entrada).pendientes()
        if not entrantes:
            print("Nada nuevo.")
            return 0
        for linea in ejecutar(entrantes, SiddexDesdeExcel(cfg.ruta_siddex), repo, cfg, reprocesar=reprocesar):
            print(linea)
        return 0
    finally:
        sesion.close()


if __name__ == "__main__":
    raise SystemExit(main())
