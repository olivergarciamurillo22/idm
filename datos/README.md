# datos/

Aquí van los datos reales de IDM. **Nada de esta carpeta entra en git** (está en `.gitignore`).

Estructura esperada (la crea el programa si no existe):

```
datos/
  entrada/            PDFs y fotos de albaranes/facturas que llegan (buzón o carpeta)
  procesados/         documentos ya tratados, renombrados por SHA-256
  siddex/             exports de Siddex (Maestro de Artículos, Proveedores, Fabricantes, Pedidos, Stock, escandallos .xls)
  planning/           PLANNING_IDM_MENSUAL.xlsx
  pedidos/            PDFs de pedido generados (se copian a H:\0_PEDIDOS_TRANSMITIDOS\<año>)
  salida/             Excel de necesidades, hojas para Siddex, correos simulados (.eml)
  encargos.jsonl      registro de encargos (hasta que almacen/ lo pase a la base de datos)
  idm.db              base de datos SQLite
```

Los tests **no** usan esta carpeta: usan `fixtures/` con documentos ficticios.
