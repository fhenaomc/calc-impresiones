"""Configuración del cotizador: valores por defecto y lectura/escritura de config.json.

La idea clave: el programa SIEMPRE tiene un juego completo de valores por defecto
(CONFIG_POR_DEFECTO). El archivo config.json solo "sobrescribe" lo que el usuario
haya cambiado. Así, si en una versión futura agregamos un ajuste nuevo, los
config.json viejos siguen funcionando: el ajuste nuevo toma su valor por defecto.
"""

import copy
import json
import sys
from pathlib import Path

NOMBRE_ARCHIVO = "config.json"

CONFIG_POR_DEFECTO = {
    # --- Tóner -------------------------------------------------------------
    # Rendimiento = páginas que imprime un cartucho con 5 % de cobertura (norma del fabricante).
    "toner": {
        "C": {"precio": 200000, "rendimiento": 17000},
        "M": {"precio": 200000, "rendimiento": 17000},
        "Y": {"precio": 200000, "rendimiento": 17000},
        "K": {"precio": 180000, "rendimiento": 28000},
    },
    "cobertura_referencia_pct": 5.0,

    # --- Papel -------------------------------------------------------------
    # Medidas en mm. El área relativa a carta escala el consumo de tinta.
    "papel": {
        "carta":  {"nombre": "Carta",  "ancho_mm": 215.9, "alto_mm": 279.4, "precio_resma": 15000, "hojas_resma": 500},
        "oficio": {"nombre": "Oficio", "ancho_mm": 215.9, "alto_mm": 330.2, "precio_resma": 19000, "hojas_resma": 500},
    },

    # --- Costos del negocio (además de tóner y papel) ----------------------
    # Mantenimiento: cada repuesto o visita se reparte entre las hojas de su ciclo.
    # "solo_color": el repuesto solo se gasta con hojas a color (tambores C, M, Y).
    # ESTIMADOS (oct. 2026): confirmar costos y ciclos con el técnico de la impresora.
    # Ciclo de 120.000 hojas: típico de kits de fusor Ricoh de esta gama.
    "mantenimiento": [
        {"nombre": "Visita técnica preventiva", "costo": 180000, "cada_hojas": 30000, "solo_color": False},
        {"nombre": "Kit de fusor",               "costo": 1200000, "cada_hojas": 120000, "solo_color": False},
        {"nombre": "Unidad de imagen negra",     "costo": 500000, "cada_hojas": 120000, "solo_color": False},
        {"nombre": "Unidades de imagen C, M, Y", "costo": 1500000, "cada_hojas": 120000, "solo_color": True},
        {"nombre": "Banda de transferencia",     "costo": 900000, "cada_hojas": 200000, "solo_color": False},
    ],
    # Energía: costo del mes repartido entre las hojas del mes. Valores ALTOS a propósito:
    # la ficha Ricoh da 1,16 kWh/semana (uso de oficina con apagado); aquí se asume encendida
    # todo el día (≈ 9 veces más). EPM estrato 4: $885/kWh (nov. 2026) + margen por recargos.
    "energia": {"potencia_w": 150, "horas_dia": 12, "dias_mes": 26, "precio_kwh": 1000},
    "hojas_mes": 3000,         # ESTIMADO: hojas impresas al mes (ver contador de la Ricoh)
    "capital_pct": 50.0,       # de lo que sobra (venta − costo): % para ahorro e imprevistos

    # --- Precio --------------------------------------------------------------
    "margen_pct": 40.0,          # precio = costo / (1 - margen)
    "factor_correccion": 1.15,   # multiplica el costo de tinta; >1 = estimar por encima
    "redondeo": 50,              # siempre hacia ARRIBA al múltiplo más cercano

    # --- Análisis de imagen ------------------------------------------------
    "analisis": {
        "dpi": 75,                    # resolución para renderizar páginas
        "umbral_croma": 0.10,         # 0-1: diferencia entre R,G,B para calcular tinta de color en un píxel
        # Decisión "¿hoja a color?": solo cuentan MANCHAS de color intenso. Calibrado (oct. 2026):
        # escaneo con celular ≤ 0,004 %, puntico naranja del logo IAC 0,005 %, logos EDAFA 0,22 %.
        "umbral_croma_decision": 0.15,
        "radio_mancha_px": 1,         # la mancha debe medir al menos (2·radio+1)² píxeles (3×3 ≈ 1 mm)
        "area_min_color_pct": 0.02,   # % de la hoja con manchas de color para sugerir color (≈ 3,5 × 3,5 mm)
        "gcr": 0.5,                   # 0-1: cuánto de la mezcla CMY se reemplaza por K en píxeles de color
    },

    # --- Apariencia (colores y demás en cotizador/tema.py) ------------------
    "apariencia": {"tamano_letra": 12},

    # --- Rangos (tarifa fija por rango) ------------------------------------
    # Cada rango cubre páginas hasta cierta cobertura total (suma C+M+Y+K, en %).
    # El precio del rango se calcula con el modelo de costos en su límite superior
    # (así toda página del rango queda cobrada por encima de su costo real),
    # salvo que se fije un "precio_manual" por tamaño, ej. {"carta": 1000}.
    # Límites calibrados con muestras/referencia (ver herramientas/generar_referencias.py):
    #   texto b/n ≈ 7 %, texto + título a color ≈ 13 %, foto media página ≈ 50-68 %,
    #   dos fotos ≈ 100-117 %, foto página completa ≈ 145-180 %.
    # Precios de venta acordados (sep. 2026): b/n fijo $700; color $1.000 a $4.000.
    # Oficio se cobra igual que carta (se vende poco y el margen lo permite).
    "rangos_bn": [
        {"nombre": "B/N normal",   "cobertura_max_pct": 12,  "precio_manual": {"carta": 700, "oficio": 700}},
        {"nombre": "B/N cargado",  "cobertura_max_pct": 40,  "precio_manual": {"carta": 700, "oficio": 700}},
        {"nombre": "B/N total",    "cobertura_max_pct": 100, "precio_manual": {"carta": 700, "oficio": 700}},
    ],
    "rangos_color": [
        {"nombre": "Color mínimo", "cobertura_max_pct": 20,  "precio_manual": {"carta": 1000, "oficio": 1000}},
        {"nombre": "Color medio",  "cobertura_max_pct": 80,  "precio_manual": {"carta": 2000, "oficio": 2000}},
        {"nombre": "Color alto",   "cobertura_max_pct": 140, "precio_manual": {"carta": 3000, "oficio": 3000}},
        {"nombre": "Color total",  "cobertura_max_pct": 250, "precio_manual": {"carta": 4000, "oficio": 4000}},
    ],
}


def carpeta_programa() -> Path:
    """Carpeta donde vive el programa: junto al .exe si está empaquetado, o la raíz del proyecto."""
    if getattr(sys, "frozen", False):  # PyInstaller marca sys.frozen = True
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _mezclar(base: dict, cambios: dict) -> dict:
    """Mezcla recursiva: los valores de `cambios` reemplazan a los de `base`."""
    resultado = copy.deepcopy(base)
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(resultado.get(clave), dict):
            resultado[clave] = _mezclar(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado


def cargar(ruta: Path | None = None) -> dict:
    ruta = ruta or carpeta_programa() / NOMBRE_ARCHIVO
    if not ruta.exists():
        return copy.deepcopy(CONFIG_POR_DEFECTO)
    with open(ruta, encoding="utf-8") as f:
        return _mezclar(CONFIG_POR_DEFECTO, json.load(f))


def guardar(config: dict, ruta: Path | None = None) -> None:
    ruta = ruta or carpeta_programa() / NOMBRE_ARCHIVO
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
