# Instalación en el servidor Windows de IDM

Todo corre en un PC o servidor Windows de IDM con Python 3.12. Sin Docker ni servicios externos.

## 1. Instalar

```
:: Python 3.12 desde python.org (marcar "Add python.exe to PATH")
cd C:\idm-compras                 :: carpeta del programa (clonada de GitHub o copiada)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.ejemplo .env
notepad .env                      :: rutas, buzones, SMTP, MODO_SIMULACION=true
python -m pytest                  :: todo en verde antes de seguir
ejecutar.bat migrar               :: crea datos\idm.db
```

Carpetas que hay que rellenar (ver `datos/README.md`):
- `datos\siddex\`: exports de Siddex (Maestro de Artículos, Proveedores, Fabricantes, Pedidos, Stock, escandallos .xls).
- `datos\planning\PLANNING_IDM_MENSUAL.xlsx`.
- `datos\entrada\`: aquí se dejan PDFs o fotos a mano; los buzones IMAP descargan aquí también.

Las contraseñas de los buzones y del SMTP las teclea en `.env` quien lleve la informática de IDM. **Nunca se envían por escrito.**

## 2. Tareas programadas

Abrir "Programador de tareas" o usar `schtasks` desde un cmd con permisos (ajustar rutas y usuario):

```
:: Procesar buzones y carpeta de entrada cada 10 minutos
schtasks /Create /TN "IDM compras - procesar buzon" /SC MINUTE /MO 10 ^
  /TR "C:\idm-compras\ejecutar.bat procesar_buzon" /RU "IDM\usuario" /RL LIMITED

:: Bandeja de revisión al iniciar sesión (o al arrancar, con /SC ONSTART y usuario de servicio)
schtasks /Create /TN "IDM compras - bandeja" /SC ONLOGON ^
  /TR "C:\idm-compras\ejecutar.bat servir_bandeja" /RU "IDM\usuario"

:: Necesidades del mes: el día 1 a las 7:00 (la hoja del planning se pasa por argumento)
schtasks /Create /TN "IDM compras - calcular mes" /SC MONTHLY /D 1 /ST 07:00 ^
  /TR "C:\idm-compras\ejecutar.bat calcular_mes --hoja SEPT_26" /RU "IDM\usuario"
```

`generar_pedidos` se lanza a mano cuando Fernandillo quiere (o se programa a diario si se decide así).

La bandeja queda en `http://<ip-del-servidor>:8000` para los PCs de la red local. No se expone a Internet.

## 3. Actualizar el programa

```
cd C:\idm-compras
git pull                          :: o copiar la carpeta nueva encima
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
ejecutar.bat migrar
```

## 4. Si algo falla

- `ejecutar.bat procesar_buzon --sin-imap` procesa solo la carpeta (descarta el correo como causa).
- `ejecutar.bat ejecutar_golden` y `ejecutar.bat benchmark_lector` comprueban que el programa sigue leyendo bien.
- La tabla `eventos` de `datos\idm.db` cuenta qué se hizo con cada documento (se abre con "DB Browser for SQLite").
- Un documento mal leído se rechaza en la bandeja y se teclea en Siddex como siempre: el circuito manual sigue existiendo.
- Copia de seguridad: `datos\` entera (base de datos, documentos procesados, equivalencias aprendidas).
