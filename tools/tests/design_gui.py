"""Test (1.13): Gestalten wie in Inkscape – Pfad-Operationen, Ausrichten/Verteilen, Versatz,
Umriss, Kopien im Raster/Kreis, Stern/Spirale, Sperren, Einrasten, Farbpipette."""
import math
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from shapely.geometry import box
from stichwizard import controls, design, shapes
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)

def sq(x, y, s=20, color="#E53935"):
    o = EmbObject("shape"); o.set_geometry(box(x - s / 2, y - s / 2, x + s / 2, y + s / 2))
    o.fill["color"] = color
    return o
def select(*objs):
    w.scene.clearSelection()
    for o in objs:
        w.items[o.id].setSelected(True)
    QTest.qWait(5)
def setdoc(*objs):
    w.doc.objects = list(objs); w.sync_items([o.id for o in objs])

# ---- Pfad-Operationen
a, b = sq(0, 0), sq(10, 0, color="#1E88E5")
setdoc(a, b); w.path_op("intersect")
g = w.doc.objects[0].world_geometry()
check("Schnittmenge: 10 × 20 mm", len(w.doc.objects) == 1 and abs(g.area - 200) < 1)
a, b = sq(0, 0), sq(10, 0)
setdoc(a, b); w.path_op("exclude")
check("Exklusion: zwei Reststücke (2 × 200 mm²)", abs(w.doc.objects[0].world_geometry().area - 400) < 1)
a, b = sq(0, 0), sq(10, 0)
setdoc(a, b); w.path_op("divide")
areas = sorted(round(o.world_geometry().area) for o in w.doc.objects)
check("Teilen: untere Form in zwei Stücke, obere entfällt", areas == [200, 200])
check("Stücke behalten den Stil der unteren Form", all(o.fill["color"] == "#E53935" for o in w.doc.objects))

# ---- Ausrichten / Verteilen
a, b, c = sq(-30, 5, 10), sq(0, -8, 20), sq(40, 12, 14)
setdoc(a, b, c); select(a, b, c)
w.align_selected("top")
tops = [w.items[o.id].mapRectToScene(w.items[o.id].stitch_rect()).top() for o in (a, b, c)]
check("Oben ausrichten", max(tops) - min(tops) < 0.05)
w.align_selected("hcenter")
cx = [w.items[o.id].mapRectToScene(w.items[o.id].stitch_rect()).center().x() for o in (a, b, c)]
check("Horizontal zentrieren", max(cx) - min(cx) < 0.05)
a, b, c = sq(-40, 0, 10), sq(-25, 0, 10), sq(40, 0, 10)
setdoc(a, b, c); select(a, b, c)
w.distribute_selected("x")
rs = sorted((w.items[o.id].mapRectToScene(w.items[o.id].stitch_rect()) for o in (a, b, c)), key=lambda r: r.left())
gaps = [rs[1].left() - rs[0].right(), rs[2].left() - rs[1].right()]
check(f"Gleichmäßig verteilt (Lücken {gaps[0]:.1f} / {gaps[1]:.1f})", abs(gaps[0] - gaps[1]) < 0.05)
w.set_align_ref("hoop"); select(a)
w.align_selected("left")
hw = w.doc.hoop_size[0]
check("Am Rahmen ausrichten", abs(w.items[a.id].mapRectToScene(w.items[a.id].stitch_rect()).left() + hw / 2) < 0.05)
w.set_align_ref("selection")
# Gruppe zählt als Einheit
g1, g2, c3 = sq(-20, 0, 10), sq(-5, 0, 10), sq(30, 20, 10)
setdoc(g1, g2, c3); select(g1, g2); w.group_selected(); select(g1, c3)
before = g2.x - g1.x
w.align_selected("bottom")
check("Gruppe bleibt beim Ausrichten zusammen", abs((g2.x - g1.x) - before) < 1e-6 and abs(g1.y - g2.y) < 1e-6)

# ---- Versatz und Umriss
controls.ask_values.auto = {"d": 2.0, "round": False}
a = sq(0, 0, 20); setdoc(a); select(a)
w.offset_selected(True)
check("Erweitern um 2 mm (24 × 24)", abs(w.doc.objects[0].world_geometry().area - 576) < 1)
select(w.doc.objects[0]); w.offset_selected(False)
check("Schrumpfen um 2 mm", abs(w.doc.objects[0].world_geometry().area - 400) < 1)
controls.ask_values.auto = {"d": 3.0, "kind": "satin", "w": 3.0, "round": True}
t1, t2 = sq(-15, 0, 10), sq(15, 0, 10)
setdoc(t1, t2); select(t1, t2); w.outline_selected()
rings = [o for o in w.doc.objects if o.kind == "line"]
check("Umriss: je getrenntem Teil eine geschlossene Satinlinie", len(rings) == 2 and
      all(o.closed and o.border["type"] == "satin" for o in rings))
