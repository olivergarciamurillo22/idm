# CLAUDE.md · idm-compras

Instrucciones para cualquier asistente (Claude Code u otro) que trabaje en este repositorio.

## NORMA ABSOLUTA: nada de Nuray

- Este proyecto es de **Oliver García Murillo** (GitHub: `olivergarciamurillo22`) y Pedro, para IDM.
- **No tiene ninguna relación con Nuray.** Está prohibido:
  - hacer `git push` a cualquier remoto, cuenta u organización de Nuray (`nuraydevs` o similar);
  - usar la sesión de `gh` de `nuraydevs` para crear repos, issues o PRs de este proyecto;
  - copiar código, configuración, `.env`, credenciales, dominios o recursos (Vercel, Supabase, etc.) de Nuray aquí, ni de aquí a Nuray;
  - mencionar Nuray en commits, documentación, README o código.
- El único remoto válido es `github.com/olivergarciamurillo22/idm` (antes se llamó `idm-compras`; la carpeta local conserva ese nombre). El hook `.githooks/pre-push` solo deja empujar a `github.com/olivergarciamurillo22/`.
- El remoto (`git@github.com:olivergarciamurillo22/idm.git`) usa la Deploy Key `~/.ssh/idm_compras` fijada en la config local (`core.sshCommand`). No se usa `gh` ni ninguna credencial de Nuray. Push solo cuando Oliver lo pide; nunca `--force` sin su autorización explícita.
- Autoría de commits en este repo: `olivergarciamurillo22 <replika.agency@gmail.com>` (config local, no global).
- Si alguna vez hiciera falta `gh`, la sesión debe ser `olivergarciamurillo22`; si no lo es, no crear ni empujar nada.

## Qué es este proyecto

Automatización del circuito de compras de IDM (pedido → albarán → recepción → factura) alrededor del ERP Siddex.
Leer `ARQUITECTURA.md` antes de tocar nada. Los principios de ahí no se negocian.

## Reglas de trabajo

- **Ningún dato real de IDM entra en git**: `datos/` está ignorada; los tests usan `fixtures/` (ficticios, con valores
  inventados). `tests/unit/test_sin_identificadores_reales.py` guarda huellas de identificadores reales conocidos y falla
  si vuelven; el hook `pre-commit` bloquea documentos fuera de fixtures. Material real (fotos, exports, verdad de
  referencia, mapa de productos, códigos de proveedor en Siddex) solo en `datos/`.
- **Ningún documento real sale de la máquina** sin autorización escrita de IDM: `ALLOW_EXTERNAL_DOCUMENT_PROCESSING`
  y `EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED` en `.env`, más `--autorizo-envio-externo` en el benchmark. Para probar una
  clave cloud, `tests/cloud` envía solo la imagen sintética del repositorio.
- **Lectura de documentos**: cloud (Azure, Mistral) como vía principal detrás de `DocumentProvider`; Tesseract congelado
  como respaldo y baseline. No instalar más OCR local pesado ni optimizar Tesseract con trucos para las fotos de prueba.
- **El modelo lee, no escribe**: la IA solo extrae datos de documentos que entran. Decisiones = código determinista.
- **Dinero con `Decimal`**, redondeo solo en `src/idm/dominio/dinero.py`.
- **Windows primero**: todo texto se lee y escribe con `encoding="utf-8"` (lo vigila `tests/unit/test_calidad_codigo.py`),
  los ficheros se abren con `with`, nada de rutas con `/` fijas en código de producción.
- **Los tests no leen el `.env` del desarrollador** (fixture automática en `tests/conftest.py`); una prueba que necesite
  configuración la pone con `monkeypatch.setenv` o construyendo `Config`.
- **Español** en nombres de dominio y comentarios. Funciones pequeñas. Docstring de tres líneas por módulo.
- **Sin infraestructura extra**: nada de Docker obligatorio, colas, microservicios, frontend JS. Python + SQLite + FastAPI/Jinja2.
- **Reparto**: Pedro → `necesidades/ encargos/ pedidos/ siddex/ equivalencias/`. Oliver → `albaranes/ documental/ cotejo/ bandeja/`. Compartidos y bloqueados salvo acuerdo → `dominio/ almacen/ fixtures/golden/`. No se toca la carpeta del otro sin avisar.
- **No inventar requisitos**: si algo no está en `docs/` o en `DECISIONES.md`, se pregunta. Cada decisión importante va a `DECISIONES.md` con fecha.
- **Un commit por fase**, con mensaje que dice qué se puede ejecutar ahora que antes no.
- Nunca pedir contraseñas por escrito ni guardarlas en el repo: van en `.env` (ignorado).

## Cómo ejecutar

Estado actual, bloqueos y siguientes pasos: `docs/ESTADO.md`.

```
./ejecutar.sh verificar             # tests + lint + formato + golden + hooks: debe decir TODO VERDE antes de commitear
./ejecutar.sh tests                 # pytest (Windows: ejecutar.bat tests)
./ejecutar.sh lint                  # ruff check + ruff format --check
.venv/bin/ruff format src tests migrations   # formato (antes de cada commit)
./ejecutar.sh calcular_mes --help   # tareas (Windows: ejecutar.bat calcular_mes --help)
```
