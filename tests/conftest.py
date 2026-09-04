"""Asegura que la raiz del repo este en sys.path para importar agent/ y tools/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
