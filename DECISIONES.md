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

## 2026-09-24 · Estructura de fixtures: ficticios / reales anonimizados / golden / problematicos / no_procesables
`fixtures/ficticios/` (inventados, generados por script), `fixtures/reales/` (solo `*.anonimizado.*` con fila en
`ANONIMIZACION.md`; el resto ignorado), `fixtures/golden/` (resultado esperado), `fixtures/problematicos/` (casos sin
regla de IDM, tests xfail) y `fixtures/no_procesables/` (corrupto, vacío, Excel, texto, escaneo sin texto).
Se eligió esto frente a `tests/fixtures/` porque los fixtures los usan también las tareas (`benchmark_lector`,
`ejecutar_golden`) fuera de pytest.

## 2026-09-24 · Tres capas contra la fuga de datos reales
1) `.gitignore` ignora pdf/xls/xlsx/eml/imágenes en todo el repo y solo los readmite en las carpetas de fixtures
permitidas; 2) `.githooks/pre-commit` bloquea datos/, documentos fuera de fixtures, reales sin `.anonimizado.`, `.env`
y ficheros > 5 MB; 3) `tests/unit/test_proteccion_datos.py` comprueba las dos cosas. Cada clon nuevo debe ejecutar
`git config core.hooksPath .githooks` (está en docs/instalacion-windows.md).

## 2026-09-24 · El lector responde siempre con un ResultadoLectura explícito
`PDF_TEXTO`, `REQUIERE_OCR` (escaneo o imagen), `EXCEL`, `VACIO`, `CORRUPTO` (no abre, o .pdf que no empieza por %PDF),
`NO_SOPORTADO`. Ningún camino devuelve "datos vacíos" sin motivo. OCR sigue fuera de alcance: REQUIERE_OCR deja el
documento EN_REVISION para que Fernando lo teclee.

## 2026-09-24 · Estados nuevos ERROR y NO_PROCESABLE; errores como datos
`EstadoDocumento` añade ERROR (fallo técnico inesperado, con traceback guardado, reprocesable) y NO_PROCESABLE (corrupto,
vacío, Excel, extensión desconocida: alguien tiene que mirar el fichero). Los errores conocidos son `ErrorProcesamiento`
(código cerrado `CodigoError`, mensaje, recuperable, detalle) guardados con el documento; la excepción genérica solo
queda como red de seguridad en `procesar()` para que un fichero raro no tumbe el lote. Los duplicados siguen sin crear
documento: son un evento sobre el original.

## 2026-09-24 · Trazabilidad por ejecución: Ejecucion + Traza por documento + reglas evaluadas
Cada pasada de `procesar_buzon` es una fila en `ejecuciones` (id, tarea, inicio/fin, versión, contadores). Cada documento
guarda una `Traza` (fichero, sha, resultado de lectura, tipo, proveedor y método, campos extraídos, normalizaciones,
artículos con método, pedido y método, albaranes relacionados, factura, reglas con resultado, diferencias, errores,
estado final, nº de reproceso) y todos sus eventos llevan `ejecucion_id`. Las reglas las escribe la propia función pura
(`CotejoLinea.reglas`), así la traza no reinterpreta el cotejo. `VERSION_PROCESAMIENTO` en `cotejo/procesar.py` se
cambia cuando cambia algo que altera el resultado. Sin sistema de observabilidad aparte: es JSON en la base de datos.

## 2026-09-24 · Idempotencia: sha256 primero, (proveedor, tipo, número) después, y la base de datos manda
Mismo contenido (aunque cambie el nombre) → `duplicado_sha`, evento sobre el original, fichero retirado de la entrada.
Mismo número con contenido distinto → `duplicado_numero`. Si dos procesos se cruzan, la restricción única de la BD
lanza `ConflictoDuplicado` y `procesar()` lo resuelve como duplicado sin dejar nada a medias. Reproceso solo explícito
(`--reprocesar` o `--reprocesar-id`): conserva id y fecha de recepción, incrementa `reprocesos`, y se niega si el
documento está APROBADO. Lo que ya está registrado no se toca al volver a pasar el mismo fichero.

