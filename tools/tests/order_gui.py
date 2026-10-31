"""Test: Sprungreihenfolge in der Simulation sehen und bearbeiten."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
OUT = sys.argv[1]
from testdata import jumpy_dst
app = QApplication(sys.argv); app.setStyle('Fusion')
from stichwizard.__main__ import apply_light_palette
apply_light_palette(app)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
from stichwizard import engine, jumps
from stichwizard.mainwindow import MainWindow
from stichwizard.model import EmbObject
from stichwizard.optimizer_dialog import OptimizerDialog
from shapely.geometry import box
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
def n_st(doc):
    return doc.stats()["stitches"]
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(80)
# --- Knopf »Simulation« öffnet die Simulation mit Sprüngen
seen = []
orig_exec = QDialog.exec
def fake_exec(self):
    seen.append((type(self).__name__, self.windowTitle()))
    return 0
QDialog.exec = fake_exec
w.open_document(jumpy_dst(OUT))   # eigene Datei mit vielen Sprüngen
w.a_sim.trigger()
QDialog.exec = orig_exec
check(f"Simulation zeigt Sprünge: {seen}", seen and seen[0] == ("OptimizerDialog", "Stick-Simulator & Optimierer"))
# --- Sprünge nummeriert im Bild, Seitenleiste ein-/ausblendbar
d = OptimizerDialog(w, "Stick-Simulation"); d.resize(1360, 860); d.show(); QTest.qWait(80)
n_jumps = len(d.records)
d.slider.setValue(d.slider.maximum() // 2); QTest.qWait(30)
img = d.view.grab(); img.save(os.path.join(OUT, "sim_nummern.png"))
check(f"{n_jumps} Sprünge mit Reihenfolge-Nummer", n_jumps > 5 and all("line" in r for r in d.records))
d.btn_side.setChecked(False); QTest.qWait(10)
hidden = not d.side.isVisible()
d.btn_side.setChecked(True); QTest.qWait(10)
check("Sprung-Seitenleiste ein-/ausblendbar", hidden and d.side.isVisible())
# --- Teil innerhalb der Stickdatei früher sticken
inside = [r for r in d.records if r["kind"] == "inside"]
rec = inside[3]
d.select_record(rec["index"]); QTest.qWait(10)
check("Reihenfolge-Text beim gewählten Sprung", f"Nach Sprung {rec['index'] + 1}" in d.order_label.text())
before = n_st(w.doc)
target = rec["b"]
d.edit_order("earlier"); QTest.qWait(10)
sel = d.selected_record()
check(f"Teil früher sticken: »{d.sel_label.text()}«", "gestickt" in d.sel_label.text())
check("Stichzahl unverändert", n_st(w.doc) == before)
check(f"Sprung zu dem Teil ist jetzt früher ({rec['index'] + 1} → {sel['index'] + 1 if sel else '?'})",
      sel is not None and sel["index"] < rec["index"] and abs(sel["b"][0] - target[0]) < 0.05)
d.undo(); QTest.qWait(10)
again = [r for r in d.records if r["kind"] == "inside"][3]
check("Rückgängig stellt die Reihenfolge wieder her", abs(again["b"][0] - target[0]) < 0.05)
# --- Teil umdrehen
d.select_record(again["index"])
d.edit_order("reverse"); QTest.qWait(10)
check(f"Teil umdrehen: »{d.sel_label.text()}«", "rückwärts" in d.sel_label.text() and n_st(w.doc) == before)
d.accept()
# --- Zwischen Objekten: Objekt später sticken
w.doc.objects = []
for x in (-40, 40, 0):                  # Objektliste: links, rechts, Mitte
    o = EmbObject("shape"); o.set_geometry(box(x - 5, -5, x + 5, 5)); o.fill["color"] = "#1E88E5"
    w.doc.objects.append(o)
w.doc.order_mode = "auto"; w.sync_items([]); w.commit()
names = {o.id: n for o, n in zip(w.doc.objects, ("links", "rechts", "mitte"))}
seq = lambda: [names[i] for i, _, _ in jumps.stitch_order(w.doc)]
auto_seq = seq()
# als ganzer Weg geplant: in einer Richtung durch (die Füllungen enden unten links -> von rechts
# nach links ist hier am kürzesten), Mitte nie zuerst
check(f"Automatisch kürzester Weg: {auto_seq}", auto_seq == ["rechts", "mitte", "links"])
d = OptimizerDialog(w, "Stick-Simulation"); d.show(); QTest.qWait(50)
between = [r for r in d.records if r["kind"] == "between" and not r["same"]]
first = between[0]
d.select_record(first["index"])
check("Umdrehen zwischen Objekten gesperrt", not d.btn_reverse.isEnabled())
d.edit_order("later"); QTest.qWait(10)
check(f"Objekt später sticken → {seq()}, Modus »von Hand«",
      seq() == ["rechts", "links", "mitte"] and w.doc.order_mode == "manual" and not d.auto_order.isChecked())
d.auto_order.setChecked(True); QTest.qWait(10)
check(f"Wieder automatisch → {seq()}", seq() == auto_seq and w.doc.order_mode == "auto")
d.accept()
# --- Reihenfolge-Modus wird gespeichert
w.doc.order_mode = "manual"
from stichwizard.model import Document
d2 = Document(); d2.load_json(w.doc.to_json())
check("Reihenfolge-Modus wird mit dem Projekt gespeichert", d2.order_mode == "manual")
print("ERGEBNIS:", sum(ok), "/", len(ok))
