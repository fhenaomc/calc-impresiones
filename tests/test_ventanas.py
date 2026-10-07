"""Pruebas de la interfaz: se crean las ventanas de verdad (sin mostrarlas) y se simula al usuario."""

import copy
import tkinter as tk
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from cotizador import config as cfg
from cotizador import interfaz, ventana_precios
from cotizador.formato import leer_pesos


@pytest.fixture(scope="session")
def _tk():
    # Una sola raíz Tk para todas las pruebas: crear y destruir muchas Tk() en un
    # proceso falla de forma intermitente en Windows ("Can't find a usable tk.tcl").
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def root(_tk):
    """Ventana hija nueva para cada prueba; se destruye al terminar."""
    w = tk.Toplevel(_tk)
    w.withdraw()
    yield w
    w.destroy()


@pytest.fixture
def guardados(monkeypatch):
    """Reemplaza cfg.guardar para no escribir config.json real; devuelve lo que se habría guardado."""
    lista = []
    monkeypatch.setattr(ventana_precios.cfg, "guardar", lambda c: lista.append(c))
    return lista


def ventana(root, config=None, al_guardar=None):
    from cotizador import tema
    return ventana_precios.VentanaPrecios(root, config or copy.deepcopy(cfg.CONFIG_POR_DEFECTO),
                                          tema.fuentes(12), al_guardar or (lambda c: None))


def test_leer_pesos():
    assert leer_pesos("$1.500") == 1500
    assert leer_pesos(" 700 ") == 700
    with pytest.raises(ValueError):
        leer_pesos("mil")


def test_guardar_precio_nuevo(root, guardados):
    v = ventana(root)
    _, _, v_carta, *_ = v.entradas[4]   # índice 4 = Color medio (3 rangos b/n + 2.º de color)
    v_carta.set("2.500")
    v.guardar()
    nuevo = guardados[0]
    assert nuevo["rangos_color"][1]["precio_manual"] == {"carta": 2500, "oficio": 2500}  # oficio copia a carta


def test_oficio_distinto(root, guardados):
    v = ventana(root)
    v.igual_oficio.set(False)
    v._sincronizar_oficio()
    _, _, _, v_oficio, *_ = v.entradas[0]
    v_oficio.set("900")
    v.guardar()
    assert guardados[0]["rangos_bn"][0]["precio_manual"] == {"carta": 700, "oficio": 900}


def test_precio_invalido_no_guarda(root, guardados, monkeypatch):
    errores = []
    monkeypatch.setattr(ventana_precios.messagebox, "showerror", lambda *a, **k: errores.append(a))
    v = ventana(root)
    v.entradas[0][2].set("abc")
    v.guardar()
    assert errores and not guardados


def test_bajo_costo_pide_confirmacion(root, guardados, monkeypatch):
    monkeypatch.setattr(ventana_precios.messagebox, "askyesno", lambda *a, **k: False)  # usuario dice "No"
    v = ventana(root)
    v.entradas[6][2].set("100")  # Color total a $100: por debajo del costo
    v.guardar()
    assert not guardados


def test_restaurar_vuelve_a_los_originales(root):
    v = ventana(root)
    v.entradas[3][2].set("5000")
    v.restaurar()
    assert leer_pesos(v.entradas[3][2].get()) == 1000


def test_app_cotiza_una_imagen(root, tmp_path):
    """Flujo completo sin hilos: imagen -> análisis -> resumen en la ventana."""
    img = np.full((1100, 850, 3), 255, np.uint8)
    img[:550] = (0, 128, 255)  # media hoja azul -> color
    ruta = tmp_path / "foto.png"
    Image.fromarray(img).save(ruta)

    app = interfaz.App(root, copy.deepcopy(cfg.CONFIG_POR_DEFECTO))
    from cotizador.cobertura import analizar_archivo
    app.trabajo = [(Path(ruta), i, c) for i, c in enumerate(analizar_archivo(ruta, app.config["analisis"]))]
    app.copias.set(3)
    app.recotizar()
    assert app.cotizacion.paginas[0].rango.startswith("Color")
    assert app.total.cget("text") == "$" + f"{app.cotizacion.paginas[0].precio * 3:,}".replace(",", ".")
    assert "3 copias" in app.etiqueta_total.cget("text")


