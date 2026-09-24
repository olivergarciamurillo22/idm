"""Bloqueo de instancia única para las tareas programadas: si procesar_buzon tarda más de 10 minutos, la siguiente
ejecución no debe pisarla. Fichero de bloqueo creado con O_EXCL (atómico en Windows y Linux) con pid y hora;
si el fichero es más viejo que la caducidad se considera abandonado (proceso muerto) y se sustituye."""

import os
import time
from pathlib import Path


class YaEnEjecucion(Exception):
    pass


class Bloqueo:
    def __init__(self, ruta: Path, caducidad_segundos: int = 2 * 3600) -> None:
        self.ruta = Path(ruta)
        self.caducidad = caducidad_segundos

    def _intentar(self) -> bool:
        try:
            fd = os.open(self.ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()} {time.time():.0f}\n")
        return True

    def __enter__(self) -> "Bloqueo":
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        if self._intentar():
            return self
        try:
            edad = time.time() - self.ruta.stat().st_mtime
        except FileNotFoundError:
            edad = self.caducidad + 1
        if edad > self.caducidad:
            self.ruta.unlink(missing_ok=True)
            if self._intentar():
                return self
        raise YaEnEjecucion(
            f"Otra ejecución tiene el bloqueo {self.ruta} (edad {edad:.0f}s). Si el proceso murió, borra el fichero."
        )

    def __exit__(self, *_exc) -> None:
        self.ruta.unlink(missing_ok=True)
