# Estado del proyecto y cómo retomarlo

Punto de partida para cualquier sesión de trabajo (Oliver, Pedro o un asistente). Se actualiza al cerrar cada bloque.
Última actualización: 25/09/2026.

## En 1 minuto
- Circuito completo construido: necesidades → encargos → pedidos → lectura de albaranes/facturas → cotejo al céntimo →
  bandeja de revisión, con base de datos, trazabilidad, idempotencia y tareas programadas.
- Lectura de fotos y escaneos por **proveedores documentales** (`docs/DOCUMENT-PROVIDERS.md`): Tesseract local
  congelado como respaldo y baseline; Azure Document Intelligence y Mistral OCR implementados pero **bloqueados** hasta
  que IDM autorice sacar documentos (`ALLOW_EXTERNAL_DOCUMENT_PROCESSING=false`).
- Nada real de IDM en git: `datos/` ignorada, hook `pre-commit`, test guardián con huellas de los identificadores reales.
- Verificación automática en GitHub (Linux y Windows) en cada push: `.github/workflows/verificacion.yml`.

## Antes de tocar nada
```
git pull
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip install -r requirements.txt
git config core.hooksPath .githooks                  # una vez por clon
./ejecutar.sh verificar                              # Windows: ejecutar.bat verificar → debe decir TODO VERDE
```
Leer `CLAUDE.md`, `ARQUITECTURA.md`, `DECISIONES.md` (las últimas entradas) y `docs/PENDIENTE-IDM.md`.

## Cifras de referencia
| Qué | Valor | Dónde |
|---|---|---|
| Suite | 225 tests, 2 cloud saltados, 5 xfail deliberados | `./ejecutar.sh verificar` |
| Baseline Tesseract (9 fotos reales, congelada) | número 8/9 · fecha 9/9 · CIF 9/9 · líneas 33/50 · completos 4/9 | `src/idm/documental/baseline_tesseract.json` |
| Golden | 3 casos, 0 diferencias | `fixtures/golden/` |

## Bloqueado por decisiones o datos externos
| Qué | De quién | Desbloquea |
|---|---|---|
| Autorización escrita para procesar documentos fuera (y con qué proveedor y región) | Ángel | Benchmark cloud con fotos reales, lector de producción |
| Cuenta de Mistral con OCR habilitado (hoy: límite 0 peticiones/min) | Oliver | Probar Mistral |
| Recurso Azure Document Intelligence (endpoint + clave, región UE) | Oliver | Probar Azure |
| Exports reales de Siddex, códigos A4R L/E/LE, mapa de planning | Fernandillo / Miguel | Necesidades y pedidos reales |
| Albaranes de Cruz, Bondioli y Jucamp; facturas que agrupen albaranes | Fernandillo / Fernando | Plantillas y cotejo de facturas reales |
| Reglas P01, P02, factura parcial, descuentos en cascada, número de Meyras | Fernando | Casos `xfail` → golden |
| Reescribir el historial de git para borrar los identificadores reales antiguos | Oliver | Limpieza total del repositorio remoto |

La lista completa y priorizada está en `docs/PENDIENTE-IDM.md`.

## Siguientes pasos que no dependen de nadie
1. Cuando haya cuenta cloud operativa: `IDM_RUN_CLOUD_TESTS=1 python -m pytest tests/cloud` (solo imagen sintética).
2. Con autorización de IDM: `benchmark_documentos --provider benchmark --proveedores tesseract,azure,mistral
   --autorizo-envio-externo` sobre `datos/analisis_real/benchmark` y decidir el motor en `DECISIONES.md`.
3. Con los exports reales: `ejecutar.bat revisar_exports` y ajustar `datos/siddex/columnas.json`.
4. Instalación piloto en el Windows de IDM siguiendo `docs/instalacion-windows.md`.

## Dónde está cada cosa
| Tema | Código | Documentación |
|---|---|---|
| Dominio y cotejo al céntimo | `src/idm/dominio/`, `src/idm/cotejo/` | `ARQUITECTURA.md` |
| Lectura de documentos | `src/idm/albaranes/`, `src/idm/documental/` | `docs/DOCUMENT-PROVIDERS.md`, `docs/reglas-proveedor/` |
| Necesidades, encargos, pedidos, Siddex | `src/idm/necesidades/`, `encargos/`, `pedidos/`, `siddex/` | `docs/as-is/` |
| Base de datos y trazabilidad | `src/idm/almacen/`, `migrations/` | `DECISIONES.md` |
| Bandeja | `src/idm/bandeja/` | `README.md` |
| Material real (nunca en git) | `datos/` | `datos/README.md`, `fixtures/reales/README.md` |
