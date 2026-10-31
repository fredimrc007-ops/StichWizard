"""Test (1.18.1): Lizenztexte der mitgelieferten Bestandteile und Fenster »Lizenzen Dritter«."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
from stichwizard.help import ABOUT, LicensesDialog, licenses_dir
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)

d = licenses_dir()
files = set(os.listdir(d)) if os.path.isdir(d) else set()
for f in ("LIZENZEN-DRITTER.txt", "Stickschriften.txt", "LGPL-3.0.txt", "LGPL-2.1.txt",
          "GPL-3.0.txt", "PSF-2.0.txt", "pyembroidery-LICENSE.txt", "CC-BY-SA-4.0.txt"):
    check(f"Lizenzdatei {f}", f in files and os.path.getsize(os.path.join(d, f)) > 500)
over = open(os.path.join(d, "LIZENZEN-DRITTER.txt"), encoding="utf-8").read()
for part in ("Qt for Python", "LGPL-3.0", "GEOS", "NumPy", "pyembroidery", "Ink/Stitch", "Garnkarten"):
    check(f"Übersicht nennt {part}", part in over)
check("Keine unbekannten Versionen in der Übersicht", " ?\n" not in over)
fonts = open(os.path.join(d, "Stickschriften.txt"), encoding="utf-8").read()
check("Alle 129 Stickschriften mit Lizenz", fonts.count("\n--- ") == 129)
check("Nicht-kommerzielle Schriften sind gekennzeichnet", "NUR NICHT-KOMMERZIELL" in fonts)
check("Kein Hinweis auf eine kommerzielle Qt-Lizenz", not any("Qt-Commercial" in f for f in files))
check("Über-Text verweist auf die Lizenzen", "Lizenzen Dritter" in ABOUT and "LGPL" in ABOUT)
dlg = LicensesDialog()
dlg.show(); QTest.qWait(50)
check("Fenster zeigt zuerst die Übersicht", dlg.files.item(0).text() == "Übersicht"
      and "Lizenzen der mitgelieferten" in dlg.text.toPlainText())
dlg.files.setCurrentRow([dlg.files.item(i).text() for i in range(dlg.files.count())].index("LGPL-3.0"))
check("Volltext LGPL-3.0 anzeigbar", "LESSER GENERAL PUBLIC LICENSE" in dlg.text.toPlainText())
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
