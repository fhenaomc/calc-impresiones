"""Construye el .exe del cotizador y arma la carpeta para copiar en la USB.

Uso:  .venv\\Scripts\\python herramientas\\construir_exe.py

Resultado:  dist\\Net Papeleria - Cotizador\\
              Cotizador Net Papeleria.exe   <- el programa (un solo archivo, ~40-60 MB)
              LEEME.txt                     <- instrucciones para los dueños
              Licencia letra pixelada.txt   <- la licencia OFL exige acompañar la letra

Decisiones:
  * --onefile: un solo .exe, fácil de copiar. Al abrir se descomprime en una carpeta temporal,
    por eso tarda unos segundos en arrancar (la versión "carpeta" arranca más rápido pero son
    cientos de archivos que se pueden borrar por error).
  * --windowed: sin ventana negra de consola.
  * --collect-all tkinterdnd2: el arrastrar y soltar usa archivos binarios (tkdnd) que
    PyInstaller no detecta solo.
  * --add-data recursos: la letra Press Start 2P va dentro del .exe.
  * config.json NO se incluye: el programa trae los valores por defecto y crea config.json
    junto al .exe la primera vez que se guarden precios o costos.
"""

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import PyInstaller.__main__  # noqa: E402

from cotizador import pixelart  # noqa: E402

NOMBRE = "Cotizador Net Papeleria"          # sin tildes en el nombre del archivo: evita líos en Windows
CARPETA = RAIZ / "dist" / "Net Papeleria - Cotizador"
TRABAJO = RAIZ / "build"

LEEME = """\
COTIZADOR DE IMPRESIONES - NET PAPELERIA
========================================

CÓMO ABRIRLO
  Doble clic en "Cotizador Net Papeleria".
  La primera vez tarda unos segundos en abrir; es normal.

  Si Windows muestra "Windows protegió su PC":
    clic en "Más información" y luego en "Ejecutar de todas formas".
  (Sale porque el programa no está "firmado" por una empresa; es seguro.)

CÓMO COTIZAR
  1. Arrastre el archivo (PDF o foto) al recuadro amarillo,
     o haga clic en el recuadro para buscarlo.
     También puede arrastrar el archivo encima del ícono del programa.
  2. Elija el tamaño (Carta u Oficio) y el número de copias.
  3. El total aparece abajo en verde.
  4. "Ver detalle hoja por hoja" muestra cada hoja. Ahí puede pasar
     hojas a blanco y negro o a color si el cliente lo pide.
  5. "Nueva cotización" para empezar con otro cliente.

  Archivos de Word, Excel o PowerPoint: ábralos y use
  Archivo -> Guardar como -> PDF. Luego arrastre el PDF.

CAMBIAR PRECIOS O COSTOS
  Botón "Precios": precio de venta de cada rango.
  Botón "Costos": tóner, papel, mantenimiento, luz y hojas al mes.
  Los cambios se guardan en el archivo "config.json" que aparece
  junto al programa. NO borre ese archivo (ahí quedan sus precios).

IMPORTANTE
  Deje el programa en esta carpeta. Si lo mueve, mueva también
  config.json junto con él.
"""


def crear_icono() -> Path:
    """Ícono .ico con varios tamaños (Windows usa el que necesite: barra de tareas, escritorio...)."""
    TRABAJO.mkdir(exist_ok=True)
    ruta = TRABAJO / "icono.ico"
    tamanos = [16, 32, 48, 64, 128, 256]
    imagenes = [pixelart.icono(t) for t in tamanos]
    imagenes[-1].save(ruta, format="ICO", sizes=[(t, t) for t in tamanos], append_images=imagenes[:-1])
    return ruta


def main():
    icono = crear_icono()
    sep = ";"  # separador de --add-data en Windows
    PyInstaller.__main__.run([
        str(RAIZ / "iniciar.py"),
        "--name", NOMBRE,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(icono),
        "--add-data", f"{RAIZ / 'cotizador' / 'recursos'}{sep}cotizador/recursos",
        "--collect-all", "tkinterdnd2",
        "--distpath", str(RAIZ / "dist"),
        "--workpath", str(TRABAJO),
        "--specpath", str(TRABAJO),
        # Librerías que el programa no usa (solo las herramientas de desarrollo): no inflan el .exe
        "--exclude-module", "pytest",
        "--exclude-module", "openpyxl",
        "--exclude-module", "win32com",
        "--exclude-module", "PyInstaller",
    ])

    CARPETA.mkdir(parents=True, exist_ok=True)
    exe = RAIZ / "dist" / f"{NOMBRE}.exe"
    shutil.move(str(exe), CARPETA / exe.name)
    (CARPETA / "LEEME.txt").write_text(LEEME, encoding="utf-8-sig")  # con BOM: el Bloc de notas lo abre bien
    shutil.copy(RAIZ / "cotizador" / "recursos" / "OFL-PressStart2P.txt", CARPETA / "Licencia letra pixelada.txt")
    tamano = (CARPETA / exe.name).stat().st_size / 1e6
    print(f"\nListo: {CARPETA}\n  {exe.name}: {tamano:.0f} MB")


if __name__ == "__main__":
    main()
