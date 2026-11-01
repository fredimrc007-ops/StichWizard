"""StichWizard – Sticksoftware."""
import sys

__version__ = "1.32.2"

WINDOWS = sys.platform == "win32"
DEFAULT_FONT = "Arial" if WINDOWS else "DejaVu Sans"
MONO_FONT = "Consolas" if WINDOWS else "DejaVu Sans Mono"
