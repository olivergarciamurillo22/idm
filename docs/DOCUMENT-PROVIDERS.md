# Proveedores documentales

Cómo lee el programa las fotos y los PDF escaneados, cómo se cambia de motor, qué protege el envío de documentos fuera
de IDM, cuánto cuesta y cómo se compara un motor con otro.

## 1. Arquitectura

```
documento (PDF, JPG, PNG, HEIC)
   │
   ├─ PDF con texto ────────────► pdfplumber (local, gratis, privado) ─────────────┐
   │                                                                               │
   └─ foto / escaneo                                                               │
        │                                                                          │
        ▼  documental/entrada.py                                                   │
   normalización: original para motores locales; JPEG derivado a resolución       │
   completa para externos (HEIC no se envía); sha del original y del enviado       │
        │                                                                          │
        ▼  DocumentProvider.analizar()        ← política de envío externo          │
   ┌──────────────┬──────────────────────────────┬──────────────────────────┐     │
   │ Tesseract    │ Azure Document Intelligence  │ Mistral Document AI (OCR)│     │
   │ (local)      │ (cloud, prebuilt-layout)     │ (cloud, mistral-ocr)     │     │
   └──────────────┴──────────────────────────────┴──────────────────────────┘     │
        │  ResultadoDocumental común: texto, palabras con caja y confianza,         │
        │  tablas, pares clave-valor, campos estructurados, metadatos y coste       │
        ▼  documental/normalizacion.py                                             │
   normalización IDM: plantillas por layout (albaranes/plantillas.py), campos      │
   del proveedor solo para completar huecos, campos dudosos por confianza          │
        │                                                                          │
        ▼                                                                          ▼
   DocumentoLeido (dominio: no sabe qué motor lo leyó) ──► reglas deterministas ──► cotejo ──► bandeja
```

Tres capas, tres responsabilidades:

| Capa | Qué hace | Qué NO hace |
|---|---|---|
| **Respaldo local** (Tesseract) | Leer sin sacar nada de la máquina; desarrollo; baseline del benchmark | No se optimiza más: su baseline está congelada |
| **Document intelligence cloud** (Azure, Mistral) | Leer mejor fotos difíciles, tablas y pares clave-valor | No decide nada; no ve el dominio; no escribe en Siddex |
| **Reglas IDM** (plantillas, normalización, cotejo) | Interpretar lo leído y decidir verde/ámbar al céntimo | No sabe qué motor leyó el documento |

Principio intacto: **el modelo lee, no escribe**. Ningún proveedor aprueba un albarán, cambia un precio ni redacta un
texto. Lo leído por cualquier motor de imagen queda siempre en ÁMBAR para que una persona lo mire.

Código: `src/idm/documental/` (`base.py` contrato y errores, `modelo.py` resultado común, `privacidad.py`, `entrada.py`,
`normalizacion.py`, `tesseract.py`, `azure.py`, `mistral.py`, `google.py` hueco preparado, `router.py`, `lector.py`,
`costes.py` y `tarifas.json`, `registro.py`, `benchmark.py`).

## 2. Configuración (`.env`)

| Variable | Valores | Defecto |
|---|---|---|
| `DOCUMENT_PROVIDER` | `ninguno` · `tesseract` · `azure` · `mistral` · `benchmark` (· `google`, no implementado) | `ninguno` (si no está, se usa el antiguo `OCR_MOTOR`) |
| `DOCUMENT_PROVIDER_FALLBACK` | vacío o un proveedor distinto del principal | vacío |
| `DOCUMENT_PROVIDERS_BENCHMARK` | lista separada por comas; el primero lee, los demás se comparan | `tesseract` |
| `ALLOW_EXTERNAL_DOCUMENT_PROCESSING` | `true` / `false` | **`false`** |
| `EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED` | lista de externos autorizados, p. ej. `mistral` | vacío |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` / `_KEY` | del recurso en el portal de Azure | vacío |
| `AZURE_DOCUMENT_INTELLIGENCE_MODEL` / `_API_VERSION` / `_FEATURES` | `prebuilt-layout` / `2024-11-30` / `keyValuePairs` | esos |
| `MISTRAL_API_KEY` | de console.mistral.ai | vacío |
| `MISTRAL_OCR_MODEL` / `_ENDPOINT` | `mistral-ocr-latest` / `https://api.mistral.ai/v1/ocr` | esos |
| `MISTRAL_OCR_CONFIDENCE` | `word` · `page` · `none` | `word` |
| `MISTRAL_DOCUMENT_ANNOTATION` | `true` para pedir campos estructurados con un esquema fijo (coste aparte) | `false` |
| `DOCUMENT_PRICING_FILE` | fichero de tarifas propio | vacío (`documental/tarifas.json`) |
| `DOCUMENT_PROVIDER_TIMEOUT_S` / `_MAX_RETRIES` | segundos / intentos | `120` / `3` |

