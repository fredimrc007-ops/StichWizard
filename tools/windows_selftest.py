"""Selbsttest der Windows-Version (läuft mit dem installierten Python unter Windows/Wine).

Aufruf: python.exe tools\\windows_selftest.py <ausgabeordner>
"""
import os
import sys
import time

out = sys.argv[1] if len(sys.argv) > 1 else "."
sys.stdout.reconfigure(encoding="utf-8")
HIDDEN = "--native" in sys.argv     # echtes Windows-Plugin, aber Fenster nicht anzeigen
if HIDDEN:
    sys.argv.remove("--native")
    os.environ["QT_QPA_PLATFORM"] = "windows"
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
t0 = time.time()
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])
app.setStyle("Fusion")
import stichwizard  # noqa: E402
import stichwizard.__main__ as mm  # noqa: E402
from stichwizard import fileio  # noqa: E402
from stichwizard.mainwindow import MainWindow  # noqa: E402
from stichwizard.model import EmbObject  # noqa: E402

mm.apply_light_palette(app)
mm.install_translations(app)
print("Qt-Plugin:", app.platformName(), "| Plattform:", sys.platform, "| Python", sys.version.split()[0], "| StichWizard",
      stichwizard.__version__, "| Textschrift", stichwizard.DEFAULT_FONT)
w = MainWindow()
w.resize(1400, 880)
if HIDDEN:
    w.setAttribute(Qt.WA_DontShowOnScreen)
w.show()
app.processEvents()
print(f"Start: {time.time() - t0:.1f}s, KI-Schnittstelle: {w.api_server.running()} ({w.lbl_ai.text()})")
w.add_motif("Herz")
t = EmbObject("text", "Test")
t.text["text"] = "Windows"
t.y = 45
t.fill.update(type="satin", angle=0, color="#1565C0")
w.add_objects([t])
st = w.doc.stats()
print("Design:", st["stitches"], "Stiche,", st["colors"], "Farben")
path = os.path.join(out, "windows_test.pes")
res = fileio.export_file(w.doc, path, True)
back = fileio.import_file(path)
print("Export PES:", os.path.getsize(path), "Bytes, wieder eingelesen:",
      sum(len(b["stitches"]) for b in back.blocks), "Punkte, Optimierung:", res)
app.processEvents()
w.grab().save(os.path.join(out, "windows_test.png"))
print("Screenshot gespeichert")
w.dirty = False
if len(sys.argv) > 2 and sys.argv[2] == "serve":
    print("Warte auf KI-Befehle …", flush=True)
    app.exec()
