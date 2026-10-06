"""Pruebas con imágenes sintéticas cuya cobertura conocemos de antemano.

Se ejecutan con:  .venv\\Scripts\\python -m pytest
"""

import numpy as np
import pytest

from cotizador.cobertura import analizar_imagen
from cotizador.config import CONFIG_POR_DEFECTO

ANALISIS = CONFIG_POR_DEFECTO["analisis"]
BLANCO, NEGRO = (255, 255, 255), (0, 0, 0)


def hoja(color_fondo=BLANCO, alto=1100, ancho=850):
    return np.full((alto, ancho, 3), color_fondo, dtype=np.uint8)


def test_hoja_blanca_no_gasta_tinta():
    cob = analizar_imagen(hoja(), ANALISIS)
    assert cob.total == pytest.approx(0)
    assert not cob.es_color


def test_hoja_negra_es_100_k_y_bn():
    cob = analizar_imagen(hoja(NEGRO), ANALISIS)
    assert cob.k == pytest.approx(100)
    assert cob.c == cob.m == cob.y == 0
    assert not cob.es_color


def test_gris_medio_es_50_k():
    cob = analizar_imagen(hoja((128, 128, 128)), ANALISIS)
    assert cob.k == pytest.approx(49.8, abs=0.1)
    assert not cob.es_color


def test_media_hoja_cian_es_50_c():
    img = hoja()
    img[:550] = (0, 255, 255)  # cian puro: R=0 -> C=1
    cob = analizar_imagen(img, ANALISIS)
    assert cob.c == pytest.approx(50)
    assert cob.m == pytest.approx(0) and cob.y == pytest.approx(0)
    assert cob.es_color


def test_rojo_puro_usa_magenta_y_amarillo():
    cob = analizar_imagen(hoja((255, 0, 0)), ANALISIS)
    assert cob.m == pytest.approx(100) and cob.y == pytest.approx(100)
    assert cob.c == pytest.approx(0)


def test_titulo_pequeno_a_color_vuelve_color_la_pagina():
    img = hoja()
    img[100:130, 100:400] = (200, 30, 30)  # ~1 % de la hoja
    assert analizar_imagen(img, ANALISIS).es_color


def test_ruido_jpeg_en_gris_no_es_color():
    rng = np.random.default_rng(0)
    img = hoja((200, 200, 200)).astype(np.int16)
    img += rng.integers(-8, 9, img.shape)  # variaciones pequeñas por canal
    cob = analizar_imagen(np.clip(img, 0, 255).astype(np.uint8), ANALISIS)
    assert not cob.es_color


def test_gcr_deja_mas_tinta_de_color_en_colores_oscuros():
    # Marrón oscuro: parte común CMY alta. Con gcr=0.5 la mitad pasa a K.
    cob = analizar_imagen(hoja((80, 40, 20)), ANALISIS)
    c0 = 1 - 80 / 255  # tinta cruda de cian
    kmin = 1 - 80 / 255  # min(C,M,Y) = C en este color
    assert cob.k == pytest.approx(50 * kmin, abs=0.1)
    assert cob.c == pytest.approx(100 * (c0 - 0.5 * kmin), abs=0.1)


def test_halo_de_color_de_escaneo_no_es_color():
    """Escaneo con celular: letras negras con un borde de color pálido de 1 píxel."""
    img = hoja()
    for fila in range(100, 1000, 20):          # 45 renglones de "texto"
        img[fila:fila + 6, 80:770] = NEGRO
        img[fila - 1, 80:770] = (235, 200, 215)  # halo rosado arriba (croma ≈ 0,14)
        img[fila + 6, 80:770] = (190, 230, 200)  # halo verdoso abajo (croma ≈ 0,16)
    cob = analizar_imagen(img, ANALISIS)
    assert not cob.es_color


def test_puntico_de_color_diminuto_no_es_color():
    img = hoja()
    img[50:56, 50:56] = (255, 120, 0)  # punto naranja de 6×6 px (~2 mm)
    assert not analizar_imagen(img, ANALISIS).es_color


def test_k_gris_de_una_foto():
    cob = analizar_imagen(hoja((255, 0, 0)), ANALISIS)  # rojo puro: gris = 1 - 1/3
    assert cob.k_gris == pytest.approx(100 * 2 / 3, abs=0.1)
