"""Política técnica de envío de documentos fuera de la máquina: ALLOW_EXTERNAL_DOCUMENT_PROCESSING (por defecto false)
y lista explícita de proveedores externos permitidos (EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED). Ambas deben dejarlo pasar.
Es una comprobación en código que ejecutan los propios proveedores cloud antes de construir la petición, no un aviso."""

from dataclasses import dataclass


class _Denegado(Exception):
    pass


@dataclass(frozen=True)
class PoliticaEnvioExterno:
    permitido: bool = False
    proveedores: frozenset[str] = frozenset()

    @classmethod
    def desde_config(cls, cfg) -> "PoliticaEnvioExterno":
        return cls(bool(cfg.allow_external_document_processing), frozenset(cfg.external_document_providers_allowed))

    def motivo_rechazo(self, proveedor: str) -> str | None:
        if not self.permitido:
            return (
                f"Envío de documentos a '{proveedor}' rechazado: ALLOW_EXTERNAL_DOCUMENT_PROCESSING=false. "
                "Solo se activa cuando IDM confirme por escrito que los documentos pueden procesarse fuera."
            )
        if proveedor not in self.proveedores:
            return (
                f"Envío de documentos a '{proveedor}' rechazado: no está en EXTERNAL_DOCUMENT_PROVIDERS_ALLOWED "
                f"({', '.join(sorted(self.proveedores)) or 'vacío'}). Cada proveedor externo se autoriza uno a uno."
            )
        return None

    def comprobar(self, proveedor: str) -> None:
        from idm.documental.base import ProcesamientoExternoNoAutorizado

        if (motivo := self.motivo_rechazo(proveedor)) is not None:
            raise ProcesamientoExternoNoAutorizado(motivo)


NINGUNO = PoliticaEnvioExterno()
