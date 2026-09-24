# Protocolo de validación del piloto

**Objetivo.** Procesar automáticamente al menos **10 operaciones históricas completas** (pedido → albarán(es) →
factura) y comparar el resultado del programa con lo que administración (Fernando) hizo en Siddex. El piloto no toca
Siddex: lee exports y documentos, y deja el resultado en la bandeja.

## 1. Preparación
1. Exports de Siddex del periodo en `datos/siddex/` (artículos, proveedores, fabricantes, pedidos con recibidas, stock).
   `ejecutar.bat revisar_exports` sin FALTA en columnas requeridas.
2. Documentos del periodo en `datos/piloto/<operacion>/` (albaranes y factura de cada operación, PDF o foto).
3. Verdad esperada: Fernando rellena `datos/piloto/esperado.xlsx` (una fila por documento) con: proveedor, nº de albarán
   tal como lo tecleó en Siddex, nº de pedido usado, nº de registro de Siddex, líneas (código IDM, cantidad, precio,
   dto) y las incidencias que él marcó (precio distinto, exceso, portes, sin pedido, sin precio).
4. `ejecutar.bat migrar` sobre una base de datos limpia (`DATABASE_URL=sqlite:///datos/piloto.db` en `.env`).

## 2. Ejecución
```
ejecutar.bat procesar_buzon --sin-imap --carpeta datos\piloto\<operacion>     (una operación cada vez, albaranes antes que la factura)
ejecutar.bat servir_bandeja                                                    (revisión en pantalla)
```
Cada pasada queda como una `Ejecución`; cada documento lleva su `Traza` (qué se leyó, qué se normalizó, qué pedido se
usó, qué reglas se aplicaron y con qué resultado).

## 3. Registro por operación (`docs/piloto/<fecha>/operacion_<n>.md`, copiar de la plantilla de abajo)

| Campo | Contenido |
|---|---|
| Entrada | ficheros (nombre, sha256), pedido en Siddex, proveedor |
| Resultado esperado | lo que hizo Fernando (de `esperado.xlsx`) |
| Resultado obtenido | lo que dice la bandeja/traza: proveedor, número normalizado, pedido, semáforo, avisos por línea |
| Diferencias | campo a campo |
| Motivo | lectura / equivalencia / normalización / regla de cotejo / dato de Siddex / regla que falta |
| Corrección realizada | commit o "pendiente de IDM" (enlace a PENDIENTE-IDM.md) |
| Regresión añadida | caso en `fixtures/golden/` o `fixtures/problematicos/` (anonimizado) |

## 4. Métricas (se calculan sobre el total del piloto)

| Métrica | Definición |
|---|---|
| Documentos leídos correctamente | proveedor, número, fecha, nº de líneas y cada línea (código, cantidad, precio, dto) iguales a lo esperado / documentos con texto |
| Documentos que requieren OCR | resultado REQUIERE_OCR / total (escaneos y fotos) |
| Pedidos identificados correctamente | pedido elegido == pedido que usó Fernando / albaranes con pedido |
| Albaranes vinculados correctamente | albaranes que la factura encuentra por número normalizado / albaranes referenciados |
| Facturas vinculadas correctamente | facturas con todos sus albaranes encontrados e importes cuadrados / facturas |
| Líneas cotejadas correctamente | líneas con el mismo veredicto (verde/ámbar y motivo) que Fernando / líneas |
| Incidencias detectadas | incidencias que Fernando marcó y el programa también / incidencias de Fernando (sensibilidad) |
| Falsos positivos | avisos del programa que Fernando no habría dado (ámbar que él aprueba sin tocar) |
| Falsos negativos | incidencias de Fernando que el programa dio por buenas |
| Operaciones con intervención humana | documentos que Fernando tuvo que corregir (equivalencia, número, rechazo) / documentos |

Cálculo: `ejecutar.bat benchmark_lector --carpeta datos/piloto/<operacion>` para la lectura (con `.json` de verdad por
documento), y para el resto se rellena la hoja `docs/piloto/metricas.xlsx` a mano a partir de las trazas (hasta que
haya volumen para automatizarlo).

## 5. Criterio para pasar al hito 3 (recepción asistida)
- Lectura ≥ 90 % en documentos con texto de los cinco grandes.
- Pedido identificado correctamente en el 100 % de los albaranes que traen "su pedido" y ≥ 80 % del resto.
- Cero falsos negativos en precio (ningún precio distinto dado por bueno).
- Falsos positivos explicables y con regla pendiente apuntada.

## Plantilla de operación
```
# Operación <n> · <proveedor> · <mes>
Entrada: ...
Esperado: ...
Obtenido: ...
Diferencias: ...
Motivo: ...
Corrección: ...
Regresión: ...
```
