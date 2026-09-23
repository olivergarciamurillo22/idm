# Cómo se hace hoy (AS-IS, reconstruido de audios y fotos el 23/09/2026)

1. Llega el albarán físico con la mercancía. Formatos distintos por proveedor (Recambios La Cepa, Grupo Meyras, RECACOR…).
   No todos traen precio: RECACOR no.
2. En Siddex: **Almacén → Introducción de Registros de Entrada**. Siddex genera un Nº Registro interno (p. ej. 20262921)
   con fecha y hora.
3. Se identifica el proveedor buscando en la tabla PROVEEDR (La Cepa = código 1411; RECACOR = 864). Siddex muestra razón
   social, CIF, dirección, forma de pago.
4. **Con pedido**: opción *Importar Pedidos a Proveedor* (campos Proveedor, Almacén, Nuestro Pedido, Su Pedido, Su Albarán,
   Fecha Recepción, Hora, Orden, Cliente). Siddex recupera las líneas del pedido (artículo interno, descripción, cantidad,
   unidad, precio, lote, fecha, estado) y la persona marca las recibidas. Ejemplo: pedido 20261060, albarán B26 0100005283,
   artículo 134.000.842 TERMINAL FASTON H. 9,4 AMAR, 100 uds a 0,300; en el papel de La Cepa: referencia PVCC550942,
   100 uds, 0,30, descuento 45 %.
5. **Sin pedido**: se crea la entrada a mano. Se teclea la referencia del proveedor y, si el artículo está configurado en el
   Maestro de Artículos, Siddex recupera el artículo interno (RECACOR MO01001 ↔ "SERVICIO TURISMO (CONTRATOS)").
   **El código alternativo por proveedor existe y funciona.**
6. La descripción interna de IDM puede ser distinta de la del proveedor y la mantienen.
7. Cantidad y unidad según el artículo (UD, M, LT).
8. Precios y descuentos: Siddex guarda **bruto y descuento por separado**; los totales cuadran con el papel
   (ejemplo: 5 × 9,14 con 45 % = 25,14; 5 × 6,40 = 32; base 57,14, IVA 12,00, total 69,14).
9. Albarán sin precio: se deja vacío. Cuando llega la factura, buscan el albarán y completan el precio real. Si el precio de
   compra ha cambiado, lo actualizan en Enlaces → Maestro de Artículos. El precio de venta lleva un margen manual que varía
   por artículo (ejemplo 60 %). **Nuestro sistema no toca precios de venta ni el maestro: solo avisa.**
10. Buscador histórico: *Buscar Registros de la Tabla ENTRADA* (NumeroRegistro, Fecha, NumeroAlbaran, CodigoProveedor, Nombre).
11. Escriben a mano en el papel los últimos cuatro dígitos del Nº Registro (2921, 2922, 2923). Pendiente de confirmar, pero
    muy consistente. Nuestro sistema devuelve ese número (campo "Nº registro Siddex" al aprobar en la bandeja).
12. Normalizan a mano el número de albarán: RECACOR imprime 5526/2.063 y en Siddex va 5526/2063; La Cepa imprime
    AC B26 0100005206 y en Siddex va B26 0100005206. **Reglas por proveedor, no generales.**

## Dudas abiertas
- Significado exacto de la anotación manuscrita.
- Cuántos proveedores van sin pedido o sin precio.
- Criterio para marcar líneas al importar.
- Si las normalizaciones son reglas generales.
- ¿Siddex permite importar pedidos desde fichero? (pregunta clave pendiente)

## Volumen (Preguntas rápidas, 22/09)
- Unos 150 pedidos de compra al mes (junio). Albaranes al mes: Siddex no lo calcula.
- Fernando mete hasta 40 albaranes en un día cuando se acumulan; el 60 % de su tiempo se va en meterlos a mano.
- Cinco proveedores con más albaranes: Complementos y Suministros Cruz, Recambios La Cepa, Grupo Electro Meyras, Bondioli, Jucamp.
- Tolerancia de precio: cero. Exceso de cantidad: se avisa. Facturas: la mayoría agrupan mes o quincena. Portes: pocos fijos.