## 2026-09-24 · procesar_buzon es de instancia única
Bloqueo por fichero con O_EXCL (`datos/procesar_buzon.lock`, caducidad 2 h) para que la tarea programada de cada
10 minutos no se pise a sí misma si una pasada tarda más.

## 2026-09-24 · Columnas de Siddex: configuración central, alias externos e informe por fichero
`siddex/columnas.py` es el único sitio con los nombres de columna (campo, alias, requerida, descripción); marcado
PROVISIONAL hasta tener los exports reales. Alias extra sin tocar código en `datos/siddex/columnas.json`. Cada lectura
deja un `InformeColumnas` (encontradas ← cabecera real, faltantes requeridas/opcionales, columnas sin uso, fila de
cabecera, nº de filas). Falta una requerida → `ColumnasFaltantes` con mensaje que lista las cabeceras vistas; el
gateway no estricto devuelve vacío y lo apunta en `avisos` (estricto=True lanza). Las filas llevan siempre todos los
campos (None si la columna no está) para que ningún consumidor reviente por KeyError. `revisar_exports` imprime todo
esto: es lo primero que se ejecuta cuando lleguen los ficheros reales.

## 2026-09-24 · Caché de pedidos por mtime en SiddexDesdeExcel
`pedidos_abiertos`, `pedido` y `pendiente_recibir` releían el Excel en cada llamada (una por documento procesado).
Ahora se cachea por fecha de modificación del fichero; al sustituir el export, se relee solo.

## 2026-09-24 · Casos sin regla de IDM: representados, no decididos
`fixtures/problematicos/` (P01 segundo albarán del mismo pedido con Siddex sin refrescar, P02 total impreso distinto de
la suma de líneas) y tres tests `xfail(strict=True)` en `tests/unit/test_escenarios.py` (los dos anteriores y la factura
parcial). Cada uno tiene un `PENDIENTE.md` o un motivo que dice qué decisión falta. Cuando IDM decida y se implemente,
el XPASS estricto obliga a moverlos a golden. La factura parcial hoy sale VERDE y solo informa (`lineas_no_facturadas`):
es provisional, no una regla.

## 2026-09-24 · HEIC de iPhone entra por el mismo circuito
`pillow-heif` (pip, con ruedas para Windows) registra HEIC/HEIF en Pillow. `albaranes/imagenes.py` abre cualquier formato
aplicando la orientación EXIF, deja un derivado JPEG local nombrado por el sha del original (`derivados.jsonl` guarda la
relación) y nunca toca el original. Los derivados viven en `datos/` y no entran en git.

## 2026-09-24 · OCR local como prototipo detrás de una interfaz, decidido por benchmark
`MotorOCR` (reconocer(imagen) → ResultadoOCR) con `MotorTesseract` (binario local por subprocess) y `MotorNulo`.
`LectorImagenOCR` = imagen → preprocesado → orientación por confianza → OCR en varios modos → el mismo intérprete de texto
que el PDF. El dominio no sabe que existe el OCR. Se activa con `OCR_MOTOR=tesseract`; por defecto `ninguno` (REQUIERE_OCR).
Los números están en `docs/benchmark-lector-real.md`; Tesseract NO es decisión de producción.

## 2026-09-24 · Preprocesado: solo lo que el benchmark justifica
Tubería por defecto `contraste_3200,recorte_3200` (dos pasadas unidas): reescalar a 3200 px, gris, autocontraste, y una
segunda pasada recortando al área con texto. Binarizar y suavizar existen pero no se usan porque empeoran. La orientación
se decide probando 0/90/180/270 en pequeño y sumando la confianza de las palabras fiables (el OSD de Tesseract falla).

