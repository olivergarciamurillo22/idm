"""Stock y pendiente de recibir: qué se descuenta antes de pedir y con qué prudencia.
Fernandillo no mira el stock de Siddex, así que puede no estar al día: por defecto solo se descuenta una lista
corta de componentes grandes (motores, bombas) hasta confirmar que Siddex se parece a las estanterías."""

from decimal import Decimal

from idm.dominio.dinero import CERO
from idm.necesidades.calculo import Necesidad, redondear_a_multiplo

# PENDIENTE (Fernandillo): códigos de componentes grandes cuyo stock en Siddex sí es fiable.
# Vacío = no se descuenta nada salvo que se llame con descontar_todo=True.
COMPONENTES_GRANDES: frozenset[str] = frozenset()


def descontar(
    necesidades: list[Necesidad],
    stock: dict[str, Decimal],
    pendiente_recibir: dict[str, Decimal],
    descontar_todo: bool = False,
    codigos_fiables: frozenset[str] = COMPONENTES_GRANDES,
) -> list[Necesidad]:
    """Recalcula neta y a pedir descontando stock y pendiente solo en los códigos fiables (o en todos)."""
    for n in necesidades:
        if descontar_todo or n.codigo in codigos_fiables:
            n.stock = stock.get(n.codigo, CERO)
            n.pendiente_recibir = pendiente_recibir.get(n.codigo, CERO)
        else:
            n.stock = CERO
            n.pendiente_recibir = CERO
        n.cantidad_neta = max(CERO, n.cantidad_bruta - n.stock - n.pendiente_recibir)
        n.cantidad_pedir = redondear_a_multiplo(n.cantidad_neta, n.multiplo)
        n.importe = (n.cantidad_pedir * n.precio).quantize(Decimal("0.01")) if n.precio is not None else CERO
    return necesidades
