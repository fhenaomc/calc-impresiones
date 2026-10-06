"""Ventana "Costos del negocio": todo lo que entra en el costo de una hoja.

Pestañas:
  1. Tóner y papel      precio y rendimiento de cada tóner; precio de la resma.
  2. Mantenimiento      lista editable de repuestos/visitas con su costo y cada cuántas hojas.
  3. Energía y volumen  consumo de la impresora, precio del kWh y hojas impresas al mes.
  4. Avanzado           factor de corrección, reparto, límites de rangos y detección de color.

A la derecha, el RESULTADO se recalcula mientras se escribe: cuánto cuesta cada rango,
a cuánto se vende y cuánto queda. Así se responde "¿y si el papel se duplica?" al instante.

Cómo está hecho: cada casilla es un `Campo` que sabe en qué parte de la configuración
vive (su "ruta", p. ej. ("toner", "C", "precio")) y cómo leer/escribir su número.
`_leer()` arma una configuración nueva con todas las casillas; si alguna está mal,
dice cuál. Los precios de venta NO se tocan aquí: tienen su propia ventana.
"""

import copy
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from . import config as cfg
from . import tema
from .costos import costo_energia, costo_mantenimiento, costo_papel, energia_mes, tabla_rangos
from .formato import leer_numero, numero, pesos

# tipo -> (decimales al mostrar, ¿se lee con decimales?, prefijo)
TIPOS = {"pesos": (0, False, "$"), "entero": (0, False, ""), "decimal": (2, True, ""), "uno": (1, True, "")}


@dataclass
class Campo:
    ruta: tuple
    etiqueta: str
    tipo: str
    var: tk.StringVar
    minimo: float | None = None   # valor mínimo permitido (exclusivo si minimo_exclusivo)
    maximo: float | None = None
    minimo_exclusivo: bool = True


def _obtener(config, ruta):
    for clave in ruta:
        config = config[clave]
    return config


def _poner(config, ruta, valor):
    for clave in ruta[:-1]:
        config = config[clave]
    config[ruta[-1]] = valor


def _mostrar(valor, tipo):
    dec, _, prefijo = TIPOS[tipo]
    return prefijo + numero(valor, dec)


