@echo off
REM Lanza una tarea de src\idm\tareas con el entorno del proyecto (Windows).
REM   ejecutar.bat <tarea> [args]      ej.: ejecutar.bat procesar_buzon --sin-imap
REM   ejecutar.bat tests [args]        pytest
REM   ejecutar.bat lint                ruff check + ruff format --check
REM   ejecutar.bat ayuda               lista de tareas
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONPATH=src"
set "PYTHONIOENCODING=utf-8"
if not exist ".venv\Scripts\python.exe" (
  echo No existe .venv. Crea el entorno: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
if "%~1"=="" goto ayuda
set "TAREA=%~1"
set "ARGS=%*"
if "%ARGS%"=="%TAREA%" (set "RESTO=") else (call set "RESTO=%%ARGS:*%TAREA% =%%")
if /i "%TAREA%"=="ayuda" goto ayuda
if /i "%TAREA%"=="tests" (
  .venv\Scripts\python.exe -m pytest %RESTO%
  exit /b %errorlevel%
)
if /i "%TAREA%"=="lint" (
  .venv\Scripts\python.exe -m ruff check src tests migrations && .venv\Scripts\python.exe -m ruff format --check src tests migrations
  exit /b %errorlevel%
)
.venv\Scripts\python.exe -m idm.tareas.%TAREA% %RESTO%
exit /b %errorlevel%

:ayuda
echo Tareas disponibles:
echo   migrar             crea o actualiza datos\idm.db
echo   procesar_buzon     procesa buzones IMAP y datos\entrada  (--sin-imap, --carpeta X, --fichero X, --reprocesar)
echo   servir_bandeja     bandeja de revision en http://ip:8000
echo   calcular_mes       necesidades del mes  (--hoja SEPT_26)
echo   generar_pedidos    pedidos por proveedor desde encargos y necesidades
echo   benchmark_lector   aciertos por campo del lector
echo   ejecutar_golden    golden dataset
echo   tests / lint       pytest / ruff
exit /b 0
