# Decisiones

Una entrada fechada por decisión importante. Lo que no está aquí ni en `docs/` no se asume: se pregunta.

## 2026-09-23 · Arquitectura sencilla en el servidor de IDM
Python 3.12, SQLite + SQLAlchemy 2 (portable a PostgreSQL por URL), FastAPI + Jinja2 en red local, tareas programadas de Windows.
Sin Docker obligatorio ni infraestructura cloud. Motivo: IDM pidió sencillez; dos desarrolladores; debe correr en su PC/servidor.

## 2026-09-23 · El modelo lee, no escribe
Los modelos de IA solo extraen datos de documentos entrantes. Toda decisión es código determinista. Ningún texto que salga de IDM lo redacta un modelo. Motivo: confianza de Ángel padre y trazabilidad.

## 2026-09-23 · Ningún dato de IDM en git
`datos/` ignorada desde el primer commit; tests con documentos ficticios en `fixtures/`. Códigos de artículo de ejemplo en fixtures son inventados.

## 2026-09-23 · Este repositorio no tiene relación con Nuray
Cuenta de GitHub: `olivergarciamurillo22`. Se prohíbe empujar a remotos de Nuray o usar su sesión de `gh`; lo bloquea `.githooks/pre-push` y lo fija `CLAUDE.md`.

## 2026-09-23 · pyproject.toml solo con configuración
Sin `[project]` ni build backend, por petición expresa. El paquete se ejecuta con `PYTHONPATH=src` mediante `ejecutar.bat` / `ejecutar.sh`; pytest lo resuelve con `pythonpath = ["src"]`.

## 2026-09-23 · Tolerancia cero en el cotejo de precio
Fernando: "tiene que cuadrar al céntimo". Bruto y descuento se comparan por separado; el importe de línea se redondea a dos decimales con ROUND_HALF_UP en `dominio/dinero.py` (5 × 9,14 × 0,55 = 25,135 → 25,14, como hace Siddex).

## 2026-09-23 · Exceso de cantidad y portes: ámbar, nunca verde
Fernando avisa cuando llega más de lo pedido. Portes solo verdes si están pactados para ese proveedor en las reglas.

## 2026-09-23 · Albarán sin precio no es error: es PENDIENTE_FACTURA
RECACOR y otros no ponen precio. La línea queda ámbar con motivo PRECIO_PENDIENTE y el precio se completa cuando llega la factura.

## 2026-09-23 · La función `cotejar` vive en `dominio/cotejar.py`
`cotejo/cotejar.py` (Oliver) solo orquesta: resuelve proveedor, artículos y pedido, y llama a la función pura. Así la función se prueba sin nada alrededor (principio 4).

## 2026-09-23 · Encargos en JSONL hasta que exista `almacen/`
`encargos/registro.py` define la interfaz `RepositorioEncargos` con una implementación en fichero (`datos/encargos.jsonl`) para que el hito 2 no dependa de la base de datos. En la Fase 6 se añade la implementación SQL sin cambiar a quien la usa.

## 2026-09-23 · Formato del PDF de pedido
No tenemos todavía un PDF real de `H:\0_PEDIDOS_TRANSMITIDOS`. `pedidos/pdf.py` genera un formato limpio con cabecera desde `.env`; se ajustará al formato de IDM cuando tengamos una muestra. PENDIENTE.

## 2026-09-23 · Correo de pedidos: primero simulado, luego borrador, luego automático
`MODO_SIMULACION=true` deja el correo como `.eml` en `datos/salida/correo/` con el PDF adjunto; Fernandillo lo abre y lo envía. Solo cuando lleve semanas sin fallos se pasa a envío automático.

## 2026-09-23 · Lector de imagen mínimo
`LectorImagenNulo` devuelve un documento sin líneas y con aviso "requiere lectura de imagen". Elegir OCR local o servicio externo depende de que IDM conteste si los documentos pueden salir de la empresa. La interfaz `leer(ruta)` no cambia.

## 2026-09-23 · Columnas de los exports de Siddex son provisionales
Solo está verificado el escandallo (BIFF2, columnas 0/4/5/11/12/15/16/17). Para Maestro de Artículos, Proveedores, Fabricantes, Pedidos y Stock, `siddex/desde_excel.py` lee por nombre de cabecera con una tabla al principio del fichero que hay que ajustar cuando lleguen los exports reales.

## 2026-09-23 · Longitud de línea 120 en ruff
Con nombres en español y docstrings de tres líneas, 100 quedaba corto. 120 mantiene el código legible en pantalla partida y evita partir docstrings.

## 2026-09-23 · Formato fijo para encargos por mensaje
`proveedor ; artículo ; cantidad [; unidad]`, una línea por encargo. Sin modelo que interprete texto libre: el formato es
deliberadamente rígido para que el registro sea inequívoco y quepa en un WhatsApp. El formulario web acepta lo mismo pegado.

