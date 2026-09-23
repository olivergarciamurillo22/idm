# CLAUDE.md · idm-compras

Instrucciones para cualquier asistente (Claude Code u otro) que trabaje en este repositorio.

## NORMA ABSOLUTA: nada de Nuray

- Este proyecto es de **Oliver García Murillo** (GitHub: `olivergarciamurillo22`) y Pedro, para IDM.
- **No tiene ninguna relación con Nuray.** Está prohibido:
  - hacer `git push` a cualquier remoto, cuenta u organización de Nuray (`nuraydevs` o similar);
  - usar la sesión de `gh` de `nuraydevs` para crear repos, issues o PRs de este proyecto;
  - copiar código, configuración, `.env`, credenciales, dominios o recursos (Vercel, Supabase, etc.) de Nuray aquí, ni de aquí a Nuray;
  - mencionar Nuray en commits, documentación, README o código.
- El único remoto válido es `github.com/olivergarciamurillo22/idm-compras`. El hook `.githooks/pre-push` lo comprueba.
- Autoría de commits en este repo: `olivergarciamurillo22 <replika.agency@gmail.com>` (config local, no global).
- Si la sesión activa de `gh` no es `olivergarciamurillo22`, **no crear ni empujar nada**: avisar a Oliver para que haga `gh auth login` con su cuenta.

## Qué es este proyecto

Automatización del circuito de compras de IDM (pedido → albarán → recepción → factura) alrededor del ERP Siddex.
Leer `ARQUITECTURA.md` antes de tocar nada. Los principios de ahí no se negocian.

## Reglas de trabajo

- **Ningún dato real de IDM entra en git**: `datos/` está ignorada; los tests usan `fixtures/` (ficticios).
- **El modelo lee, no escribe**: la IA solo extrae datos de documentos que entran. Decisiones = código determinista.
- **Dinero con `Decimal`**, redondeo solo en `src/idm/dominio/dinero.py`.
- **Español** en nombres de dominio y comentarios. Funciones pequeñas. Docstring de tres líneas por módulo.
- **Sin infraestructura extra**: nada de Docker obligatorio, colas, microservicios, frontend JS. Python + SQLite + FastAPI/Jinja2.
- **Reparto**: Pedro → `necesidades/ encargos/ pedidos/ siddex/ equivalencias/`. Oliver → `albaranes/ cotejo/ bandeja/`. Compartidos y bloqueados salvo acuerdo → `dominio/ almacen/ fixtures/golden/`. No se toca la carpeta del otro sin avisar.
- **No inventar requisitos**: si algo no está en `docs/` o en `DECISIONES.md`, se pregunta. Cada decisión importante va a `DECISIONES.md` con fecha.
- **Un commit por fase**, con mensaje que dice qué se puede ejecutar ahora que antes no.
- Nunca pedir contraseñas por escrito ni guardarlas en el repo: van en `.env` (ignorado).

## Cómo ejecutar

```
.venv/bin/python -m pytest          # tests (pyproject pone pythonpath=src)
.venv/bin/ruff check src tests      # lint
./ejecutar.sh calcular_mes --ayuda  # tareas (Windows: ejecutar.bat)
```
