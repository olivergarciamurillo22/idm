"""Guardianes de fallos que no se ven en el Mac pero sí en el Windows de IDM: leer o escribir texto sin encoding
explícito (Windows usa cp1252 y rompe con acentos) y subprocess en modo texto sin encoding (Tesseract devuelve UTF-8).
Analiza el árbol sintáctico de todos los .py del proyecto; no ejecuta nada."""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CARPETAS = ("src", "tests", "fixtures", "migrations")
METODOS_TEXTO = {"read_text", "write_text"}


def _ficheros():
    for carpeta in CARPETAS:
        yield from (RAIZ / carpeta).rglob("*.py")


def _modo(llamada: ast.Call, posicion: int) -> str | None:
    for kw in llamada.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    if len(llamada.args) > posicion and isinstance(llamada.args[posicion], ast.Constant):
        return llamada.args[posicion].value
    return None


def _sin_encoding(llamada: ast.Call) -> bool:
    return not any(kw.arg == "encoding" for kw in llamada.keywords)


def test_texto_siempre_con_encoding():
    fallos = []
    for fichero in _ficheros():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), str(fichero))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            f = nodo.func
            nombre = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if nombre in METODOS_TEXTO and _sin_encoding(nodo):
                fallos.append(f"{fichero.relative_to(RAIZ)}:{nodo.lineno} {nombre}() sin encoding")
            elif nombre == "open" and not (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id in ("os", "pdfplumber", "Image", "urllib", "tarfile")
            ):
                posicion = 0 if isinstance(f, ast.Attribute) else 1  # Path.open(mode) / open(ruta, mode)
                modo = _modo(nodo, posicion) or "r"
                if "b" not in modo and _sin_encoding(nodo):
                    fallos.append(f"{fichero.relative_to(RAIZ)}:{nodo.lineno} open() en modo texto sin encoding")
    assert not fallos, "\n".join(fallos)


def test_subprocess_texto_con_encoding():
    fallos = []
    for fichero in _ficheros():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), str(fichero))
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr in ("run", "check_output")
            ):
                if isinstance(nodo.func.value, ast.Name) and nodo.func.value.id == "subprocess":
                    texto = any(kw.arg == "text" and getattr(kw.value, "value", False) for kw in nodo.keywords)
                    if texto and _sin_encoding(nodo):
                        fallos.append(f"{fichero.relative_to(RAIZ)}:{nodo.lineno} subprocess en texto sin encoding")
    assert not fallos, "\n".join(fallos)


def test_los_tests_no_leen_el_env_del_desarrollador():
    """Aunque el .env local tenga claves reales, dentro de los tests la configuración es la de por defecto."""
    from idm import config

    cfg = config.cargar()
    assert cfg.mistral_key == "" and cfg.azure_key == ""
    assert cfg.allow_external_document_processing is False and cfg.document_provider == "ninguno"


def test_errores_de_configuracion_son_claros(monkeypatch):
    import pytest

    from idm import config

    monkeypatch.setenv("BANDEJA_PUERTO", "")  # vacío = valor por defecto
    assert config.cargar().bandeja_puerto == 8000
    monkeypatch.setenv("DOCUMENT_PROVIDER_TIMEOUT_S", "noventa")
    with pytest.raises(config.ConfiguracionInvalida, match="DOCUMENT_PROVIDER_TIMEOUT_S"):
        config.cargar()
    monkeypatch.delenv("DOCUMENT_PROVIDER_TIMEOUT_S")
    monkeypatch.setenv("ALLOW_EXTERNAL_DOCUMENT_PROCESSING", "ture")  # errata
    with pytest.raises(config.ConfiguracionInvalida, match="true o false"):
        config.cargar()


def test_tesseract_en_windows_se_busca_en_la_ruta_del_instalador(monkeypatch, tmp_path):
    from idm.albaranes import ocr

    exe = tmp_path / "tesseract.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(ocr.shutil, "which", lambda _: None)
    monkeypatch.setattr(ocr, "RUTAS_WINDOWS", (str(exe),))
    assert ocr.resolver_ejecutable("tesseract", sistema="nt") == str(exe)
    assert ocr.resolver_ejecutable("tesseract", sistema="posix") == "tesseract"
    assert ocr.resolver_ejecutable("C:/otro/tesseract.exe", sistema="nt") == "C:/otro/tesseract.exe"
