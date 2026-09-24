# fixtures/reales · documentos reales anonimizados

Aquí van copias de documentos reales de IDM **después** de anonimizarlas. Sirven para el piloto (docs/VALIDACION-PILOTO.md)
y para golden tests con formatos reales de los proveedores.

## Regla
1. El original se queda en `datos/` (ignorada). Aquí solo entra la copia anonimizada.
2. El fichero se llama `<proveedor>_<tipo>_<n>.anonimizado.<ext>` (p. ej. `la-cepa_albaran_01.anonimizado.pdf`).
   `.gitignore` ignora todo lo demás en esta carpeta y `.githooks/pre-commit` bloquea cualquier otro nombre.
3. Cada fichero tiene una fila en `ANONIMIZACION.md` diciendo qué se cambió y quién lo revisó.
4. Qué se anonimiza: CIF y datos fiscales de IDM, importes si IDM lo pide, nombres de personas, direcciones, correos,
   teléfonos, números de cuenta. **Se conservan** la estructura, las referencias de artículo, las cantidades y el formato
   del número de albarán, porque es lo que el lector tiene que aprender.
5. Sin la aprobación de Ángel para sacar documentos de IDM, esta carpeta se queda vacía.

Herramienta: `fixtures/reales/anonimizar.py` (pendiente de escribir cuando tengamos el primer documento y sepamos qué campos tapar).
