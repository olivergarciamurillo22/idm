# Arquitectura de idm-compras

## Principios que no se negocian

1. **El modelo lee, no escribe.** Los modelos de IA solo extraen datos de documentos que entran (albaranes, facturas). Toda decisión (aceptar, avisar, proponer pedido) es código determinista y explicable. Ningún texto que salga de IDM lo redacta un modelo.
2. **Ningún dato de IDM entra en el repositorio.** `datos/` está en `.gitignore` desde el primer commit. Los tests usan documentos ficticios en `fixtures/`.
3. **Sencillez.** Corre en un PC/servidor Windows de IDM. Sin Docker obligatorio, Kubernetes, Temporal, Kafka, microservicios, Terraform, Next.js ni LangChain. Hoy es un programa en Python con una base de datos local, construido para que mañana se pueda poner encima lo que haga falta.
4. **El núcleo es Python puro y se prueba sin nada alrededor.** `cotejar(albaran, pedido, reglas)` se ejecuta sin base de datos, sin web, sin Siddex y sin ningún modelo.
5. **Dinero con `Decimal`, nunca `float`.** Redondeo explícito a dos decimales en un solo sitio: `dominio/dinero.py`.
6. **Estados separados por dimensión**, no un único `status`:
   - documento: `RECIBIDO, LEIDO, COTEJADO, EN_REVISION, APROBADO, RECHAZADO` y laterales `ERROR` (fallo técnico,
     reprocesable) y `NO_PROCESABLE` (corrupto, vacío, Excel, formato no admitido). Los duplicados no crean documento.
   - lectura (`ResultadoLectura`): `PDF_TEXTO, REQUIERE_OCR, EXCEL, VACIO, CORRUPTO, NO_SOPORTADO`
   - relación con pedido: `CON_PEDIDO, SIN_PEDIDO, PEDIDO_PROPUESTO`
   - precio: `CONOCIDO, PENDIENTE_FACTURA`
   - entrega: `COMPLETA, PARCIAL, EXCESO`
7. **Toda pieza externa detrás de una interfaz fija e intercambiable:** lector de documentos (`leer(ruta) -> DocumentoLeido`), pasarela a Siddex (`SiddexGateway`), envío de correo, almacenamiento de ficheros. El dominio no conoce nombres de tablas de Siddex ni proveedores de IA.
8. **Siddex, tres niveles en el tiempo:** primero exportaciones a Excel (`SiddexDesdeExcel`), luego lectura directa de su base de datos en solo lectura (`SiddexDesdeBD`, cuando haya acceso), y escritura solo por una vía soportada y al final del proyecto. **Nunca se escribe en la base de datos de producción de Siddex por detrás de la aplicación.**
9. **Golden dataset:** `fixtures/golden/` con documentos ficticios y su resultado esperado en JSON; pytest los ejecuta todos y falla si algo que funcionaba deja de funcionar.
10. **Idempotencia:** un documento se identifica por su SHA-256 y por `(proveedor, tipo, número normalizado)`; procesarlo dos veces no crea dos registros.
11. **Trazabilidad:** tabla de eventos de negocio (`documento.recibido`, `proveedor.resuelto`, `articulo.resuelto` con método, `precio.comparado`, `decision.tomada`) separada de los logs técnicos. Cada pasada es una `Ejecución` y cada documento guarda una `Traza` (lectura, proveedor y método, campos extraídos, normalizaciones, artículos con método, pedido y método, albaranes, factura, reglas de cotejo con resultado, diferencias, errores, estado final, versión de procesamiento).
12. **Errores como datos:** los errores conocidos son `ErrorProcesamiento` (código cerrado, mensaje, recuperable) guardados con el documento; la excepción genérica es solo red de seguridad para que un fichero raro no tumbe el lote.
13. **Sin datos reales en git, con tres capas:** `.gitignore` (documentos ignorados salvo en fixtures permitidas), hook `pre-commit` y test que lo comprueba. Estructura `fixtures/{ficticios, reales (anonimizados), golden, problematicos, no_procesables}`.

## Diagrama de piezas

