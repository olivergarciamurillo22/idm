# Benchmark real del lector de imágenes (lote de fotos del 23/09/2026)

Primera medición sobre material **real** (las fotos y la verdad de referencia están en `datos/`, ignoradas por git;
aquí solo cifras). 27 fotos HEIC de iPhone: 18 pantallas de Siddex y 9 de albaranes en papel (6 albaranes distintos de
3 proveedores; 3 fotos repetidas: una girada 90°, dos cortadas). Motor: Tesseract 5.5 local (`spa+eng`), sin enviar nada
fuera de la máquina. Todo determinista.

## Qué se mide
Verdad de referencia tecleada a mano para los 9 documentos (6 distintos). Campos: tipo, CIF, número, fecha, nuestro pedido
(no consta en ningún papel: 9/9 es "correctamente vacío"), nº de líneas y, por línea, referencia, cantidad, precio,
descuento e importe. "Completo" = número, fecha, nº de líneas y todas las líneas bien.

**Detección visual/manual durante el análisis** (lo que una persona ve en la foto) ≠ **extracción automática** (lo que saca
el programa). La tabla es extracción automática.

## Resultados (documentos con texto en papel, 9 fotos)

| Configuración | tipo | cif | número | fecha | nº líneas | líneas (5 campos × 10) | completos |
|---|---|---|---|---|---|---|---|
| Sin OCR (estado anterior: todo REQUIERE_OCR) | 0/9 | 2/9 | 0/9 | 0/9 | 0/9 | 6/50 | 0/9 |
| OCR, sin preprocesado, OSD de Tesseract, psm 6 | 4/9 | 4/9 | 3/9 | 4/9 | 1/9 | 11/50 | 1/9 |
| OCR, gris+contraste 2400 px, psm 6 | 4/9 | 6/9 | 1/9 | 1/9 | 1/9 | 8/50 | 0/9 |
| OCR, orientación por confianza (4 giros), psm 4+6, 2400 px | 5/9 | 9/9 | 4/9 | 6/9 | 3/9 | 18/50 | 1/9 |
| + filas geométricas, 3200 px, psm 4+6+11 | 5/9 | 9/9 | 8/9 | 9/9 | 4/9 | 23/50 | 2/9 |
| + recorte al texto (segunda tubería unida) | 9/9 | 9/9 | 8/9 | 9/9 | 6/9 | 33/50 | 3/9 |
| **+ ruido con límites de palabra (configuración final)** | **9/9** | **9/9** | **8/9** | **9/9** | **6/9** | **35/50** | **4/9** |

Tiempo: 6–10 s por foto en un portátil (4 giros de prueba + 3 modos × 2 tuberías).

## Lo que enseña
- **La orientación es lo primero.** El OSD de Tesseract se equivocó en 2 de 5 fotos; probar los cuatro giros y quedarse con
  el de más palabras fiables acertó en todas.
- **El recorte al área con texto es lo que más aporta** en fotos donde el papel ocupa una parte pequeña del encuadre: las
  columnas numéricas pequeñas pasan de ilegibles a correctas.
- **Cada modo de segmentación ve cosas distintas** (psm 4 columnas, 6 bloque, 11 disperso); unir sus textos y dejar que las
  primeras lecturas manden funciona mejor que elegir uno.
- **Binarizar empeora** (33 % número) y no se usa.
- Lo que sigue fallando y por qué: una foto en mano e inclinada con precio a 4 decimales (números ilegibles), una foto
  cortada por el borde (número fuera de encuadre), un dígito confundido en una referencia (C→O) y en un número (2→5),
  una M leída como 1 en una referencia. Ninguno se "arregla" inventando: van a la bandeja en ámbar para corregir a mano.
- Las 18 pantallas de Siddex no son documentos: el sistema las clasifica como imagen sin albarán reconocible y quedan
  en revisión (no se han incluido en la tabla).

## Cómo repetirlo
```
ejecutar.bat benchmark_lector --carpeta datos\analisis_real\benchmark --lector ocr --detalle
ejecutar.bat benchmark_lector --carpeta datos\analisis_real\benchmark --lector ocr --tuberia contraste_3200 --psm 6
```
Sobre fixtures ficticios (sin OCR): `ejecutar.bat benchmark_lector` sigue dando 100 % en PDF con texto.

## Decisión
Tesseract local queda como **prototipo** detrás de `MotorOCR`, activable con `OCR_MOTOR=tesseract`. No es decisión de
producción: con 20 albaranes reales de los cinco grandes se repetirá la medición y se compararán al menos otro motor
local (RapidOCR/PaddleOCR, instalable por pip, sin binario) y, si IDM autoriza sacar documentos, un servicio externo.
