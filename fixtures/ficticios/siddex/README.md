# fixtures/ficticios/siddex

Exports **ficticios** con la misma estructura que los reales de Siddex.

- `escandallo_ficticio.xls`, `escandallo_ficticio_L.xls`: "Simulación de Costos" en BIFF2 (Excel 2.0), generados por `generar_biff2.py`.
  Columnas 0-based: nivel 0, cabecera 1, sec 3, código 4, descripción 5, cantidad 11, unidad 12, precio 15, importe 16, tipo 17.
  Incluyen las incidencias reales: artículo sin precio, conjunto sin despiece, código en minúscula, hierro (CORTE TUBO / CHAPA KG).
- `articulos.xlsx`, `proveedores.xlsx`, `fabricantes.xlsx`, `pedidos.xlsx`, `stock.xlsx`: generados por `generar_exports.py`.
  Sus cabeceras son PROVISIONALES (ver `COLUMNAS` en `src/idm/siddex/desde_excel.py`) hasta tener los exports reales.
- `../planning_ficticio.xlsx`: hoja `SEPT_26`, cabecera en la fila 4, datos desde la 5 en columnas B..E.

Proveedores ficticios: 9001 = FICT_VEGA, 9002 = FICT_RECAMBIOS, 9003 = FICT_ELECTRO.
