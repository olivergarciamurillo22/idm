# fixtures

| Carpeta | Qué contiene | ¿Se versiona? |
|---|---|---|
| `ficticios/` | Documentos, exports de Siddex, planning e **imágenes sintéticas** (`imagenes/`, para HEIC y OCR) inventados que imitan la estructura real. Los generan los scripts `generar*.py`. | Sí |
| `reales/` | Documentos reales de IDM **anonimizados deliberadamente** (ver su README y `ANONIMIZACION.md`). | Solo ficheros `*.anonimizado.*` con entrada en `ANONIMIZACION.md`; el resto está ignorado y el hook lo bloquea |
| `golden/` | Casos con resultado esperado en JSON; pytest los ejecuta todos. | Sí (contenido ficticio o anonimizado) |
| `problematicos/` | Casos que hoy NO resolvemos bien y esperan una regla de IDM. Tests `xfail`. | Sí |
| `no_procesables/` | Ficheros corruptos, vacíos, Excel, escaneos sin texto: el lector debe responder con un resultado claro, no vacío. | Sí (generados) |

Los datos reales sin anonimizar viven en `datos/` (ignorada) y nunca aquí.
