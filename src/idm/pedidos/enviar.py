"""Envío del pedido por correo al proveedor: interfaz Correo con CorreoSimulado (.eml en disco) y CorreoSMTP.
El texto del correo es una plantilla fija escrita por IDM y rellenada con datos: ningún modelo redacta nada.
En MODO_SIMULACION nunca sale nada: el .eml se abre con Outlook y lo envía una persona."""

import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from idm.dominio.modelos import Pedido, Proveedor

ASUNTO = "Pedido de compra {numero} - {empresa}"
CUERPO = """Buenos días,

Adjuntamos nuestro pedido de compra nº {numero} con fecha {fecha}.
Por favor, indicad este número en el albarán y en la factura.

Un saludo,
{empresa}
{telefono}
"""


@dataclass
class Mensaje:
    para: str
    asunto: str
    cuerpo: str
    adjunto: Path | None = None


class Correo(Protocol):
    def enviar(self, mensaje: Mensaje) -> str: ...


def componer(pedido: Pedido, proveedor: Proveedor, empresa: dict[str, str], pdf: Path | None) -> Mensaje:
    if not proveedor.email:
        raise ValueError(f"El proveedor {proveedor.nombre} no tiene correo en el maestro")
    datos = {
        "numero": pedido.numero,
        "empresa": empresa.get("nombre", "IDM"),
        "fecha": f"{pedido.fecha:%d/%m/%Y}" if pedido.fecha else "",
        "telefono": empresa.get("telefono", ""),
    }
    return Mensaje(para=proveedor.email, asunto=ASUNTO.format(**datos), cuerpo=CUERPO.format(**datos), adjunto=pdf)


def _construir(mensaje: Mensaje, remitente: str) -> EmailMessage:
    em = EmailMessage()
    em["From"] = remitente
    em["To"] = mensaje.para
    em["Subject"] = mensaje.asunto
    em.set_content(mensaje.cuerpo)
    if mensaje.adjunto:
        em.add_attachment(
            mensaje.adjunto.read_bytes(), maintype="application", subtype="pdf", filename=mensaje.adjunto.name
        )
    return em


class CorreoSimulado:
    """Escribe el correo como .eml en una carpeta. Devuelve la ruta. No conecta con ningún servidor."""

    def __init__(self, carpeta: Path, remitente: str = "pedidos@simulado.local") -> None:
        self.carpeta = Path(carpeta)
        self.remitente = remitente

    def enviar(self, mensaje: Mensaje) -> str:
        self.carpeta.mkdir(parents=True, exist_ok=True)
        numero = mensaje.asunto.split(" ")[3] if mensaje.asunto.count(" ") >= 3 else "correo"
        nombre = f"{datetime.now():%Y%m%d_%H%M%S}_{numero}.eml"
        ruta = self.carpeta / nombre
        ruta.write_bytes(bytes(_construir(mensaje, self.remitente)))
        return str(ruta)


class CorreoSMTP:
    def __init__(self, host: str, puerto: int, usuario: str, clave: str, remitente: str) -> None:
        self.host, self.puerto, self.usuario, self.clave, self.remitente = host, puerto, usuario, clave, remitente

    def enviar(self, mensaje: Mensaje) -> str:
        em = _construir(mensaje, self.remitente)
        with smtplib.SMTP(self.host, self.puerto, timeout=30) as smtp:
            smtp.starttls()
            if self.usuario:
                smtp.login(self.usuario, self.clave)
            smtp.send_message(em)
        return f"enviado a {mensaje.para} ({datetime.now():%d/%m/%Y %H:%M})"
