#!/bin/sh
# Lanza una tarea de src/idm/tareas con el entorno del proyecto (Mac/Linux). Windows: ejecutar.bat
#   ./ejecutar.sh <tarea> [args]     ./ejecutar.sh tests [args]     ./ejecutar.sh lint
cd "$(dirname "$0")" || exit 1
export PYTHONPATH=src PYTHONIOENCODING=utf-8
tarea="$1"; shift
case "$tarea" in
  ""|ayuda) sed -n '/^:ayuda/,/^exit/p' ejecutar.bat | grep "^echo" | sed 's/^echo //' ;;
  tests) exec .venv/bin/python -m pytest "$@" ;;
  lint) .venv/bin/python -m ruff check src tests migrations && .venv/bin/python -m ruff format --check src tests migrations ;;
  *) exec .venv/bin/python -m "idm.tareas.$tarea" "$@" ;;
esac
