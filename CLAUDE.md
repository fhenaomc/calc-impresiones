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
- Cualquier color apreciable (≥ 0,05 % del área) vuelve la página "color".
- Una página b/n muy cargada cuesta más que una normal.
- **Siempre estimar por encima**: redondeo hacia arriba, factor de corrección > 1,
  precio del rango calculado en su límite superior con el tóner más caro.
- Margen sobre precio de venta: `precio = costo / (1 − 0,40)`.
- Un tamaño de papel por trabajo (carta, oficio, doble carta). Sin doble cara.
- Resultado: resumen agrupado ("8 pág. B/N normal × $150 …") + detalle por página.
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
tests/                   pytest con imágenes sintéticas de cobertura conocida
herramientas/generar_referencias.py   PDFs de referencia por rango (fotos de Windows)
muestras/                archivos reales de prueba (NO se versionan: datos de clientes)
```

## Comandos
```
.venv\Scripts\python -m pytest
.venv\Scripts\python -m cotizador.cli --rangos
.venv\Scripts\python -m cotizador.cli muestras\archivo.pdf --detalle --tamano carta --copias 2
.venv\Scripts\python herramientas\generar_referencias.py
```
Entorno: Python 3.14 en `.venv` (PyMuPDF, Pillow, numpy, pytest). Importar `pymupdf`, no `fitz`.

## Datos de la impresora / costos (config por defecto)
- Tóner C/M/Y: $200.000, rinde 17.000 pág. al 5 %. K: $180.000, 28.000 pág.
- Papel: resma 500 hojas; carta $15.000, oficio $19.000.
- PROVISIONAL (confirmar con el usuario): precio doble carta ($30.000/resma),
  medida de oficio (216 × 330 mm), desgaste por página (color $40, b/n $20).

## Plan por etapas
1. ✅ Motor de cobertura y costos con PDF e imágenes, probado con `muestras/`.
2. ⬜ Interfaz tkinter + tkinterdnd2 (arrastrar y soltar, copias, tamaño, resumen, detalle).
3. ⬜ Word/Excel/PowerPoint → PDF vía Office (pywin32 COM); LibreOffice como alternativa;
   mensaje claro si ninguno está.
4. ⬜ Pantalla de ajustes (todos los valores de config, incl. precio manual por rango).
5. ⬜ .exe único con PyInstaller (incluir binarios de tkinterdnd2) + guía de calibración.
