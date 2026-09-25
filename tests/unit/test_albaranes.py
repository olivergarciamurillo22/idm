"""Tests de albaranes/: extracción, normalización por proveedor, lector sobre PDF ficticios, carpeta y adjuntos IMAP.
Todo sobre fixtures/ficticios/documentos; sin servidor de correo real."""

from datetime import date
from decimal import Decimal
from email.message import EmailMessage

from idm.albaranes import benchmark
from idm.albaranes.buzon import CarpetaEntrada, RegistroProcesados, adjuntos_admitidos
from idm.albaranes.extraer import extraer, sha256_fichero
from idm.albaranes.lector import LectorAutomatico, leer
from idm.albaranes.normalizar import normalizar_numero
from idm.dominio.estados import CodigoError, ResultadoLectura, TipoDocumento

DOCS = "documentos"


def test_extraer_pdf_con_texto_y_tablas(fixtures):
    ex = extraer(fixtures / DOCS / "albaran_vega_bruto_descuento.pdf")
    assert ex.tiene_texto and ex.paginas == 1
    assert ex.tablas[0][0][:3] == ["Referencia", "Descripción", "Cantidad"]
    assert not extraer(fixtures / DOCS / "albaran_recambios_sin_precio_foto.png").tiene_texto


def test_normalizar_numero_por_proveedor():
    assert normalizar_numero("RECACOR", "4410/3.172") == "4410/3172"
    assert normalizar_numero("LA_CEPA", "AC B26 0100008882") == "B26 0100008882"
    assert normalizar_numero("FICT_ELECTRO", "ALB. 2026/1.234") == "2026/1234"
    assert normalizar_numero("OTRO", "  ab  12 ") == "AB 12"  # solo reglas comunes
    assert normalizar_numero(None, "x.1") == "X.1"


def test_lector_albaran_bruto_descuento(fixtures):
    doc = leer(fixtures / DOCS / "albaran_vega_bruto_descuento.pdf")
    assert doc.metodo == "pdf_texto" and doc.tipo == TipoDocumento.ALBARAN
    assert doc.cif == "B00000001" and doc.numero == "AC B26 0100008881"
    assert doc.fecha == date(2026, 9, 14) and doc.nuestro_pedido == "20269060"
    assert len(doc.lineas) == 3
    assert doc.lineas[1].codigo_proveedor == "ABR-6205"
    assert doc.lineas[1].precio_bruto == Decimal("9.14") and doc.lineas[1].descuento_pct == Decimal("45")
    assert doc.lineas[1].importe == Decimal("25.14")
    assert doc.base == Decimal("73.64") and doc.total == Decimal("89.10")
    assert doc.confianza == 1.0 and doc.avisos == []
    assert doc.sha256 == sha256_fichero(fixtures / DOCS / "albaran_vega_bruto_descuento.pdf")


def test_lector_albaran_sin_precio(fixtures):
    doc = leer(fixtures / DOCS / "albaran_recambios_sin_precio.pdf")
    assert doc.numero == "4410/3.172" and doc.nuestro_pedido is None
    assert [li.precio_bruto for li in doc.lineas] == [None, None]
    assert doc.base is None


def test_lector_albaran_prefijo_puntos_y_portes(fixtures):
    doc = leer(fixtures / DOCS / "albaran_electro_puntos_prefijo.pdf")
    assert doc.numero == "ALB. 2026/1.234"
    assert doc.lineas[-1].es_portes and doc.lineas[-1].importe == Decimal("9.00")


def test_lector_factura(fixtures):
    doc = leer(fixtures / DOCS / "factura_vega_agrupa.pdf")
    assert doc.tipo == TipoDocumento.FACTURA and doc.numero == "F26/000731"
    assert doc.albaranes_referenciados == ["AC B26 0100008881", "AC B26 0100005301"]
    assert doc.lineas[3].albaran == "AC B26 0100005301" and doc.lineas[4].es_portes


