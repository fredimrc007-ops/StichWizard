"""Test (1.27): Kreuzstich – Stichfolge (Zickzack-Methode, Halb-/Viertelkreuze, Rückstich),
Objektart »cross« (Stiche, Rahmen, Speichern/Laden, Export), Bild → Kreuzstich und das
Kreuzstich-Atelier (Werkzeuge, Rückgängig, Farben) samt Bearbeiten per Doppelklick."""
import math
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
import pyembroidery as pe
from stichwizard import crossstitch as cs, engine, fileio
from stichwizard.crossdialog import CrossDialog
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)

# ---- Stichfolge
d = cs.new(10, 4, 2.0)
d["cells"] = [[x, 1, 0, "x"] for x in range(2, 7)]
runs = cs.color_runs(d, 0)
fwd, back = runs
check("Volle Kreuze: eine Reihe hin (/) und eine zurück (\\)", len(runs) == 2)
diag = lambda pts: sum(1 for a, b in zip(pts, pts[1:]) if abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1)
check(f"Je Reihe 5 Schenkel ({diag(fwd)}/{diag(back)})", diag(fwd) == 5 and diag(back) == 5)
check("Hin: unten links → oben rechts, zurück endet oben links am ersten Kästchen",
      fwd[0] == (2, 2) and fwd[1] == (3, 1) and back[-1] == (2, 1))
seg_ok = all((abs(a[0] - b[0]), abs(a[1] - b[1])) in ((1, 1), (0, 1)) for a, b in zip(fwd, fwd[1:]))
check("Verbindungen liegen auf Kästchenkanten (nur Schenkel und senkrechte Kanten)", seg_ok)
d["passes"] = 3
check("Kräftig: jeder Schenkel 3×", diag(cs.color_runs(d, 0)[0]) == 15)
d["passes"] = 1
d["cells"] = [[0, 0, 0, "x"], [2, 0, 0, "x"], [5, 0, 0, "/"], [0, 3, 1, "q2"]]
runs0 = cs.color_runs(d, 0)
check("Lücken trennen die Reihen, Halbkreuz nur hin", len(runs0) == 5)
check("Viertelkreuz: Ecke unten rechts → Mitte", cs.color_runs(d, 1) == [[(1, 4), (0.5, 3.5)]])
d["back"] = [[0, 0, 3, 0, 2], [3, 0, 3, 3, 2], [6, 4, 5, 4, 2]]
check("Rückstich: anschließende Strecken werden verkettet",
      sorted(len(p) for p in cs._back_paths(d["back"])) == [2, 3])
blocks = cs.stitches(d)
check(f"Kreuze vor Rückstich, Farben getrennt ({[c for c, _ in blocks]})",
      [c for c, _ in blocks] == [d["palette"][0], d["palette"][1], d["palette"][2]])

