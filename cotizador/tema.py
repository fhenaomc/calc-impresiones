"""Apariencia de la interfaz: colores, letras y botones en UN solo lugar.

Hay dos estilos; se elige en config.json:
    "apariencia": {"tema": "pixel", "tamano_letra": 12}      # "pixel" o "clasico"
(también desde el programa: Costos → Avanzado → Estilo).

Estilo "pixel" (Net Papelería):
  * Colores del pendón de la papelería: fucsia, amarillo, rojo y blanco.
  * Marco, logo, títulos y el total con letra pixelada (Press Start 2P, licencia OFL,
    incluida en cotizador/recursos). Botones y textos de detalle con letra normal,
    porque lo más importante es que se lea bien.
  * Press Start 2P está dibujada en una cuadrícula de 8 píxeles: solo se ve nítida en
    múltiplos de 8 px. Por eso sus tamaños se dan en PÍXELES (número negativo en tkinter).

Para cambiar colores o letras, edite TEMAS; la lógica del programa no se toca.
"""

import ctypes
import math
from pathlib import Path

RECURSOS = Path(__file__).resolve().parent / "recursos"
FUENTE_PIXEL = "Press Start 2P"
ARCHIVO_FUENTE_PIXEL = RECURSOS / "PressStart2P-Regular.ttf"
FAMILIA = "Segoe UI"  # letra normal de Windows 10/11

TEMAS = {
    "clasico": {
        "pixel": False,
        "colores": {
            "fondo": "#F4F6F8", "panel": "#FFFFFF", "texto": "#1F2933", "texto_suave": "#616E7C",
            "primario": "#1F4E78", "primario_texto": "#FFFFFF",
            "zona_soltar": "#E3EEF9", "zona_activa": "#C7DDF5", "borde": "#9FB3C8",
            "marco": "#F4F6F8", "boton": "#FFFFFF", "boton_texto": "#1F4E78",
            "total": "#0B6E4F", "alerta_fondo": "#FDECEA", "alerta_texto": "#B42318",
        },
        "boton": {"relief": "solid", "bd": 1},
        "grosor_marco": 0,
    },
    "pixel": {
        "pixel": True,
        "colores": {
            "fondo": "#FBD3E3",          # rosado claro (centro del pendón)
            "panel": "#FFFFFF",
            "texto": "#2B1020",
            "texto_suave": "#7A4A62",
            "primario": "#C2185B",       # fucsia oscuro: títulos
            "primario_texto": "#FFFFFF",
            "zona_soltar": "#FFF3B0",    # amarillo pálido
            "zona_activa": "#FFE14D",    # amarillo del óvalo del pendón
            "borde": "#8E1B4F",
            "marco": "#E2337F",          # fucsia del pendón: marco y barra de título
            "marco_oscuro": "#8E1B4F",
            "amarillo": "#FFE14D",
            "rojo": "#E3262E",
            "boton": "#FFE14D",
            "boton_texto": "#8E1B4F",
            "total": "#0B7A3E",
            "alerta_fondo": "#FDECEA",
            "alerta_texto": "#B42318",
        },
        "boton": {"relief": "raised", "bd": 3},   # botón "de videojuego": se hunde al hacer clic
        "grosor_marco": 6,
    },
}

# Color de fondo de cada rango (mismos que la tabla de precios en Excel), en ambos estilos.
COLORES_RANGO = {
    "B/N normal": "#F2F2F2", "B/N cargado": "#D9D9D9", "B/N total": "#BFBFBF",
    "Color mínimo": "#FFF4D6", "Color medio": "#FFE0B2", "Color alto": "#FFCC99", "Color total": "#F8B195",
}
COLOR_RANGO_POR_DEFECTO = "#FFFFFF"

# Estilo activo. Los módulos leen tema.COLORES, tema.PIXEL, etc.; activar() los cambia.
NOMBRE = "pixel"
PIXEL = True
COLORES = dict(TEMAS["pixel"]["colores"])
ESTILO = TEMAS["pixel"]


def activar(nombre: str) -> None:
    """Activa un estilo. Debe llamarse ANTES de crear las ventanas."""
    global NOMBRE, PIXEL, ESTILO
    if nombre not in TEMAS:
        nombre = "pixel"
    NOMBRE, ESTILO = nombre, TEMAS[nombre]
    PIXEL = ESTILO["pixel"]
    COLORES.clear()
    COLORES.update(ESTILO["colores"])  # se modifica el mismo diccionario: quien lo importó ve el cambio


def cargar_fuente_pixel() -> bool:
    """Carga la letra pixelada SOLO para este programa (no se instala en Windows)."""
    try:
        FR_PRIVATE = 0x10
        return ctypes.windll.gdi32.AddFontResourceExW(str(ARCHIVO_FUENTE_PIXEL), FR_PRIVATE, 0) > 0
    except Exception:
        return False


def color_rango(nombre: str) -> str:
    return COLORES_RANGO.get(nombre.replace(" (+)", ""), COLOR_RANGO_POR_DEFECTO)


def _px8(unidades: float, escala: float) -> int:
    """Tamaño en píxeles múltiplo de 8 (para que la letra pixelada se vea nítida). Negativo = píxeles en tkinter."""
    # floor(x + 0,5) redondea 2,5 -> 3; round() de Python daría 2 ("redondeo bancario")
    return -8 * max(1, math.floor(unidades * escala + 0.5))


def escala_de_pantalla(pixeles_por_pulgada: float) -> float:
    """1,0 / 1,25 / 1,5... Se ajusta a pasos de 0,25 (las escalas reales de Windows) para que
    un 95,9 en vez de 96 no cambie el redondeo de los tamaños."""
    return max(1.0, round(pixeles_por_pulgada / 96 * 4) / 4)


def fuentes(tamano_base: int, escala_pantalla: float = 1.0) -> dict:
    """Fuentes del estilo activo. escala_pantalla = 1,25 si Windows está al 125 %, etc."""
    b = tamano_base
    normal = {
        "normal":  (FAMILIA, b),
        "negrita": (FAMILIA, b, "bold"),
        "pequena": (FAMILIA, max(b - 2, 8)),
        "boton":   (FAMILIA, b, "bold"),
    }
    if not PIXEL:
        return normal | {
            "titulo":  (FAMILIA, b + 6, "bold"),
            "seccion": (FAMILIA, b, "bold"),
            "soltar":  (FAMILIA, b + 4, "bold"),
            "total":   (FAMILIA, b + 14, "bold"),
            "copias":  (FAMILIA, b + 6, "bold"),
        }
    e = escala_pantalla * b / 12  # todo crece si se sube el tamaño de letra
    return normal | {
        "titulo":  (FUENTE_PIXEL, _px8(2, e)),    # títulos de ventanas
        "seccion": (FUENTE_PIXEL, _px8(1.5, e)),  # "Tamaño:", "Copias:", "Resumen"
        "soltar":  (FUENTE_PIXEL, _px8(2, e)),    # "Arrastre aquí el archivo"
        "total":   (FUENTE_PIXEL, _px8(4, e)),    # el total grande
        "copias":  (FUENTE_PIXEL, _px8(3, e)),    # número de copias
    }


def estilo_boton(fuentes_: dict, principal: bool = False) -> dict:
    """Opciones de tk.Button según el estilo: úselas como tk.Button(..., **estilo_boton(F))."""
    C = COLORES
    return dict(
        font=fuentes_["boton"],
        bg=C["primario"] if principal else C["boton"],
        fg=C["primario_texto"] if principal else C["boton_texto"],
        activebackground=C["zona_activa"], cursor="hand2", padx=12, pady=4,
        **ESTILO["boton"],
    )