```
                    ┌──────────────────────────── ENTRADAS ────────────────────────────┐
                    │  Planning (Excel)   Escandallos Siddex (.xls BIFF2)   Encargos    │
                    │  Buzones IMAP / carpeta datos/entrada (PDF, fotos)                │
                    └──────────────┬───────────────────────────┬────────────────────────┘
                                   │                           │
              ┌────────────────────▼──────────┐   ┌────────────▼───────────────────────┐
              │ necesidades/                  │   │ albaranes/                          │
              │  planning · mapa · calculo ·  │   │  buzon → extraer → lector (interfaz)│
              │  stock                        │   │  → normalizar (nº por proveedor)    │
              └───────────┬───────────────────┘   └────────────┬───────────────────────┘
                          │ Necesidad[]                        │ DocumentoLeido
              ┌───────────▼───────────────────┐   ┌────────────▼───────────────────────┐
              │ encargos/  (registro urgente) │   │ equivalencias/  cod. proveedor↔IDM  │
              └───────────┬───────────────────┘   └────────────┬───────────────────────┘
                          │                                    │ Albaran / Factura
              ┌───────────▼───────────────────┐   ┌────────────▼───────────────────────┐
              │ pedidos/                      │   │ cotejo/                             │
              │  generar → pdf → enviar       │◄──┤  cotejar (dominio puro, al céntimo) │
              │  → exportar_siddex            │   │  proponer_pedido · facturas         │
              └───────────┬───────────────────┘   └────────────┬───────────────────────┘
                          │                                    │ Cotejo + Avisos
              ┌───────────▼────────────────────────────────────▼───────────────────────┐
              │ dominio/   modelos Pydantic · estados · reglas · dinero (Decimal)       │
              │            SIN dependencias de BD, web, Siddex ni modelos               │
              └───────────┬────────────────────────────────────┬───────────────────────┘
                          │                                    │
              ┌───────────▼───────────────────┐   ┌────────────▼───────────────────────┐
              │ siddex/  SiddexGateway        │   │ almacen/  SQLAlchemy 2 + Alembic    │
              │  desde_excel (hoy)            │   │  documentos · pedidos · encargos    │
              │  desde_bd (solo lectura, TODO)│   │  eventos de negocio (trazabilidad)  │
              │  escritura (vía soportada, al │   └────────────┬───────────────────────┘
              │  final, nunca por detrás)     │                │
              └───────────────────────────────┘   ┌────────────▼───────────────────────┐
                                                  │ bandeja/  FastAPI + Jinja2 (LAN)    │
                                                  │  lista · documento | datos leídos   │
                                                  │  aprobar / rechazar · encargos      │
                                                  └────────────────────────────────────┘
              ┌────────────────────────────────────────────────────────────────────────┐
              │ tareas/  calcular_mes · procesar_buzon · generar_pedidos ·             │
              │          ejecutar_golden · servir_bandeja   (Tareas programadas Windows)│
              └────────────────────────────────────────────────────────────────────────┘
```

## Flujo de un albarán

```
PDF/foto ─► buzon ─► sha256 (¿ya visto? → duplicado, evento sobre el original) ─► lector.leer(ruta)
        ─► ResultadoLectura: PDF_TEXTO sigue · IMAGEN_OCR sigue pero siempre ÁMBAR · REQUIERE_OCR → EN_REVISION
           · CORRUPTO/VACIO/EXCEL/NO_SOPORTADO → NO_PROCESABLE
        (imagen/HEIC: abrir con EXIF → preprocesado → mejor giro de 4 → OCR psm 4/6/11 × 2 tuberías → texto → intérprete)
        ─► DocumentoLeido ─► normalizar nº por proveedor
        ─► equivalencias (código proveedor → código IDM, con método)
        ─► ¿nuestro pedido? ─┬─ sí ─► cotejar(albaran, pedido, reglas) → Cotejo (verde/ámbar)
                             └─ no ─► proponer_pedido(albaran) → PEDIDO_PROPUESTO
        ─► almacen (documento + traza + eventos con ejecucion_id; (proveedor,tipo,nº) único → duplicado_numero)
        ─► bandeja (Fernando aprueba / rechaza) · reproceso solo explícito y nunca sobre APROBADO
        ─► número de registro devuelto para anotarlo en el papel
```

## Interfaces fijas

| Interfaz | Módulo | Implementaciones |
|---|---|---|
| `LectorDocumentos.leer(ruta) -> DocumentoLeido` | `albaranes/lector.py` | `LectorTextoPDF` (pdfplumber), `LectorImagenOCR` (imagen/HEIC → preprocesado → `MotorOCR` → mismo intérprete de texto), `LectorImagenNulo` (REQUIERE_OCR) |
| `MotorOCR.reconocer(imagen) -> ResultadoOCR` | `albaranes/ocr.py` | `MotorTesseract` (binario local), `MotorNulo`; otros motores locales se añaden aquí y se comparan con `benchmark_lector` |
| `FuenteDocumentos.pendientes()` | `albaranes/buzon.py` | `CarpetaEntrada`, `BuzonIMAP` |
| `SiddexGateway` | `siddex/gateway.py` | `SiddexDesdeExcel`, `SiddexDesdeBD` (TODO), escritura solo vía soportada |
| `Correo.enviar(mensaje)` | `pedidos/enviar.py` | `CorreoSimulado` (.eml en datos/salida), `CorreoSMTP` |
| `RepositorioEncargos` | `encargos/registro.py` | `EncargosJSONL`, `EncargosSQL` |
| `Repositorio` (documentos, pedidos, eventos) | `almacen/repositorio.py` | SQLAlchemy (SQLite / PostgreSQL por URL) |

## Reparto

Pedro: `necesidades/ encargos/ pedidos/ siddex/ equivalencias/`. Oliver: `albaranes/ cotejo/ bandeja/`.
Compartidos y bloqueados salvo acuerdo: `dominio/ almacen/ fixtures/golden/`.
