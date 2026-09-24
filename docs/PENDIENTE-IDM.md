# Pendiente de IDM · checklist de lo que hay que conseguir físicamente

Cada línea: qué es, para qué lo necesitamos, qué módulo desbloquea y prioridad. Se tacha cuando está en `datos/`
(nunca en git) o cuando IDM ha contestado y la decisión está en `DECISIONES.md`.
Cómo pedirlo: por el grupo de WhatsApp, poco y todos los días. Contraseñas nunca por escrito.

| # | Qué | Para qué | Módulo que desbloquea | Prioridad | Estado |
|---|---|---|---|---|---|
| 1 | **Export Artículos** (Maestro de Artículos con todas las columnas: proveedor habitual, unidad, múltiplo/caja, precio, descuento, tipo) | Proveedor y múltiplo de cada artículo; precio de referencia; aviso de precio cambiado | `siddex/desde_excel` (`articulos`), `necesidades/calculo` (múltiplos), `pedidos/generar`, `cotejo/facturas` | **Crítica** | Pendiente |
| 2 | **Export Proveedores** (código, razón social, CIF, correo) | Identificar al proveedor de cada documento por CIF; correo para enviar pedidos; claves reales del registro | `equivalencias/proveedores` (rellenar `codigo_siddex` y `cif` de los 6 grandes), `pedidos/enviar` | **Crítica** | **Evidencia parcial (fotos 23/09):** códigos Siddex 1411 y 864 y CIF de dos proveedores vistos en pantalla y papel → en `datos/proveedores_conocidos.csv` (fuera de git). Falta el export completo con correos |
| 3 | **Export Fabricantes** (artículo ↔ código alternativo por proveedor) | Traducir la referencia del albarán al código IDM sin preguntar | `equivalencias/tabla`, `cotejo/interpretar` | **Crítica** | Pendiente |
| 4 | **Export Pedidos** de los últimos 3 meses (con líneas, cantidades recibidas y referencia del proveedor si la hay) | Cotejar albaranes reales; saber si "recibida" existe en el export (caso P01) | `siddex/desde_excel` (`pedidos`), `cotejo/cotejar.buscar_pedido` | **Crítica** | **Evidencia parcial (fotos 23/09):** pantalla de importación muestra Nº Pedido, Línea, Artículo, Descripción, Ctd. Acept., Ud. Stock, Precio, Lote, Fecha Entrega, Estado; las líneas ya recibidas desaparecen de la lista. Falta el export |
| 5 | **Export Stock** (Consulta de Stocks completa) y confirmar si se parece a las estanterías | Descontar stock antes de pedir; decidir la lista de componentes grandes fiables | `necesidades/stock` (`COMPONENTES_GRANDES`) | Alta | Pendiente |
| 6 | **PDF real de un pedido transmitido** (`H:\0_PEDIDOS_TRANSMITIDOS\2026`) | Copiar el formato de IDM en el PDF que generamos | `pedidos/pdf.py` | Alta | Pendiente |
| 7 | **10–20 albaranes en PDF** de los cinco grandes (Cruz, La Cepa, Meyras, Bondioli, Jucamp) y **2–3 fotos** de albaranes en papel | Afinar plantillas de lectura por proveedor; benchmark real; decidir OCR | `albaranes/plantillas`, `albaranes/normalizar`, `docs/reglas-proveedor/*` | **Crítica** | **Parcial (fotos 23/09):** 6 albaranes en papel fotografiados (3 proveedores) en `datos/material_real/`. Faltan Cruz, Bondioli y Jucamp, y PDFs digitales de todos |
| 8 | **4–5 facturas** que agrupen esos albaranes (mes, quincena, varios) | Casar factura con N albaranes; portes; precios pendientes | `cotejo/facturas` | **Crítica** | Pendiente |
| 9 | **Ejemplo de pedido con varios albaranes** (entregas parciales) y cómo lo ve Fernando en Siddex | Regla P01 (fuente de "cantidad recibida"); cerrar pedido parcial | `cotejo/cotejar`, P01 | Alta | **Evidencia parcial (fotos 23/09):** pedido con 12 líneas del que faltan las 8, 10 y 11 en la pantalla de importación (recibidas antes). La regla P01 sigue pendiente de Fernando |
| 10 | **Ejemplo de factura con varios albaranes** ya conciliada por Fernando | Verdad esperada para el piloto | `docs/VALIDACION-PILOTO.md` | Alta | Pendiente |
| 11 | **Un caso problemático** que Fernando recuerde (precio distinto, exceso, portes, albarán sin pedido) con cómo lo resolvió | Golden real; comprobar que marcamos lo mismo que él | `fixtures/reales`, `fixtures/golden` | Alta | Pendiente |
| 12 | **Definición de JEV** (qué es, dónde entra en el circuito) | Oliver pidió "valorar incorporar Jev"; no está en ningún documento | Por decidir | Media | Pendiente (pregunta a Oliver/Pedro) |
| 13 | **Códigos de escandallo A4R L / E / LE** (y si existen como producto en Siddex o son base + opciones) | Calcular necesidades de todas las variantes del planning | `necesidades/mapa_productos.csv` | **Crítica** (hito 2) | Pendiente (Fernandillo) |
| 14 | **Mapa nombre de planning → código Siddex** para todos los productos del mes | Sin él, el cálculo del mes salta filas | `necesidades/mapa_productos.csv` | **Crítica** (hito 2) | Pendiente (Fernandillo) |
| 15 | **Reglas de tolerancia**: confirmado "al céntimo" para precio; ¿y para el total impreso con redondeos distintos (P02)? | Cotejo de totales | `dominio/reglas`, P02 | Alta | Parcial (precio: cero, Fernando 22/09). Nuevo caso visto: proveedor con precio a 4 decimales (7,8400) frente a Siddex a 3 (9,140): ¿cómo se teclea? → Fernando |
| 16 | **Portes**: lista de proveedores con porte fijo pactado e importe | Verde automático en portes pactados | `dominio/reglas.portes_pactados` | Media | Pendiente (Fernando: "algunos sí") |
| 17 | **Descuentos**: ¿algún proveedor aplica descuento en cascada (45 % + 5 %) o rappel en factura? | Comparar descuento como un solo porcentaje o como cadena | `dominio/cotejar._comparar_precio` | Media | Pendiente |
| 18 | **Entregas parciales**: ¿se cierra el pedido cuando llega el resto o hay pedidos que quedan abiertos meses? ¿Quién los cierra? | Estado de pendientes y limpieza de pedidos abiertos | `cotejo/cotejar`, bandeja | Alta | Pendiente |
| 19 | **Facturas parciales**: si una factura no incluye todas las líneas de un albarán, ¿se acepta y se espera o se avisa? | Regla del test xfail `test_factura_parcial_regla_pendiente` | `cotejo/facturas` | Alta | Pendiente |
| 20 | **¿Pueden salir los documentos de IDM a un servicio externo?** Y si sí: ¿a cuál (Azure en región UE, Mistral en UE), con qué contrato de tratamiento de datos, y sus datos pueden usarse para entrenar? | Activar `ALLOW_EXTERNAL_DOCUMENT_PROCESSING` y la lista de proveedores; hasta entonces las fotos solo se leen en local | `documental/` (ya preparado: Azure y Mistral implementados, bloqueados por defecto) | **Crítica** (hito 3) | Pendiente → **Ángel** (por escrito) |
| 21 | **¿Siddex permite importar pedidos desde fichero?** y formato | Escribir pedidos sin teclear | `pedidos/exportar_siddex`, `siddex/gateway.SiddexEscritura` | **Crítica** (hito 2) | Pendiente (Miguel / Cristóbal) |
| 22 | **Acceso al servidor de Siddex** y usuario de solo lectura a la base de datos | Segundo nivel del gateway | `siddex/desde_bd` | Media (hito 5) | Correo enviado a Era Informática |
| 23 | **Buzones** info@, info2@, almacen@ (acceso IMAP configurado por quien lleve la informática) | Entrada automática de documentos | `albaranes/buzon`, `.env` | Alta (hito 3) | Pendiente |
| 24 | **Escandallos** del resto de máquinas del planning | Necesidades completas del mes | `siddex/lectura` | Alta (hito 2) | Solo A4R y FUMIMATIC |
| 25 | **Planning** actual (`PLANNING_IDM_MENSUAL.xlsx`) cada vez que Ángel lo cambie | Recalcular | `necesidades/planning` | Alta | Tenemos septiembre |
| 26 | **Significado de la anotación manuscrita** en el papel (últimos 4 dígitos del nº de registro) | Devolver el número correcto al aprobar | bandeja (`numero_registro_siddex`) | Media | **Resuelto por evidencia documental (fotos 23/09):** el número escrito en el albarán (2921, 2920, 2919, 2918, 2923) son los 4 últimos dígitos del Nº Registro de Siddex (20262921…). Confirmación verbal de Fernando: deseable, no imprescindible |
| 27 | **Número de albarán de Meyras en Siddex**: imprime `20.0xxxxx` con punto; ¿Fernando lo teclea con o sin punto? | Regla de normalización del proveedor | `albaranes/normalizar` | Alta | **Nuevo (fotos 23/09)** → Fernando |
| 28 | **Serie "20" al crear el registro de entrada** (diálogo "Introduzca la serie"): ¿es siempre 20 = año? | Devolver el Nº Registro completo y preparar la escritura futura | `siddex/gateway.SiddexEscritura` | Media | **Nuevo (fotos 23/09)** → Fernando |
| 29 | **Descuentos en cascada**: un proveedor imprime tres columnas de descuento (45 0 0). ¿Se usan las tres alguna vez? | Comparar descuento como uno o como cadena | `dominio/cotejar` | Media | **Nuevo (fotos 23/09)** → Fernando |
| 30 | **Fotos de albarán como vía de entrada**: ¿quién las hace, con qué móvil, y se pueden mandar al buzón desde el móvil? | Calidad de imagen (plana, sin mano) decide el OCR | `albaranes/buzon`, `albaranes/imagenes` | Alta (hito 3) | **Nuevo (fotos 23/09)** → Fernandillo / Miguel |
| 31 | **Motor de lectura definitivo**: Tesseract queda como respaldo local (baseline 33/50 líneas, 4/9 completos). Comparar Azure y Mistral con `benchmark_documentos` sobre las mismas fotos cuando se autorice el punto 20 | Lector de producción | `documental/` | Alta (hito 3) | Preparado; bloqueado por el punto 20 |
| 32 | **Cuenta de Mistral con OCR habilitado** (hoy responde límite 0 peticiones/min) y **recurso de Azure Document Intelligence** (endpoint + clave, región UE) | Poder ejecutar el benchmark A/B | `.env` | Alta | Oliver |

