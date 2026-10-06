"""Dibujos en pixel art generados con código (sin archivos de imagen).

Técnica: se dibuja en tamaño diminuto (1 píxel = 1 "cuadrito") y se agranda con
Image.NEAREST, que copia cada píxel en bloque sin suavizar: así quedan los bordes
duros típicos de los videojuegos de 8 bits.

Un sprite es un "mapa" de texto: cada carácter es un píxel y la PALETA dice su color
('.' = transparente). Para cambiar un dibujo, edite el mapa.
"""

from PIL import Image, ImageDraw, ImageFont

from . import tema

PALETA = {
    "K": (43, 16, 32),      # contorno oscuro
    "W": (255, 255, 255),   # papel
    "g": (214, 214, 222),   # gris claro
    "G": (150, 150, 165),   # gris
    "D": (95, 95, 110),     # gris oscuro
    "R": (227, 38, 46),     # rojo (luz de encendido)
    "Y": (255, 225, 77),    # amarillo
    "C": (0, 174, 239),     # cian
    "M": (236, 0, 140),     # magenta
}

# Impresora de 16×16 con una hoja saliendo; las rayitas de la hoja son los 4 tóners.
IMPRESORA = [
    "....KKKKKKKK....",
    "....KWWWWWWK....",
    "....KWWWWWWK....",
    "..KKKKKKKKKKKK..",
    ".KggggggggggggK.",
    "KgggggggggggRYgK",
    "KgGGGGGGGGGGGGgK",
    "KgggggggggggggGK",
    "KGGKKKKKKKKKKGGK",
    "KDDKWWWWWWWWKDDK",
    "KKKKWCCMMYYKKKKK",
    "....WWWWWWWW....",
    "....WKKKKKKW....",
    "....WWWWWWWW....",
    "....WKKKKWWW....",
    "....KKKKKKKK....",
]


def sprite(mapa: list[str], escala: int) -> Image.Image:
    alto, ancho = len(mapa), len(mapa[0])
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    for y, fila in enumerate(mapa):
        for x, c in enumerate(fila):
            if c != ".":
                img.putpixel((x, y), PALETA[c] + (255,))
    return img.resize((ancho * escala, alto * escala), Image.NEAREST)


def _hex(color: str) -> tuple:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _fuente(px: int = 8) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(tema.ARCHIVO_FUENTE_PIXEL), px)


def _texto(d: ImageDraw.ImageDraw, xy, texto, color, sombra=None, fuente=None):
    """Texto pixelado sin suavizado, con sombra de 1 píxel opcional (como las letras del pendón)."""
    d.fontmode = "1"  # sin antialias: píxeles duros
    fuente = fuente or _fuente()
    if sombra:
        d.text((xy[0] + 1, xy[1] + 1), texto, font=fuente, fill=sombra)
    d.text(xy, texto, font=fuente, fill=color)


def encabezado(escala: int, subtitulo: str = "COTIZADOR · RICOH MP C3003") -> Image.Image:
    """Barra de título: impresora + óvalo amarillo con 'Net Papelería' + letrero de la impresora.

    Se dibuja a tamaño real de 8 bits y luego se agranda `escala` veces.
    """
    C = tema.COLORES
    fuente = _fuente(8)
    nombre = "Net Papelería"
    ancho_nombre = int(fuente.getlength(nombre))
    ancho_sub = int(fuente.getlength(subtitulo))

    ovalo_w, ovalo_h = ancho_nombre + 20, 18
    ancho = 2 + 32 + 6 + max(ovalo_w, ancho_sub) + 4
    alto = 32
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    img.alpha_composite(sprite(IMPRESORA, 2), (2, 0))  # impresora al doble: alto completo de la barra

    x0 = 2 + 32 + 6
    # Óvalo amarillo con borde rojo oscuro y una franja de brillo (como el logo del pendón)
    d.ellipse((x0, 1, x0 + ovalo_w, 1 + ovalo_h), fill=_hex(C.get("amarillo", "#FFE14D")),
              outline=_hex(C.get("marco_oscuro", "#8E1B4F")))
    d.line((x0 + 16, 3, x0 + ovalo_w - 16, 3), fill=(255, 248, 200))  # brillo, dentro del óvalo
    _texto(d, (x0 + 10, 6), nombre, _hex(C.get("rojo", "#E3262E")), sombra=(150, 20, 30), fuente=fuente)
    # Letrero de la impresora, blanco con sombra oscura
    _texto(d, (x0, 22), subtitulo,
           (255, 255, 255), sombra=_hex(C.get("marco_oscuro", "#8E1B4F")), fuente=fuente)
    return img.resize((ancho * escala, alto * escala), Image.NEAREST)


def icono(tamano: int = 32) -> Image.Image:
    """Ícono de la ventana (y del .exe): la impresora en pixel art."""
    return sprite(IMPRESORA, max(1, tamano // 16))
