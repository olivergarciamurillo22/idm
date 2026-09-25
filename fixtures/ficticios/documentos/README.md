# fixtures/ficticios/documentos

Documentos **ficticios** que imitan la estructura de los reales. Ningún dato de IDM ni de sus proveedores.

| Fichero | Imita | Qué prueba |
|---|---|---|
| `albaran_vega_bruto_descuento` | tipo Recambios La Cepa | bruto + descuento por línea, número con prefijo `AC` que Siddex no guarda, referencia a nuestro pedido |
| `albaran_recambios_sin_precio` | tipo RECACOR | sin precio (llega con la factura), número con puntos `4410/3.172` → `4410/3172` |
| `albaran_electro_puntos_prefijo` | proveedor eléctrico | número con prefijo y puntos `ALB. 2026/1.234`, línea de portes, artículo fuera del pedido |
| `factura_vega_agrupa` | factura quincenal | agrupa dos albaranes, portes aparte, precio cambiado |

Cada documento existe en dos formas:
- `.json`: la lectura correcta (lo que el lector debería sacar). Sirve de verdad para el benchmark.
- `.pdf`: generado por `generar_pdfs.py` con reportlab (PDF con texto, se lee con pdfplumber).

Proveedores ficticios: `FICT_VEGA` (Suministros Ficticios La Vega S.L., B00000001), `FICT_RECAMBIOS`
(Recambios Ejemplo S.A., A00000002), `FICT_ELECTRO` (Electro Ficticio S.L., B00000003).
