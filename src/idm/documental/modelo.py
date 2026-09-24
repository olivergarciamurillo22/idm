"""Modelo común de salida de cualquier proveedor documental: páginas, palabras con caja y confianza, tablas, pares
clave-valor, campos estructurados y metadatos de la llamada. Confianzas normalizadas a 0..1; coordenadas con su unidad.
No interpreta nada de negocio (eso es normalizacion.py) y no depende de ningún proveedor concreto."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class Caja(BaseModel):
    pagina: int = 1
    x0: float
    y0: float
    x1: float
    y1: float
    unidad: str = "px"  # px o inch (Azure devuelve pulgadas para PDF)

    @classmethod
    def desde_poligono(cls, poligono: list[float] | None, pagina: int = 1, unidad: str = "px") -> "Caja | None":
        """Polígono plano [x1,y1,x2,y2,...] (Azure v4) → rectángulo que lo contiene."""
        if not poligono or len(poligono) < 4:
            return None
        xs, ys = poligono[0::2], poligono[1::2]
        return cls(pagina=pagina, x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys), unidad=unidad)


class Palabra(BaseModel):
    texto: str
    confianza: float | None = None
    caja: Caja | None = None


class LineaTexto(BaseModel):
    texto: str
    caja: Caja | None = None


class Pagina(BaseModel):
    numero: int
    ancho: float | None = None
    alto: float | None = None
    unidad: str | None = None
    angulo: float | None = None
    palabras: list[Palabra] = Field(default_factory=list)
    lineas: list[LineaTexto] = Field(default_factory=list)


class Celda(BaseModel):
    fila: int
    columna: int
    texto: str = ""
    cabecera: bool = False
    extension_filas: int = 1
    extension_columnas: int = 1
    caja: Caja | None = None


class Tabla(BaseModel):
    filas: int
    columnas: int
    celdas: list[Celda] = Field(default_factory=list)
    pagina: int | None = None

    def como_filas(self) -> list[list[str | None]]:
        """Rejilla fila×columna (formato de pdfplumber) para reutilizar el mapeo de cabeceras de albaranes/lector.py."""
        rejilla: list[list[str | None]] = [[None] * self.columnas for _ in range(self.filas)]
        for c in self.celdas:
            if 0 <= c.fila < self.filas and 0 <= c.columna < self.columnas:
                rejilla[c.fila][c.columna] = c.texto
        return rejilla


class ParClaveValor(BaseModel):
    clave: str
    valor: str | None = None
    confianza: float | None = None
    caja: Caja | None = None


class CampoExtraido(BaseModel):
    """Campo estructurado propuesto por el proveedor (modelo prebuilt de Azure, anotación de Mistral…). Solo es una
    propuesta: la normalización IDM lo usa para completar huecos y la decisión sigue siendo determinista."""

    nombre: str
    valor: str | None = None
    confianza: float | None = None
    caja: Caja | None = None


class LineaExtraida(BaseModel):
    campos: dict[str, CampoExtraido] = Field(default_factory=dict)


class MetadatosMotor(BaseModel):
    proveedor: str
    modelo: str
    externo: bool
    version_api: str | None = None
    request_id: str | None = None
    fecha: datetime = Field(default_factory=datetime.now)
    tiempo_s: float = 0.0
    paginas_procesadas: int = 0
    coste_estimado_usd: Decimal | None = None
    coste_estimado_eur: Decimal | None = None
    sha256_enviado: str | None = None  # hash de lo que salió de la máquina (p. ej. el JPEG derivado del HEIC)
    tipo_enviado: str | None = None


class ResultadoDocumental(BaseModel):
    texto: str = ""
    texto_alternativo: str = ""  # segunda lectura del mismo documento (filas geométricas, cabecera/pie separados…)
    paginas: list[Pagina] = Field(default_factory=list)
    tablas: list[Tabla] = Field(default_factory=list)
    pares: list[ParClaveValor] = Field(default_factory=list)
    campos: dict[str, CampoExtraido] = Field(default_factory=dict)
    lineas: list[LineaExtraida] = Field(default_factory=list)
    metadatos: MetadatosMotor
    avisos: list[str] = Field(default_factory=list)

    @property
    def palabras(self) -> list[Palabra]:
        return [p for pagina in self.paginas for p in pagina.palabras]

    @property
    def confianza_media(self) -> float | None:
        confianzas = [p.confianza for p in self.palabras if p.confianza is not None]
        if not confianzas:
            return None
        return round(sum(confianzas) / len(confianzas), 4)

    def resumen_campos(self) -> dict[str, int]:
        """Cuánto devolvió el proveedor (para la traza de la llamada, sin contenido)."""
        return {
            "paginas": len(self.paginas),
            "palabras": len(self.palabras),
            "tablas": len(self.tablas),
            "pares": len(self.pares),
            "campos": len(self.campos),
            "lineas": len(self.lineas),
            "caracteres": len(self.texto),
        }
