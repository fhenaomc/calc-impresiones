# Cotizador de impresiones — papelería

Programa de escritorio (Windows 10, en español) para cotizar impresiones en una
**Ricoh MP C3003** (láser color CMYK). Lo usan los padres del autor, que no son
técnicos: la interfaz debe ser muy simple. El autor (Felipe) es ingeniero mecánico
aprendiendo programación: **explicar las decisiones y el código**, no solo entregarlo.

## Reglas de negocio (acordadas)
- Se analiza cada página: cobertura C, M, Y, K y si es color o gris.
- **Tarifa fija por rango** (no precio exacto). Rangos b/n: normal / cargado / total.
  Rangos color: mínimo (b/n con título o logo a color) / medio (foto de ½ página) /
  alto (dos fotos) / total (foto a página completa).
- Detección automática de color: solo cuentan MANCHAS de color intenso (croma ≥ 0,15 y
  erosión 3×3) que sumen ≥ 0,02 % de la hoja (≈ 3,5 × 3,5 mm). Así un escaneo con celular
  (halos de color en las letras) y el puntico naranja del logo IAC quedan en B/N.
- **La decisión final es del usuario**: en el detalle cada hoja puede pasarse a B/N o color
  (✋ = decidido a mano), y en la ventana principal "Todo en blanco y negro" manda sobre todo.
  Una hoja impresa en B/N se cobra con `k_gris` (toda la hoja pasada a gris), no con su K a color.
- Una página b/n muy cargada cuesta más que una normal.
- **Siempre estimar por encima**: redondeo hacia arriba, factor de corrección > 1,
  precio del rango calculado en su límite superior con el tóner más caro.
- **Precios de venta fijos (acordados sep. 2026)**, en `precio_manual` de config:
  B/N $700 en los 3 rangos; color mínimo $1.000, medio $2.000, alto $3.000, total $4.000.
  Oficio = mismo precio que carta. El modelo de costos se usa para clasificar y para
  alertar (`bajo_costo`) si un precio fijo deja de cubrir el costo máximo del rango.
- Sin precio manual, el precio sale del modelo: `costo / (1 − 0,40)` redondeado arriba.
- Reparto sugerido: (venta − tinta − papel) → 50 % capital (mantenimiento) / 50 % ganancia.
  El desgaste no se resta aparte en ese reparto: lo cubre el capital.
- Un tamaño de papel por trabajo: **carta u oficio** (no se imprime doble carta). Sin doble cara.
- Resultado: resumen agrupado ("8 pág. B/N normal × $700 …") + detalle por página.
- Moneda: pesos colombianos, formato `$1.250`.

## Modelo de costos (`cotizador/costos.py`)
```
tinta_canal = (precio_tóner / rendimiento) × (cobertura_canal / 5 %) × área_relativa
costo       = Σ tinta × factor_corrección + papel + desgaste(color|bn)
precio      = ceil( costo / (1 − margen) / redondeo ) × redondeo
```
Clasificación: la página cae en el primer rango con `cobertura_total (C+M+Y+K) ≤ límite`.

## Conversión RGB → CMYK (`cotizador/cobertura.py`)
- Píxel neutro (croma < `umbral_croma`): solo K = 1 − promedio(RGB).
- Píxel de color: C=1−R, M=1−G, Y=1−B y se pasa una fracción `gcr` (0,5) de
  min(C,M,Y) a K. GCR bajo = más tinta de color = estimación conservadora.
- Es una aproximación; el `factor_correccion` se calibra con el consumo real.
- Imágenes sueltas (JPG/PNG) se asumen a página completa (por encima).

