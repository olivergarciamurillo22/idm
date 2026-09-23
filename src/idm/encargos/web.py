"""Formulario web de encargos (móvil): proveedor, artículo, cantidad. Se monta dentro de la bandeja.
También acepta el texto con formato fijo de mensaje.py para pegar un WhatsApp entero.
No decide nada: guarda en el RepositorioEncargos que le inyecten."""

from decimal import Decimal

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from idm.dominio.dinero import a_decimal
from idm.dominio.estados import EstadoEncargo, OrigenEncargo
from idm.encargos import mensaje
from idm.encargos.registro import Encargo, RepositorioEncargos


def crear_router(repositorio: RepositorioEncargos, plantillas) -> APIRouter:
    router = APIRouter()

    @router.get("/encargos", response_class=HTMLResponse)
    def formulario(request: Request, ok: str = "", error: str = ""):
        pendientes = repositorio.listar(EstadoEncargo.PENDIENTE)
        return plantillas.TemplateResponse(request, "encargos.html", {
            "pendientes": pendientes, "ok": ok, "error": error, "formato": mensaje.FORMATO,
        })

    @router.post("/encargos")
    def registrar(proveedor: str = Form(""), articulo: str = Form(""), cantidad: str = Form(""),
                  unidad: str = Form("UD"), quien: str = Form(""), texto: str = Form("")):
        if texto.strip():
            r = mensaje.interpretar(texto, quien=quien)
            for e in r.encargos:
                repositorio.guardar(e)
            error = " · ".join(r.errores)
            return RedirectResponse(f"/encargos?ok={len(r.encargos)}&error={error}", status_code=303)
        cant = a_decimal(cantidad)
        if not proveedor.strip() or not articulo.strip() or cant is None or cant <= Decimal("0"):
            return RedirectResponse("/encargos?error=Faltan+proveedor,+artículo+o+cantidad", status_code=303)
        repositorio.guardar(Encargo(proveedor=proveedor.strip(), articulo=articulo.strip(), cantidad=cant,
                                    unidad=(unidad or "UD").upper(), quien=quien, origen=OrigenEncargo.WEB))
        return RedirectResponse("/encargos?ok=1", status_code=303)

    @router.post("/encargos/{id_encargo}/anular")
    def anular(id_encargo: str):
        repositorio.marcar([id_encargo], EstadoEncargo.ANULADO)
        return RedirectResponse("/encargos", status_code=303)

    return router
