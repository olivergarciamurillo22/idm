# Layouts de albarán observados (estructura, sin datos)

De las fotos reales del 23/09/2026 salen tres estructuras distintas. Se describen aquí sin nombres comerciales, CIF ni
importes; el mapa proveedor → layout está en `albaranes/plantillas.py` y los datos reales en `datos/` (fuera de git).

| | Layout A | Layout B | Layout C |
|---|---|---|---|
| Número | etiqueta "Tipo / Serie / Nº Albarán" en un recuadro, valor en la línea siguiente | cabecera de tabla "ALBARAN Nº", valor debajo | tabla "Fecha \| Nº Albaranes Salida \| SU DOC. \| Nº PÁGINA", valores debajo |
| Forma del número | `XX Y00 0000000000` (prefijo de 2 letras que Siddex no guarda) | `00.000000` (punto de millar) | `0000/0.000` (Siddex quita el punto) |
| Fecha | "Fecha/Hora" con `dd/mm/aaaa / hh:mm:ss` | columna FECHA `dd/mm/aaaa` | columna Fecha `dd/mm/aaaa` |
| Nuestro pedido | recuadro "Pedido" del proveedor, siempre 0: **no consta** | "S/REFERENCIA" vacío | "SU DOC." vacío |
| Columnas de línea | Familia · Referencia · Denominación · Precio · % Descuentos (×3) · Cantidad · Imp. Línea | REFERENCIA · DESCRIPCION · CANTIDAD · PRECIO (4 decimales) · DTO. · IMPORTE | CÓDIGO · CONCEPTO · UDS. · PRECIO U. · DTO · PRECIO TOTAL |
| Precio en el albarán | sí, 2 decimales, hasta 3 descuentos en cascada | sí, 4 decimales, 1 descuento | **no** (llega con la factura) |
| Particularidad | los números de cada línea van medio renglón por encima del texto | texto legal vertical en el margen (ruido OCR) | firma digital impresa; tabla de totales vacía |
| Portes | columna del pie ("Portes") | columna del pie ("PORTES") | no aparece |
| CIF del proveedor en el papel | sí | **no** (solo el del cliente) | sí |
| Manuscrito | 4 dígitos arriba a la derecha | 4 dígitos junto a "Nº PROVEEDOR" | ninguno en la muestra |

El CIF de IDM aparece en los tres (bloque del cliente): `EMPRESA_CIF` en `.env` lo excluye al identificar proveedor.
Proveedores sin CIF en el papel se identifican por nombre (patrones en el registro de proveedores).
