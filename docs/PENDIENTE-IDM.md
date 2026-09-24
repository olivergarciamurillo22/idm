# Pendiente de IDM · checklist de lo que hay que conseguir físicamente

Cada línea: qué es, para qué lo necesitamos, qué módulo desbloquea y prioridad. Se tacha cuando está en `datos/`
(nunca en git) o cuando IDM ha contestado y la decisión está en `DECISIONES.md`.
Cómo pedirlo: por el grupo de WhatsApp, poco y todos los días. Contraseñas nunca por escrito.

| # | Qué | Para qué | Módulo que desbloquea | Prioridad | Estado |
|---|---|---|---|---|---|
| 1 | **Export Artículos** (Maestro de Artículos con todas las columnas: proveedor habitual, unidad, múltiplo/caja, precio, descuento, tipo) | Proveedor y múltiplo de cada artículo; precio de referencia; aviso de precio cambiado | `siddex/desde_excel` (`articulos`), `necesidades/calculo` (múltiplos), `pedidos/generar`, `cotejo/facturas` | **Crítica** | Pendiente |
| 2 | **Export Proveedores** (código, razón social, CIF, correo) | Identificar al proveedor de cada documento por CIF; correo para enviar pedidos; claves reales del registro | `equivalencias/proveedores` (rellenar `codigo_siddex` y `cif` de los 6 grandes), `pedidos/enviar` | **Crítica** | Pendiente |
| 3 | **Export Fabricantes** (artículo ↔ código alternativo por proveedor) | Traducir la referencia del albarán al código IDM sin preguntar | `equivalencias/tabla`, `cotejo/interpretar` | **Crítica** | Pendiente |
| 4 | **Export Pedidos** de los últimos 3 meses (con líneas, cantidades recibidas y referencia del proveedor si la hay) | Cotejar albaranes reales; saber si "recibida" existe en el export (caso P01) | `siddex/desde_excel` (`pedidos`), `cotejo/cotejar.buscar_pedido` | **Crítica** | Pendiente |
| 5 | **Export Stock** (Consulta de Stocks completa) y confirmar si se parece a las estanterías | Descontar stock antes de pedir; decidir la lista de componentes grandes fiables | `necesidades/stock` (`COMPONENTES_GRANDES`) | Alta | Pendiente |
| 6 | **PDF real de un pedido transmitido** (`H:\0_PEDIDOS_TRANSMITIDOS\2026`) | Copiar el formato de IDM en el PDF que generamos | `pedidos/pdf.py` | Alta | Pendiente |
| 7 | **10–20 albaranes en PDF** de los cinco grandes (Cruz, La Cepa, Meyras, Bondioli, Jucamp) y **2–3 fotos** de albaranes en papel | Afinar plantillas de lectura por proveedor; benchmark real; decidir OCR | `albaranes/plantillas`, `albaranes/normalizar`, `docs/reglas-proveedor/*` | **Crítica** | Pendiente (Miguel pide a los proveedores que manden PDF) |
| 8 | **4–5 facturas** que agrupen esos albaranes (mes, quincena, varios) | Casar factura con N albaranes; portes; precios pendientes | `cotejo/facturas` | **Crítica** | Pendiente |
| 9 | **Ejemplo de pedido con varios albaranes** (entregas parciales) y cómo lo ve Fernando en Siddex | Regla P01 (fuente de "cantidad recibida"); cerrar pedido parcial | `cotejo/cotejar`, P01 | Alta | Pendiente |
| 10 | **Ejemplo de factura con varios albaranes** ya conciliada por Fernando | Verdad esperada para el piloto | `docs/VALIDACION-PILOTO.md` | Alta | Pendiente |
| 11 | **Un caso problemático** que Fernando recuerde (precio distinto, exceso, portes, albarán sin pedido) con cómo lo resolvió | Golden real; comprobar que marcamos lo mismo que él | `fixtures/reales`, `fixtures/golden` | Alta | Pendiente |
| 12 | **Definición de JEV** (qué es, dónde entra en el circuito) | Oliver pidió "valorar incorporar Jev"; no está en ningún documento | Por decidir | Media | Pendiente (pregunta a Oliver/Pedro) |
| 13 | **Códigos de escandallo A4R L / E / LE** (y si existen como producto en Siddex o son base + opciones) | Calcular necesidades de todas las variantes del planning | `necesidades/mapa_productos.csv` | **Crítica** (hito 2) | Pendiente (Fernandillo) |
| 14 | **Mapa nombre de planning → código Siddex** para todos los productos del mes | Sin él, el cálculo del mes salta filas | `necesidades/mapa_productos.csv` | **Crítica** (hito 2) | Pendiente (Fernandillo) |
| 15 | **Reglas de tolerancia**: confirmado "al céntimo" para precio; ¿y para el total impreso con redondeos distintos (P02)? | Cotejo de totales | `dominio/reglas`, P02 | Alta | Parcial (precio: cero) |
| 16 | **Portes**: lista de proveedores con porte fijo pactado e importe | Verde automático en portes pactados | `dominio/reglas.portes_pactados` | Media | Pendiente (Fernando: "algunos sí") |
| 17 | **Descuentos**: ¿algún proveedor aplica descuento en cascada (45 % + 5 %) o rappel en factura? | Comparar descuento como un solo porcentaje o como cadena | `dominio/cotejar._comparar_precio` | Media | Pendiente |
| 18 | **Entregas parciales**: ¿se cierra el pedido cuando llega el resto o hay pedidos que quedan abiertos meses? ¿Quién los cierra? | Estado de pendientes y limpieza de pedidos abiertos | `cotejo/cotejar`, bandeja | Alta | Pendiente |
| 19 | **Facturas parciales**: si una factura no incluye todas las líneas de un albarán, ¿se acepta y se espera o se avisa? | Regla del test xfail `test_factura_parcial_regla_pendiente` | `cotejo/facturas` | Alta | Pendiente |
| 20 | **¿Pueden salir los documentos de IDM a un servicio externo?** (Azure DI / modelo multimodal) o todo local | Elegir el lector de imagen para escaneos y fotos | `albaranes/lector` (REQUIERE_OCR) | **Crítica** (hito 3) | Pendiente (Ángel) |
| 21 | **¿Siddex permite importar pedidos desde fichero?** y formato | Escribir pedidos sin teclear | `pedidos/exportar_siddex`, `siddex/gateway.SiddexEscritura` | **Crítica** (hito 2) | Pendiente (Miguel / Cristóbal) |
| 22 | **Acceso al servidor de Siddex** y usuario de solo lectura a la base de datos | Segundo nivel del gateway | `siddex/desde_bd` | Media (hito 5) | Correo enviado a Era Informática |
| 23 | **Buzones** info@, info2@, almacen@ (acceso IMAP configurado por quien lleve la informática) | Entrada automática de documentos | `albaranes/buzon`, `.env` | Alta (hito 3) | Pendiente |
| 24 | **Escandallos** del resto de máquinas del planning | Necesidades completas del mes | `siddex/lectura` | Alta (hito 2) | Solo A4R y FUMIMATIC |
| 25 | **Planning** actual (`PLANNING_IDM_MENSUAL.xlsx`) cada vez que Ángel lo cambie | Recalcular | `necesidades/planning` | Alta | Tenemos septiembre |
| 26 | **Significado de la anotación manuscrita** en el papel (últimos 4 dígitos del nº de registro) | Devolver el número correcto al aprobar | bandeja (`numero_registro_siddex`) | Media | Pendiente de confirmar |

## Qué hacer en cuanto llegue cada cosa
- Exports (1–5): copiar a `datos/siddex/`, ejecutar `ejecutar.bat revisar_exports` y ajustar `columnas.json` o
  `siddex/columnas.py` hasta que todo salga OK; después `ejecutar.bat tests`.
- Documentos (7, 8, 11): dejar los originales en `datos/entrada/`, ejecutar `ejecutar.bat procesar_buzon --sin-imap`,
  mirar la bandeja, y anonimizar los que vayan a `fixtures/reales/` (registro en `ANONIMIZACION.md`). Afinar
  `albaranes/plantillas.py` y `normalizar.py` por proveedor; ejecutar `benchmark_lector --carpeta datos/entrada` (con
  los `.json` de verdad tecleados a mano para 5–10 documentos).
- Reglas (15–19): escribir la decisión en `DECISIONES.md`, implementarla, y mover el caso de `problematicos` a `golden`.
