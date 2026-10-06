@echo off
rem Abre el cotizador con doble clic (versión de desarrollo, mientras llega el .exe).
rem %~dp0 = carpeta donde está este .bat; así funciona aunque se mueva la carpeta del proyecto.

cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo No se encontro el entorno de Python ^(.venv^) en esta carpeta.
    echo Creelo con:  python -m venv .venv  y luego  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

rem "start" abre el programa y cierra esta ventana negra de inmediato.
start "" ".venv\Scripts\pythonw.exe" -m cotizador
