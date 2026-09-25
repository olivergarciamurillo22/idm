"""Concurrencia real con SQLite en modo WAL: la bandeja atiende en varios hilos (una sesión por hilo) mientras la tarea
programada escribe desde otro proceso (aquí, otra conexión independiente). Nada debe fallar con "database is locked"
ni mezclar sesiones entre hilos."""

import threading

from sqlalchemy import text

from idm import config
from idm.almacen.documentos import DocumentoRegistrado, Evento
from idm.almacen.sesion import abrir, migrar, motor
from idm.dominio.estados import TipoDocumento


def _cfg(tmp_path):
    return config.Config(
        ruta_datos=tmp_path,
        ruta_entrada=tmp_path,
        ruta_procesados=tmp_path,
        ruta_siddex=tmp_path,
        ruta_planning=tmp_path / "x",
        ruta_pedidos_pdf=tmp_path,
        ruta_salida=tmp_path,
        ruta_pedidos_transmitidos=None,
        database_url=f"sqlite:///{tmp_path / 'idm.db'}",
        modo_simulacion=True,
    )


def _doc(i: int, origen: str) -> DocumentoRegistrado:
    return DocumentoRegistrado(
        sha256=f"{origen}{i:060d}"[:64].ljust(64, "0"),
        tipo=TipoDocumento.ALBARAN,
        proveedor="PROV",
        numero=f"{origen}-{i}",
        numero_original=f"{origen}-{i}",
        ruta="x",
    )


def test_wal_activo(tmp_path):
    cfg = _cfg(tmp_path)
    migrar(cfg.database_url)
    with motor(cfg.database_url).connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_hilos_y_otro_proceso_escribiendo_a_la_vez(tmp_path):
    cfg = _cfg(tmp_path)
    migrar(cfg.database_url)
    _, repo_bandeja, _ = abrir(cfg)  # como servir_bandeja: una instancia compartida por todos los hilos
    _, repo_tarea, _ = abrir(cfg)  # como procesar_buzon: su propio motor (otro proceso en producción)
    errores: list[BaseException] = []

    def trabajo(repo, origen, n=15):
        try:
            for i in range(n):
                d = repo.guardar(_doc(i, origen))
                repo.registrar_evento(Evento(tipo="documento.recibido", documento_id=d.id))
                repo.listar()
        except BaseException as exc:  # noqa: BLE001 - se comprueba abajo
            errores.append(exc)

    hilos = [threading.Thread(target=trabajo, args=(repo_bandeja, f"b{k}")) for k in range(4)]
    hilos.append(threading.Thread(target=trabajo, args=(repo_tarea, "t")))
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=120)
    assert not errores, errores[:3]
    assert len(repo_tarea.listar()) == 5 * 15
    assert len(repo_bandeja.eventos()) == 5 * 15