def test_alerta_aparece_si_precio_bajo_costo(root):
    config = copy.deepcopy(cfg.CONFIG_POR_DEFECTO)
    config["rangos_color"][3]["precio_manual"] = {"carta": 100, "oficio": 100}
    app = interfaz.App(root, config)
    assert app.alerta.winfo_manager() == "pack"
    assert "Color total" in app.alerta.cget("text")


def _app_con_foto_y_texto(root, tmp_path):
    """App con 2 hojas: una foto a color y una hoja de texto gris."""
    from cotizador.cobertura import analizar_archivo
    foto = np.full((1100, 850, 3), 255, np.uint8)
    foto[:550] = (0, 128, 255)
    texto = np.full((1100, 850, 3), 255, np.uint8)
    texto[100:1000:20, 80:770] = 0
    rutas = []
    for nombre, img in (("foto.png", foto), ("texto.png", texto)):
        Image.fromarray(img).save(tmp_path / nombre)
        rutas.append(tmp_path / nombre)
    app = interfaz.App(root, copy.deepcopy(cfg.CONFIG_POR_DEFECTO))
    for r in rutas:
        app.trabajo += [(r, i, c) for i, c in enumerate(analizar_archivo(r, app.config["analisis"]))]
    app.recotizar()
    return app


def test_detalle_cambia_hoja_a_bn_y_actualiza_total(root, tmp_path):
    from cotizador.costos import BN
    app = _app_con_foto_y_texto(root, tmp_path)
    antes = app.cotizacion.total
    assert app.cotizacion.paginas[0].es_color
    app.abrir_detalle()
    det = app.detalle
    det.lista.selection_set(det.lista.get_children()[0])
    det._cambiar(BN)
    assert not app.cotizacion.paginas[0].es_color
    assert app.cotizacion.total < antes
    valores = det.lista.item(det.lista.get_children()[0], "values")  # [archivo, hoja, imprimir, ...]
    assert valores[2].startswith("✋")
    det._cambiar(None)  # volver a la sugerencia
    assert app.cotizacion.total == antes
    det.destroy()
    assert app.detalle is None


def test_todo_bn_y_nueva_cotizacion_reinicia(root, tmp_path):
    app = _app_con_foto_y_texto(root, tmp_path)
    app.todo_bn.set(True)
    app.recotizar()
    assert not any(p.es_color for p in app.cotizacion.paginas)
    app.limpiar()
    assert not app.todo_bn.get() and app.modos == {} and app.cotizacion is None


# ----------------------------------------------------------------------------- costos del negocio
from cotizador import ventana_costos  # noqa: E402


def costos(root, monkeypatch, guardados_costos):
    from cotizador import tema
    monkeypatch.setattr(ventana_costos.cfg, "guardar", lambda c: guardados_costos.append(c))
    return ventana_costos.VentanaCostos(root, copy.deepcopy(cfg.CONFIG_POR_DEFECTO), tema.fuentes(12),
                                        al_guardar=lambda c: None)


def _campo(v, ruta):
    return next(c for c in v.campos if c.ruta == ruta)


def test_costos_lee_lo_mismo_que_la_config(root, monkeypatch):
    v = costos(root, monkeypatch, [])
    nuevo = v._leer()
    base = cfg.CONFIG_POR_DEFECTO
    assert nuevo["toner"] == base["toner"] and nuevo["energia"] == base["energia"]
    assert nuevo["mantenimiento"] == base["mantenimiento"]
    assert nuevo["factor_correccion"] == base["factor_correccion"]


