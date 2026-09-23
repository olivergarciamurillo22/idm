"""generar_pedidos: encargos pendientes (+ necesidades del mes) → un pedido por proveedor: PDF, correo, hoja Siddex.
Uso: ejecutar.bat generar_pedidos [--hoja SEPT_26] [--solo-encargos] [--enviar]   (sin --enviar: correo simulado .eml)
Marca los encargos como EN_PEDIDO con el número provisional."""

import argparse
import shutil
from datetime import date
from pathlib import Path

from idm import config
from idm.almacen.documentos import Evento, Repositorio
from idm.almacen.sesion import abrir
from idm.dominio.estados import EstadoEncargo
from idm.encargos.registro import EncargosJSONL, RepositorioEncargos
from idm.necesidades import mapa as mapa_mod
from idm.necesidades.calculo import calcular
from idm.necesidades.planning import leer_planning
from idm.pedidos import enviar, exportar_siddex, generar, pdf
from idm.siddex.desde_excel import SiddexDesdeExcel
from idm.siddex.gateway import SiddexGateway


def ejecutar(
    cfg: config.Config,
    gateway: SiddexGateway,
    repositorio: RepositorioEncargos,
    correo: enviar.Correo,
    hoja: str | None,
    fecha: date | None = None,
    mapa: Path = mapa_mod.RUTA_MAPA_POR_DEFECTO,
    almacen: Repositorio | None = None,
) -> list[str]:
    fecha = fecha or date.today()
    informe: list[str] = []
    necesidades = []
    if hoja:
        planning = leer_planning(cfg.ruta_planning, hoja)
        resultado = calcular(planning, gateway, mapa_mod.cargar_mapa(mapa), hoja=hoja)
        necesidades = resultado.necesidades
        informe += [f"AVISO necesidades: {t}" for t in resultado.incidencias]
    encargos = repositorio.listar(EstadoEncargo.PENDIENTE)
    articulos = gateway.articulos()
    proveedores = gateway.proveedores()
    por_clave = {p.clave: p for p in proveedores}
    r = generar.generar(necesidades, encargos, articulos, proveedores, fecha)
    informe += [f"AVISO sin proveedor: {t}" for t in r.sin_proveedor]

    for pedido in r.pedidos:
        prov = por_clave.get(pedido.proveedor)
        ruta_pdf = pdf.generar_pdf(pedido, prov, cfg.empresa, cfg.ruta_pedidos_pdf)
        if cfg.ruta_pedidos_transmitidos:
            cfg.ruta_pedidos_transmitidos.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ruta_pdf, cfg.ruta_pedidos_transmitidos / ruta_pdf.name)
        linea = f"{pedido.numero} {pedido.proveedor}: {len(pedido.lineas)} líneas, {pedido.total} € → {ruta_pdf.name}"
        if prov and prov.email:
            destino = correo.enviar(enviar.componer(pedido, prov, cfg.empresa, ruta_pdf))
            linea += f" · correo: {destino}"
        else:
            linea += " · SIN CORREO del proveedor (no se envía)"
        informe.append(linea)
        if almacen is not None:
            almacen.guardar_pedido(pedido)
            almacen.registrar_evento(
                Evento(
                    tipo="pedido.generado",
                    datos={
                        "pedido": pedido.numero,
                        "proveedor": pedido.proveedor,
                        "lineas": len(pedido.lineas),
                        "pdf": str(ruta_pdf),
                    },
                )
            )
            if prov and prov.email:
                almacen.registrar_evento(
                    Evento(
                        tipo="correo.enviado",
                        datos={"pedido": pedido.numero, "destino": destino, "simulado": cfg.modo_simulacion},
                    )
                )
        ids = r.encargos_por_pedido.get(pedido.numero, [])
        if ids:
            repositorio.marcar(ids, EstadoEncargo.EN_PEDIDO, pedido.numero)
    if r.pedidos:
        ruta_hoja = cfg.ruta_salida / f"pedidos_siddex_{fecha:%Y%m%d}.xlsx"
        hoja_siddex = exportar_siddex.exportar(r.pedidos, por_clave, ruta_hoja)
        informe.append(f"Hoja para Siddex: {hoja_siddex}")
    else:
        informe.append("No hay nada que pedir.")
    return informe


def main(argv: list[str] | None = None) -> int:
    cfg = config.cargar()
    p = argparse.ArgumentParser(description="Genera pedidos por proveedor a partir de encargos y necesidades.")
    p.add_argument("--hoja", help="hoja del planning para incluir las necesidades del mes")
    p.add_argument("--enviar", action="store_true", help="envía por SMTP de verdad (si no, .eml simulado)")
    p.add_argument(
        "--jsonl", action="store_true", help="encargos desde datos/encargos.jsonl en vez de la base de datos"
    )
    args = p.parse_args(argv)
    cfg.crear_carpetas()
    gateway = SiddexDesdeExcel(cfg.ruta_siddex)
    almacen = None
    if args.jsonl:
        repositorio: RepositorioEncargos = EncargosJSONL(cfg.ruta_datos / "encargos.jsonl")
    else:
        _, almacen, repositorio = abrir(cfg)
    if args.enviar and not cfg.modo_simulacion:
        correo: enviar.Correo = enviar.CorreoSMTP(
            cfg.smtp_host, cfg.smtp_puerto, cfg.smtp_usuario, cfg.smtp_clave, cfg.smtp_remitente
        )
    else:
        correo = enviar.CorreoSimulado(cfg.ruta_salida / "correo", cfg.smtp_remitente or "pedidos@simulado.local")
    for linea in ejecutar(cfg, gateway, repositorio, correo, args.hoja, almacen=almacen):
        print(linea)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
