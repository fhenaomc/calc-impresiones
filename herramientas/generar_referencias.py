"""Genera PDFs de referencia (uno por rango) para calibrar los límites de los rangos.

Casos que definió el usuario:
  1. Mínimo: documento b/n con un título decorado a color.
  2. Medio:  una foto que ocupa media página, con márgenes.
  3. Alto:   dos fotos como la anterior.
  4. Total:  foto a página completa.

Uso:  .venv\\Scripts\\python herramientas\\generar_referencias.py [carpeta_de_fotos]
"""

import sys
from pathlib import Path

import pymupdf

SALIDA = Path(__file__).resolve().parent.parent / "muestras" / "referencia"
CARTA = pymupdf.paper_rect("letter")  # 612 × 792 puntos (1 pt = 1/72")
MARGEN = 54  # 3/4"

TEXTO = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
         "incididunt ut labore et dolore magna aliqua. ") * 28


def pagina_texto(doc, con_titulo_color):
    p = doc.new_page(width=CARTA.width, height=CARTA.height)
    if con_titulo_color:
        p.draw_rect(pymupdf.Rect(MARGEN, MARGEN, CARTA.width - MARGEN, MARGEN + 40),
                    color=None, fill=(0.1, 0.3, 0.7))
        p.insert_text((MARGEN + 12, MARGEN + 28), "INFORME MENSUAL", fontsize=22, color=(1, 1, 1))
    cuerpo = pymupdf.Rect(MARGEN, MARGEN + 60, CARTA.width - MARGEN, CARTA.height - MARGEN)
    sobrante = p.insert_textbox(cuerpo, TEXTO, fontsize=10.5)
    assert sobrante >= 0, "el texto no cabe en la página"
    return p


def foto_en(p, rect, foto):
    p.insert_image(rect, filename=str(foto), keep_proportion=False)


def main():
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Windows\Web\Wallpaper")
    fotos = sorted(carpeta.rglob("img2*.jpg"))[:4]
    SALIDA.mkdir(parents=True, exist_ok=True)
    ancho_util = CARTA.width - 2 * MARGEN
    mitad = (CARTA.height - 2 * MARGEN) / 2

    casos = {}
    doc = pymupdf.open(); pagina_texto(doc, False); casos["0_texto_bn"] = doc
    doc = pymupdf.open(); pagina_texto(doc, True); casos["1_titulo_color"] = doc
    for i, foto in enumerate(fotos):
        doc = pymupdf.open(); p = doc.new_page(width=CARTA.width, height=CARTA.height)
        foto_en(p, pymupdf.Rect(MARGEN, MARGEN, MARGEN + ancho_util, MARGEN + mitad - 6), foto)
        casos[f"2_media_pagina_{i}"] = doc

        doc = pymupdf.open(); p = doc.new_page(width=CARTA.width, height=CARTA.height)
        foto_en(p, pymupdf.Rect(MARGEN, MARGEN, MARGEN + ancho_util, MARGEN + mitad - 6), foto)
        otra = fotos[(i + 1) % len(fotos)]
        foto_en(p, pymupdf.Rect(MARGEN, MARGEN + mitad + 6, MARGEN + ancho_util, CARTA.height - MARGEN), otra)
        casos[f"3_dos_fotos_{i}"] = doc

        doc = pymupdf.open(); p = doc.new_page(width=CARTA.width, height=CARTA.height)
        foto_en(p, CARTA, foto)
        casos[f"4_pagina_completa_{i}"] = doc

    for nombre, doc in casos.items():
        doc.save(SALIDA / f"{nombre}.pdf")
    print(f"{len(casos)} PDFs en {SALIDA}")


if __name__ == "__main__":
    main()