def test_papel_al_doble_sube_el_costo(root, monkeypatch):
    from cotizador.costos import tabla_rangos
    g = []
    v = costos(root, monkeypatch, g)
    antes = tabla_rangos(v._leer(), "carta", False)[0]["costo_limite"]
    _campo(v, ("papel", "carta", "precio_resma")).var.set("$30.000")
    v.guardar()
    despues = tabla_rangos(g[0], "carta", False)[0]["costo_limite"]
    assert despues == pytest.approx(antes + 30)  # papel de $30 a $60 por hoja


def test_agregar_y_quitar_mantenimiento(root, monkeypatch):
    g = []
    v = costos(root, monkeypatch, g)
    v._agregar_mant({"nombre": "Rodillos", "costo": 100000, "cada_hojas": 50000, "solo_color": False})
    v._quitar_mant(v.filas_mant[0])  # quita la visita técnica
    v.guardar()
    nombres = [m["nombre"] for m in g[0]["mantenimiento"]]
    assert "Rodillos" in nombres and "Visita técnica preventiva" not in nombres


def test_dato_invalido_se_reporta_y_no_guarda(root, monkeypatch):
    g, errores = [], []
    monkeypatch.setattr(ventana_costos.messagebox, "showerror", lambda *a, **k: errores.append(a[1]))
    v = costos(root, monkeypatch, g)
    _campo(v, ("hojas_mes",)).var.set("0")
    v.guardar()
    assert not g and "Hojas impresas al mes" in errores[0]


def test_limites_de_rangos_deben_crecer(root, monkeypatch):
    v = costos(root, monkeypatch, [])
    _campo(v, ("rangos_color", 1, "cobertura_max_pct")).var.set("10")  # medio < mínimo (20)
    with pytest.raises(ValueError, match="menor a mayor"):
        v._leer()


# ----------------------------------------------------------------------------- estilos
def test_estilo_clasico_sigue_funcionando(root):
    from cotizador import tema
    config = copy.deepcopy(cfg.CONFIG_POR_DEFECTO)
    config["apariencia"]["tema"] = "clasico"
    app = interfaz.App(root, config)
    assert not tema.PIXEL and tema.COLORES["fondo"] == tema.TEMAS["clasico"]["colores"]["fondo"]
    assert tema.fuentes(12)["total"][0] == tema.FAMILIA
    interfaz.preparar_estilo(cfg.CONFIG_POR_DEFECTO)  # deja el estilo por defecto para las demás pruebas
    assert tema.PIXEL


def test_estilo_pixel_usa_letra_pixelada_en_multiplos_de_8(root):
    import tkinter.font as tkf
    from cotizador import tema
    interfaz.App(root, copy.deepcopy(cfg.CONFIG_POR_DEFECTO))
    assert tema.FUENTE_PIXEL in tkf.families(root)
    for clave in ("titulo", "seccion", "soltar", "total", "copias"):
        familia, tamano = tema.fuentes(12, 1.25)[clave]
        assert familia == tema.FUENTE_PIXEL and tamano < 0 and tamano % 8 == 0


def test_pixelart_dibuja_logo_e_icono():
    from cotizador import pixelart
    assert pixelart.icono(32).size == (32, 32)
    logo = pixelart.encabezado(2)
    assert logo.height == 64 and logo.width > 300


def test_escala_de_pantalla_no_depende_de_decimales():
    from cotizador import tema
    assert tema.escala_de_pantalla(95.9) == tema.escala_de_pantalla(96) == 1.0
    assert tema.escala_de_pantalla(120.1) == 1.25
    # la sección (1,5 unidades) debe dar 16 px tanto al 100 % como al 125 %
    assert tema._px8(1.5, 1.0) == tema._px8(1.5, 1.25) == -16


def test_errores_quedan_registrados(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "carpeta_programa", lambda: tmp_path)
    monkeypatch.setattr(interfaz.messagebox, "showerror", lambda *a, **k: None)
    try:
        1 / 0
    except ZeroDivisionError as e:
        interfaz._avisar_error(type(e), e, e.__traceback__)
    assert "ZeroDivisionError" in (tmp_path / "errores.log").read_text(encoding="utf-8")