Las claves nunca van en el código ni en git, y `Config` las oculta en `repr()`, así que un `print(cfg)` tampoco las filtra.

## 3. Privacidad (protección técnica, no solo documental)

1. **Bandera maestra** `ALLOW_EXTERNAL_DOCUMENT_PROCESSING=false` por defecto.
2. **Lista explícita** `EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED`: cada externo se autoriza por nombre.
3. **Al arrancar**: el router no construye un proveedor externo sin (1) y (2); `procesar_buzon` sale con código 3 y
   el mensaje del motivo sin tocar ningún documento.
4. **En cada llamada**: `ProveedorExternoBase.analizar()` vuelve a comprobar la política antes de preparar la petición.
   Si alguien construye el proveedor a mano saltándose el router, tampoco sale nada.
5. **Benchmark**: además de (1) y (2) exige `--autorizo-envio-externo` en la línea de órdenes.
6. **Fallback**: si Azure (o el que sea) falla técnicamente, el documento queda en `ERROR` recuperable y se reintenta
   con `procesar_buzon --reintentar-pendientes`. Nunca se manda a otro tercero por su cuenta. Un respaldo solo existe si
   se configura en `DOCUMENT_PROVIDER_FALLBACK`, y si es externo pasa también (1) y (2).
7. **Lo que sale**: el PDF o imagen tal cual, o el JPEG derivado del HEIC. Nada más (ni rutas, ni nombres de IDM).
8. **Límite de cuota a cero** (cuenta sin la API habilitada, p. ej. sin facturación): error permanente con mensaje claro,
   sin reintentos inútiles.

Tests que lo comprueban: `tests/unit/test_documental_privacidad.py` (cero peticiones sin autorización, rechazo al
arrancar, código 3, secretos fuera de `repr` y de los registros).

## 4. Trazabilidad

Cada llamada queda en `datos/llamadas_documentales.jsonl` (fuera de git): proveedor, modelo, fecha, sha del original y
del enviado, tiempo, estado (`ok`, `error_transitorio`, `error_permanente`, `rechazado_privacidad`), cuánto devolvió
(páginas, palabras, tablas, pares, campos, caracteres), confianza media, coste estimado, request id y ejecución.
**No** se registran claves, cabeceras, el documento ni su texto. Además, cada documento procesado lleva el evento de
negocio `documento.proveedor_documental` y su `DocumentoLeido` guarda `motor`, `coste_estimado_eur`, `campos_dudosos` y
`metadatos_motor`, que la bandeja enseña.

## 5. Benchmark A/B

Misma verdad de referencia (`<nombre>.json` junto a cada documento) y mismas métricas para todos:

```
ejecutar.bat benchmark_documentos --provider tesseract
ejecutar.bat benchmark_documentos --provider mistral  --autorizo-envio-externo
ejecutar.bat benchmark_documentos --provider azure    --autorizo-envio-externo
ejecutar.bat benchmark_documentos --provider benchmark --proveedores tesseract,azure,mistral --autorizo-envio-externo --json datos\comparativa.json
```

