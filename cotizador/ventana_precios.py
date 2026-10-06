"""Ventana para cambiar los precios de venta de cada rango.

Pensada para los dueños: un renglón por rango, el costo máximo como referencia y
una casilla para cobrar oficio igual que carta. Al guardar se escribe config.json
(junto al programa) y la ventana principal se actualiza sola.
Los ajustes técnicos (tóner, papel, umbrales) van en la pantalla de ajustes (etapa 4).
"""

import copy
import tkinter as tk
from tkinter import messagebox

from . import config as cfg
from . import tema
from .costos import tabla_rangos
from .formato import leer_pesos, pesos


class VentanaPrecios(tk.Toplevel):
    def __init__(self, padre, config: dict, fuentes: dict, al_guardar):
        super().__init__(padre)
        self.title("Precios de venta")
        self.config_original = config
        self.al_guardar = al_guardar
        self.F, C = fuentes, tema.COLORES
        self.configure(bg=C["fondo"], padx=18, pady=14)
        self.transient(padre)   # se queda encima de la ventana principal
        self.grab_set()         # y la bloquea mientras está abierta (ventana "modal")

        tk.Label(self, text="Precios de venta por hoja", font=fuentes["titulo"], fg=C["primario"],
                 bg=C["fondo"]).grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(self, text="Escriba el precio y presione Guardar. «Nos cuesta hasta» es lo máximo que puede\n"
                            "costar una hoja de ese rango (tinta, papel, mantenimiento y energía); el precio debe ser mayor.",
                 font=fuentes["pequena"], fg=C["texto_suave"], bg=C["fondo"], justify="left"
                 ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))

        self.igual_oficio = tk.BooleanVar(value=self._oficio_es_igual(config))
        self.entradas = []  # [(grupo, índice, var_carta, var_oficio, entry_oficio, costo_carta, costo_oficio)]

        fila = 2
        for titulo, grupo, es_color in (("Blanco y negro", "rangos_bn", False), ("Color", "rangos_color", True)):
            tk.Label(self, text=titulo, font=fuentes["negrita"], fg=C["primario"], bg=C["fondo"]
                     ).grid(row=fila, column=0, sticky="w", pady=(8, 2))
            for j, t in enumerate(("Nos cuesta hasta", "Carta", "Oficio"), start=1):
                tk.Label(self, text=t, font=fuentes["pequena"], fg=C["texto_suave"], bg=C["fondo"]
                         ).grid(row=fila, column=j)
            fila += 1
            costos_carta = tabla_rangos(config, "carta", es_color)
            costos_oficio = tabla_rangos(config, "oficio", es_color)
            for i, rango in enumerate(config[grupo]):
                tk.Label(self, text=rango["nombre"], font=fuentes["normal"], bg=tema.color_rango(rango["nombre"]),
                         anchor="w", width=14, padx=6, relief="solid", bd=1).grid(row=fila, column=0, sticky="ew", pady=2)
                tk.Label(self, text=pesos(costos_carta[i]["costo_limite"]), font=fuentes["normal"],
                         fg=C["texto_suave"], bg=C["fondo"], width=10).grid(row=fila, column=1)
                v_carta = tk.StringVar(value=pesos(costos_carta[i]["precio"]))
                v_oficio = tk.StringVar(value=pesos(costos_oficio[i]["precio"]))
                tk.Entry(self, textvariable=v_carta, font=fuentes["negrita"], width=9, justify="right"
                         ).grid(row=fila, column=2, padx=4)
                e_oficio = tk.Entry(self, textvariable=v_oficio, font=fuentes["normal"], width=9, justify="right")
                e_oficio.grid(row=fila, column=3, padx=4)
                v_carta.trace_add("write", lambda *_: self._sincronizar_oficio())
                self.entradas.append((grupo, i, v_carta, v_oficio, e_oficio,
                                      costos_carta[i]["costo_limite"], costos_oficio[i]["costo_limite"]))
                fila += 1

        tk.Checkbutton(self, text="Cobrar oficio igual que carta", variable=self.igual_oficio,
                       font=fuentes["normal"], bg=C["fondo"], command=self._sincronizar_oficio
                       ).grid(row=fila, column=0, columnspan=4, sticky="w", pady=(10, 0))
        fila += 1

        botones = tk.Frame(self, bg=C["fondo"])
        botones.grid(row=fila, column=0, columnspan=4, sticky="ew", pady=(14, 0))
        estilo = dict(font=fuentes["boton"], relief="solid", bd=1, padx=12, pady=4, cursor="hand2")
        tk.Button(botones, text="Guardar", command=self.guardar, bg=C["primario"], fg=C["primario_texto"],
                  **estilo).pack(side="right")
        tk.Button(botones, text="Cancelar", command=self.destroy, bg=C["panel"], **estilo).pack(side="right", padx=8)
        tk.Button(botones, text="Volver a los precios originales", command=self.restaurar,
                  bg=C["panel"], **estilo).pack(side="left")
        self._sincronizar_oficio()

    # ------------------------------------------------------------------
    @staticmethod
    def _oficio_es_igual(config):
        return all((r.get("precio_manual") or {}).get("carta") == (r.get("precio_manual") or {}).get("oficio")
                   for r in config["rangos_bn"] + config["rangos_color"])

    def _sincronizar_oficio(self):
        """Si la casilla está marcada, oficio copia a carta y no se puede editar."""
        for _, _, v_carta, v_oficio, e_oficio, *_ in self.entradas:
            if self.igual_oficio.get():
                v_oficio.set(v_carta.get())
                e_oficio.config(state="disabled")
            else:
                e_oficio.config(state="normal")

    def restaurar(self):
        for grupo, i, v_carta, v_oficio, *_ in self.entradas:
            original = cfg.CONFIG_POR_DEFECTO[grupo][i]["precio_manual"] if i < len(cfg.CONFIG_POR_DEFECTO[grupo]) else {}
            if original.get("carta"):
                v_carta.set(pesos(original["carta"]))
            if original.get("oficio"):
                v_oficio.set(pesos(original["oficio"]))
        self.igual_oficio.set(True)
        self._sincronizar_oficio()

    def guardar(self):
        nuevo = copy.deepcopy(self.config_original)
        bajo_costo = []
        for grupo, i, v_carta, v_oficio, _, costo_carta, costo_oficio in self.entradas:
            rango = nuevo[grupo][i]
            try:
                carta, oficio = leer_pesos(v_carta.get()), leer_pesos(v_oficio.get())
            except ValueError:
                messagebox.showerror("Precio no válido", f"Revise el precio de «{rango['nombre']}».\n"
                                     "Escriba solo números, por ejemplo 1500.", parent=self)
                return
            if carta <= 0 or oficio <= 0:
                messagebox.showerror("Precio no válido", f"El precio de «{rango['nombre']}» debe ser mayor que cero.",
                                     parent=self)
                return
            if carta < costo_carta or oficio < costo_oficio:
                bajo_costo.append(rango["nombre"])
            rango["precio_manual"] = {"carta": carta, "oficio": oficio}

        if bajo_costo and not messagebox.askyesno(
                "Precio por debajo del costo",
                "Con estos precios se pierde dinero en:\n\n" + "\n".join(bajo_costo) + "\n\n¿Guardar de todos modos?",
                icon="warning", parent=self):
            return
        try:
            cfg.guardar(nuevo)
        except OSError as e:
            messagebox.showerror("No se pudo guardar", f"No se pudo escribir config.json:\n{e}", parent=self)
            return
        self.al_guardar(nuevo)
        self.destroy()
