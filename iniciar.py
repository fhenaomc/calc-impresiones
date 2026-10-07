"""Punto de entrada del programa empaquetado (.exe).

PyInstaller necesita un script que arranque el programa; `python -m cotizador` no le sirve.
Si se arrastra un archivo sobre el ícono del .exe, Windows lo pasa como argumento y se cotiza.
"""

from cotizador.interfaz import main

if __name__ == "__main__":
    main()
