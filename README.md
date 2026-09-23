# idm-compras

Automatización del circuito de compras de IDM (pedido de compra → albarán → recepción → factura) alrededor del ERP Siddex.
Calcula necesidades desde el planning y los escandallos, registra encargos, genera y envía pedidos, lee albaranes y facturas,
los coteja al céntimo contra el pedido y deja lo que no cuadra en una bandeja de revisión. **El modelo lee, no escribe.**

Léase `ARQUITECTURA.md` (principios y piezas) y `DECISIONES.md` (por qué se hizo cada cosa).

## Instalación (Windows o Mac/Linux)

```
git clone https://github.com/olivergarciamurillo22/idm-compras.git
cd idm-compras
python -m venv .venv                      # Python 3.12
.venv\Scripts\activate                    # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.ejemplo .env                    # Mac/Linux: cp .env.ejemplo .env
notepad .env                              # rutas, buzones, MODO_SIMULACION=true
python -m pytest                          # todo en verde
ejecutar.bat migrar                       # crea datos/idm.db (Mac/Linux: ./ejecutar.sh migrar)
ejecutar.bat servir_bandeja               # http://<ip-del-pc>:8000
```

## Cómo se ejecuta cada pieza

Todas las tareas se lanzan con `ejecutar.bat <tarea> [args]` (Windows) o `./ejecutar.sh <tarea> [args]`.

| Tarea | Qué hace | Ejemplo |
|---|---|---|
| `calcular_mes` | Planning × escandallos → Excel de necesidades por artículo | `ejecutar.bat calcular_mes --hoja SEPT_26` |
| `generar_pedidos` | Encargos + necesidades → pedido por proveedor: PDF, correo (simulado), hoja para Siddex | `ejecutar.bat generar_pedidos` |
| `procesar_buzon` | Lee buzones IMAP o `datos/entrada`, extrae, coteja y guarda en la base de datos | `ejecutar.bat procesar_buzon --carpeta datos/entrada` |
| `ejecutar_golden` | Ejecuta todos los casos de `fixtures/golden/` y muestra aciertos | `ejecutar.bat ejecutar_golden` |
| `benchmark_lector` | Aciertos por campo del lector sobre `fixtures/documentos/` | `ejecutar.bat benchmark_lector` |
| `servir_bandeja` | Bandeja de revisión web en la red local | `ejecutar.bat servir_bandeja` |
| `migrar` | Crea o actualiza el esquema de la base de datos (Alembic) | `ejecutar.bat migrar` |

Tests y lint:

```
python -m pytest
ruff check src tests
```

## Dónde va cada cosa

- `datos/` datos reales de IDM (ignorada por git). Ver `datos/README.md`.
- `fixtures/` documentos y exports **ficticios** para tests y golden dataset.
- `src/idm/` código. `docs/` cómo se hace hoy (as-is) y reglas por proveedor.
- Instalación como tarea programada de Windows: `docs/instalacion-windows.md`.
