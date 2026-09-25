"""Ningún identificador real de IDM conocido (nº de albarán, pedido, registro, códigos de artículo, referencias de
proveedor, CIF) puede volver a los ficheros versionados. Guarda solo su huella SHA-256, nunca el valor, y la compara
con cada palabra candidata de los ficheros de texto versionados. Para añadir uno, calcula su huella en local."""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
EXTENSIONES = {".py", ".md", ".json", ".csv", ".html", ".txt", ".toml", ".ini", ".bat", ".sh", ".mako", ".yml", ".yaml"}
CANDIDATO = re.compile(r"[A-Za-z0-9][A-Za-z0-9./]{5,}[A-Za-z0-9]")
HUELLAS_REALES = {
    "001f1f247d8a3fd46cd6d117fbcc4ec09776f4ed694a4a5bf367547ae99fbe86",
    "1176dbde3196e94e96aede5bb5f76b8663cca0edb00b0b49851b840be0ffa518",
    "26c605eef727ea46bcbe85e2a35722fd0fccdd30e7ca54c5529bc8dab67c99d9",
    "298800a7f2d85d3cb67bc4ae8c806628d47dd2445c0aedaf33504859db570c69",
    "391c7eefe2f133ec4fbcfc1038e86a0bbb428e64b0c78937cb375fb8344c6704",
    "473d8540a7e2d5880cadb93060482f6f2ae9a4f23a6ecfcb069a415f6b5e48a0",
    "501beca610365df937ebdbec0061ebb68c5dd6e1f49583adb567f554b274f33b",
    "575d0996697036f1aabb4622d27104abfee9a52f9ccce15ba1d8b3d68362a9c4",
    "6de73aa74539c075c2cba77b24faa3c2dd31357f3dd1db26529644e9ede02fe1",
    "71480f5299b0e0cea30960229ea27ca993d1fb2eb8935c01234c043c7c566379",
    "88f27b9ae45e574ff83ff81ce79c3e801cb0b10d611e26527cf77e9e736e80d3",
    "995065314cbd1f37d249fef5cbda1765d7fb84db2caa9f7bcb76220f6769bdb4",
    "9b701c2050aebb4a2b24279e1f7a5b9d04a6cd577bd9e29f449d115e2546bf59",
    "a758074e334cb9a24935d3bd63c9219ee4b286e0584c74dde5353ebdcfd8bb98",
    "c24e67e80d8cb7772101fd49bf7d73fdd4c598f9f8b90438521ae02dfd982bb6",
    "c42c3483712906cd37094ee60d14f14c168e08c54193df7e6072310f9989d019",
    "cd5704533d0181ce85e13cbd8f17a9b7c4d794ca19a63ebec173a9ed23ed63af",
    "d08ee2cebfb53a6c191c9877382c9ffeb0fdeb28670d4e7faea14c93f2d8cb96",
    "dda89cbca1f0896c26a057bf1f2a0a846b59ea0e5bdf6bdc4874fd103d09191b",
    "e0749c9589a4b64a9884c08e941fb578a6745f1e46f71ea2b6884c97e8a7570d",
    "e1fc3872d770cab427607698d30ff0121c9bc09b5485acd223c4d9c1a0205857",
    "f535bfd4e584fc65eadfb74ffc685fbb96ffa5671be1a9bdffe74b7f7a897045",
    "ff1954b93769375fdac31a3de7cf57b16dfdbdd01cd225068d0cd1baa88d3fee",
    "fff60dea69d60900346bc85cc00f4322e542b9436fe6aa6f6a91abb84c51c953",
}


def _huella(token: str) -> str:
    return hashlib.sha256(token.upper().encode()).hexdigest()


def _versionados() -> list[Path]:
    salida = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return [RAIZ / f for f in salida.splitlines() if Path(f).suffix in EXTENSIONES and not f.startswith("datos/")]


@pytest.mark.skipif(shutil.which("git") is None, reason="git no disponible")
def test_ningun_identificador_real_en_ficheros_versionados():
    encontrados = []
    for fichero in _versionados():
        if not fichero.is_file():
            continue
        for n, linea in enumerate(fichero.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for token in CANDIDATO.findall(linea):
                if _huella(token) in HUELLAS_REALES:
                    encontrados.append(f"{fichero.relative_to(RAIZ)}:{n}")
    assert not encontrados, "Identificador real de IDM en: " + ", ".join(encontrados)


def test_el_guardian_funciona():
    assert len(HUELLAS_REALES) >= 20
    assert _huella("valor-inventado") not in HUELLAS_REALES