## 2026-09-23 · Numeración provisional de pedidos
`P-AAAAMMDD-NN` hasta que el pedido se graba en Siddex; entonces se guarda `numero_siddex`. El PDF y el correo llevan el
provisional; en la hoja para Siddex aparece también para que Fernandillo lo relacione.

## 2026-09-23 · El lector de texto usa primero tablas con rejilla y después regex por línea
pdfplumber devuelve las tablas con rejilla limpias (cabecera + celdas); se mapean por nombre de cabecera. Si el PDF no
tiene rejilla se prueba una regex por línea. Las plantillas por proveedor real heredan la genérica hasta tener sus PDF.

## 2026-09-23 · La foto de albarán entra por el mismo circuito y sale con confianza 0
`LectorImagenNulo` no lee nada pero deja el documento en la bandeja con el aviso "requiere lectura de imagen". Así el
circuito ya funciona con papel fotografiado (Fernando teclea) mientras IDM decide si los documentos pueden salir.

## 2026-09-23 · Búsqueda del pedido para un albarán
Primero el "su pedido" que trae el albarán; si no viene o no existe, el pedido abierto del mismo proveedor con más
líneas en común (por código IDM o referencia del proveedor). Si no hay ninguno, SIN_PEDIDO y pedido propuesto.

## 2026-09-23 · Pedido propuesto se confirma en la bandeja y sale como hoja para Siddex
Fernandillo confirma en /pedidos; el albarán pasa a CON_PEDIDO con el número `PP-<albarán>` y se genera la misma hoja
Excel que para los pedidos normales. No se graba nada en Siddex por detrás.

## 2026-09-23 · Equivalencias confirmadas en la bandeja quedan aprendidas
Cuando Fernando escribe el código IDM de una referencia desconocida, se guarda en `datos/equivalencias_aprendidas.csv`
y se usa en los siguientes documentos (método "aprendida"). El Maestro de Fabricantes sigue mandando cuando existe.

## 2026-09-23 · ruff format como formato único
El código se formatea con `ruff format` (estilo black, 120 columnas) para que Pedro y Oliver no discutan estilo.

## 2026-09-23 · Base de datos: columnas indexadas + JSON con el detalle
`documentos`, `eventos`, `encargos` y `pedidos` en SQLAlchemy 2. Las columnas por las que se filtra (sha256, proveedor,
tipo, número, estado, semáforo) son columnas reales con índices y restricciones únicas (idempotencia la garantiza la BD);
el detalle (líneas, cotejo, lectura) va en una columna JSON con el volcado del modelo Pydantic. Sencillo de leer con
"DB Browser for SQLite" y portable a PostgreSQL sin cambiar código.

## 2026-09-23 · Alembic gestiona el esquema; 'ejecutar.bat migrar' lo aplica
Sin `create_all` en producción. La migración inicial es `migrations/versions/0001_esquema_inicial.py`. La URL sale de
`.env` (DATABASE_URL); en tests se pasa una URL temporal.

## 2026-09-23 · Los eventos de negocio tienen un catálogo cerrado
`almacen/eventos.TIPOS`. Un tipo nuevo se añade ahí y en la ARQUITECTURA; así la trazabilidad no se llena de nombres sueltos.

## 2026-09-24 · Dependencias HTTP: httpx2 sí, httpx no
Versiones instaladas: fastapi 0.141.1, starlette 1.7.0, uvicorn 0.53.0, httpx2 2.13.1. `starlette.testclient` importa
`httpx2` y solo cae a `httpx` (0.x) si no está; el metadato de Starlette dice "Test client built on httpx2". Nada del
código de producción usa ninguno de los dos: solo `TestClient` en tests. Por tanto `httpx` se quita de requirements
(estaba solo porque hacía pasar tests por accidente y ni siquiera llegó a instalarse) y `httpx2` se queda como
dependencia de desarrollo. Se fija `starlette>=1.0,<2` para que una actualización de FastAPI no cambie el cliente de tests.

## 2026-09-24 · Consola UTF-8 en Windows
Windows arranca la consola en cp1252 y `print` con acentos o "→" lanza UnicodeEncodeError. `tareas/_consola.preparar()`
reconfigura stdout/stderr y `ejecutar.bat` fija `chcp 65001` y `PYTHONIOENCODING=utf-8`.

## 2026-09-24 · El remoto se llama `idm`, no `idm-compras`
Oliver ha creado `github.com/olivergarciamurillo22/idm`. La carpeta local conserva el nombre `idm-compras`. Ningún
asistente configura el remoto ni empuja: lo hace Oliver.
