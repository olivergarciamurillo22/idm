"""Aplicación FastAPI de la bandeja: crear_app(repositorio, encargos, cfg, aprender) devuelve la app lista para uvicorn.
Rutas: / (lista), /documentos/{id}, /documentos/{id}/fichero, aprobar, rechazar, equivalencia; /pedidos; /encargos.
Toda decisión que se toma aquí la toma una persona y queda como evento decision.tomada."""

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from idm.albaranes.imagenes import ImagenNoLegible, abrir, es_imagen
from idm.almacen.documentos import Evento, Repositorio
from idm.config import Config
from idm.dominio.estados import EstadoDocumento, RelacionPedido, Semaforo, TipoDocumento
from idm.encargos.registro import RepositorioEncargos
from idm.encargos.web import crear_router as router_encargos
from idm.equivalencias.tabla import TablaEquivalencias
from idm.pedidos import exportar_siddex
from idm.pedidos.pdf import nombre_seguro

PLANTILLAS = Path(__file__).with_name("plantillas")


def crear_app(
    repositorio: Repositorio,
    encargos: RepositorioEncargos,
    cfg: Config,
    tabla: TablaEquivalencias | None = None,
    proveedores: dict | None = None,
) -> FastAPI:
    app = FastAPI(title="IDM compras · bandeja")
    plantillas = Jinja2Templates(directory=str(PLANTILLAS))
    plantillas.env.globals["simulacion"] = cfg.modo_simulacion
    proveedores = proveedores or {}

    def evento(tipo: str, doc_id: str, datos: dict) -> None:
        repositorio.registrar_evento(Evento(tipo=tipo, documento_id=doc_id, datos=datos))

    @app.get("/", response_class=HTMLResponse)
    def lista(request: Request, estado: str = "", semaforo: str = "", proveedor: str = "", tipo: str = ""):
        docs = repositorio.listar(
            estado=EstadoDocumento(estado) if estado else None,
            semaforo=Semaforo(semaforo) if semaforo else None,
            proveedor=proveedor or None,
            tipo=TipoDocumento(tipo) if tipo else None,
        )
        return plantillas.TemplateResponse(
            request,
            "lista.html",
            {
                "documentos": docs,
                "estado": estado,
                "semaforo": semaforo,
                "proveedor": proveedor,
                "tipo": tipo,
                "estados": [e.value for e in EstadoDocumento],
            },
        )

    @app.get("/documentos/{id_doc}", response_class=HTMLResponse)
    def documento(request: Request, id_doc: str, ok: str = ""):
        doc = repositorio.obtener(id_doc)
        if doc is None:
            return HTMLResponse("No existe", status_code=404)
        return plantillas.TemplateResponse(
            request,
            "documento.html",
            {
                "d": doc,
                "eventos": repositorio.eventos(id_doc),
                "ok": ok,
                "es_pdf": doc.ruta.lower().endswith(".pdf"),
            },
        )

    @app.get("/documentos/{id_doc}/fichero")
    def fichero(id_doc: str, rot: int = 0, lado: int = 1800):
        """PDF tal cual; imagen (incluido HEIC) como JPEG derivado local con orientación EXIF y giro opcional."""
        doc = repositorio.obtener(id_doc)
        if doc is None or not Path(doc.ruta).exists():
            return HTMLResponse("Fichero no disponible", status_code=404)
        ruta = Path(doc.ruta)
        if not es_imagen(ruta):
            return FileResponse(doc.ruta)
        carpeta = cfg.ruta_datos / "derivados_bandeja"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{doc.sha256}_{rot % 360}_{lado}.jpg"
        if not destino.exists():
            try:
                img = abrir(ruta)
            except ImagenNoLegible as exc:
                return HTMLResponse(f"Imagen no legible: {exc}", status_code=415)
            if rot % 360:
                img = img.rotate(-(rot % 360), expand=True)
            img.thumbnail((lado, lado))
            img.convert("RGB").save(destino, "JPEG", quality=88)
        return FileResponse(destino, media_type="image/jpeg")

    @app.post("/documentos/{id_doc}/corregir")
    def corregir(
        id_doc: str,
        numero: str = Form(""),
        fecha: str = Form(""),
        proveedor: str = Form(""),
        nuestro_pedido: str = Form(""),
        quien: str = Form(""),
    ):
        """Corrección manual de la cabecera leída (OCR o PDF). Queda como evento; el cotejo se repite con reprocesar."""
        from datetime import date

        from idm.albaranes.normalizar import normalizar_numero

        doc = repositorio.obtener(id_doc)
        if doc is None:
            return HTMLResponse("No existe", status_code=404)
        cambios: dict[str, str] = {}
        if proveedor.strip() and proveedor.strip().upper() != doc.proveedor:
            cambios["proveedor"] = f"{doc.proveedor} → {proveedor.strip().upper()}"
            doc.proveedor = proveedor.strip().upper()
            if doc.albaran:
                doc.albaran.proveedor = doc.proveedor
        if numero.strip() and numero.strip() != doc.numero_original:
            nuevo = normalizar_numero(doc.proveedor, numero.strip())
            cambios["numero"] = f"{doc.numero} → {nuevo}"
            doc.numero_original, doc.numero = numero.strip(), nuevo
            if doc.albaran:
                doc.albaran.numero_original, doc.albaran.numero = numero.strip(), nuevo
        if fecha.strip() and doc.albaran:
            try:
                doc.albaran.fecha = date.fromisoformat(fecha.strip())
                cambios["fecha"] = fecha.strip()
            except ValueError:
                return HTMLResponse("Fecha no válida (AAAA-MM-DD)", status_code=400)
        if nuestro_pedido.strip() and doc.albaran:
            doc.albaran.nuestro_pedido = nuestro_pedido.strip()
            cambios["nuestro_pedido"] = nuestro_pedido.strip()
        if cambios:
            doc.notas = (doc.notas + " | " if doc.notas else "") + "corregido a mano: " + ", ".join(cambios)
            repositorio.guardar(doc)
            evento("decision.tomada", doc.id, {"decision": "CORRECCION_MANUAL", "quien": quien, "cambios": cambios})
        return RedirectResponse(f"/documentos/{id_doc}?ok=corregido", status_code=303)

    @app.post("/documentos/{id_doc}/aprobar")
    def aprobar(id_doc: str, numero_registro_siddex: str = Form(""), quien: str = Form(""), notas: str = Form("")):
        doc = repositorio.obtener(id_doc)
        if doc is None:
            return HTMLResponse("No existe", status_code=404)
        from datetime import datetime

        doc.estado = EstadoDocumento.APROBADO
        doc.numero_registro_siddex = numero_registro_siddex.strip() or None
        doc.decidido_por, doc.decidido_en, doc.notas = quien, datetime.now(), notas
        repositorio.guardar(doc)
        evento(
            "decision.tomada",
            doc.id,
            {
                "decision": "APROBADO",
                "quien": quien,
                "numero_registro_siddex": doc.numero_registro_siddex,
                "notas": notas,
            },
        )
        return RedirectResponse(f"/documentos/{id_doc}?ok=aprobado", status_code=303)

    @app.post("/documentos/{id_doc}/rechazar")
    def rechazar(id_doc: str, quien: str = Form(""), notas: str = Form("")):
        doc = repositorio.obtener(id_doc)
        if doc is None:
            return HTMLResponse("No existe", status_code=404)
        from datetime import datetime

        doc.estado = EstadoDocumento.RECHAZADO
        doc.decidido_por, doc.decidido_en, doc.notas = quien, datetime.now(), notas
        repositorio.guardar(doc)
        evento("decision.tomada", doc.id, {"decision": "RECHAZADO", "quien": quien, "notas": notas})
        return RedirectResponse(f"/documentos/{id_doc}?ok=rechazado", status_code=303)

    @app.post("/documentos/{id_doc}/equivalencia")
    def equivalencia(id_doc: str, linea: int = Form(...), codigo_idm: str = Form(...)):
        """Una persona confirma a qué código IDM corresponde una referencia del proveedor: queda aprendida."""
        doc = repositorio.obtener(id_doc)
        if doc is None or doc.albaran is None or linea >= len(doc.albaran.lineas):
            return HTMLResponse("No existe", status_code=404)
        li = doc.albaran.lineas[linea]
        li.codigo_idm = codigo_idm.strip().upper()
        li.metodo_resolucion = "confirmada_bandeja"
        if tabla is not None and li.codigo_proveedor:
            tabla.aprender(
                doc.proveedor, li.codigo_proveedor, li.codigo_idm, cfg.ruta_datos / "equivalencias_aprendidas.csv"
            )
        repositorio.guardar(doc)
        evento(
            "articulo.resuelto",
            doc.id,
            {
                "linea": linea,
                "codigo_proveedor": li.codigo_proveedor,
                "codigo_idm": li.codigo_idm,
                "metodo": "confirmada_bandeja",
            },
        )
        return RedirectResponse(f"/documentos/{id_doc}?ok=equivalencia", status_code=303)

    @app.get("/pedidos", response_class=HTMLResponse)
    def pedidos_propuestos(request: Request):
        docs = [
            d
            for d in repositorio.listar()
            if d.pedido_propuesto is not None and d.relacion == RelacionPedido.PEDIDO_PROPUESTO
        ]
        return plantillas.TemplateResponse(request, "pedidos.html", {"documentos": docs})

    @app.post("/pedidos/{id_doc}/confirmar")
    def confirmar_pedido(id_doc: str, quien: str = Form("")):
        """Fernandillo confirma el pedido propuesto: se exporta la hoja para Siddex y el albarán pasa a CON_PEDIDO."""
        doc = repositorio.obtener(id_doc)
        if doc is None or doc.pedido_propuesto is None:
            return HTMLResponse("No existe", status_code=404)
        pedido = doc.pedido_propuesto
        pedido.relacion = RelacionPedido.CON_PEDIDO
        ruta = exportar_siddex.exportar(
            [pedido], proveedores, cfg.ruta_salida / f"pedido_propuesto_{nombre_seguro(pedido.numero)}.xlsx"
        )
        doc.relacion, doc.pedido = RelacionPedido.CON_PEDIDO, pedido.numero
        repositorio.guardar(doc)
        evento(
            "decision.tomada",
            doc.id,
            {"decision": "PEDIDO_CONFIRMADO", "pedido": pedido.numero, "quien": quien, "hoja_siddex": str(ruta)},
        )
        return RedirectResponse(f"/documentos/{id_doc}?ok=pedido_confirmado", status_code=303)

    app.include_router(router_encargos(encargos, plantillas))
    return app
