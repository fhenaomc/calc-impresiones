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


def numero(valor: float, decimales: int = 0) -> str:
    """Formato colombiano: 30000 -> '30.000'; 0.15 con 2 decimales -> '0,15'."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def leer_numero(texto: str, decimales: bool = False) -> float:
    """Lee un número escrito por el usuario.

    Enteros/pesos: el punto es separador de miles ('1.500' -> 1500).
    Decimales: la coma es decimal ('0,15' -> 0.15); también acepta '0.15'.
    Lanza ValueError si no es un número.
    """
    t = texto.strip().replace("$", "").replace("%", "").replace(" ", "")
    if decimales:
        t = t.replace(".", "").replace(",", ".") if "," in t else t
    else:
        t = t.replace(".", "").replace(",", "")
    try:
        return float(t)
    except ValueError:
        raise ValueError(f"No es un número válido: {texto!r}") from None
