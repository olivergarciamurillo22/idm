"""Estados por dimensión (documento, pedido, precio, entrega) y semáforo del cotejo.
Cada enumeración es una dimensión independiente: un documento tiene las cuatro a la vez.
No contiene transiciones ni lógica: eso lo decide el código que cambia el estado."""

from enum import StrEnum


class EstadoDocumento(StrEnum):
    """Ciclo: RECIBIDO (pendiente) → LEIDO → COTEJADO → EN_REVISION (requiere revisión) → APROBADO | RECHAZADO.
    Laterales: ERROR (fallo técnico, se puede reprocesar) y NO_PROCESABLE (corrupto, vacío o formato no admitido).
    Los duplicados no crean documento: quedan como evento documento.duplicado sobre el original."""

    RECIBIDO = "RECIBIDO"
    LEIDO = "LEIDO"
    COTEJADO = "COTEJADO"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    ERROR = "ERROR"
    NO_PROCESABLE = "NO_PROCESABLE"


class ResultadoLectura(StrEnum):
    """Qué ha podido hacer el lector con el fichero. Nunca se devuelve "datos vacíos" sin decir por qué."""

    PDF_TEXTO = "PDF_TEXTO"  # PDF con capa de texto: leído
    IMAGEN_OCR = "IMAGEN_OCR"  # imagen o escaneo leído por OCR local: campos con confianza, revisar en bandeja
    REQUIERE_OCR = "REQUIERE_OCR"  # PDF escaneado o imagen sin motor OCR disponible o configurado
    PROVEEDOR_NO_DISPONIBLE = "PROVEEDOR_NO_DISPONIBLE"  # el servicio de lectura falló técnicamente: reintentar luego
    EXCEL = "EXCEL"  # hoja de cálculo en la entrada: no es un documento de proveedor
    VACIO = "VACIO"  # fichero de 0 bytes
    CORRUPTO = "CORRUPTO"  # no se puede abrir
    NO_SOPORTADO = "NO_SOPORTADO"  # extensión desconocida


class CodigoError(StrEnum):
    LECTURA_CORRUPTO = "LECTURA_CORRUPTO"
    LECTURA_VACIO = "LECTURA_VACIO"
    LECTURA_NO_SOPORTADA = "LECTURA_NO_SOPORTADA"
    LECTURA_EXCEL = "LECTURA_EXCEL"
    LECTURA_REQUIERE_OCR = "LECTURA_REQUIERE_OCR"
    PROVEEDOR_DESCONOCIDO = "PROVEEDOR_DESCONOCIDO"
    FICHERO_INACCESIBLE = "FICHERO_INACCESIBLE"
    GATEWAY_SIDDEX = "GATEWAY_SIDDEX"
    CONFLICTO_DUPLICADO = "CONFLICTO_DUPLICADO"
    REPROCESO_NO_PERMITIDO = "REPROCESO_NO_PERMITIDO"
    PROVEEDOR_DOCUMENTAL_NO_DISPONIBLE = "PROVEEDOR_DOCUMENTAL_NO_DISPONIBLE"
    PROVEEDOR_DOCUMENTAL_ERROR = "PROVEEDOR_DOCUMENTAL_ERROR"
    PROCESAMIENTO_EXTERNO_NO_AUTORIZADO = "PROCESAMIENTO_EXTERNO_NO_AUTORIZADO"
    INESPERADO = "INESPERADO"


class RelacionPedido(StrEnum):
    CON_PEDIDO = "CON_PEDIDO"
    SIN_PEDIDO = "SIN_PEDIDO"
    PEDIDO_PROPUESTO = "PEDIDO_PROPUESTO"


class EstadoPrecio(StrEnum):
    CONOCIDO = "CONOCIDO"
    PENDIENTE_FACTURA = "PENDIENTE_FACTURA"


class EstadoEntrega(StrEnum):
    COMPLETA = "COMPLETA"
    PARCIAL = "PARCIAL"
    EXCESO = "EXCESO"


class Semaforo(StrEnum):
    VERDE = "VERDE"  # todo cuadra: artículo, cantidad, precio y descuento
    AMBAR = "AMBAR"  # algo no cuadra o falta: revisión humana con motivo


class TipoDocumento(StrEnum):
    ALBARAN = "ALBARAN"
    FACTURA = "FACTURA"
    DESCONOCIDO = "DESCONOCIDO"


class TipoAviso(StrEnum):
    SIN_PEDIDO = "SIN_PEDIDO"
    LINEA_SIN_PEDIDO = "LINEA_SIN_PEDIDO"
    ARTICULO_NO_RESUELTO = "ARTICULO_NO_RESUELTO"
    PRECIO_DISTINTO = "PRECIO_DISTINTO"
    DESCUENTO_DISTINTO = "DESCUENTO_DISTINTO"
    EXCESO_CANTIDAD = "EXCESO_CANTIDAD"
    PRECIO_PENDIENTE = "PRECIO_PENDIENTE"
    PORTES_NO_PACTADOS = "PORTES_NO_PACTADOS"
    ALBARAN_NO_ENCONTRADO = "ALBARAN_NO_ENCONTRADO"
    IMPORTE_NO_CUADRA = "IMPORTE_NO_CUADRA"
    PRECIO_CAMBIADO = "PRECIO_CAMBIADO"
    LECTURA_INCOMPLETA = "LECTURA_INCOMPLETA"


class OrigenEncargo(StrEnum):
    PLANNING = "PLANNING"
    WEB = "WEB"
    MENSAJE = "MENSAJE"
    ALBARAN = "ALBARAN"  # pedido propuesto a partir de un albarán sin pedido


class EstadoEncargo(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_PEDIDO = "EN_PEDIDO"
    ANULADO = "ANULADO"
