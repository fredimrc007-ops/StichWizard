"""Test (1.25): Spirograph (Innenrad, Außenrad, Rosette, Guilloche) und Text in Form
(Word Sculpt) – Geometrie, Einfügen als Gruppe, Rückgängig, Menüband."""
import math
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QScrollArea
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
QDialog.exec = lambda self: 1           # Vorschau-Fenster sofort mit der ersten Einstellung bestätigen
from shapely.geometry import Point
from stichwizard import engine, spiro, templates, wordsculpt
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)


def stitches(objs):
    return sum(1 for o in objs for _, b in o.stitch_blocks() for s in b if s[2] == engine.STITCH)


def setdoc(*objs):
    w.doc.objects = list(objs)
    w.sync_items([o.id for o in objs])
    w.commit()
    QTest.qWait(5)


# ---- Spirograph-Mathematik
pts = spiro.hypotrochoid(96, 42, 0.85)
check("Innenrad schließt sich (Anfang = Ende nach allen Umläufen)",
      math.dist(pts[0], spiro.hypotrochoid(96, 42, 0.85)[0]) < 1e-9 and
      math.dist(pts[-1], pts[0]) < 3.0)
r = [math.hypot(x, y) for x, y in pts]
check(f"Innenrad: Radius zwischen R−r−d und R−r+d ({min(r):.1f}…{max(r):.1f})",
      abs(max(r) - (54 + 0.85 * 42)) < 0.5 and abs(min(r) - (54 - 0.85 * 42)) < 0.5)
ro = spiro.rose(5, 1)
rr = [math.hypot(*q) for q in ro]
check("Rosette 5/1: 5 Blätter (Spitzen mit Radius ≈ 1)",
      sum(1 for i in range(len(rr)) if rr[i] > 0.999 and rr[i] >= rr[i - 1]
          and rr[i] >= rr[(i + 1) % len(rr)]) == 5)
bad = []
for key, title, *_ in spiro.SPIRO:
    objs = templates.build(key, None, spiro.SPIRO)
    d = Document(); d.objects = objs
    st = d.stats()
    b = st["bounds"]
    if stitches(objs) < 200 or abs(st["width"] - 90) > 12 or abs((b[0] + b[2]) / 2) > 2:
        bad.append(f"{key}:{stitches(objs)}/{st['width']:.0f}")
check(f"Alle Spirograph-Arten sticken, ~90 mm, mittig {bad}", not bad)
objs = templates.build("rose", {"layers": 4, "two": True}, spiro.SPIRO)
check("Rosette: 4 Lagen, Farben abwechselnd",
      len(objs) == 4 and objs[0].border["color"] != objs[1].border["color"] ==
      objs[3].border["color"])
setdoc()
w.open_spiro()
objs = list(w.doc.objects)
check("Spirograph einfügen (als Gruppe)", objs and len({o.group for o in objs}) == 1)
w.undo(); QTest.qWait(5)
check("Spirograph: Rückgängig", not w.doc.objects)

# ---- Text in Form
heart = wordsculpt.shape_geometry("Herz", 110)
rows = wordsculpt.rows(heart, 9.0, 2.0)
check(f"Herz: Zeilen erkannt ({len(rows)}), oben zwei Bögen getrennt",
      len(rows) >= 6 and len(rows[0][1]) == 2)
tpls = wordsculpt.sculpt_templates()
objs = templates.build("shape", None, tpls)
texts = [o for o in objs if o.kind == "text"]
check(f"Text in Form: {len(texts)} Zeilen-Schriftzüge", len(texts) >= 7)
check("Text in Form: keine Zeile kleiner als 5 mm",
      all(o.local_size()[1] * o.sy >= wordsculpt.MIN_H - 0.05 for o in texts))
star = templates.build("shape", {"shape": "Stern", "size": 130, "row": 7}, tpls)
sb = Document(); sb.objects = star
check(f"Stern: auch die Zacken unten sind beschriftet ({sb.stats()['height']:.0f} mm hoch)",
      sb.stats()["height"] > 72)
inside = all(heart.buffer(1.5).contains(Point(x, y)) for o in texts
             for _, b in o.world_blocks() for x, y, f in b[::7] if f == engine.STITCH)
check("Text in Form: alle Stiche in der Form", inside)
check("Text in Form: Stickschrift nur leicht verzerrt (Satin bleibt dicht)",
      all(abs(o.sy - 1) < 1e-6 and wordsculpt.MIN_SX - 1e-6 <= o.sx <= wordsculpt.MAX_SX + 1e-6
          for o in texts))
words = " ".join(o.text["text"] for o in texts).split()
check("Wörter wiederholen sich, bis die Form voll ist", len(words) > 7 and words[7] == "LIEBE")
once = templates.build("shape", {"repeat": False, "text": "Anna Ben"}, tpls)
check("Ohne Wiederholen: nur die eingegebenen Wörter",
      " ".join(o.text["text"] for o in once if o.kind == "text").split() == ["ANNA", "BEN"])
ol = templates.build("shape", {"outline": True, "shape": "Kreis"}, tpls)
check("Umriss als Linie dazu", ol[-1].kind == "line" and ol[-1].closed)
# ausgewählte Form
box = templates.shape(wordsculpt.shape_geometry("Wolke", 120), "#BBDEFB")
setdoc(box)
w.scene.clearSelection(); w.items[box.id].setSelected(True); QTest.qWait(5)
w.open_wordsculpt()
objs = list(w.doc.objects)
new = [o for o in objs if o is not box]
check(f"Text in ausgewählte Form: Form bleibt, {len(new)} Zeilen dazu",
      box in objs and len(new) >= 5 and all(o.kind == "text" for o in new))
g = box.world_geometry()
check("Zeilen liegen in der ausgewählten Form",
      all(g.buffer(1.5).contains(Point(o.x, o.y)) for o in new))
w.undo(); QTest.qWait(5)
check("Text in Form: Rückgängig", [o.id for o in w.doc.objects] == [box.id])

# ---- Menüband
over = []
for i in range(w.ribbon.count()):
    w.ribbon.setCurrentIndex(i); QTest.qWait(10)
    sa = w.ribbon.currentWidget()
    sa = sa if isinstance(sa, QScrollArea) else sa.findChild(QScrollArea)
    if sa.widget().sizeHint().width() > 1440:
        over.append((w.ribbon.tabText(i), sa.widget().sizeHint().width()))
check(f"Alle Reiter passen in 1440 Pixel {over}", not over)
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
