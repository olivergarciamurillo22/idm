# fixtures/ficticios/proveedores_documentales

Respuestas **grabadas a mano y ficticias** con el mismo esquema que devuelven los proveedores cloud, para probar los
conversores sin llamadas reales. Contenido inventado (proveedor "SUMINISTROS FICTICIOS LA VEGA S.L.", CIF B00000001,
albarán del layout A sintético de `fixtures/ficticios/imagenes/`). Ningún dato de IDM.

| Fichero | Esquema | Qué prueba |
|---|---|---|
| `azure_layout_albaran.json` | Azure Document Intelligence v4, GET analyzeResults (`prebuilt-layout`, `features=keyValuePairs`) | palabras con polígono y confianza, tabla con cabeceras, pares clave-valor, una palabra de baja confianza |
| `azure_invoice_albaran.json` | idem con `documents[].fields` (`prebuilt-invoice`) y sin tabla | completar cabecera y líneas desde campos estructurados |
| `mistral_ocr_albaran.json` | Mistral `POST /v1/ocr` (`table_format=markdown`, `confidence_scores_granularity=word`) | markdown con marcador de tabla, tabla aparte, confianza por palabra |
| `mistral_ocr_anotacion.json` | idem con `document_annotation` (JSON en texto) y sin tabla | campos de la anotación completan huecos |