## Estructura
```
cotizador/config.py      valores por defecto + config.json (junto al .exe o raíz del proyecto)
cotizador/cobertura.py   archivo → páginas RGB (PyMuPDF / Pillow) → % CMYK
cotizador/costos.py      modelo de costos, rangos, cotización y resumen
cotizador/cli.py         prueba por consola
cotizador/interfaz.py    ventana principal (App) + VentanaDetalle; `python -m cotizador`
cotizador/ventana_precios.py  editor de precios por rango (escribe config.json)
cotizador/tema.py        colores, letras y tamaños de la interfaz (un solo lugar)
cotizador/formato.py     pesos(), leer_pesos(), hojas()
tests/                   pytest con imágenes sintéticas de cobertura conocida
herramientas/generar_referencias.py   PDFs de referencia por rango (fotos de Windows)
herramientas/generar_tabla_precios.py documentos/Tabla de precios.xlsx (para aprobación de los dueños)
muestras/                archivos reales de prueba (NO se versionan: datos de clientes)
```

## Comandos
```
.venv\Scripts\python -m pytest
.venv\Scripts\pythonw -m cotizador          (abre la interfaz)
.venv\Scripts\python -m cotizador.cli --rangos
.venv\Scripts\python -m cotizador.cli muestras\archivo.pdf --detalle --tamano carta --copias 2
.venv\Scripts\python herramientas\generar_referencias.py
.venv\Scripts\python herramientas\generar_tabla_precios.py
```
No hay LibreOffice en el PC de desarrollo: para recalcular/verificar el .xlsx se usa Excel vía
pywin32 (`win32com.client.DispatchEx("Excel.Application")`, `CalculateFull`, `Save`).
Entorno: Python 3.14 en `.venv` (ver requirements.txt). Importar `pymupdf`, no `fitz`.

## Datos de la impresora / costos (config por defecto)
- Tóner C/M/Y: $200.000, rinde 17.000 pág. al 5 %. K: $180.000, 28.000 pág.
- Papel: resma 500 hojas; carta $15.000, oficio $19.000.
- Oficio 216 × 330 mm (confirmado como estimado válido).
- PROVISIONAL: desgaste por página (color $40, b/n $20).
- Antes de esta calculadora cobraban b/n $700 y color entre $1.500 y $5.000.

## Plan por etapas
1. ✅ Motor de cobertura y costos con PDF e imágenes, probado con `muestras/`.
   ✅ Precios fijos por rango + tabla de precios en Excel para aprobación.
2. ✅ Interfaz tkinter + tkinterdnd2: soltar/clic, tamaño, copias, resumen, detalle con
   vista previa, varios archivos ("+ Agregar otro archivo"), editor de precios, alerta bajo costo.
3. ⬜ Word/Excel/PowerPoint → PDF vía Office (pywin32 COM); LibreOffice como alternativa;
   mensaje claro si ninguno está.
4. ⬜ Pantalla de ajustes (todos los valores de config, incl. precio manual por rango).
5. ⬜ .exe único con PyInstaller (incluir binarios de tkinterdnd2) + guía de calibración.

## Notas de la interfaz
- El análisis corre en un hilo; se comunica con la ventana por `queue.Queue` + `root.after`.
  Solo el hilo principal toca widgets.
- Se guarda la cobertura (`App.trabajo`), no el precio: tamaño/copias/precios recotizan sin reanalizar.
- Soltar o clic = cotización nueva; "+ Agregar otro archivo" suma al trabajo actual.
- Si tkinterdnd2 falla, el programa sigue con clic (`_activar_soltar` atrapa el error).
- Pruebas de ventanas: UNA raíz Tk por sesión de pytest (crear muchas Tk() falla en Windows).
- Capturas para revisar la interfaz: usar `PrintWindow` (solo la ventana), nunca capturar la
  pantalla: puede incluir otras ventanas del usuario (correo, etc.).
- Pendiente de validar con los dueños: un afiche oscuro a página completa dio 78 % → "Color medio".
- `App.modos` = {posición en trabajo: BN|COLOR}; se borra con cotización nueva, no al agregar archivos.
- La ventana de detalle se refresca desde `App.recotizar()` (`App.detalle.refrescar`).