## 2026-09-24 · Plantillas describen layouts, no proveedores
`LAYOUT_A/B/C` recogen lo observado en papel real: dónde está el número (etiqueta arriba, valor debajo), su forma
(`XX Y00 0000000000`, `00.000000`, `0000/0.000`), el orden de columnas de las líneas y el ruido del pie. Los nombres
comerciales solo aparecen en el mapa proveedor→layout; los códigos Siddex y CIF reales viven en
`datos/proveedores_conocidos.csv` (fuera de git), que `equivalencias/proveedores.cargar_locales` funde con el registro.

## 2026-09-24 · Lo leído por OCR nunca es verde
Aunque el cotejo cuadre, un documento con `IMAGEN_OCR` queda ÁMBAR con el aviso de confianza y hay que aprobarlo mirando la
foto. Dos reparaciones deterministas se permiten porque la aritmética las confirma: importe sin coma ("256" → 2,56 si
cantidad × precio × dto lo da) y tipo ALBARAN si el número tiene la forma de albarán del proveedor.

## 2026-09-24 · Anotación manuscrita = últimos 4 dígitos del Nº Registro de Siddex (evidencia documental)
Las fotos muestran "9921" escrito en el albarán que Siddex registró como 20269921. No lo ha confirmado Fernando en
palabras, pero la evidencia es directa. El programa devuelve ese número al aprobar (ya estaba) y no intenta leerlo del papel.

## 2026-09-24 · Cloud como motor principal, Tesseract congelado como respaldo y baseline
Cambio de criterio de Oliver: el PC donde se desarrolla no es el entorno de procesamiento y no se persiguen puntos de OCR
local. Nueva capa `documental/` con `DocumentProvider` y un resultado común; implementados `TesseractProvider` (envuelve
el lector local sin cambiar su lógica), `AzureDocumentIntelligenceProvider` y `MistralDocumentAIProvider`; Google queda
como hueco. No se instalan más motores OCR locales: el intento con RapidOCR (ONNX) se deshizo sin commitear y se
recreó el entorno virtual desde `requirements.txt` para que no quedara nada.

## 2026-09-24 · "DocumentProvider" y no "proveedor"
En IDM "proveedor" es quien envía el albarán. Para no confundirlo, el motor de lectura se llama DocumentProvider y sus
implementaciones llevan el nombre del producto (AzureDocumentIntelligenceProvider…), como pidió Oliver.

## 2026-09-24 · APIs REST oficiales sin SDK
Azure Document Intelligence v4 (`2024-11-30`, `prebuilt-layout` con `features=keyValuePairs`, sondeo por
`Operation-Location`) y Mistral OCR (`POST /v1/ocr`, `table_format=markdown`, confianza por palabra opcional, anotación
de documento opcional). Se llaman con `urllib` de la biblioteca estándar a través de un cliente inyectable: cero
dependencias nuevas, instalación en Windows igual de simple, y tests sin red con respuestas grabadas ficticias.
Documentación consultada en las fuentes oficiales el 24/09/2026.

## 2026-09-24 · Privacidad técnica en cuatro puntos
Bandera `ALLOW_EXTERNAL_DOCUMENT_PROCESSING=false` por defecto + lista `EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED` + rechazo
al arrancar (router, `procesar_buzon` sale con código 3) + comprobación dentro de cada llamada externa. El benchmark
exige además `--autorizo-envio-externo`. Los tests reales de `tests/cloud` solo envían la imagen sintética ficticia y
por eso construyen su propia política en lugar de usar la bandera global. Los secretos de `Config` y de `Buzon` salen de
`repr()` (antes un `print(cfg)` habría mostrado la clave SMTP: corregido).

## 2026-09-24 · Fallo del proveedor = pendiente de reintento, no cambio de tercero
`ErrorTransitorio` (red, 408, 429, 5xx, sondeo agotado) → `ResultadoLectura.PROVEEDOR_NO_DISPONIBLE` → documento en
`ERROR` recuperable → `procesar_buzon --reintentar-pendientes`. `ErrorPermanente` (credenciales, documento rechazado,
cuota 0) → error no recuperable con mensaje. Solo hay respaldo si se configura `DOCUMENT_PROVIDER_FALLBACK`.