class VentanaCostos(tk.Toplevel):
    def __init__(self, padre, config: dict, fuentes: dict, al_guardar):
        super().__init__(padre)
        self.title("Costos del negocio")
        self.config_original = config
        self.al_guardar = al_guardar
        self.F, self.C = fuentes, tema.COLORES
        self.campos: list[Campo] = []
        self.filas_mant = []       # [{"nombre": var, "costo": var, "cada": var, "solo_color": BooleanVar}]
        self._pendiente = None     # recálculo programado (para no recalcular en cada tecla)
        self.configure(bg=self.C["fondo"], padx=16, pady=12)
        self.transient(padre)
        self.grab_set()

        tk.Label(self, text="Costos del negocio", font=fuentes["titulo"], fg=self.C["primario"],
                 bg=self.C["fondo"]).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(self, text="Cambie cualquier valor y vea a la derecha cómo queda el costo de cada hoja. "
                            "Nada se guarda hasta presionar «Guardar».",
                 font=fuentes["pequena"], fg=self.C["texto_suave"], bg=self.C["fondo"]
                 ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        estilo = ttk.Style(self)
        estilo.configure("Costos.TNotebook.Tab", font=fuentes["negrita"], padding=(10, 4))
        self.pestanas = ttk.Notebook(self, style="Costos.TNotebook")
        self.pestanas.grid(row=2, column=0, sticky="nsew")
        self._pestana_insumos(config)
        self._pestana_mantenimiento(config)
        self._pestana_energia(config)
        self._pestana_avanzado(config)

        self.resultado = tk.Frame(self, bg=self.C["panel"], relief="solid", bd=1, padx=12, pady=10)
        self.resultado.grid(row=2, column=1, sticky="nsew", padx=(12, 0))

        botones = tk.Frame(self, bg=self.C["fondo"])
        botones.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        b = dict(font=fuentes["boton"], relief="solid", bd=1, padx=12, pady=4, cursor="hand2")
        tk.Button(botones, text="Guardar", command=self.guardar, bg=self.C["primario"],
                  fg=self.C["primario_texto"], **b).pack(side="right")
        tk.Button(botones, text="Cancelar", command=self.destroy, bg=self.C["panel"], **b).pack(side="right", padx=8)
        tk.Button(botones, text="Volver a los valores originales", command=self.restaurar,
                  bg=self.C["panel"], **b).pack(side="left")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._recalcular()

    # ------------------------------------------------------------------ ayudas de construcción
    def _marco(self, titulo):
        m = tk.Frame(self.pestanas, bg=self.C["fondo"], padx=12, pady=10)
        self.pestanas.add(m, text=titulo)
        return m

    def _titulo(self, padre, fila, texto, col=0):
        tk.Label(padre, text=texto, font=self.F["negrita"], fg=self.C["primario"], bg=self.C["fondo"]
                 ).grid(row=fila, column=col, columnspan=3, sticky="w", pady=(10, 4))

    def _campo(self, padre, fila, col, config, ruta, etiqueta, tipo, ayuda="", **limites):
        """Crea una casilla conectada a `ruta` de la configuración."""
        var = tk.StringVar(value=_mostrar(_obtener(config, ruta), tipo))
        var.trace_add("write", lambda *_: self._programar())
        if etiqueta:
            tk.Label(padre, text=etiqueta, font=self.F["normal"], bg=self.C["fondo"], anchor="w"
                     ).grid(row=fila, column=col, sticky="w", padx=(0, 8), pady=2)
            col += 1
        tk.Entry(padre, textvariable=var, font=self.F["normal"], width=11, justify="right"
                 ).grid(row=fila, column=col, padx=4, pady=2)
        if ayuda:
            tk.Label(padre, text=ayuda, font=self.F["pequena"], fg=self.C["texto_suave"], bg=self.C["fondo"],
                     anchor="w").grid(row=fila, column=col + 1, sticky="w", padx=(4, 0))
        self.campos.append(Campo(ruta, etiqueta or str(ruta), tipo, var, **limites))
        return var

    def _encabezados(self, padre, fila, textos, col=0):
        for j, t in enumerate(textos):
            tk.Label(padre, text=t, font=self.F["pequena"], fg=self.C["texto_suave"], bg=self.C["fondo"]
                     ).grid(row=fila, column=col + j, padx=4)

    # ------------------------------------------------------------------ pestañas
    def _pestana_insumos(self, config):
        m = self._marco("Tóner y papel")
        self._titulo(m, 0, "Tóner")
        self._encabezados(m, 1, ["", "Precio", "Rinde (hojas al 5 %)"])
        nombres = {"C": "Cian", "M": "Magenta", "Y": "Amarillo", "K": "Negro"}
        for i, canal in enumerate("CMYK", start=2):
            tk.Label(m, text=nombres[canal], font=self.F["normal"], bg=self.C["fondo"], anchor="w"
                     ).grid(row=i, column=0, sticky="w")
            self._campo(m, i, 1, config, ("toner", canal, "precio"), "", "pesos", minimo=0)
            self._campo(m, i, 2, config, ("toner", canal, "rendimiento"), "", "entero", minimo=0)
            self.campos[-2].etiqueta = f"Precio del tóner {nombres[canal].lower()}"
            self.campos[-1].etiqueta = f"Rendimiento del tóner {nombres[canal].lower()}"

        self._titulo(m, 7, "Papel")
        self._encabezados(m, 8, ["", "Precio de la resma", "Hojas por resma"])
        for i, (clave, papel) in enumerate(config["papel"].items(), start=9):
            tk.Label(m, text=papel["nombre"], font=self.F["normal"], bg=self.C["fondo"], anchor="w"
                     ).grid(row=i, column=0, sticky="w")
            self._campo(m, i, 1, config, ("papel", clave, "precio_resma"), "", "pesos", minimo=0, minimo_exclusivo=False)
            self._campo(m, i, 2, config, ("papel", clave, "hojas_resma"), "", "entero", minimo=0)
            self.campos[-2].etiqueta = f"Precio de la resma {papel['nombre'].lower()}"
            self.campos[-1].etiqueta = f"Hojas por resma {papel['nombre'].lower()}"

    def _pestana_mantenimiento(self, config):
        m = self._marco("Mantenimiento")
        tk.Label(m, text="Cada repuesto o visita se reparte entre las hojas de su ciclo.\n"
                         "Ej.: visita de $180.000 cada 30.000 hojas = $6 por hoja.",
                 font=self.F["pequena"], fg=self.C["texto_suave"], bg=self.C["fondo"], justify="left"
                 ).pack(anchor="w")
        self.tabla_mant = tk.Frame(m, bg=self.C["fondo"])
        self.tabla_mant.pack(fill="x", pady=6)
        tk.Button(m, text="+ Agregar repuesto o visita", font=self.F["boton"], relief="solid", bd=1,
                  bg=self.C["panel"], fg=self.C["primario"], cursor="hand2",
                  command=lambda: self._agregar_mant({"nombre": "Nuevo", "costo": 0, "cada_hojas": 10000,
                                                      "solo_color": False})).pack(anchor="w")
        for item in config["mantenimiento"]:
            self._agregar_mant(item, redibujar=False)
        self._dibujar_mant()

    def _agregar_mant(self, item, redibujar=True):
        fila = {"nombre": tk.StringVar(value=item["nombre"]),
                "costo": tk.StringVar(value=_mostrar(item["costo"], "pesos")),
                "cada": tk.StringVar(value=_mostrar(item["cada_hojas"], "entero")),
                "solo_color": tk.BooleanVar(value=item["solo_color"])}
        for v in fila.values():
            v.trace_add("write", lambda *_: self._programar())
        self.filas_mant.append(fila)
        if redibujar:
            self._dibujar_mant()
            self._programar()

    def _quitar_mant(self, fila):
        self.filas_mant.remove(fila)
        self._dibujar_mant()
        self._programar()

    def _dibujar_mant(self):
        for w in self.tabla_mant.winfo_children():
            w.destroy()
        self._encabezados(self.tabla_mant, 0, ["Nombre", "Costo", "Cada (hojas)", "Solo color", ""])
        for i, fila in enumerate(self.filas_mant, start=1):
            tk.Entry(self.tabla_mant, textvariable=fila["nombre"], font=self.F["normal"], width=24
                     ).grid(row=i, column=0, padx=4, pady=2, sticky="w")
            tk.Entry(self.tabla_mant, textvariable=fila["costo"], font=self.F["normal"], width=11, justify="right"
                     ).grid(row=i, column=1, padx=4)
            tk.Entry(self.tabla_mant, textvariable=fila["cada"], font=self.F["normal"], width=10, justify="right"
                     ).grid(row=i, column=2, padx=4)
            tk.Checkbutton(self.tabla_mant, variable=fila["solo_color"], bg=self.C["fondo"]
                           ).grid(row=i, column=3)
            tk.Button(self.tabla_mant, text="Quitar", font=self.F["pequena"], relief="flat", bg=self.C["fondo"],
                      fg=self.C["alerta_texto"], cursor="hand2", command=lambda f=fila: self._quitar_mant(f)
                      ).grid(row=i, column=4, padx=4)

    def _pestana_energia(self, config):
        m = self._marco("Energía y volumen")
        self._titulo(m, 0, "Energía de la impresora")
        self._campo(m, 1, 0, config, ("energia", "potencia_w"), "Potencia promedio encendida (W)", "entero",
                    "ficha Ricoh: máx. 1.584 W; típico mucho menor", minimo=0, minimo_exclusivo=False)
        self._campo(m, 2, 0, config, ("energia", "horas_dia"), "Horas encendida al día", "uno", minimo=0,
                    minimo_exclusivo=False, maximo=24)
        self._campo(m, 3, 0, config, ("energia", "dias_mes"), "Días de trabajo al mes", "entero", minimo=0,
                    minimo_exclusivo=False, maximo=31)
        self._campo(m, 4, 0, config, ("energia", "precio_kwh"), "Precio del kWh", "pesos",
                    "ver recibo de EPM", minimo=0, minimo_exclusivo=False)
        self.etiqueta_energia = tk.Label(m, font=self.F["normal"], bg=self.C["fondo"], fg=self.C["texto_suave"],
                                         justify="left")
        self.etiqueta_energia.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self._titulo(m, 6, "Volumen")
        self._campo(m, 7, 0, config, ("hojas_mes",), "Hojas impresas al mes", "entero",
                    "contador de la Ricoh", minimo=0)
        tk.Label(m, text="La energía del mes se reparte entre estas hojas: si se imprime más,\n"
                         "a cada hoja le toca menos.", font=self.F["pequena"], fg=self.C["texto_suave"],
                 bg=self.C["fondo"], justify="left").grid(row=8, column=0, columnspan=3, sticky="w")

    def _pestana_avanzado(self, config):
        m = self._marco("Avanzado")
        self._titulo(m, 0, "Cálculo")
        self._campo(m, 1, 0, config, ("factor_correccion",), "Factor de corrección de tinta", "decimal",
                    "1,15 = se asume 15 % más tinta", minimo=0)
        self._campo(m, 2, 0, config, ("capital_pct",), "% de lo que sobra para ahorro", "uno",
                    "el resto es ganancia", minimo=0, minimo_exclusivo=False, maximo=100)
        self._campo(m, 3, 0, config, ("margen_pct",), "Margen si no hay precio fijo (%)", "uno",
                    minimo=0, minimo_exclusivo=False, maximo=99)

        self._titulo(m, 4, "Detección de color")
        self._campo(m, 5, 0, config, ("analisis", "umbral_croma_decision"), "Intensidad mínima del color",
                    "decimal", "0 a 1; más alto = más estricto", minimo=0, maximo=1)
        self._campo(m, 6, 0, config, ("analisis", "area_min_color_pct"), "Área mínima con color (%)",
                    "decimal", "menos que esto = B/N", minimo=0, minimo_exclusivo=False)

        # Segunda columna: límites de los rangos (así la pestaña no queda tan alta)
        tk.Frame(m, width=24, bg=self.C["fondo"]).grid(row=0, column=3)
        self._titulo(m, 0, "Límite de cada rango (% de tinta)", col=4)
        fila = 1
        for grupo in ("rangos_bn", "rangos_color"):
            for i, r in enumerate(config[grupo]):
                self._campo(m, fila, 4, config, (grupo, i, "cobertura_max_pct"), r["nombre"], "uno", minimo=0)
                fila += 1

    # ------------------------------------------------------------------ lectura y resultado
    def _leer(self) -> dict:
        """Arma una configuración nueva con lo escrito. Lanza ValueError("<campo>: <problema>")."""
        nuevo = copy.deepcopy(self.config_original)
        for c in self.campos:
            _, con_decimales, _ = TIPOS[c.tipo]
            try:
                valor = leer_numero(c.var.get(), con_decimales)
            except ValueError:
                raise ValueError(f"«{c.etiqueta}» no es un número") from None
            if c.minimo is not None and (valor <= c.minimo if c.minimo_exclusivo else valor < c.minimo):
                raise ValueError(f"«{c.etiqueta}» debe ser mayor que {numero(c.minimo)}"
                                 if c.minimo_exclusivo else f"«{c.etiqueta}» no puede ser negativo")
            if c.maximo is not None and valor > c.maximo:
                raise ValueError(f"«{c.etiqueta}» no puede pasar de {numero(c.maximo)}")
            _poner(nuevo, c.ruta, valor if con_decimales else int(valor))

        nuevo["mantenimiento"] = []
        for fila in self.filas_mant:
            nombre = fila["nombre"].get().strip() or "Sin nombre"
            try:
                costo = int(leer_numero(fila["costo"].get()))
                cada = int(leer_numero(fila["cada"].get()))
            except ValueError:
                raise ValueError(f"Mantenimiento «{nombre}»: escriba solo números") from None
            if costo < 0 or cada <= 0:
                raise ValueError(f"Mantenimiento «{nombre}»: el costo no puede ser negativo y el ciclo debe ser mayor que 0")
            nuevo["mantenimiento"].append({"nombre": nombre, "costo": costo, "cada_hojas": cada,
                                           "solo_color": fila["solo_color"].get()})

        for grupo in ("rangos_bn", "rangos_color"):
            limites = [r["cobertura_max_pct"] for r in nuevo[grupo]]
            if limites != sorted(limites) or len(set(limites)) != len(limites):
                raise ValueError("Los límites de los rangos deben ir de menor a mayor")
        return nuevo

    def _programar(self):
        """Espera 300 ms sin cambios antes de recalcular (no en cada tecla)."""
        if self._pendiente:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after(300, self._recalcular)

    def _recalcular(self):
        self._pendiente = None
        for w in self.resultado.winfo_children():
            w.destroy()
        C, F = self.C, self.F
        tk.Label(self.resultado, text="Resultado (hoja carta)", font=F["negrita"], bg=C["panel"],
                 fg=C["primario"]).grid(row=0, column=0, columnspan=4, sticky="w")
        try:
            nuevo = self._leer()
        except ValueError as e:
            tk.Label(self.resultado, text=f"Revise:\n{e}", font=F["normal"], bg=C["alerta_fondo"],
                     fg=C["alerta_texto"], wraplength=300, justify="left", padx=8, pady=6
                     ).grid(row=1, column=0, columnspan=4, sticky="ew", pady=6)
            return

        kwh, pesos_mes = energia_mes(nuevo)
        if hasattr(self, "etiqueta_energia"):
            self.etiqueta_energia.config(text=f"≈ {numero(kwh)} kWh al mes = {pesos(pesos_mes)} al mes")

        fijos = [("Papel", costo_papel(nuevo, "carta"), costo_papel(nuevo, "carta")),
                 ("Mantenimiento", costo_mantenimiento(nuevo, False), costo_mantenimiento(nuevo, True)),
                 ("Energía", costo_energia(nuevo), costo_energia(nuevo))]
        tk.Label(self.resultado, text="Costo por hoja, sin tinta:", font=F["pequena"], bg=C["panel"],
                 fg=C["texto_suave"]).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self._fila(2, ["", "B/N", "Color"], F["pequena"], C["texto_suave"])
        for i, (nombre, bn, color) in enumerate(fijos, start=3):
            self._fila(i, [nombre, pesos(bn), pesos(color)])
        self._fila(6, ["Total sin tinta", pesos(sum(f[1] for f in fijos)), pesos(sum(f[2] for f in fijos))],
                   F["negrita"])

        tk.Label(self.resultado, text="Por rango (la hoja más cargada del rango):", font=F["pequena"],
                 bg=C["panel"], fg=C["texto_suave"]).grid(row=7, column=0, columnspan=4, sticky="w", pady=(12, 0))
        self._fila(8, ["Rango", "Cuesta", "Se cobra", "Queda"], F["pequena"], C["texto_suave"])
        fila = 9
        for es_color in (False, True):
            for r in tabla_rangos(nuevo, "carta", es_color):
                queda = r["precio"] - r["costo_limite"]
                color = C["alerta_texto"] if queda < 0 else C["texto"]
                self._fila(fila, [r["nombre"], pesos(r["costo_limite"]), pesos(r["precio"]), pesos(queda)],
                           F["normal"], color, fondo=tema.color_rango(r["nombre"]))
                fila += 1
        perdidas = [r["nombre"] for c in (False, True) for r in tabla_rangos(nuevo, "carta", c) if r["bajo_costo"]]
        if perdidas:
            tk.Label(self.resultado, text="⚠ Con estos costos se pierde dinero en: " + ", ".join(perdidas)
                     + ".\nSuba esos precios en la ventana «Precios».", font=F["pequena"], bg=C["alerta_fondo"],
                     fg=C["alerta_texto"], wraplength=320, justify="left", padx=6, pady=4
                     ).grid(row=fila, column=0, columnspan=4, sticky="ew", pady=(8, 0))

    def _fila(self, fila, textos, fuente=None, color=None, fondo=None):
        for j, t in enumerate(textos):
            tk.Label(self.resultado, text=t, font=fuente or self.F["normal"], fg=color or self.C["texto"],
                     bg=fondo if (fondo and j == 0) else self.C["panel"], anchor="w" if j == 0 else "e", padx=4
                     ).grid(row=fila, column=j, sticky="ew", pady=1)

    # ------------------------------------------------------------------ botones
    def restaurar(self):
        """Vuelve a los valores de fábrica en esta ventana (los precios de venta no se tocan)."""
        defecto = cfg.CONFIG_POR_DEFECTO
        for c in self.campos:
            try:
                c.var.set(_mostrar(_obtener(defecto, c.ruta), c.tipo))
            except (KeyError, IndexError):
                pass  # un rango que no existe en los valores de fábrica
        self.filas_mant = []
        for item in defecto["mantenimiento"]:
            self._agregar_mant(item, redibujar=False)
        self._dibujar_mant()
        self._programar()

    def guardar(self):
        try:
            nuevo = self._leer()
        except ValueError as e:
            messagebox.showerror("Revise los datos", str(e), parent=self)
            return
        perdidas = [r["nombre"] for c in (False, True) for t in nuevo["papel"]
                    for r in tabla_rangos(nuevo, t, c) if r["bajo_costo"]]
        if perdidas and not messagebox.askyesno(
                "Precio por debajo del costo",
                "Con estos costos se pierde dinero en:\n\n" + "\n".join(dict.fromkeys(perdidas))
                + "\n\n¿Guardar de todos modos? (Luego suba esos precios en «Precios».)",
                icon="warning", parent=self):
            return
        try:
            cfg.guardar(nuevo)
        except OSError as e:
            messagebox.showerror("No se pudo guardar", f"No se pudo escribir config.json:\n{e}", parent=self)
            return
        self.al_guardar(nuevo)
        self.destroy()
