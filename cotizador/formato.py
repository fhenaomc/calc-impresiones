"""Funciones de formato de texto compartidas por la consola y la interfaz."""


def pesos(valor: float) -> str:
    """Formato colombiano: 1250 -> '$1.250'."""
    return "$" + f"{valor:,.0f}".replace(",", ".")


def leer_pesos(texto: str) -> int:
    """Convierte lo que escribe el usuario ('$1.500', '1500', '1.500') en entero. Lanza ValueError si no es válido."""
    limpio = texto.strip().replace("$", "").replace(".", "").replace(",", "").replace(" ", "")
    if not limpio.isdigit():
        raise ValueError(f"No es un precio válido: {texto!r}")
    return int(limpio)


def hojas(n: int) -> str:
    return f"{n} hoja" if n == 1 else f"{n} hojas"
