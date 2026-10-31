"""Test (1.15.2): eigene Rahmengrößen – anlegen, speichern, in Dateien mitnehmen, löschen."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import controls, threads
from stichwizard.api import DesignAPI
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
N = threads.N_BUILTIN_HOOPS
cb = w.hoop_combo
datas = [cb.itemData(i) for i in range(cb.count())]
check("Liste endet mit »Eigener Rahmen …«", "custom" in datas and "delete" not in datas)

# ---- über den Listeneintrag anlegen (Dialog mit vorgegebenen Werten)
controls.ask_values.auto = {"w": 180.0, "h": 300.0, "name": "Brother XL"}
cb.setCurrentIndex(cb.findData("custom"))
controls.ask_values.auto = None
QTest.qWait(20)
check("Eigener Rahmen ist aktiv: 180 × 300 mm", w.doc.hoop_size == (180.0, 300.0) and w.doc.hoop == N)
check("Name in der Liste", cb.currentText() == "Brother XL – 180 × 300 mm")
check("Rahmen in den Einstellungen gespeichert",
      w.prefs.get("custom_hoops") == [["Brother XL", 180.0, 300.0]])
check("Rahmenfeld im Bild hat die neue Größe",
      (w.hoop_item.w, w.hoop_item.h) == (180.0, 300.0))
check("»Eigenen Rahmen löschen …« erscheint", cb.findData("delete") >= 0)

# ---- gleiche Größe nicht doppelt, Grenzen
n0 = len(threads.HOOPS)
w.add_custom_hoop(180, 300)
check("Gleiche Größe wird nicht doppelt angelegt", len(threads.HOOPS) == n0)
check("Zu kleiner Rahmen wird abgelehnt", w.add_custom_hoop(5, 300) is None and len(threads.HOOPS) == n0)
w.add_custom_hoop(130, 180)
check("Feste Größe wählt den vorhandenen Rahmen", w.doc.hoop == 1 and len(threads.HOOPS) == n0)

# ---- in der Projektdatei: Größe reist mit
w.set_hoop(N)
text = w.doc.to_json()
threads.load_custom_hoops([])                         # anderer Rechner ohne diesen Rahmen
d = Document(); d.load_json(text)
check("Datei bringt ihre Rahmengröße mit", d.hoop_size == (180.0, 300.0))
threads.load_custom_hoops(w.prefs.get("custom_hoops"))
old = Document(); old.load_json('{"hoop": 4, "objects": []}')
check("Alte Dateien (nur Index) bleiben gleich", old.hoop_size == (200, 200))

# ---- neues Fenster lädt die eigenen Rahmen aus den Einstellungen
w2 = MainWindow()
check("Eigener Rahmen nach Neustart in der Liste",
      w2.hoop_combo.findText("Brother XL – 180 × 300 mm") >= 0)
w2.close()

# ---- KI-Schnittstelle: beliebige Größe »BxH«
api = DesignAPI(w)
r = api.set_hoop({"hoop": "250x170"})
check("API: eigene Größe 250x170", w.doc.hoop_size == (250.0, 170.0))
check("API: neue Größe steht in der Liste", w.hoop_combo.currentText().startswith("250 × 170 mm"))
check("API: get_options listet eigene Rahmen", "180x300" in api.get_options({})["hoops"])

# ---- löschen: Design wechselt auf den nächstgrößeren festen Rahmen
w.set_hoop(threads.hoop_for_size(180, 300))
controls.ask_values.auto = {"i": w.doc.hoop}
cb.setCurrentIndex(cb.findData("delete"))
controls.ask_values.auto = None
QTest.qWait(20)
check("Gelöscht: nicht mehr in der Liste", cb.findText("Brother XL – 180 × 300 mm") < 0)
check("Design wechselt auf den größten flachen Rahmen (360 × 200)", w.doc.hoop_size == (360, 200))
check("Einstellungen aktualisiert", all(h[1:] != [180.0, 300.0] for h in w.prefs.get("custom_hoops")))
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
