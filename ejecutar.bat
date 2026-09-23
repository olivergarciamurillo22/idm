@echo off
REM Lanza una tarea de src\idm\tareas con el entorno del proyecto.
REM Uso: ejecutar.bat <tarea> [args]   (ej.: ejecutar.bat calcular_mes --mes SEPT_26)
cd /d "%~dp0"
set PYTHONPATH=src
set TAREA=%1
shift
.venv\Scripts\python.exe -m idm.tareas.%TAREA% %1 %2 %3 %4 %5 %6 %7 %8 %9
