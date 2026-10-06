"""Cálculo de cobertura de tinta C, M, Y, K por página.

Flujo:  archivo  ->  páginas como imágenes RGB (arreglos numpy)  ->  % de cada canal.

Una imagen RGB en numpy es un arreglo de forma (alto, ancho, 3) con valores 0-255.
Todas las operaciones se hacen sobre el arreglo completo a la vez ("vectorizado"),
sin bucles por píxel: numpy las ejecuta en C y es cientos de veces más rápido.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageSequence

EXTENSIONES_PDF = {".pdf"}
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}

# Las imágenes muy grandes se reducen: el promedio de cobertura no cambia
# y el cálculo es mucho más rápido.
LADO_MAXIMO_PX = 1200


@dataclass
class CoberturaPagina:
    c: float  # % de cobertura de cada canal sobre el área de la hoja (0-100)
    m: float
    y: float
    k: float
    area_color_pct: float  # % de la hoja con píxeles de color
    es_color: bool

    @property
    def total(self) -> float:
        """Suma C+M+Y+K (puede pasar de 100 %, hasta 400 %)."""
        return self.c + self.m + self.y + self.k


def rgb_a_cmyk(rgb: np.ndarray, umbral_croma: float, gcr: float):
    """Convierte un arreglo RGB (alto, ancho, 3) uint8 a cuatro arreglos de tinta 0-1.

    Reglas (buscan estimar POR ENCIMA del consumo real):
      * Píxel neutro (gris/negro/blanco): solo tóner K. Es lo que hace la Ricoh
        con texto negro y grises.
      * Píxel de color: tinta "cruda" C=1-R, M=1-G, Y=1-B, y se reemplaza una
        fracción `gcr` de la parte común (min C,M,Y) por K. Un gcr bajo deja más
        tinta de color, que es la más cara -> estimación conservadora.
    También devuelve la máscara booleana de píxeles de color.
    """
    x = rgb.astype(np.float32) / 255.0
    r, g, b = x[..., 0], x[..., 1], x[..., 2]

    croma = x.max(axis=2) - x.min(axis=2)
    es_color = croma >= umbral_croma

    c0, m0, y0 = 1.0 - r, 1.0 - g, 1.0 - b
    k_color = gcr * np.minimum(np.minimum(c0, m0), y0)
    k_neutro = 1.0 - x.mean(axis=2)

    # np.where(condición, a, b): elige a donde la condición es verdadera, b donde no.
    c = np.where(es_color, c0 - k_color, 0.0)
    m = np.where(es_color, m0 - k_color, 0.0)
    y = np.where(es_color, y0 - k_color, 0.0)
    k = np.where(es_color, k_color, k_neutro)
    return c, m, y, k, es_color


def analizar_imagen(rgb: np.ndarray, analisis: dict) -> CoberturaPagina:
    """Cobertura de una página ya convertida a RGB."""
    c, m, y, k, es_color = rgb_a_cmyk(rgb, analisis["umbral_croma"], analisis["gcr"])
    area_color = float(es_color.mean() * 100)
    return CoberturaPagina(
        c=float(c.mean() * 100),
        m=float(m.mean() * 100),
        y=float(y.mean() * 100),
        k=float(k.mean() * 100),
        area_color_pct=area_color,
        es_color=area_color >= analisis["area_min_color_pct"],
    )


def _imagen_pil_a_rgb(img: Image.Image) -> np.ndarray:
    """PIL -> arreglo RGB, poniendo las zonas transparentes sobre fondo blanco (el papel)."""
    img = img.convert("RGBA")
    fondo = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(fondo, img).convert("RGB")
    img.thumbnail((LADO_MAXIMO_PX, LADO_MAXIMO_PX))
    return np.asarray(img)


def paginas_rgb(ruta: Path, dpi: int):
    """Generador: entrega cada página del archivo como arreglo RGB.

    Para imágenes se asume que ocupan la hoja completa (estimación por encima:
    en la práctica suelen imprimirse con márgenes blancos).
    """
    ext = ruta.suffix.lower()
    if ext in EXTENSIONES_PDF:
        with pymupdf.open(ruta) as doc:
            for pagina in doc:
                pix = pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
                yield np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    elif ext in EXTENSIONES_IMAGEN:
        with Image.open(ruta) as img:
            # ImageSequence recorre los cuadros de un TIFF de varias páginas o un GIF.
            for cuadro in ImageSequence.Iterator(img):
                yield _imagen_pil_a_rgb(cuadro)
    else:
        raise ValueError(f"Formato no soportado: {ext}")


def contar_paginas(ruta: Path) -> int:
    ext = Path(ruta).suffix.lower()
    if ext in EXTENSIONES_PDF:
        with pymupdf.open(ruta) as doc:
            return doc.page_count
    if ext in EXTENSIONES_IMAGEN:
        with Image.open(ruta) as img:
            return getattr(img, "n_frames", 1)
    raise ValueError(f"Formato no soportado: {ext}")


def analizar_archivo(ruta: Path, analisis: dict, progreso=None) -> list[CoberturaPagina]:
    """Analiza todas las páginas. `progreso(i, total)` se llama después de cada página (opcional)."""
    ruta = Path(ruta)
    total = contar_paginas(ruta) if progreso else 0
    resultado = []
    for i, rgb in enumerate(paginas_rgb(ruta, analisis["dpi"]), start=1):
        resultado.append(analizar_imagen(rgb, analisis))
        if progreso:
            progreso(i, total)
    return resultado


def imagen_pagina(ruta: Path, indice: int, dpi: int = 50) -> Image.Image:
    """Imagen PIL de una página (índice desde 0), para mostrar una vista previa."""
    ruta = Path(ruta)
    if ruta.suffix.lower() in EXTENSIONES_PDF:
        with pymupdf.open(ruta) as doc:
            pix = doc[indice].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    with Image.open(ruta) as img:
        img.seek(indice)
        return Image.fromarray(_imagen_pil_a_rgb(img))
