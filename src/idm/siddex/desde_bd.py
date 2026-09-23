"""SiddexDesdeBD: lectura directa de la base de datos de Siddex en SOLO LECTURA (segundo nivel, ARQUITECTURA §8).
Vacío hasta tener acceso al servidor (Era Informática) y un usuario de solo lectura.
Nunca escribirá: la escritura va por SiddexEscritura y solo por una vía soportada."""

# TODO(Pedro): cuando haya acceso de solo lectura a la BD de Siddex:
#   1. Confirmar motor y tablas (PROVEEDR, ENTRADA, maestro de artículos, pedidos, stock).
#   2. Implementar SiddexDesdeBD con la misma interfaz que SiddexDesdeExcel.
#   3. Usuario de BD de solo lectura; cadena de conexión en .env (SIDDEX_BD_URL), nunca en el código.
#   4. Tests contra un SQLite con las mismas tablas y datos ficticios.


class SiddexDesdeBD:
    def __init__(self, url: str) -> None:
        raise NotImplementedError("Sin acceso a la BD de Siddex todavía. Usar SiddexDesdeExcel.")