## Quién tiene que responder qué (tras las fotos del 23/09)
- **Resuelto por evidencia documental:** 26 (anotación manuscrita); normalización de La Cepa (`AC` fuera) y RECACOR (sin punto) confirmadas en pantalla.
- **Evidencia parcial:** 2, 4, 7, 9, 15.
- **Fernando:** 9 (P01), 15/P02, 16, 17, 18, 19, 27, 28, 29.
- **Fernandillo:** 5, 13, 14, 30.
- **Ángel:** 12 (Jev), 20, 21 (con Miguel).
- **Miguel / Era Informática:** 1–6 (exports), 21, 22, 23.

## Qué hacer en cuanto llegue cada cosa
- Exports (1–5): copiar a `datos/siddex/`, ejecutar `ejecutar.bat revisar_exports` y ajustar `columnas.json` o
  `siddex/columnas.py` hasta que todo salga OK; después `ejecutar.bat tests`.
- Documentos (7, 8, 11): dejar los originales en `datos/entrada/`, ejecutar `ejecutar.bat procesar_buzon --sin-imap`,
  mirar la bandeja, y anonimizar los que vayan a `fixtures/reales/` (registro en `ANONIMIZACION.md`). Afinar
  `albaranes/plantillas.py` y `normalizar.py` por proveedor; ejecutar `benchmark_lector --carpeta datos/entrada` (con
  los `.json` de verdad tecleados a mano para 5–10 documentos).
- Reglas (15–19): escribir la decisión en `DECISIONES.md`, implementarla, y mover el caso de `problematicos` a `golden`.
