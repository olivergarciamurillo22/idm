"""Catálogo de eventos de negocio y ayuda para registrarlos. Son la trazabilidad funcional, separada de los logs.
Tipos: documento.recibido/leido/duplicado, proveedor.resuelto, articulo.resuelto (con método), pedido.buscado,
precio.comparado, pedido.propuesto, factura.cotejada, decision.tomada, pedido.generado, correo.enviado."""

from idm.almacen.documentos import Evento, Repositorio

TIPOS = (
    "documento.recibido",
    "documento.leido",
    "documento.duplicado",
    "documento.no_procesable",
    "documento.error",
    "documento.reprocesado",
    "proveedor.resuelto",
    "articulo.resuelto",
    "pedido.buscado",
    "precio.comparado",
    "pedido.propuesto",
    "factura.cotejada",
    "decision.tomada",
    "pedido.generado",
    "correo.enviado",
)


def registrar(repo: Repositorio, tipo: str, datos: dict, documento_id: str | None = None) -> Evento:
    if tipo not in TIPOS:
        raise ValueError(f"Evento desconocido: {tipo}. Añádelo a almacen/eventos.TIPOS")
    return repo.registrar_evento(Evento(tipo=tipo, documento_id=documento_id, datos=datos))