## 2026-09-24 · Motores locales reciben el original; externos, el JPEG derivado
Convertir el HEIC a un JPEG reducido antes de Tesseract bajaba sus aciertos, así que los motores locales reciben el
fichero original. A los externos se envía un JPEG a resolución completa (HEIC no es universal), con el sha del
original y del enviado en la traza.

## 2026-09-24 · Baseline de Tesseract: 33/50, no 35/50
Al congelar la baseline se repitió la corrida con la herramienta antigua y con la capa nueva: ambas dan referencia 5,
cantidad 7, precio 7, descuento 7, importe 7 = **33/50** (número 8/9, fecha 9/9, CIF 9/9, completos 4/9). El 35/50
publicado antes fue un error de suma; varias filas intermedias de `docs/benchmark-lector-real.md` tampoco coincidían
con sus corridas y la tabla se ha rehecho desde los JSON guardados.

## 2026-09-24 · Coste: tarifas fechadas en un fichero, volumen como argumento
`documental/tarifas.json` (o `DOCUMENT_PRICING_FILE`) con fecha y aviso de verificar. No se inventa el volumen mensual
de IDM: `estimar_costes --documentos-mes N`. Cada llamada real guarda su coste estimado.

## 2026-09-25 · Robustez para el Windows de IDM y para el uso real
- **Texto siempre en UTF-8**: toda lectura/escritura de texto y todo subprocess en modo texto llevan `encoding` explícito
  (en Windows Python usa cp1252 y rompe con acentos; la salida de Tesseract es UTF-8). Lo vigila
  `tests/unit/test_calidad_codigo.py` analizando el código, porque ruff no lo detecta con rutas de pytest.
- **Tests aislados del `.env` del desarrollador**: `IDM_ENV_FILE` permite apuntar a otro fichero y una fixture automática
  borra las variables del programa en cada test. Antes, un test que llamaba a `config.cargar()` leía el `.env` real
  (con la clave de Mistral), y con la bandera de envío activada podría haber hecho llamadas reales.
- **SQLite con bandeja y tarea a la vez**: modo WAL, `busy_timeout` de 30 s y una sesión por hilo (`scoped_session`).
  Antes la bandeja compartía una sesión entre hilos y dos escrituras simultáneas daban "database is locked".
- **`.env` con errores**: número vacío = valor por defecto; número o booleano mal escrito = `ConfiguracionInvalida` con
  el nombre de la variable. Un booleano con errata ya no se convierte en `false` en silencio.
- **Tesseract en Windows**: `TESSERACT_CMD`, y si no está en el PATH se busca en la ruta del instalador de UB Mannheim.
- **Límite de tamaño por proveedor**: la foto convertida supera los 4 MB del plan gratuito de Azure; la entrada se
  recomprime hasta el límite (`AZURE_DOCUMENT_INTELLIGENCE_MAX_BYTES`, Mistral 50 MB) sin bajar de 1.500 px y lo anota.
- **Mistral con un parámetro opcional no admitido** (confianza por palabra, formato de tablas): un reintento sin él, anotado.

## 2026-09-25 · Fixtures anonimizados: fuera los identificadores reales de la Fase 1
Los documentos "ficticios" de la Fase 1 se construyeron con los ejemplos del contexto maestro y las fotos confirmaron
que eran reales (nº de albarán, pedido, registro, códigos de artículo, referencias de proveedor, códigos de proveedor
en Siddex). Se sustituyen por valores inventados con la misma forma en fixtures, tests y documentación; el mapa de
productos versionado pasa a ser un ejemplo con códigos inventados (`necesidades/mapa_productos.ejemplo.csv`) y el real
va a `datos/mapa_productos.csv`, que las tareas usan si existe. Los códigos de proveedor en Siddex solo viven en
`datos/proveedores_conocidos.csv`. `tests/unit/test_sin_identificadores_reales.py` guarda solo huellas SHA-256 y falla
si alguno vuelve. **El historial de git sigue conteniéndolos** (commits desde la Fase 1): borrarlos exige reescribir el
historial y `push --force`, que solo se hará si Oliver lo decide.
