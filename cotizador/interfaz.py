"""Ventana principal del cotizador (tkinter).

Organización:
  * App               -> ventana principal: soltar archivo, tamaño, copias, resumen y total.
  * VentanaDetalle    -> lista hoja por hoja con vista previa de la página.
  * Los precios se editan en ventana_precios.py; la apariencia en tema.py.

Idea importante — el análisis corre en un HILO aparte:
  Analizar un PDF largo toma unos segundos. Si se hiciera en el hilo de la ventana,
  ésta se "congelaría" (Windows mostraría "No responde"). Por eso un hilo de trabajo
  analiza y deja mensajes en una cola (queue.Queue); la ventana revisa la cola cada
  100 ms con root.after(). Regla de tkinter: SOLO el hilo principal toca la ventana.

Otra idea — se guarda el análisis, no el precio:
  self.trabajo guarda la cobertura de cada hoja. Cambiar tamaño, copias o precios solo
  vuelve a cotizar (instantáneo), sin volver a analizar el archivo.
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from . import config as cfg
from . import pixelart, tema
from .cobertura import EXTENSIONES_IMAGEN, EXTENSIONES_PDF, analizar_archivo, imagen_pagina
from .costos import BN, COLOR, cotizar, tabla_rangos
from .formato import hojas, pesos

try:  # arrastrar y soltar; si la librería faltara, el programa funciona solo con clic
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None

EXTENSIONES_SOPORTADAS = EXTENSIONES_PDF | EXTENSIONES_IMAGEN
EXTENSIONES_OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".rtf"}


class App:
    def __init__(self, root: tk.Tk, config: dict):
        self.root = root
        self.config = config
        self.trabajo = []        # [(ruta, índice de página, CoberturaPagina), ...]
        self.modos = {}          # {posición en trabajo: BN o COLOR} hojas cambiadas a mano en el detalle
        self.cotizacion = None
        self.detalle = None      # ventana de detalle abierta (para refrescarla)
        self.ocupado = False
        self.cola = queue.Queue()
        self.tamano = tk.StringVar(value="carta")
        self.copias = tk.IntVar(value=1)
        self.todo_bn = tk.BooleanVar(value=False)

        preparar_estilo(config)
        self.C = tema.COLORES
        self.escala = root.winfo_fpixels("1i") / 96  # 1,25 si Windows está al 125 %
        self.F = tema.fuentes(config["apariencia"]["tamano_letra"], self.escala)
        root.title("Net Papelería · Cotizador de impresiones")
        root.configure(bg=self.C["marco"])
        root.minsize(620, 640)
        self._icono = ImageTk.PhotoImage(pixelart.icono(32))
        root.iconphoto(True, self._icono)  # True: también para las ventanas que se abran después

        self._construir()
        self._activar_soltar()
        self.actualizar_config(config)
        self.root.after(100, self._revisar_cola)

    # ------------------------------------------------------------------ construcción
    def _boton(self, padre, texto, comando, principal=False, **kw):
        return tk.Button(padre, text=texto, command=comando, **(tema.estilo_boton(self.F, principal) | kw))

    def _construir(self):
        C, F = self.C, self.F
        # Marco grueso de color alrededor de todo (en estilo pixel; en clásico no se ve)
        grosor = tema.ESTILO["grosor_marco"]
        borde = tk.Frame(self.root, bg=C["fondo"], highlightthickness=grosor,
                         highlightbackground=C["marco"], highlightcolor=C["marco"])
        borde.pack(fill="both", expand=True)

        # --- Encabezado: barra fucsia con el logo en pixel art, o título simple en clásico
        if tema.PIXEL:
            enc = tk.Frame(borde, bg=C["marco"], padx=12, pady=8)
            enc.pack(fill="x")
            self._logo = ImageTk.PhotoImage(pixelart.encabezado(max(2, round(2 * self.escala))))
            tk.Label(enc, image=self._logo, bg=C["marco"]).pack(side="left")
        marco = tk.Frame(borde, bg=C["fondo"], padx=18, pady=14)
        marco.pack(fill="both", expand=True)
        if not tema.PIXEL:
            enc = tk.Frame(marco, bg=C["fondo"])
            enc.pack(fill="x")
            tk.Label(enc, text="Cotizador de impresiones", font=F["titulo"], fg=C["primario"],
                     bg=C["fondo"]).pack(side="left")
        botones = tk.Frame(enc, bg=enc["bg"])
        botones.pack(side="right", anchor="n" if tema.PIXEL else "center")
        self._boton(botones, "Costos", self.abrir_costos).pack(side="right")
        enc = botones
        self._boton(enc, "Precios", self.abrir_precios).pack(side="right", padx=(0, 8))
        self._boton(enc, "Nueva cotización", self.limpiar).pack(side="right", padx=8)

        # --- Aviso (solo aparece si algún precio quedó por debajo del costo)
        self.alerta = tk.Label(marco, font=F["negrita"], bg=C["alerta_fondo"], fg=C["alerta_texto"],
                               wraplength=560, justify="left", padx=10, pady=6)

        # --- Zona para soltar el archivo
        self.zona = tk.Label(marco, font=F["soltar"], bg=C["zona_soltar"], fg=C["primario"],
                             relief="ridge", bd=3 if tema.PIXEL else 2, height=4, cursor="hand2", justify="center")
        self.zona.pack(fill="x", pady=(12, 6))
        self.zona.bind("<Button-1>", lambda e: self.buscar_archivos())
        self.zona.bind("<Enter>", lambda e: self.zona.config(bg=C["zona_activa"]))
        self.zona.bind("<Leave>", lambda e: self.zona.config(bg=C["zona_soltar"]))

        # --- Estado: nombre del archivo o progreso
        fila = tk.Frame(marco, bg=C["fondo"])
        fila.pack(fill="x")
        self.estado = tk.Label(fila, font=F["normal"], fg=C["texto_suave"], bg=C["fondo"], anchor="w")
        self.estado.pack(side="left", fill="x", expand=True)
        self.boton_agregar = self._boton(fila, "+ Agregar otro archivo", lambda: self.buscar_archivos(agregar=True))
        self.progreso = ttk.Progressbar(marco, mode="determinate")

        # --- Opciones: tamaño y copias
        opc = tk.Frame(marco, bg=C["fondo"])
        opc.pack(fill="x", pady=12)
        tk.Label(opc, text="Tamaño:", font=F["seccion"], bg=C["fondo"], fg=C["primario"]).pack(side="left", padx=(0, 6))
        for clave, papel in self.config["papel"].items():
            # indicatoron=0 convierte el botón de opción en un botón grande que se queda hundido
            tk.Radiobutton(opc, text=papel["nombre"], value=clave, variable=self.tamano, indicatoron=0,
                           font=F["boton"], width=8, pady=4, bg=C["panel"], selectcolor=C["zona_activa"],
                           cursor="hand2", command=self.recotizar, **self._estilo_opcion()).pack(side="left", padx=4)

        self._boton(opc, "+", lambda: self.cambiar_copias(+1), width=2).pack(side="right")
        tk.Label(opc, textvariable=self.copias, font=F["copias"], width=3 if tema.PIXEL else 4, bg=C["panel"],
                 fg=C["texto"], relief="sunken" if tema.PIXEL else "solid", bd=3 if tema.PIXEL else 1,
                 padx=4).pack(side="right", padx=4)
        self._boton(opc, "−", lambda: self.cambiar_copias(-1), width=2).pack(side="right")
        tk.Label(opc, text="Copias:", font=F["seccion"], bg=C["fondo"], fg=C["primario"]).pack(side="right", padx=6)

        # --- Impresión: lo que sugiere el programa, o todo en B/N si el cliente lo pide
        imp = tk.Frame(marco, bg=C["fondo"])
        imp.pack(fill="x", pady=(0, 12))
        tk.Label(imp, text="Imprimir:", font=F["seccion"], bg=C["fondo"], fg=C["primario"]).pack(side="left", padx=(0, 6))
        for texto, valor in (("Como sugiere el programa", False), ("Todo en blanco y negro", True)):
            tk.Radiobutton(imp, text=texto, value=valor, variable=self.todo_bn, indicatoron=0,
                           font=F["boton"], pady=4, padx=10, bg=C["panel"], selectcolor=C["zona_activa"],
                           cursor="hand2", command=self.recotizar, **self._estilo_opcion()).pack(side="left", padx=4)

        # --- Resumen
        panel = tk.Frame(marco, bg=C["panel"], padx=14, pady=10,
                         **({"highlightthickness": 3, "highlightbackground": C["borde"]} if tema.PIXEL
                            else {"relief": "solid", "bd": 1}))
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="Resumen", font=F["seccion"], bg=C["panel"], fg=C["primario"]).pack(anchor="w")
        self.resumen = tk.Frame(panel, bg=C["panel"])
        self.resumen.pack(fill="both", expand=True, pady=6)

        pie = tk.Frame(panel, bg=C["panel"])
        pie.pack(fill="x")
        self.etiqueta_total = tk.Label(pie, text="Total", font=F["negrita"], bg=C["panel"], fg=C["texto"])
        self.etiqueta_total.pack(side="left", anchor="s")
        self.total = tk.Label(pie, text="$0", font=F["total"], bg=C["panel"], fg=C["total"])
        self.total.pack(side="right")
        self.boton_detalle = self._boton(panel, "Ver detalle hoja por hoja", self.abrir_detalle, principal=True)
        self.boton_detalle.pack(anchor="e", pady=(6, 0))

    def _estilo_opcion(self):
        """Botones de opción (Carta/Oficio, Imprimir): con relieve de videojuego en estilo pixel."""
        if tema.PIXEL:
            return {"relief": "raised", "bd": 3, "offrelief": "raised", "fg": self.C["boton_texto"]}
        return {}

    def _activar_soltar(self):
        texto = "Arrastre aquí el archivo\no haga clic para buscarlo"
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._al_soltar)
        except (NameError, AttributeError, tk.TclError):
            # Sin la librería de arrastrar (o sin sus binarios): el programa sigue sirviendo con clic.
            texto = "Haga clic aquí para buscar el archivo"
        self.zona.config(text=texto)

    # ------------------------------------------------------------------ archivos
    def _al_soltar(self, evento):
        # tk.splitlist separa la lista de rutas, incluso si tienen espacios: {C:/mi archivo.pdf}
        rutas = [Path(p) for p in self.root.tk.splitlist(evento.data)]
        self.cargar(rutas)

    def buscar_archivos(self, agregar=False):
        if self.ocupado:
            return
        tipos = [("Documentos e imágenes", " ".join(f"*{e}" for e in sorted(EXTENSIONES_SOPORTADAS))),
                 ("Todos los archivos", "*.*")]
        rutas = filedialog.askopenfilenames(title="Elegir archivo para cotizar", filetypes=tipos)
        if rutas:
            self.cargar([Path(r) for r in rutas], agregar=agregar)

    def cargar(self, rutas, agregar=False):
        """Valida los archivos y lanza el análisis en un hilo aparte."""
        if self.ocupado:
            return
        validas, office, otras = [], [], []
        for r in rutas:
            ext = r.suffix.lower()
            (validas if ext in EXTENSIONES_SOPORTADAS else office if ext in EXTENSIONES_OFFICE else otras).append(r)
        if office:
            messagebox.showinfo("Archivo de Office",
                                "Por ahora el programa lee PDF e imágenes.\n\n"
                                "Abra el documento en Word, Excel o PowerPoint y use\n"
                                "Archivo → Guardar como → PDF. Luego arrastre el PDF aquí.\n\n"
                                + "\n".join(r.name for r in office))
        if otras:
            messagebox.showwarning("Formato no reconocido",
                                   "Estos archivos no se pueden cotizar:\n\n" + "\n".join(r.name for r in otras))
        if not validas:
            return
        if not agregar:
            self.trabajo, self.modos = [], {}
            self.todo_bn.set(False)
        self.ocupado = True
        self.progreso.pack(fill="x", pady=(4, 0), after=self.estado.master)
        threading.Thread(target=self._analizar, args=(validas, dict(self.config["analisis"])), daemon=True).start()

    def _analizar(self, rutas, analisis):
        """Corre en el hilo de trabajo: NO toca la ventana, solo deja mensajes en la cola."""
        for n, ruta in enumerate(rutas, start=1):
            prefijo = f"{ruta.name}" + (f" ({n} de {len(rutas)})" if len(rutas) > 1 else "")
            try:
                coberturas = analizar_archivo(
                    ruta, analisis, progreso=lambda i, t, p=prefijo: self.cola.put(("progreso", p, i, t)))
                self.cola.put(("listo", ruta, coberturas))
            except Exception as e:  # archivo dañado, protegido con clave, etc.
                self.cola.put(("error", ruta, str(e)))
        self.cola.put(("fin",))

    def _revisar_cola(self):
        """Corre en el hilo principal cada 100 ms: aplica los mensajes del hilo de trabajo."""
        try:
            while True:
                msg = self.cola.get_nowait()
                if msg[0] == "progreso":
                    _, nombre, i, total = msg
                    self.estado.config(text=f"Analizando {nombre}: hoja {i} de {total}…")
                    self.progreso.config(maximum=total, value=i)
                elif msg[0] == "listo":
                    _, ruta, coberturas = msg
                    self.trabajo += [(ruta, i, c) for i, c in enumerate(coberturas)]
                elif msg[0] == "error":
                    messagebox.showerror("No se pudo leer el archivo",
                                         f"{msg[1].name}\n\nPuede estar dañado o protegido con contraseña.\n\n({msg[2]})")
                elif msg[0] == "fin":
                    self.ocupado = False
                    self.progreso.pack_forget()
                    self.recotizar()
        except queue.Empty:
            pass
        self.root.after(100, self._revisar_cola)

    # ------------------------------------------------------------------ cotización
    def cambiar_copias(self, delta):
        self.copias.set(min(999, max(1, self.copias.get() + delta)))
        self.recotizar()

    def limpiar(self):
        if self.ocupado:
            return
        self.trabajo, self.modos = [], {}
        self.copias.set(1)
        self.todo_bn.set(False)
        if self.detalle is not None:
            self.detalle.destroy()
        self.recotizar()

    def recotizar(self):
        for w in self.resumen.winfo_children():
            w.destroy()
        C, F = self.C, self.F

        if not self.trabajo:
            self.cotizacion = None
            self.estado.config(text="")
            self.boton_agregar.pack_forget()
            tk.Label(self.resumen, text="Aquí aparecerá el precio.", font=F["normal"],
                     fg=C["texto_suave"], bg=C["panel"]).pack(anchor="w")
            self.etiqueta_total.config(text="Total")
            self.total.config(text="$0")
            self.boton_detalle.config(state="disabled")
            return

        coberturas = [c for _, _, c in self.trabajo]
        self.cotizacion = cot = cotizar(self.config, coberturas, self.tamano.get(), self.copias.get(),
                                        modos=self.modos, todo_bn=self.todo_bn.get())

        archivos = list(dict.fromkeys(r for r, _, _ in self.trabajo))  # sin repetir, en orden
        nombre = archivos[0].name if len(archivos) == 1 else f"{len(archivos)} archivos"
        self.estado.config(text=f"{nombre} — {hojas(len(coberturas))}")
        self.boton_agregar.pack(side="right")

        # Filas del resumen, en el orden de los rangos (primero b/n, luego color)
        orden = [r["nombre"] for r in self.config["rangos_bn"] + self.config["rangos_color"]]
        filas = sorted(cot.resumen(), key=lambda f: orden.index(f["rango"].replace(" (+)", ""))
                       if f["rango"].replace(" (+)", "") in orden else 99)
        for i, f in enumerate(filas):
            tk.Label(self.resumen, text="  ", bg=tema.color_rango(f["rango"]), relief="solid", bd=1
                     ).grid(row=i, column=0, padx=(0, 8), pady=3, sticky="ns")
            celdas = [(hojas(f["paginas"]), "e"), (f["rango"], "w"),
                      (f"× {pesos(f['precio_unitario'])}", "e"),
                      (f"× {cot.copias}" if cot.copias > 1 else "", "e"),
                      (f"= {pesos(f['subtotal'])}", "e")]
            for j, (texto, lado) in enumerate(celdas, start=1):
                tk.Label(self.resumen, text=texto, font=F["negrita"] if j == 2 else F["normal"],
                         bg=C["panel"], fg=C["texto"], anchor=lado).grid(row=i, column=j, sticky="ew", padx=6)
        self.resumen.grid_columnconfigure(2, weight=1)
        cambiadas = sum(1 for p in cot.paginas if p.forzado and p.es_color != p.sugerido_color)
        if cambiadas and not self.todo_bn.get():
            tk.Label(self.resumen, text=f"✋ {hojas(cambiadas)} {'cambiada' if cambiadas == 1 else 'cambiadas'} a mano en el detalle",
                     font=F["pequena"], bg=C["panel"], fg=C["texto_suave"]
                     ).grid(row=len(filas), column=0, columnspan=6, sticky="w", pady=(6, 0))

        copias = "1 copia" if cot.copias == 1 else f"{cot.copias} copias"
        self.etiqueta_total.config(text=f"Total ({copias})")
        self.total.config(text=pesos(cot.total))
        self.boton_detalle.config(state="normal")
        if self.detalle is not None:
            self.detalle.refrescar(cot)

    # ------------------------------------------------------------------ ventanas
    def actualizar_config(self, config):
        """Se llama al iniciar y cuando se guardan precios o costos nuevos."""
        if config["apariencia"] != self.config["apariencia"]:
            messagebox.showinfo("Estilo", "El nuevo estilo o tamaño de letra se verá\n"
                                          "la próxima vez que abra el programa.")
        self.config = config
        malos = sorted({r["nombre"] for t in config["papel"] for color in (False, True)
                        for r in tabla_rangos(config, t, color) if r["bajo_costo"]})
        if malos:
            self.alerta.config(text="⚠ Estos precios no alcanzan a cubrir el costo: "
                                    + ", ".join(malos) + ". Revise en «Precios».")
            self.alerta.pack(fill="x", pady=(0, 8), before=self.zona)
        else:
            self.alerta.pack_forget()
        self.recotizar()

    def abrir_precios(self):
        from .ventana_precios import VentanaPrecios
        VentanaPrecios(self.root, self.config, self.F, al_guardar=self.actualizar_config)

    def abrir_costos(self):
        from .ventana_costos import VentanaCostos
        VentanaCostos(self.root, self.config, self.F, al_guardar=self.actualizar_config)

    def abrir_detalle(self):
        if not self.cotizacion:
            return
        if self.detalle is not None:  # ya abierta: traerla al frente
            self.detalle.lift()
            return
        self.detalle = VentanaDetalle(self.root, self, self.F)

    def cambiar_modo(self, posiciones, modo):
        """Desde el detalle: modo = BN, COLOR o None (volver a la sugerencia)."""
        for i in posiciones:
            if modo is None:
                self.modos.pop(i, None)
            else:
                self.modos[i] = modo
        self.recotizar()


class VentanaDetalle(tk.Toplevel):
    """Lista de hojas con rango y precio. Permite decidir B/N o color hoja por hoja
    (se pueden elegir varias con Shift o Ctrl) y muestra la página elegida."""

    ANCHO_VISTA = 340

    def __init__(self, padre, app, fuentes):
        super().__init__(padre)
        self.title("Detalle hoja por hoja")
        C = tema.COLORES
        self.configure(bg=C["fondo"], padx=12, pady=12)
        self.app = app
        self._foto = None  # hay que guardar la referencia o Python borra la imagen

        estilo = ttk.Style(self)
        estilo.configure("Detalle.Treeview", font=fuentes["normal"], rowheight=int(fuentes["normal"][1] * 2.3))
        estilo.configure("Detalle.Treeview.Heading", font=fuentes["negrita"])
        estilo.map("Detalle.Treeview", background=[("selected", C["primario"])],
                   foreground=[("selected", C["primario_texto"])])

        trabajo = app.trabajo
        self.varios = len({r for r, _, _ in trabajo}) > 1
        columnas = (["archivo"] if self.varios else []) + ["hoja", "imprimir", "rango", "precio", "tinta"]
        titulos = {"archivo": "Archivo", "hoja": "Hoja", "imprimir": "Imprimir en", "rango": "Rango",
                   "precio": "Precio", "tinta": "Tinta"}
        anchos = {"archivo": 260, "hoja": 60, "imprimir": 170, "rango": 160, "precio": 90, "tinta": 70}

        izq = tk.Frame(self, bg=C["fondo"])
        izq.pack(side="left", fill="both", expand=True)

        # --- Botones para cambiar B/N / color de las hojas seleccionadas
        botones = tk.Frame(izq, bg=C["fondo"])
        botones.pack(side="top", fill="x", pady=(0, 8))
        tk.Label(botones, text="Hojas seleccionadas:", font=fuentes["negrita"], bg=C["fondo"]).pack(side="left")
        estilo_b = tema.estilo_boton(fuentes) | {"padx": 10, "pady": 3}
        tk.Button(botones, text="Blanco y negro", command=lambda: self._cambiar(BN), **estilo_b
                  ).pack(side="left", padx=4)
        tk.Button(botones, text="Color", command=lambda: self._cambiar(COLOR), **estilo_b
                  ).pack(side="left", padx=4)
        tk.Button(botones, text="Lo que sugiere el programa", command=lambda: self._cambiar(None),
                  **estilo_b).pack(side="left", padx=4)
        self.aviso = tk.Label(izq, font=fuentes["pequena"], bg=C["fondo"], fg=C["alerta_texto"], anchor="w",
                              text="Está marcado «Todo en blanco y negro» en la ventana principal.")
        self._despues_de_botones = botones

        tk.Label(izq, text="Seleccione varias hojas con Shift o Ctrl. Doble clic cambia entre B/N y color.\n"
                           "«Tinta» = cuánto de la hoja cubre el tóner.   ✋ = decidido a mano.",
                 font=fuentes["pequena"], bg=C["fondo"], fg=C["texto_suave"], justify="left"
                 ).pack(side="bottom", anchor="w", pady=(6, 0))
        self.total = tk.Label(izq, font=fuentes["negrita"], bg=C["fondo"], fg=C["total"], anchor="e")
        self.total.pack(side="bottom", fill="x", pady=(6, 0))

        marco_lista = tk.Frame(izq, bg=C["fondo"])  # lista + barra lado a lado
        marco_lista.pack(side="top", fill="both", expand=True)
        self.lista = ttk.Treeview(marco_lista, columns=columnas, show="headings", style="Detalle.Treeview",
                                  height=16, selectmode="extended")
        for c in columnas:
            self.lista.heading(c, text=titulos[c])
            self.lista.column(c, width=anchos[c], anchor="w" if c in ("archivo", "rango", "imprimir") else "center")
        barra = ttk.Scrollbar(marco_lista, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra.set)
        self.lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        for _ in trabajo:
            self.lista.insert("", "end")

        self.vista = tk.Label(self, bg=C["panel"], relief="solid", bd=1, text="Elija una hoja\npara verla",
                              font=fuentes["normal"], width=self.ANCHO_VISTA // 9, fg=C["texto_suave"])
        self.vista.pack(side="left", fill="y", padx=(12, 0))

        self.lista.bind("<<TreeviewSelect>>", self._mostrar)
        self.lista.bind("<Double-1>", self._alternar)
        filas = self.lista.get_children()
        if filas:
            self.lista.selection_set(filas[0])
        self.refrescar(app.cotizacion)

    def destroy(self):
        self.app.detalle = None
        super().destroy()

    def refrescar(self, cotizacion):
        """Actualiza los renglones (la ventana principal la llama cada vez que recotiza)."""
        for item, (ruta, indice, _), p in zip(self.lista.get_children(), self.app.trabajo, cotizacion.paginas):
            modo = "Color" if p.es_color else "Blanco y negro"
            if p.forzado and p.es_color != p.sugerido_color:
                modo = "✋ " + modo
            self.lista.tag_configure(p.rango, background=tema.color_rango(p.rango))
            valores = ([ruta.name] if self.varios else []) + [
                indice + 1, modo, p.rango, pesos(p.precio), f"{p.cobertura.total:.0f} %"]
            self.lista.item(item, values=valores, tags=(p.rango,))
        copias = "" if cotizacion.copias == 1 else f" × {cotizacion.copias} copias"
        self.total.config(text=f"Total: {pesos(cotizacion.total_por_copia)}{copias} = {pesos(cotizacion.total)}"
                          if copias else f"Total: {pesos(cotizacion.total)}")
        if self.app.todo_bn.get():
            self.aviso.pack(side="top", anchor="w", after=self._despues_de_botones)
        else:
            self.aviso.pack_forget()
        self._mostrar()

    def _seleccion(self):
        filas = self.lista.get_children()
        return [filas.index(i) for i in self.lista.selection()]

    def _cambiar(self, modo):
        posiciones = self._seleccion()
        if posiciones:
            self.app.cambiar_modo(posiciones, modo)

    def _alternar(self, evento):
        item = self.lista.identify_row(evento.y)
        if not item:
            return
        i = self.lista.get_children().index(item)
        es_color = self.app.cotizacion.paginas[i].es_color
        self.app.cambiar_modo([i], BN if es_color else COLOR)

    def _mostrar(self, _evento=None):
        sel = self._seleccion()
        if not sel:
            return
        i = sel[-1]
        ruta, indice, _ = self.app.trabajo[i]
        img = imagen_pagina(ruta, indice, dpi=50)
        if not self.app.cotizacion.paginas[i].es_color:
            img = img.convert("L")  # vista previa en gris: así se verá impresa
        img.thumbnail((self.ANCHO_VISTA, int(self.ANCHO_VISTA * 1.5)))
        self._foto = ImageTk.PhotoImage(img)
        self.vista.config(image=self._foto, text="", width=0)


def _nitidez_windows():
    """Evita que Windows dibuje la ventana borrosa en pantallas con escala (125 %, 150 %)."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


_fuente_cargada = False


def preparar_estilo(config):
    """Activa el estilo de config.json y carga la letra pixelada (una sola vez)."""
    global _fuente_cargada
    tema.activar(config["apariencia"].get("tema", "pixel"))
    if tema.PIXEL and not _fuente_cargada:
        _fuente_cargada = tema.cargar_fuente_pixel()
        if not _fuente_cargada:  # sin la letra pixelada, mejor el estilo clásico que letras raras
            tema.activar("clasico")


def main():
    _nitidez_windows()
    config = cfg.cargar()
    preparar_estilo(config)  # antes de crear la ventana: la letra debe existir cuando Tk la pida
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    App(root, config)
    root.mainloop()


if __name__ == "__main__":
    main()
