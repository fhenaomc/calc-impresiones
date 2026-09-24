"""Pruebas del modelo de costos con números calculados a mano."""

import copy

import pytest

from cotizador.cobertura import CoberturaPagina
from cotizador.config import CONFIG_POR_DEFECTO
from cotizador.costos import a_precio, area_relativa, costo_por_pct, cotizar, tabla_rangos


@pytest.fixture
def config():
    """Config sin precios manuales: así se prueba el modelo de costos puro."""
    c = copy.deepcopy(CONFIG_POR_DEFECTO)
    for r in c["rangos_bn"] + c["rangos_color"]:
        r["precio_manual"] = {}
    return c


def pagina(c=0, m=0, y=0, k=0, es_color=None):
    color = es_color if es_color is not None else (c + m + y) > 0
    return CoberturaPagina(c, m, y, k, area_color_pct=10 if color else 0, es_color=color)


def test_costo_por_pct(config):
    # 200.000 / 17.000 páginas = 11,76 $ por página al 5 %  ->  2,35 $ por 1 %
    assert costo_por_pct(config, "C") == pytest.approx(200000 / 17000 / 5)


def test_area_oficio(config):
    assert area_relativa(config, "oficio") == pytest.approx(330.2 / 279.4)


def test_redondeo_siempre_hacia_arriba(config):
    config["margen_pct"] = 0
    assert a_precio(config, 101) == 150
    assert a_precio(config, 150) == 150


def test_margen_sobre_precio_de_venta(config):
    config["redondeo"] = 1
    assert a_precio(config, 60) == 100  # 60 / (1 - 0,40)


def test_precio_nunca_menor_que_costo(config):
    for cob in [pagina(k=3), pagina(k=35), pagina(c=5, m=5), pagina(c=50, m=40, y=45, k=20)]:
        p = cotizar(config, [cob]).paginas[0]
        assert p.precio >= p.costo


def test_pagina_bn_con_titulo_de_color_es_color_minimo(config):
    cot = cotizar(config, [pagina(c=0.3, m=0.5, y=0.2, k=5)])
    assert cot.paginas[0].rango == "Color mínimo"


def test_bn_cargado_cuesta_mas_que_bn_normal(config):
    cot = cotizar(config, [pagina(k=5), pagina(k=35)])
    assert cot.paginas[0].rango == "B/N normal"
    assert cot.paginas[1].rango == "B/N cargado"
    assert cot.paginas[1].precio > cot.paginas[0].precio


def test_precio_manual_reemplaza_el_calculado(config):
    config["rangos_bn"][0]["precio_manual"] = {"carta": 150}
    assert tabla_rangos(config, "carta", es_color=False)[0]["precio"] == 150
    assert cotizar(config, [pagina(k=5)]).paginas[0].precio == 150


def test_resumen_agrupa_y_multiplica_copias(config):
    cot = cotizar(config, [pagina(k=5), pagina(k=5), pagina(c=40, m=30, y=30)], copias=3)
    filas = {f["rango"]: f for f in cot.resumen()}
    assert filas["B/N normal"]["paginas"] == 2
    assert sum(f["subtotal"] for f in filas.values()) == cot.total
    assert cot.total == 3 * cot.total_por_copia


def test_pagina_saturada_sale_de_la_tabla_y_cobra_su_costo(config):
    p = cotizar(config, [pagina(c=100, m=100, y=100, k=50)]).paginas[0]
    assert p.fuera_de_tabla
    assert p.precio >= p.costo


def test_precios_acordados_cubren_el_costo():
    """Los precios fijos por defecto nunca deben quedar por debajo del costo máximo del rango."""
    for tamano in CONFIG_POR_DEFECTO["papel"]:
        for es_color in (False, True):
            for r in tabla_rangos(CONFIG_POR_DEFECTO, tamano, es_color):
                assert not r["bajo_costo"], (tamano, r["nombre"])


def test_alerta_si_el_toner_sube_mucho(config):
    config["rangos_color"][0]["precio_manual"] = {"carta": 1000}
    config["toner"]["C"]["precio"] = 5_000_000  # tóner 25 veces más caro
    assert tabla_rangos(config, "carta", es_color=True)[0]["bajo_costo"]
