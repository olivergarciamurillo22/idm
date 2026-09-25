# RECACOR

- **Clave en el programa:** `RECACOR`
- **Código en Siddex (PROVEEDR):** en `datos/proveedores_conocidos.csv` (fuera de git)
- **CIF:** PENDIENTE (Maestro de Proveedores)
- **Correo de pedidos:** PENDIENTE (Maestro de Proveedores)

## Número de albarán
Imprime `4410/3.172`; en Siddex va `4410/3172` (se quitan los puntos).

## Precio y descuento en el albarán
No: el albarán llega sin precio; se completa con la factura (PENDIENTE_FACTURA). Código alternativo SV09001 ↔ SERVICIO FICTICIO (CONTRATOS).

## Portes
No aparecen en el albarán (tabla de totales vacía). Pactados: PENDIENTE.

## Cómo factura
PENDIENTE

## Layout de lectura
Layout C de `docs/reglas-proveedor/layouts.md` (observado en fotos reales el 23/09/2026; datos en `datos/analisis_real/`).

## Documentos de muestra
Fotos reales en `datos/material_real/` (fuera de git). PENDIENTE: 3–4 albaranes y 1–2 facturas en PDF para afinar la plantilla de lectura (`albaranes/plantillas.py`).
