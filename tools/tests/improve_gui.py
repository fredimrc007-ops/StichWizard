"""Test (1.10): Gruppieren und gemeinsam skalieren, Stoffarten, Kurvenanpassung des
Steppstichs, Überlappung entfernen, Kleinteile entfernen."""
import math
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, shapes
from stichwizard.api import ApiError, DesignAPI
from stichwizard.canvas import transform_objects
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
from shapely.geometry import MultiPolygon, Polygon, box
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
api = DesignAPI(w)

def rect(wd, ht, x=0.0, y=0.0, color="#E53935"):
    o = EmbObject("shape"); o.set_geometry(shapes.rounded_rect(wd, ht, 1)); o.x, o.y = x, y
    o.fill["color"] = color
    return o
def n_st(o):
    return sum(1 for _, s in o.stitch_blocks() for p in s if p[2] == engine.STITCH)
def select(*objs):
    w.scene.clearSelection()
    for o in objs:
        w.items[o.id].setSelected(True)
    QTest.qWait(10)
def bounds(objs):
    xs = [p[0] for o in objs for _, s in o.world_blocks() for p in s]
    ys = [p[1] for o in objs for _, s in o.world_blocks() for p in s]
    return min(xs), min(ys), max(xs), max(ys)

# ============ Gruppieren
a, b, c = rect(20, 10, -20), rect(10, 10, 20, color="#1E88E5"), rect(8, 8, 0, 30)
w.doc.objects = [a, b, c]; w.sync_items([a.id, b.id])
w.group_selected()
check("Gruppieren setzt eine gemeinsame Gruppe", a.group and a.group == b.group and c.group is None)
select(a)
check("Klick auf ein Objekt wählt die ganze Gruppe", set(w.selected_objects()) == {a, b})
check("Eigenschaften zeigen die Karte »Gruppe«", w.props.c_sel.isVisible() and
      not w.props.c_fill.isVisible())
w.scene.clearSelection()
QApplication.keyboardModifiers = staticmethod(lambda: Qt.AltModifier)
w.items[a.id].setSelected(True); QTest.qWait(10)
check("Alt+Klick wählt nur das einzelne Objekt", w.selected_objects() == [a])
QApplication.keyboardModifiers = staticmethod(lambda: Qt.NoModifier)
select(a)
x0, y0, x1, y1 = bounds([a, b])
w.props.sel_w.setValue((x1 - x0) * 1.5); QTest.qWait(10)
nx0, ny0, nx1, ny1 = bounds([a, b])
check("Gruppe über die Breite gemeinsam skaliert (×1,5)",
      abs((nx1 - nx0) / (x1 - x0) - 1.5) < 0.03 and abs((ny1 - ny0) / (y1 - y0) - 1.5) < 0.03)
check("Abstand der Objekte wächst mit", abs((b.x - a.x) - 60) < 0.5 and abs(a.sx - 1.5) < 0.01)
check("Nicht gruppiertes Objekt bleibt unverändert", c.sx == 1.0 and c.x == 0)
# Eckgriffe: gemeinsam um die Mitte skalieren und drehen
cx, cy = (nx0 + nx1) / 2, (ny0 + ny1) / 2
transform_objects([a, b], (cx, cy), scale=0.5)
check("Griffe: gemeinsam auf die Hälfte", abs(a.sx - 0.75) < 0.01 and abs((b.x - a.x) - 30) < 0.5)
transform_objects([a, b], (cx, cy), angle=90)
check("Griffe: gemeinsam um 90° gedreht", abs(a.rot - 90) < 1e-6 and abs(a.x - b.x) < 0.5)
w.rebuild([a, b])
w.props.set_selection([a, b])
check("Um 90° gedreht: frei skalierbar", w.props.sel_lock.isEnabled())
transform_objects([a, b], (cx, cy), angle=30)
w.rebuild([a, b]); w.props.set_selection([a, b])
check("Schräg gedrehte Gruppe nur proportional", not w.props.sel_lock.isEnabled())
transform_objects([a, b], (cx, cy), angle=-30)
w.rebuild([a, b])
w.mirror(True)
check("Spiegeln einer Gruppe spiegelt auch die Lage", a.rot == 270 and a.sx < 0)
select(a); w.duplicate()
new = [o for o in w.doc.objects if o not in (a, b, c)]
check("Duplikat einer Gruppe ist eine neue, eigene Gruppe",
      len(new) == 2 and new[0].group == new[1].group and new[0].group != a.group)
d2 = Document(); d2.load_json(w.doc.to_json())
check("Gruppen werden gespeichert", d2.objects[0].group == a.group)
select(a); w.ungroup_selected()
check("Gruppe auflösen", a.group is None and b.group is None)

# ============ Stoffarten
w.doc.objects = []; w.sync_items()
o = rect(40, 30); w.doc.objects = [o]; w.sync_items()
base = n_st(o)
w.set_fabric_type("towel")
check("Frottee: dichter und kräftigere Unterlage (mehr Stiche)", n_st(o) > base * 1.1)
check("Stoffart ändert die Objektwerte nicht", o.fill["density"] == 0.4 and o.fill["ul_layers"] == 1)
w.set_fabric_type("leather")
check("Leder: deutlich weniger Stiche", n_st(o) < base * 0.85)
check("Stoffart in der Oberfläche", w.fabtype_combo.currentData() == "leather")
d3 = Document(); d3.load_json(w.doc.to_json())
check("Stoffart wird gespeichert", d3.fabric_type == "leather")
w.set_fabric_type("standard")
check("Zurück auf Standard = wie vorher", n_st(o) == base)
r = api.call("set_hoop", {"fabric_type": "jersey"})
check("API: Stoffart setzen", r["fabric_type"] == "jersey" and engine.FABRIC == "jersey")
try:
    api.call("set_hoop", {"fabric_type": "stein"}); bad = False