Por defecto usa `datos/analisis_real/benchmark` (las 9 fotos reales, fuera de git) si existe; si no, las imágenes
sintéticas de `fixtures/ficticios/imagenes`. Salida: una columna por proveedor con CABECERA (proveedor, CIF, número,
fecha), LÍNEAS (referencia, descripción, cantidad, precio, descuento, importe y los 5 campos de la baseline), ESTRUCTURA
(nº de líneas exacto, tablas devueltas, columnas reconocidas, líneas enteras correctas) y OPERACIÓN (completos, tiempo
mediana y p95, coste medio, campos de baja confianza, errores), más la baseline congelada de Tesseract como referencia.

Baseline congelada (`src/idm/documental/baseline_tesseract.json`, 9 fotos reales, 24/09/2026): número 8/9, fecha 9/9,
CIF 9/9, líneas 33/50, completos 4/9. Con las métricas nuevas, Tesseract da además proveedor 9/9, descripción 7/10,
nº de líneas exacto 6/9, líneas enteras 5/10, 0 tablas, mediana 10,3 s y p95 15,4 s por foto.

Comprobar una clave sin tocar documentos de IDM: `IDM_RUN_CLOUD_TESTS=1 python -m pytest tests/cloud` envía solo la
imagen sintética del repositorio.

## 6. Costes

```
ejecutar.bat estimar_costes --documentos-mes 300 --paginas-por-documento 1
```

Tarifas en `src/idm/documental/tarifas.json`, **fechadas y orientativas**: se escribieron sin poder verificarlas en línea
y deben comprobarse en la página de precios de cada proveedor antes de presupuestar. Con las del 24/09/2026 (1 página por
documento, 0,92 €/USD):

| Proveedor | €/documento | €/100 | €/1.000 | 300 docs/mes (escenario, no dato de IDM) |
|---|---|---|---|---|
| Tesseract (local) | 0 | 0 | 0 | 0 |
| Azure `prebuilt-layout` | 0,0092 | 0,92 | 9,20 | 2,76 |
| Mistral `mistral-ocr-latest` | 0,0018 | 0,18 | 1,84 | 0,55 |

El volumen mensual real de albaranes y facturas de IDM no se conoce (Fernandillo: "el programa no lo calcula"); por eso
la tarea lo pide como argumento. Cada llamada real registra su coste estimado y la bandeja lo muestra.

## 7. Cómo añadir otro proveedor (ej. Google Document AI)

1. `src/idm/documental/<nombre>.py`: clase que hereda de `ProveedorExternoBase` (o implementa `DocumentProvider` si es
   local), con `nombre`, `modelo`, `disponible()` y `_analizar(DocumentoEntrada) -> ResultadoDocumental`.
2. Una función pura `convertir(respuesta, metadatos)` que traduzca la respuesta al modelo común. Los campos del
   proveedor se mapean a los nombres neutros (`numero`, `fecha`, `cif`, `nuestro_pedido`; en líneas `codigo_proveedor`,
   `descripcion`, `cantidad`, `precio_bruto`, `descuento_pct`, `importe`).
3. HTTP con `documental/http.py` + `reintentos.llamar()`; nada de SDK si no hace falta.
4. Registrarlo en `router.py` (`EXTERNOS` y `crear_proveedor`), sus variables en `config.py` y `.env.ejemplo`, y su
   tarifa en `tarifas.json`.
5. Una respuesta grabada y ficticia en `fixtures/ficticios/proveedores_documentales/` y tests sin red con `HTTPFalso`,
   más uno real en `tests/cloud/` que solo use la imagen sintética.

`google.py` ya existe como hueco: el router lo reconoce y responde "preparado pero no implementado".

## 8. Estado de las conexiones (24/09/2026)

- **Mistral**: clave configurada en el `.env` local. La API responde `429` con `x-ratelimit-limit-req-minute: 0`: la
  cuenta no tiene OCR habilitado (normalmente falta activar la facturación en console.mistral.ai). Solo se envió la
  imagen sintética de pruebas.
- **Azure**: faltan endpoint y clave de un recurso Document Intelligence (región UE recomendada).
- **Ninguna foto real ha salido de la máquina.** Para el benchmark con las 9 fotos hace falta la autorización de IDM
  (PENDIENTE-IDM nº 20), activar las dos variables de privacidad y ejecutar con `--autorizo-envio-externo`.