t1, t2 = sq(-6, 0, 10), sq(6, 0, 10)
setdoc(t1, t2); select(t1, t2); w.outline_selected()
ring = [o for o in w.doc.objects if o.kind == "line"]
check("Umriss: nahe Teile bekommen einen gemeinsamen Rand", len(ring) == 1)

# ---- Kopien
controls.ask_values.auto = {"cols": 3, "rows": 2, "gx": 5.0, "gy": 5.0}
a = sq(0, 0, 10); setdoc(a); select(a); w.copies_grid()
check("Raster 3 × 2 = 6 Objekte", len(w.doc.objects) == 6)
xs = sorted({round(o.x, 2) for o in w.doc.objects})
check("Rasterabstand = Breite + Lücke", len(xs) == 3 and abs((xs[1] - xs[0]) - (xs[2] - xs[1])) < 0.01
      and abs(xs[1] - xs[0] - 15) < 0.6)
controls.ask_values.auto = {"n": 6, "radius": 20.0, "rotate": True}
a = sq(0, 0, 6); setdoc(a); select(a); w.copies_circle()
objs = w.doc.objects
cy = a.y + 20
check("Kreis: 6 Objekte im Abstand 20 mm um den Mittelpunkt", len(objs) == 6 and
      all(abs(math.hypot(o.x - a.x, o.y - cy) - 20) < 0.6 for o in objs))
check("Kopien mitgedreht", sorted(round(o.rot) for o in objs) == [0, 60, 120, 180, 240, 300])

# ---- Stern / Spirale
controls.ask_values.auto = {"polygon": False, "n": 5, "size": 40.0, "ratio": 0.45, "rot": 0.0,
                            "round": False}
setdoc(); w.make_star()
st = w.doc.objects[-1]
check("Stern mit 10 Punkten", st.kind == "shape" and len(st.curve[0]) == 10)
controls.ask_values.auto = {"polygon": True, "n": 6, "size": 40.0, "ratio": 0.45, "rot": 0.0,
                            "round": False}
w.make_star()
check("Sechseck", len(w.doc.objects[-1].curve[0]) == 6)
controls.ask_values.auto = {"turns": 3.0, "size": 40.0, "inner": 1.0}
w.make_spiral()
sp = w.doc.objects[-1]
check("Spirale als Linie", sp.kind == "line" and abs(sp.world_geometry().bounds[2] -
                                                     sp.world_geometry().bounds[0] - 40) < 4)
controls.ask_values.auto = None

# ---- Sperren
a, b = sq(-20, 0), sq(20, 0); setdoc(a, b); select(a)
w.lock_selected()
check("Gesperrt: nicht mehr wählbar", a.locked and not (w.items[a.id].flags() & w.items[a.id].GraphicsItemFlag.ItemIsSelectable))
w.select_all()
check("Alles auswählen lässt Gesperrtes aus", w.selected_objects() == [b])
d = Document(); d.load_json(w.doc.to_json())
check("Sperre wird gespeichert", d.objects[0].locked)
w.unlock_all()
check("Alle entsperren", not a.locked and bool(w.items[a.id].flags() & w.items[a.id].GraphicsItemFlag.ItemIsSelectable))

# ---- Einrasten
a, b = sq(-30, 0, 10), sq(20, 15, 10)
setdoc(a, b); select(a)
w.canvas.snap = True
w.canvas._start_snap()
w.items[a.id].setPos(19.6 - 0.0, 3.3)        # fast bündig mit b (Mitte x = 20) und Raster y
w.canvas._apply_snap(True)
r = w.items[a.id].mapRectToScene(w.items[a.id].stitch_rect())
check("Rastet an der Mitte des anderen Objekts ein", abs(r.center().x() - 20) < 0.05)
check("Hilfslinie wird angezeigt", any(ax == "x" for ax, _ in w.canvas.snap_lines))
w.items[a.id].setPos(19.6, 3.3); w.canvas._apply_snap(False)
check("Alt: kein Einrasten", abs(w.items[a.id].pos().x() - 19.6) < 1e-9 and not w.canvas.snap_lines)

