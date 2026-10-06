"""Cotizador por consola (para probar el motor antes de tener interfaz).

Uso:
    python -m cotizador.cli archivo.pdf [--tamano carta|oficio|doble_carta] [--copias N] [--detalle]
    python -m cotizador.cli --rangos      # muestra la tabla de precios por rango
"""

import argparse
import sys
from pathlib import Path

from . import config as cfg
from .cobertura import analizar_archivo
from .costos import cotizar, tabla_rangos
from .formato import pesos


def mostrar_rangos(config: dict) -> None:
    for tamano, papel in config["papel"].items():
        print(f"\n== {papel['nombre']} ==")
        for es_color in (False, True):
            for r in tabla_rangos(config, tamano, es_color):
                marca = " (manual)" if r["precio_es_manual"] else ""
                marca += "  ⚠ PRECIO POR DEBAJO DEL COSTO" if r["bajo_costo"] else ""
                print(f"  {r['nombre']:<14} hasta {r['cobertura_max_pct']:>4}%   "
                      f"costo {pesos(r['costo_limite']):>7}   precio {pesos(r['precio']):>7}{marca}")


def main(argv=None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Cotizador de impresiones")
    ap.add_argument("archivos", nargs="*", type=Path)
    ap.add_argument("--tamano", default="carta")
    ap.add_argument("--copias", type=int, default=1)
    ap.add_argument("--detalle", action="store_true", help="muestra cada página")
    ap.add_argument("--rangos", action="store_true", help="muestra la tabla de precios por rango")
    args = ap.parse_args(argv)

    config = cfg.cargar()
    if args.rangos:
        mostrar_rangos(config)

    for ruta in args.archivos:
        cot = cotizar(config, analizar_archivo(ruta, config["analisis"]), args.tamano, args.copias)
        print(f"\n### {ruta.name}  ({len(cot.paginas)} pág., {args.tamano}, {args.copias} copia(s))")
        if args.detalle:
            print(f"  {'Pág':>3}  {'C%':>5} {'M%':>5} {'Y%':>5} {'K%':>5}  {'Área col%':>9}  {'Costo':>7}  Rango")
            for p in cot.paginas:
                c = p.cobertura
                print(f"  {p.numero:>3}  {c.c:5.1f} {c.m:5.1f} {c.y:5.1f} {c.k:5.1f}  {c.area_color_pct:9.2f}  "
                      f"{pesos(p.costo):>7}  {p.rango} {pesos(p.precio)}")
        for fila in cot.resumen():
            print(f"  {fila['paginas']:>3} pág. {fila['rango']:<16} × {pesos(fila['precio_unitario']):>7}"
                  f" × {cot.copias} = {pesos(fila['subtotal'])}")
        print(f"  TOTAL: {pesos(cot.total)}")


if __name__ == "__main__":
    main()
