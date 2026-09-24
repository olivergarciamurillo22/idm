"""Bloqueo de instancia única para tareas programadas: segunda ejecución rechazada, bloqueo caducado sustituido,
liberación al salir aunque falle."""

import os
import time

import pytest

from idm.tareas.bloqueo import Bloqueo, YaEnEjecucion


def test_segunda_instancia_rechazada(tmp_path):
    ruta = tmp_path / "procesar_buzon.lock"
    with Bloqueo(ruta):
        assert ruta.exists()
        with pytest.raises(YaEnEjecucion):
            with Bloqueo(ruta):
                pass
    assert not ruta.exists()


def test_bloqueo_caducado_se_sustituye(tmp_path):
    ruta = tmp_path / "x.lock"
    ruta.write_text("999999 0")
    viejo = time.time() - 10_000
    os.utime(ruta, (viejo, viejo))
    with Bloqueo(ruta, caducidad_segundos=3600):
        assert ruta.read_text().split()[0] == str(os.getpid())


def test_se_libera_aunque_falle(tmp_path):
    ruta = tmp_path / "x.lock"
    with pytest.raises(RuntimeError):
        with Bloqueo(ruta):
            raise RuntimeError("boom")
    assert not ruta.exists()
