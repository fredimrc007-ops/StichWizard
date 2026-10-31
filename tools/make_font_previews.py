"""Erzeugt die Vorschaubilder der Stickschriften (stichwizard/fonts/previews/*.png)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])
from stichwizard import embfont  # noqa: E402
from stichwizard.fontdialog import SHIPPED, render_preview  # noqa: E402

os.makedirs(SHIPPED, exist_ok=True)
for f in embfont.font_index():
    render_preview(f["id"], "Abc").save(os.path.join(SHIPPED, f["id"] + ".png"))
print(len(os.listdir(SHIPPED)), "Vorschaubilder")
