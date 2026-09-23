#!/bin/sh
# Lanza una tarea de src/idm/tareas con el entorno del proyecto.
# Uso: ./ejecutar.sh <tarea> [args]   (ej.: ./ejecutar.sh calcular_mes --mes SEPT_26)
cd "$(dirname "$0")" || exit 1
tarea="$1"; shift
PYTHONPATH=src exec .venv/bin/python -m "idm.tareas.$tarea" "$@"
