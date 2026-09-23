# Arquitectura de idm-compras

## Principios que no se negocian

1. **El modelo lee, no escribe.** Los modelos de IA solo extraen datos de documentos que entran (albaranes, facturas). Toda decisión (aceptar, avisar, proponer pedido) es código determinista y explicable. Ningún texto que salga de IDM lo redacta un modelo.
2. **Ningún dato de IDM entra en el repositorio.** `datos/` está en `.gitignore` desde el primer commit. Los tests usan documentos ficticios en `fixtures/`.
3. **Sencillez.** Corre en un PC/servidor Windows de IDM. Sin Docker obligatorio, Kubernetes, Temporal, Kafka, microservicios, Terraform, Next.js ni LangChain. Hoy es un programa en Python con una base de datos local, construido para que mañana se pueda poner encima lo que haga falta.
4. **El núcleo es Python puro y se prueba sin nada alrededor.** `cotejar(albaran, pedido, reglas)` se ejecuta sin base de datos, sin web, sin Siddex y sin ningún modelo.
5. **Dinero con `Decimal`, nunca `float`.** Redondeo explícito a dos decimales en un solo sitio: `dominio/dinero.py`.
6. **Estados separados por dimensión**, no un único `status`:
   - documento: `RECIBIDO, LEIDO, COTEJADO, EN_REVISION, APROBADO, RECHAZADO`
   - relación con pedido: `CON_PEDIDO, SIN_PEDIDO, PEDIDO_PROPUESTO`
   - precio: `CONOCIDO, PENDIENTE_FACTURA`
   - entrega: `COMPLETA, PARCIAL, EXCESO`
7. **Toda pieza externa detrás de una interfaz fija e intercambiable:** lector de documentos (`leer(ruta) -> DocumentoLeido`), pasarela a Siddex (`SiddexGateway`), envío de correo, almacenamiento de ficheros. El dominio no conoce nombres de tablas de Siddex ni proveedores de IA.
8. **Siddex, tres niveles en el tiempo:** primero exportaciones a Excel (`SiddexDesdeExcel`), luego lectura directa de su base de datos en solo lectura (`SiddexDesdeBD`, cuando haya acceso), y escritura solo por una vía soportada y al final del proyecto. **Nunca se escribe en la base de datos de producción de Siddex por detrás de la aplicación.**
9. **Golden dataset:** `fixtures/golden/` con documentos ficticios y su resultado esperado en JSON; pytest los ejecuta todos y falla si algo que funcionaba deja de funcionar.
10. **Idempotencia:** un documento se identifica por su SHA-256 y por `(proveedor, tipo, número normalizado)`; procesarlo dos veces no crea dos registros.
11. **Trazabilidad:** tabla de eventos de negocio (`documento.recibido`, `proveedor.resuelto`, `articulo.resuelto` con método, `precio.comparado`, `decision.tomada`) separada de los logs técnicos.

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
PDF/foto ─► buzon ─► sha256 (¿ya visto? → fin) ─► extraer (texto >80 car.? pdfplumber : imagen)
        ─► lector.leer(ruta) → DocumentoLeido ─► normalizar nº por proveedor
        ─► equivalencias (código proveedor → código IDM, con método)
        ─► ¿nuestro pedido? ─┬─ sí ─► cotejar(albaran, pedido, reglas) → Cotejo (verde/ámbar)
                             └─ no ─► proponer_pedido(albaran) → PEDIDO_PROPUESTO
        ─► almacen (documento + eventos) ─► bandeja (Fernando aprueba / rechaza)
        ─► número de registro devuelto para anotarlo en el papel
```

## Interfaces fijas

| Interfaz | Módulo | Implementaciones |
|---|---|---|
| `LectorDocumentos.leer(ruta) -> DocumentoLeido` | `albaranes/lector.py` | `LectorTextoPDF` (pdfplumber), `LectorImagenNulo` (mínimo; OCR/modelo detrás) |
| `FuenteDocumentos.pendientes()` | `albaranes/buzon.py` | `CarpetaEntrada`, `BuzonIMAP` |
| `SiddexGateway` | `siddex/gateway.py` | `SiddexDesdeExcel`, `SiddexDesdeBD` (TODO), escritura solo vía soportada |
| `Correo.enviar(mensaje)` | `pedidos/enviar.py` | `CorreoSimulado` (.eml en datos/salida), `CorreoSMTP` |
| `RepositorioEncargos` | `encargos/registro.py` | `EncargosJSONL`, `EncargosSQL` |
| `Repositorio` (documentos, pedidos, eventos) | `almacen/repositorio.py` | SQLAlchemy (SQLite / PostgreSQL por URL) |

## Reparto

Pedro: `necesidades/ encargos/ pedidos/ siddex/ equivalencias/`. Oliver: `albaranes/ cotejo/ bandeja/`.
Compartidos y bloqueados salvo acuerdo: `dominio/ almacen/ fixtures/golden/`.
