"""Test: jeden Knopf/Menüpunkt einmal echt auslösen (wie ein Klick) und Fehler sammeln.
Dialoge werden automatisch abgebrochen bzw. mit einem Pfad im Testordner beantwortet;
es wird nichts außerhalb des Testordners gespeichert und kein Programm geöffnet."""
import os
import sys
import traceback
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QMessageBox
from PySide6.QtTest import QTest
OUT = sys.argv[1]
app = QApplication(sys.argv); app.setStyle('Fusion')
errors = []
sys.excepthook = lambda t, v, tb: errors.append("".join(traceback.format_exception(t, v, tb)))
opened = []
QDesktopServices.openUrl = staticmethod(lambda url: opened.append(url.toLocalFile()) or True)
QDialog.exec = lambda self: 0
for name in ("information", "warning", "critical", "about"):
    setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Ok))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
QMessageBox.exec = lambda self: QMessageBox.No
save_target = {}
def fake_save(parent, caption="", directory="", filt="", *a, **k):
    ext = os.path.splitext(directory)[1] or ".pdf"
    path = os.path.join(OUT, "aktion_" + "".join(c for c in caption if c.isalnum())[:30] + ext)
    save_target[caption] = path
    return path, filt
QFileDialog.getSaveFileName = staticmethod(fake_save)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
QInputDialog.getText = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getItem = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getDouble = staticmethod(lambda *a, **k: (0.0, False))
from stichwizard.mainwindow import MainWindow
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
w.close = lambda *a: None          # »Beenden« nicht wirklich schließen
SKIP = ("Beenden",)
from testdata import hafnerei_project
proj = hafnerei_project(OUT)
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
acts = [a for a in w.findChildren(QAction) if a.text() and not any(s in a.text() for s in SKIP)]
tried = 0
for a in acts:
    w.open_document(proj); QTest.qWait(5)
    w.scene.clearSelection()
    if w.doc.objects:
        w.items[w.doc.objects[-1].id].setSelected(True)
    before = len(errors)
    try:
        a.trigger()
        QTest.qWait(5)
        if a.isCheckable() and a.isChecked() and a.text().replace("\n", " ") == "Dichte prüfen":
            a.trigger()
    except Exception:
        errors.append(traceback.format_exc())
    tried += 1
    if len(errors) > before:
        print("  Fehler bei:", a.text().replace("\n", " "))
check(f"{tried} Knöpfe/Menüpunkte ausgelöst – Fehler: {len(errors)}", not errors)
for e in errors[:5]:
    print(e)
sheet = [p for c, p in save_target.items() if "Arbeitsblatt" in c]
check("Arbeitsblatt per Knopf gespeichert", sheet and os.path.getsize(sheet[0]) > 10000)
check("Arbeitsblatt danach zum Anzeigen geöffnet", any(p.endswith(".pdf") for p in opened))
print("ERGEBNIS:", sum(ok), "/", len(ok))