def test_lector_imagen_nulo(fixtures):
    doc = leer(fixtures / DOCS / "albaran_recambios_sin_precio_foto.png")
    assert doc.metodo == "imagen_nulo" and doc.confianza == 0.0 and doc.lineas == []
    assert doc.resultado == ResultadoLectura.REQUIERE_OCR and not doc.leido
    assert doc.errores[0].codigo == CodigoError.LECTURA_REQUIERE_OCR and not doc.errores[0].recuperable
    assert "requiere lectura de imagen" in doc.avisos[0]


def test_lector_no_procesables(fixtures_raiz):
    carpeta = fixtures_raiz / "no_procesables"
    esperado = {
        "corrupto.pdf": (ResultadoLectura.CORRUPTO, CodigoError.LECTURA_CORRUPTO),
        "vacio.pdf": (ResultadoLectura.VACIO, CodigoError.LECTURA_VACIO),
        "hoja.xlsx": (ResultadoLectura.EXCEL, CodigoError.LECTURA_EXCEL),
        "texto.txt": (ResultadoLectura.NO_SOPORTADO, CodigoError.LECTURA_NO_SOPORTADA),
        "escaneado_sin_texto.pdf": (ResultadoLectura.REQUIERE_OCR, CodigoError.LECTURA_REQUIERE_OCR),
    }
    for nombre, (resultado, codigo) in esperado.items():
        doc = leer(carpeta / nombre)
        assert doc.resultado == resultado, nombre
        assert doc.errores and doc.errores[0].codigo == codigo, nombre
        assert doc.avisos and doc.lineas == [] and not doc.leido, nombre


def test_lector_pdf_renombrado_es_corrupto(tmp_path):
    f = tmp_path / "foto_renombrada.pdf"
    f.write_bytes(b"\x89PNG\r\n" + b"x" * 100)
    doc = leer(f)
    assert doc.resultado == ResultadoLectura.CORRUPTO and "%PDF" in doc.avisos[0]


def test_lector_fichero_inexistente(tmp_path):
    doc = LectorAutomatico().leer(tmp_path / "no_existe.pdf")
    assert doc.resultado == ResultadoLectura.CORRUPTO and doc.errores[0].codigo == CodigoError.FICHERO_INACCESIBLE


def test_lector_extension_no_soportada(tmp_path):
    f = tmp_path / "cosa.txt"
    f.write_text("hola", encoding="utf-8")
    assert LectorAutomatico().leer(f).resultado == ResultadoLectura.NO_SOPORTADO


def test_carpeta_entrada_y_registro(fixtures, tmp_path):
    pendientes = CarpetaEntrada(fixtures / DOCS).pendientes()
    assert {p.ruta.suffix for p in pendientes} == {".pdf", ".png"}
    assert all(len(p.sha256) == 64 for p in pendientes)
    assert CarpetaEntrada(tmp_path / "no_existe").pendientes() == []
    registro = RegistroProcesados(tmp_path / "procesados.jsonl")
    assert not registro.contiene("<a@b>")
    registro.anotar("<a@b>", {"adjuntos": []})
    assert RegistroProcesados(tmp_path / "procesados.jsonl").contiene("<a@b>")


def test_adjuntos_admitidos(fixtures):
    em = EmailMessage()
    em["From"] = "proveedor@ficticio.local"
    em.set_content("Adjunto albarán")
    em.add_attachment(b"%PDF-1.4 ficticio", maintype="application", subtype="pdf", filename="Albarán 2026/1.234.pdf")
    em.add_attachment(b"hola", maintype="text", subtype="plain", filename="notas.txt")
    em.add_attachment(b"\x89PNG", maintype="image", subtype="png", filename="foto.png")
    adjuntos = adjuntos_admitidos(em)
    assert [n for n, _ in adjuntos] == ["Albar_n_2026_1.234.pdf", "foto.png"]
    assert adjuntos[0][1].startswith(b"%PDF")


def test_benchmark_sobre_fixtures(fixtures):
    r = benchmark.ejecutar(fixtures / DOCS, incluir_imagenes=False)
    assert r.aciertos == r.totales  # con texto, todo acierta
    r = benchmark.ejecutar(fixtures / DOCS, incluir_imagenes=True)
    assert r.totales["numero"] == 5 and r.aciertos["numero"] == 4
    assert "numero" in r.tabla()