# Raster-Knopf mit Einrasten-Menü
menu = w.grid_btn.menu()
texts = [a.text() for a in menu.actions()]
check("Raster-Knopf: Menü mit »Einrasten ein/aus«", w.a_snap in menu.actions() and w.grid_btn.defaultAction() is w.a_grid)
w.a_snap.trigger()
check("Einrasten über das Menü ausschalten", not w.canvas.snap and w.prefs.get("snap") is False)
w.a_snap.trigger()
check("… und wieder einschalten", w.canvas.snap and w.prefs.get("snap") is True)
w.a_snap_grid.setChecked(False); w.a_snap_center.setChecked(False)
w.a_snap_objects.setChecked(False)
a, b = sq(-30, 0, 10), sq(23, 15, 10)
setdoc(a, b); select(a); w.canvas._start_snap()
w.items[a.id].setPos(22.6, 3.3); w.canvas._apply_snap(True)
cxa = w.items[a.id].mapRectToScene(w.items[a.id].stitch_rect()).center().x()
check("Ohne »an Objekten«: rastet nicht an der Objektmitte", abs(cxa - 22.6) < 1e-6)
w.a_snap_objects.setChecked(True)
w.canvas._start_snap(); w.items[a.id].setPos(22.6, 3.3); w.canvas._apply_snap(True)
cxa = w.items[a.id].mapRectToScene(w.items[a.id].stitch_rect()).center().x()
check("Mit »an Objekten«: rastet an der Objektmitte", abs(cxa - 23) < 0.05)
w.a_snap_grid.setChecked(False); w.a_snap_center.setChecked(False)
check("Einrast-Ziele werden gespeichert", w.prefs.get("snap_grid") is False and w.prefs.get("snap_center") is False)
w.a_snap_grid.setChecked(True); w.a_snap_center.setChecked(True)
step = [m for m in menu.actions() if m.menu() and m.text() == "Rasterweite"][0].menu()
[x for x in step.actions() if x.text() == "5 mm"][0].trigger()
check("Rasterweite über das Menü", w.opts.grid_step == 5 and w.prefs.get("grid_step") == 5)
[x for x in step.actions() if x.text() == "10 mm"][0].trigger()

# echter Mauszug: Objekt nahe an die Mitte eines anderen ziehen
a, b = sq(-30, 0, 10), sq(20, 15, 10)
setdoc(a, b); w.scene.clearSelection(); w.canvas.snap = True
c = w.canvas; vp = c.viewport(); v = lambda x, y: c.mapFromScene(QPointF(x, y))
w.set_tool("select")
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(a.x, a.y))
for i in range(1, 11):
    QTest.mouseMove(vp, v(a.x + i * 4.95, a.y + i * 0.5))
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(a.x + 49.5, a.y + 5))
ra = w.items[a.id].mapRectToScene(w.items[a.id].stitch_rect())
check(f"Mauszug rastet ein (Mitte x = {ra.center().x():.2f})", abs(ra.center().x() - 20) < 0.05
      and abs(a.x - w.items[a.id].pos().x()) < 1e-9)

# ---- Farbpipette
img = QImage(100, 100, QImage.Format_RGB32); img.fill(QColor("#2E7D32"))
path = OUT + "/vorlage.png"; img.save(path)
a = sq(0, 0); setdoc(a); select(a)
w.load_template(path) if False else None
from stichwizard import autodigitize
w.template_item.apply({"png": __import__("base64").b64encode(open(path, "rb").read()).decode(),
                       "width": 60.0, "x": 0.0, "y": 0.0, "opacity": 0.5, "visible": True,
                       "locked": True})
select(a); w.pick_color()
check("Pipette wartet auf Klick", w.canvas.tool == "pick")
w.on_point_picked(5.0, 5.0)
from stichwizard.threads import thread_name
check(f"Farbe aus der Vorlage übernommen ({a.fill['color']})", QColor(a.fill["color"]).green() > 100 and
      QColor(a.fill["color"]).red() < 90)

# ---- Menüband: alles passt
over = []
for i in range(w.ribbon.count()):
    w.ribbon.setCurrentIndex(i); QTest.qWait(10)
    sa = w.ribbon.currentWidget()
    sa = sa if isinstance(sa, QScrollArea) else sa.findChild(QScrollArea)
    if sa.widget().sizeHint().width() > 1440:
        over.append((w.ribbon.tabText(i), sa.widget().sizeHint().width()))
check(f"Alle Reiter passen in 1440 Pixel {over}", not over)
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
