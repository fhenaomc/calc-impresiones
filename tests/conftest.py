# Permite importar el paquete `cotizador` desde las pruebas sin instalarlo.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
