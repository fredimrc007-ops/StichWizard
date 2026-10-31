"""Erzeugt das Programmsymbol: Windows-.ico mit allen gängigen Größen, oder mit
--hicolor ORDNER NAME PNG-Symbole für Linux (hicolor-Thema, z. B. für das Flatpak)."""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication

app = QGuiApplication(sys.argv[:1])
from stichwizard import icons  # noqa: E402

pm = icons.app_logo(256)                  # Zauberer mit Sticknadel
if sys.argv[1] == "--hicolor":
    for n in (32, 48, 64, 128, 256, 512):
        d = os.path.join(sys.argv[2], f"{n}x{n}", "apps")
        os.makedirs(d, exist_ok=True)
        icons.app_logo(n).save(os.path.join(d, sys.argv[3] + ".png"))
    print("Symbole:", sys.argv[2])
    sys.exit(0)
buf = QBuffer()
buf.open(QIODevice.WriteOnly)
pm.save(buf, "PNG")
from PIL import Image  # noqa: E402
img = Image.open(io.BytesIO(bytes(buf.data())))
img.save(sys.argv[1], sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Symbol:", sys.argv[1])
