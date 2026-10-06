"""Apariencia de la interfaz: colores, letras y tamaños en UN solo lugar.

Para cambiar cómo se ve el programa, edite este archivo; la lógica no se toca.
El tamaño base de la letra también se puede cambiar sin programar, en config.json:
    "apariencia": {"tamano_letra": 13}
"""

FAMILIA = "Segoe UI"  # letra estándar de Windows 10/11

COLORES = {
    "fondo":          "#F4F6F8",
    "panel":          "#FFFFFF",
    "texto":          "#1F2933",
    "texto_suave":    "#616E7C",
    "primario":       "#1F4E78",   # azul de títulos y botones principales
    "primario_texto": "#FFFFFF",
    "zona_soltar":    "#E3EEF9",   # recuadro "arrastre aquí"
    "zona_activa":    "#C7DDF5",   # recuadro cuando el mouse pasa por encima
    "borde":          "#9FB3C8",
    "total":          "#0B6E4F",   # verde del total
    "alerta_fondo":   "#FDECEA",
    "alerta_texto":   "#B42318",
}

# Color de fondo de cada rango (mismos que la tabla de precios en Excel).
# Si se agrega un rango nuevo sin color aquí, se usa COLOR_RANGO_POR_DEFECTO.
COLORES_RANGO = {
    "B/N normal": "#F2F2F2", "B/N cargado": "#D9D9D9", "B/N total": "#BFBFBF",
    "Color mínimo": "#FFF4D6", "Color medio": "#FFE0B2", "Color alto": "#FFCC99", "Color total": "#F8B195",
}
COLOR_RANGO_POR_DEFECTO = "#FFFFFF"


def color_rango(nombre: str) -> str:
    return COLORES_RANGO.get(nombre.replace(" (+)", ""), COLOR_RANGO_POR_DEFECTO)


def fuentes(tamano_base: int) -> dict:
    """Fuentes derivadas del tamaño base. Todo escala junto si cambia el tamaño base."""
    b = tamano_base
    return {
        "normal":  (FAMILIA, b),
        "negrita": (FAMILIA, b, "bold"),
        "pequena": (FAMILIA, max(b - 2, 8)),
        "titulo":  (FAMILIA, b + 6, "bold"),
        "soltar":  (FAMILIA, b + 4, "bold"),
        "total":   (FAMILIA, b + 14, "bold"),
        "boton":   (FAMILIA, b, "bold"),
        "copias":  (FAMILIA, b + 6, "bold"),
    }
