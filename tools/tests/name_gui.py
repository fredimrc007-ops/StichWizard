"""Test: Programmname StichWizard und Zauberer-Symbol."""
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from stichwizard import icons
from stichwizard.help import ABOUT
from stichwizard.mainwindow import MainWindow
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.show(); QTest.qWait(50)
check("Fenstertitel nennt StichWizard", "StichWizard" in w.windowTitle())
check("Über-Fenster nennt StichWizard", "StichWizard" in ABOUT and "StickStudio" not in ABOUT)
check("Über-Knopf heißt »Über StichWizard«", "StichWizard" in w.a_about.text())
img = icons.app_logo(64).toImage()
check("Symbol ist gezeichnet (Mitte nicht leer)", img.pixelColor(32, 32).alpha() > 200)
check("Symbol hat transparente Ecken", img.pixelColor(0, 0).alpha() == 0)
check("Fenstersymbol gesetzt", not w.windowIcon().isNull())
# PDF-Anleitung unter Hilfe
check("Anleitung (PDF) wird gefunden", w.manual_path() is not None)
opened = []
import stichwizard.mainwindow as mw
mw.QDesktopServices.openUrl = staticmethod(lambda url: opened.append(url.toLocalFile()) or True)
w.show_manual()
check("Hilfe › Anleitung öffnet das PDF", opened and opened[0].endswith("StichWizard-Anleitung.pdf"))
check("Knopf im Reiter Hilfe", "Anleitung\n(PDF)" == w.a_manual.text())
print(f"{sum(ok)}/{len(ok)}")
w.close()
sys.exit(0 if all(ok) else 1)
