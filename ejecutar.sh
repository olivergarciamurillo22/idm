#!/bin/sh
# Lanza una tarea de src/idm/tareas con el entorno del proyecto (Mac/Linux). Windows: ejecutar.bat
#   ./ejecutar.sh <tarea> [args]     ./ejecutar.sh tests [args]     ./ejecutar.sh lint     ./ejecutar.sh verificar
cd "$(dirname "$0")" || exit 1
export PYTHONPATH=src PYTHONIOENCODING=utf-8
tarea="$1"; shift
case "$tarea" in
  ""|ayuda) sed -n '/^:ayuda/,/^exit/p' ejecutar.bat | grep "^echo" | sed 's/^echo //' ;;
  tests) exec .venv/bin/python -m pytest "$@" ;;
  lint) .venv/bin/python -m ruff check src tests migrations && .venv/bin/python -m ruff format --check src tests migrations ;;
  verificar)
    echo "== tests" && .venv/bin/python -m pytest -q || exit 1
    echo "== lint" && .venv/bin/python -m ruff check src tests migrations || exit 1
    echo "== formato" && .venv/bin/python -m ruff format --check src tests migrations || exit 1
    echo "== golden" && .venv/bin/python -m idm.tareas.ejecutar_golden || exit 1
    [ "$(git config core.hooksPath)" = ".githooks" ] || echo "AVISO: falta 'git config core.hooksPath .githooks'"
    echo "TODO VERDE" ;;
  *) exec .venv/bin/python -m "idm.tareas.$tarea" "$@" ;;
esac
