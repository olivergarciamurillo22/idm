# P02 · El total impreso por el proveedor no cuadra con la suma de sus propias líneas

**Situación.** Un proveedor calcula el importe de línea con más decimales y redondea solo el total: 3 líneas de
7 × 0,335 = 2,345 → el proveedor imprime 2,35 por línea (7,05 en total) pero la base impresa es 7,04 (suma sin redondear
2,345 × 3 = 7,035 → 7,04). Nuestro cotejo compara precio y descuento (que cuadran) y da VERDE; el total del albarán que
Fernando teclea en Siddex diferirá un céntimo del papel y la factura no cuadrará "al céntimo".

**Qué necesitamos de IDM.** Cuando el total impreso y la suma de líneas no coinciden, ¿qué manda para Siddex: la suma
de líneas (nuestro cálculo, igual que Siddex) o el total impreso? ¿Se avisa siempre o se acepta ±0,01 en el total?

**Esperado provisional.** Ámbar con aviso IMPORTE_NO_CUADRA en el cotejo (hoy el cotejo no mira el total impreso; solo
el lector baja la confianza). El test está `xfail` hasta decidirlo.
