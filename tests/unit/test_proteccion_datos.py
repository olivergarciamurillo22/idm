"""Comprueba que .gitignore y el hook pre-commit protegen los datos reales de IDM: datos/, documentos fuera de fixtures,
fixtures/reales sin anonimizar y .env quedan fuera; los fixtures ficticios, golden y no procesables sí se versionan."""

import shutil
import subprocess

import pytest

GIT = shutil.which("git")


def _ignorado(raiz, ruta: str) -> bool:
    r = subprocess.run([GIT, "check-ignore", "-q", ruta], cwd=raiz, capture_output=True)
    return r.returncode == 0


@pytest.mark.skipif(GIT is None, reason="git no disponible")
@pytest.mark.parametrize(
    "ruta",
    [
        "datos/entrada/albaran_real.pdf",
        "datos/material_real/fotos_2026-09-24/IMG_2384.HEIC",
        "datos/material_real/fotos_2026-09-24/derivados/abc_1600.jpg",
        "datos/analisis_real/FORMATOS_PROVEEDORES.md",
        "datos/proveedores_conocidos.csv",
        "docs/foto_albaran.HEIC",
        "src/idm/foto.heic",
        "datos/siddex/articulos.xlsx",
        "datos/idm.db",
        "docs/albaran_real.pdf",
        "src/idm/factura.xlsx",
        "fixtures/reales/la-cepa_albaran_01.pdf",
        "fixtures/reales/exports/pedidos.xlsx",
        ".env",
        ".env.produccion",
        "salida/correo/x.eml",
    ],
)
def test_datos_reales_ignorados(raiz, ruta):
    assert _ignorado(raiz, ruta), f"{ruta} debería estar ignorado"


@pytest.mark.skipif(GIT is None, reason="git no disponible")
@pytest.mark.parametrize(
    "ruta",
    [
        "fixtures/ficticios/documentos/albaran_vega_bruto_descuento.pdf",
        "fixtures/ficticios/siddex/articulos.xlsx",
        "fixtures/ficticios/planning_ficticio.xlsx",
        "fixtures/golden/02_recambios_sin_precio_sin_pedido/documento.pdf",
        "fixtures/no_procesables/corrupto.pdf",
        "fixtures/ficticios/imagenes/albaran_sintetico.heic",
        "fixtures/ficticios/imagenes/albaran_sintetico_exif6.heic",
        "fixtures/reales/la-cepa_albaran_01.anonimizado.pdf",
        "fixtures/reales/README.md",
        ".env.ejemplo",
        "datos/README.md",
    ],
)
def test_fixtures_versionables(raiz, ruta):
    assert not _ignorado(raiz, ruta), f"{ruta} no debería estar ignorado"


@pytest.mark.skipif(GIT is None, reason="git no disponible")
def test_hook_pre_commit_bloquea_documento_real(raiz, tmp_path):
    """Simula el hook sobre un índice temporal: un PDF fuera de fixtures debe bloquear el commit."""
    hook = raiz / ".githooks" / "pre-commit"
    assert hook.exists()
    repo = tmp_path / "repo"
    subprocess.run([GIT, "init", "-q", str(repo)], check=True)
    (repo / "docs").mkdir()
    (repo / "docs" / "albaran_real.pdf").write_bytes(b"%PDF-1.4 ficticio")
    (repo / "docs" / "IMG_0001.HEIC").write_bytes(b"\x00\x00\x00\x18ftypheic")
    (repo / "notas.md").write_text("ok", encoding="utf-8")
    subprocess.run([GIT, "add", "-f", "docs/albaran_real.pdf", "docs/IMG_0001.HEIC", "notas.md"], cwd=repo, check=True)
    r = subprocess.run(["sh", str(hook)], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and r.stdout.count("BLOQUEADO") == 2
    subprocess.run([GIT, "rm", "-q", "--cached", "docs/albaran_real.pdf", "docs/IMG_0001.HEIC"], cwd=repo, check=True)
    r = subprocess.run(["sh", str(hook)], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