except ApiError:
    bad = True
check("API: unbekannte Stoffart abgelehnt", bad)
w.set_fabric_type("standard")

# ============ Kurvenanpassung
circ = [(4 * math.cos(t / 60 * 2 * math.pi), 4 * math.sin(t / 60 * 2 * math.pi)) for t in range(61)]
engine.CURVE_TOL = 0.0
plain = engine.running_stitch(circ, 3.0)
engine.CURVE_TOL = 0.2
fine = engine.running_stitch(circ, 3.0)
dev = lambda pts: max(abs(math.hypot((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) - 4)
                      for p, q in zip(pts, pts[1:]))
check(f"Kleiner Kreis: Stiche geteilt ({len(plain)} → {len(fine)})", len(fine) > len(plain))
check("… und weichen höchstens 0,2 mm ab", dev(fine) <= 0.2 + 1e-6 < dev(plain))
check("Gerade Linie behält volle Stichlänge", len(engine.running_stitch([(0, 0), (30, 0)], 3.0)) == 11)
rw = [(0, 0), (10, 0), (10, 10), (0, 0)]
fw = engine.running_stitch(rw, 2.5, corners=True)
bw = engine.running_stitch(rw[::-1], 2.5, corners=True)
check("Hin- und Rückweg treffen dieselben Einstiche", sorted((round(x, 3), round(y, 3)) for x, y in fw)
      == sorted((round(x, 3), round(y, 3)) for x, y in bw))

# ============ Überlappung entfernen
QInputDialog.getDouble = staticmethod(lambda *a, **k: (1.0, True))
low = rect(40, 30, color="#43A047"); top = rect(20, 16, color="#FDD835")
w.doc.objects = [low, top]; w.sync_items([])
before = n_st(low)
w.remove_overlaps()
g = low.world_geometry()
check(f"Verdeckter Bereich wird nicht mehr gestickt ({before} → {n_st(low)} Stiche)",
      n_st(low) < before * 0.95 and len(list(g.interiors if g.geom_type == 'Polygon' else [])) == 1)
hole = Polygon(g.interiors[0])
check("1 mm bleibt unter dem oberen Objekt überlappend", abs(hole.bounds[2] - (10 - 1)) < 0.6)
check("Oberes Objekt bleibt unverändert", top.world_geometry().area > 300)
low2 = rect(40, 30); low2.border.update(type="satin"); top2 = rect(10, 10)
w.doc.objects = [low2, top2]; w.sync_items([])
a0 = low2.world_geometry().area
w.remove_overlaps()
check("Form mit Rand wird übersprungen (mit Hinweis)", low2.world_geometry().area == a0 and
      "übersprungen" in w.lbl_tip.text())

# ============ Kleinteile entfernen
QInputDialog.getDouble = staticmethod(lambda *a, **k: (2.0, True))
s = EmbObject("shape")
s.set_geometry(MultiPolygon([Polygon([(0, 0), (20, 0), (20, 20), (0, 20)],
                                     [[(5, 5), (6, 5), (6, 6), (5, 6)], [(10, 10), (15, 10), (15, 15), (10, 15)]]),
                             box(30, 0, 31, 1)]))
tiny = EmbObject("shape"); tiny.set_geometry(box(0, 0, 1, 1)); tiny.x = 50
ln = EmbObject("line"); ln.set_points([(0, 0), (1, 0)])
w.doc.objects = [s, tiny, ln]; w.sync_items([])
w.cleanup_small()
g = s.raw_geometry()
check("Kleines Inselstück und kleines Loch entfernt, großes Loch bleibt",
      g.geom_type == "Polygon" and len(g.interiors) == 1)
check("Winzige Objekte und Linien gelöscht", w.doc.objects == [s])

# ============ Tastenkürzel eindeutig (doppelte Kürzel schaltet Qt stumm)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt as _Qt
seen, dup = {}, []
for a in w.findChildren(QAction):
    for ks in a.shortcuts():
        key = ks.toString()
        if key in seen and seen[key] is not a:
            dup.append(f"{key}: {seen[key].text()!r} / {a.text()!r}")
        seen[key] = a
check("Kein Tastenkürzel doppelt vergeben" + (f" ({dup})" if dup else ""), not dup)
w.doc.objects = [rect(10, 10, -10), rect(10, 10, 10)]; w.sync_items([o.id for o in w.doc.objects])
w.canvas.setFocus(); QTest.qWait(30)
QTest.keyClick(w.canvas, _Qt.Key_G, _Qt.ControlModifier); QTest.qWait(30)
check("Strg+G kombiniert wieder", len(w.doc.objects) == 1)
w.doc.objects = [rect(10, 10, -10), rect(10, 10, 10)]; w.sync_items([o.id for o in w.doc.objects])
QTest.keyClick(w.canvas, _Qt.Key_G, _Qt.ControlModifier | _Qt.AltModifier); QTest.qWait(30)
check("Strg+Alt+G gruppiert", w.doc.objects[0].group and w.doc.objects[0].group == w.doc.objects[1].group)
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
