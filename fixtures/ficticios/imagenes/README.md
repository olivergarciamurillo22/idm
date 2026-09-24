# fixtures/ficticios/imagenes

Imágenes **sintéticas** (dibujadas con Pillow por `generar.py`, sin ningún dato real) que reproducen la estructura del
layout A observado en papel real: etiqueta "Tipo / Serie / Nº Albarán" con el valor debajo, columnas Familia · Referencia ·
Denominación · Precio · tres descuentos · Cantidad · Imp. Línea, pie de totales y una anotación manuscrita simulada.

| Fichero | Qué prueba |
|---|---|
| `albaran_sintetico.{png,jpg,heic}` + `.json` | lectura por OCR de una foto limpia; HEIC sin EXIF |
| `albaran_sintetico_exif6.heic` | HEIC guardado girado con EXIF Orientation=6: se endereza al abrir |
| `albaran_sintetico_girado90.jpg` | foto en horizontal de un documento vertical: el lector prueba los 4 giros |
| `albaran_sintetico_borroso.jpg` | foto borrosa: baja confianza, no revienta |
| `albaran_sintetico_cortado.jpg` | documento cortado por la derecha |
| `dos_documentos.jpg` | dos documentos en una foto (hoy se lee como uno: límite conocido) |
| `corrupto.heic` | HEIC ilegible → CORRUPTO |

Los tests de OCR se saltan si `tesseract` no está instalado. Regenerar: `PYTHONPATH=src .venv/bin/python fixtures/ficticios/imagenes/generar.py`.