# ---- Objekt
o = EmbObject("cross")
o.cross = cs.new(20, 10, 2.5)
o.cross["cells"] = [[x, y, (x // 5) % 2, "x"] for x in range(20) for y in range(10)]
b = o.local_bounds()
check(f"Rahmen = Raster 50 × 25 mm ({b[2] - b[0]:.1f} × {b[3] - b[1]:.1f})",
      abs(b[2] - b[0] - 50) < 0.01 and abs(b[3] - b[1] - 25) < 0.01)
bl = o.stitch_blocks()
st = sum(1 for _, s in bl for p in s if p[2] == engine.STITCH)
check(f"Zwei Farben, sinnvolle Stichzahl ({st})", len(bl) == 2 and 700 < st < 1600)
longest = max(math.dist(a[:2], b[:2]) for _, s in bl for a, b in zip(s, s[1:]) if b[2] == engine.STITCH)
check(f"Längster Stich ≈ Kästchendiagonale ({longest:.2f} mm)", longest < 2.5 * math.sqrt(2) + 0.6)
o.sx = o.sy = 2.0
b2 = [p for _, s in o.stitch_blocks() for p in s]
check("Skalieren vergrößert die Kreuze", max(p[0] for p in b2) - min(p[0] for p in b2) > 95)
o.sx = o.sy = 1.0
doc = Document(); doc.objects = [o]
d2 = Document(); d2.load_json(doc.to_json())
check("Speichern/Laden", d2.objects[0].kind == "cross" and d2.objects[0].cross == o.cross)
pes = os.path.join(OUT, "kreuz.pes")
fileio.export_file(doc, pes)
pat = pe.read(pes)
check("Export PES mit 2 Farben", len(pat.threadlist) == 2 and
      sum(1 for s in pat.stitches if s[2] == pe.STITCH) > 700)

# ---- Bild → Kreuzstich
img = QImage(200, 100, QImage.Format_ARGB32)
img.fill(QColor("#FFFFFF"))
p = QPainter(img)
p.fillRect(QRectF(0, 0, 100, 100), QColor("#D32F2F"))
p.fillRect(QRectF(120, 20, 60, 60), QColor("#1565C0"))
p.end()
cells, pal, rows = cs.from_image(img, 40, 2)
reds = sum(1 for c in cells if pal[c[2]] and QColor(pal[c[2]]).red() > 180)
check(f"Bild: 40 × {rows} Kästchen, 2 Farben {pal}", rows == 20 and len(pal) == 2)
check(f"Bild: Weiß bleibt frei, Flächen stimmen ({len(cells)} Kästchen, {reds} rot)",
      abs(len(cells) - (400 + 144)) < 40 and abs(reds - 400) < 25)

# ---- Atelier
dlg = CrossDialog(w, None, "#FFFFFF", (130, 180))
dlg.snapshot(); dlg.apply("x", 1, 1, 0)
dlg.snapshot(); dlg.apply("/", 2, 1, 0)
dlg.snapshot(); dlg.apply("q", 3, 1, 2)
dlg.snapshot(); dlg.apply("x", 3, 1, 0)
check("Volles Kreuz ersetzt Viertelkreuze im Kästchen",
      (3, 1, "q2") not in dlg.cells and dlg.cells[(3, 1, "c")][1] == "x")
dlg.undo()
check("Atelier: Rückgängig", (3, 1, "q2") in dlg.cells and (3, 1, "c") not in dlg.cells)
dlg.redo()
check("Atelier: Wiederholen", dlg.cells[(3, 1, "c")][1] == "x")
dlg.select_color(1)
dlg.snapshot(); dlg.flood(10, 10)
filled = sum(1 for k, v in dlg.cells.items() if v[0] == 1)
check(f"Füllen: alle leeren Kästchen außer den belegten ({filled})", filled == 40 * 40 - 3)
dlg.snapshot(); dlg.apply("erase", 1, 1, 0)
check("Radierer", (1, 1, "c") not in dlg.cells)
dlg.back.append([0, 0, 5, 0, 3])
dlg.remove_unused()
check("Unbenutzte Farben entfernen (Farbindizes neu nummeriert)",
      len(dlg.data["palette"]) == 3 and dlg.back[0][4] == 2)
dlg.accept()
check("Übernehmen liefert Daten", dlg.result_data and len(dlg.result_data["cells"]) == 40 * 40 - 3 + 2
      and dlg.result_data["back"])
dlg.show(); QTest.qWait(150); dlg.grab().save(os.path.join(OUT, "atelier.png")); dlg.close()

# ---- im Programm: neu, bearbeiten per Doppelklick, Rückgängig
def fake_exec(self):
    self.snapshot()
    for x in range(5):
        self.apply("x", x, 0, 0)
    self.accept()
    return 1
CrossDialog.exec = fake_exec
w.doc.objects = []; w.sync_items(); w.commit()
w.open_cross()
objs = list(w.doc.objects)
check("Kreuzstich einfügen", len(objs) == 1 and objs[0].kind == "cross" and
      len(objs[0].cross["cells"]) == 5)
co = objs[0]
w.scene.clearSelection(); w.items[co.id].setSelected(True); QTest.qWait(5)
w.props.set_object(co)
check("Eigenschaften zeigen die Karte »Kreuzstich«", w.props.c_cross.isVisibleTo(w.props)
      and not w.props.c_fill.isVisibleTo(w.props))
def edit_exec(self):
    self.snapshot(); self.apply("x", 0, 5, 0); self.accept(); return 1
CrossDialog.exec = edit_exec
w.canvas.crossRequested.emit(co)
check("Doppelklick: vorhandenes Muster bearbeitet", len(co.cross["cells"]) == 6 and
      len(w.doc.objects) == 1)
w.undo(); QTest.qWait(5)
check("Rückgängig nach dem Bearbeiten", len(w.doc.objects[0].cross["cells"]) == 5)
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
