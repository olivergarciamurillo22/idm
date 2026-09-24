"""Orquesta el cotejo de un albarán leído: interpreta, busca el pedido en el gateway, llama a la función pura,
y si no hay pedido propone uno. Devuelve todo junto (albarán, pedido, cotejo, propuesta, avisos, eventos).
No toca la base de datos ni la bandeja: eso lo hace tareas/procesar_buzon."""

from dataclasses import dataclass, field

from idm.cotejo.interpretar import Evento, interpretar_albaran
from idm.cotejo.proponer_pedido import proponer
from idm.dominio.cotejar import cotejar
from idm.dominio.modelos import Albaran, Aviso, Cotejo, DocumentoLeido, Pedido
from idm.dominio.reglas import REGLAS_POR_DEFECTO, ReglasCotejo
from idm.equivalencias.tabla import TablaEquivalencias
from idm.siddex.gateway import SiddexGateway


@dataclass
class ResultadoDocumento:
    albaran: Albaran
    pedido: Pedido | None
    cotejo: Cotejo
    pedido_propuesto: Pedido | None
    metodo_pedido: str  # "nuestro_pedido", "pedido_abierto", "ninguno"
    proveedor_metodo: str = "no_resuelto"
    avisos: list[Aviso] = field(default_factory=list)
    eventos: list[Evento] = field(default_factory=list)


def buscar_pedido(albaran: Albaran, gateway: SiddexGateway) -> tuple[Pedido | None, str]:
    """Primero el número que trae el albarán; si no, el pedido abierto del proveedor con más líneas en común."""
    if albaran.nuestro_pedido:
        pedido = gateway.pedido(albaran.nuestro_pedido)
        if pedido is not None:
            return pedido, "nuestro_pedido"
    codigos = {li.codigo_idm for li in albaran.lineas if li.codigo_idm}
    referencias = {li.codigo_proveedor for li in albaran.lineas if li.codigo_proveedor}
    mejor, coincidencias = None, 0
    for pedido in gateway.pedidos_abiertos(albaran.proveedor):
        n = sum(
            1
            for lp in pedido.lineas
            if lp.codigo_idm in codigos or (lp.codigo_proveedor and lp.codigo_proveedor in referencias)
        )
        if n > coincidencias:
            mejor, coincidencias = pedido, n
    return (mejor, "pedido_abierto") if mejor else (None, "ninguno")


def cotejar_documento(
    doc: DocumentoLeido, gateway: SiddexGateway, tabla: TablaEquivalencias, reglas: ReglasCotejo = REGLAS_POR_DEFECTO
) -> ResultadoDocumento:
    interpretado = interpretar_albaran(doc, tabla, gateway.proveedores())
    albaran = interpretado.albaran
    pedido, metodo = buscar_pedido(albaran, gateway)
    eventos = interpretado.eventos + [
        Evento("pedido.buscado", {"metodo": metodo, "pedido": pedido.numero if pedido else None})
    ]
    resultado_cotejo = cotejar(albaran, pedido, reglas)
    eventos.append(
        Evento(
            "precio.comparado",
            {
                "semaforo": resultado_cotejo.semaforo,
                "entrega": resultado_cotejo.entrega,
                "precio": resultado_cotejo.precio,
                "avisos": [a.tipo for a in resultado_cotejo.todos_los_avisos],
            },
        )
    )
    propuesto = None
    if pedido is None:
        propuesto = proponer(albaran, gateway.articulos())
        eventos.append(Evento("pedido.propuesto", {"numero": propuesto.numero, "lineas": len(propuesto.lineas)}))
    return ResultadoDocumento(
        albaran=albaran,
        pedido=pedido,
        cotejo=resultado_cotejo,
        pedido_propuesto=propuesto,
        metodo_pedido=metodo,
        proveedor_metodo=interpretado.proveedor_metodo,
        avisos=interpretado.avisos,
        eventos=eventos,
    )
