"""Modelo de costos y asignación de rangos (tarifa fija por rango).

Costo de una página:
    tinta_canal = (precio_tóner / rendimiento) × (cobertura_canal / 5 %) × área_relativa
    costo       = Σ tinta_canal × factor_corrección + papel + desgaste
    precio      = costo / (1 − margen)   → redondeado hacia arriba

Rangos: cada rango tiene un límite de cobertura total (C+M+Y+K). Una página cae
en el primer rango cuyo límite cubre su cobertura. El precio del rango es el del
modelo evaluado en ese límite, suponiendo que toda la tinta es del tóner más caro
del grupo; por eso el precio cobrado nunca queda por debajo del costo real.
"""

import math
from dataclasses import dataclass

from .cobertura import CoberturaPagina

CANALES = ("C", "M", "Y", "K")


def area_relativa(config: dict, tamano: str) -> float:
    """Área del papel dividida por el área de carta (carta = 1.0)."""
    p, carta = config["papel"][tamano], config["papel"]["carta"]
    return (p["ancho_mm"] * p["alto_mm"]) / (carta["ancho_mm"] * carta["alto_mm"])


def costo_por_pct(config: dict, canal: str) -> float:
    """Pesos que cuesta 1 % de cobertura de un canal en una hoja carta."""
    t = config["toner"][canal]
    return t["precio"] / t["rendimiento"] / config["cobertura_referencia_pct"]


def costo_fijo(config: dict, tamano: str, es_color: bool) -> float:
    """Papel + desgaste de una página."""
    p = config["papel"][tamano]
    papel = p["precio_resma"] / p["hojas_resma"]
    desgaste = config["desgaste_por_pagina"]["color" if es_color else "bn"]
    return papel + desgaste


def costo_tinta(config: dict, cob: CoberturaPagina, tamano: str) -> float:
    pcts = {"C": cob.c, "M": cob.m, "Y": cob.y, "K": cob.k}
    crudo = sum(pcts[ch] * costo_por_pct(config, ch) for ch in CANALES)
    return crudo * area_relativa(config, tamano) * config["factor_correccion"]


def a_precio(config: dict, costo: float) -> int:
    """Aplica margen sobre precio de venta y redondea hacia arriba."""
    precio = costo / (1 - config["margen_pct"] / 100)
    r = config["redondeo"]
    return int(math.ceil(precio / r) * r) if r > 0 else int(math.ceil(precio))


# --------------------------------------------------------------------------- rangos

def _costo_pct_peor_caso(config: dict, es_color: bool) -> float:
    """Costo de 1 % de cobertura con el tóner más caro del grupo (color: C/M/Y; b/n: K)."""
    canales = ("C", "M", "Y") if es_color else ("K",)
    return max(costo_por_pct(config, ch) for ch in canales)


def _costo_limite(config: dict, rango: dict, tamano: str, es_color: bool) -> float:
    tinta = (rango["cobertura_max_pct"] * _costo_pct_peor_caso(config, es_color)
             * area_relativa(config, tamano) * config["factor_correccion"])
    return tinta + costo_fijo(config, tamano, es_color)


def tabla_rangos(config: dict, tamano: str, es_color: bool) -> list[dict]:
    """Lista de rangos con su costo límite y el precio que se cobra."""
    rangos = config["rangos_color" if es_color else "rangos_bn"]
    tabla = []
    for r in rangos:
        costo_lim = _costo_limite(config, r, tamano, es_color)
        manual = (r.get("precio_manual") or {}).get(tamano)
        tabla.append({
            "nombre": r["nombre"],
            "cobertura_max_pct": r["cobertura_max_pct"],
            "costo_limite": costo_lim,
            "precio": int(manual) if manual else a_precio(config, costo_lim),
            "precio_es_manual": bool(manual),
        })
    return tabla


@dataclass
class CotizacionPagina:
    numero: int
    cobertura: CoberturaPagina
    costo: float           # costo real estimado (tinta + papel + desgaste)
    rango: str
    precio: int            # precio cobrado (el del rango)
    fuera_de_tabla: bool   # la página superó el último rango: se cobra su precio calculado


def cotizar_pagina(config: dict, cob: CoberturaPagina, tamano: str, numero: int) -> CotizacionPagina:
    costo = costo_tinta(config, cob, tamano) + costo_fijo(config, tamano, cob.es_color)
    tabla = tabla_rangos(config, tamano, cob.es_color)
    for r in tabla:
        if cob.total <= r["cobertura_max_pct"]:
            return CotizacionPagina(numero, cob, costo, r["nombre"], r["precio"], False)
    ultimo = tabla[-1]
    precio = max(ultimo["precio"], a_precio(config, costo))
    return CotizacionPagina(numero, cob, costo, ultimo["nombre"] + " (+)", precio, True)


@dataclass
class Cotizacion:
    paginas: list[CotizacionPagina]
    copias: int
    tamano: str

    def resumen(self) -> list[dict]:
        """Agrupa por rango: [{'rango', 'paginas', 'precio_unitario', 'subtotal'}], una fila por precio."""
        grupos: dict[tuple, int] = {}
        for p in self.paginas:
            grupos[(p.rango, p.precio)] = grupos.get((p.rango, p.precio), 0) + 1
        return [
            {"rango": rango, "paginas": n, "precio_unitario": precio, "subtotal": n * precio * self.copias}
            for (rango, precio), n in grupos.items()
        ]

    @property
    def total_por_copia(self) -> int:
        return sum(p.precio for p in self.paginas)

    @property
    def total(self) -> int:
        return self.total_por_copia * self.copias


def cotizar(config: dict, coberturas: list[CoberturaPagina], tamano: str = "carta", copias: int = 1) -> Cotizacion:
    paginas = [cotizar_pagina(config, cob, tamano, i + 1) for i, cob in enumerate(coberturas)]
    return Cotizacion(paginas, copias, tamano)
