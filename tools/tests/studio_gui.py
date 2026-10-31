"""Test (1.14): Designstudio – Bézier-Stift, Anfasser im Punkte-Werkzeug."""
import math
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import curves
from stichwizard.curves import CORNER, CTRL, CURVE
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
c = w.canvas; vp = c.viewport(); v = lambda x, y: c.mapFromScene(QPointF(x, y))
c.snap = False

# ---- Kurven: ohne Anfasser unverändert, mit Anfassern Bézier
old = [[0, 0, CORNER], [10, 0, CURVE], [10, 10, CURVE], [0, 10, CORNER]]
check("Ohne Anfasser: Abschnitte wie bisher (4)", len(curves.segments(old, True)) == 4)
bz = [[0, 0, CORNER], [0, -10, CTRL], [20, -10, CTRL], [20, 0, CORNER]]
pl = curves.polyline(bz, False)
check("Bézier-Abschnitt: Scheitel bei y = −7,5", abs(min(p[1] for p in pl) + 7.5) < 0.05)
c1a, c2a, M, c1b, c2b = curves.split_cubic((0, 0), (0, -10), (20, -10), (20, 0), 0.5)
check("Teilen nach De Casteljau trifft die Kurve", abs(M[0] - 10) < 1e-9 and abs(M[1] + 7.5) < 1e-9)

# ---- Bézier-Stift: Klick, Klick+Ziehen, Klick auf Start = Form
w.doc.objects = []; w.sync_items([])
w.set_tool("pen"); c.setFocus()
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(-20, 10))
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(0, -15))
for i in range(1, 6):
    QTest.mouseMove(vp, v(i * 2, -15))
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(10, -15))
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(20, 10))
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(-20, 10))
o = w.doc.objects[-1] if w.doc.objects else None
check("Stift: geschlossene Form entsteht", o is not None and o.kind == "shape")
types = [q[2] for q in o.curve[0]] if o else []
check(f"Glatter Punkt mit zwei Anfassern ({types})", types.count(CTRL) >= 2 and CURVE in types)
g = o.world_geometry()
from shapely.geometry import LineString as _LS
cut = g.intersection(_LS([(5, -40), (5, 40)]))
check(f"Runder Scheitel statt Ecke (bei x = 5: y = {cut.bounds[1]:.1f})",
      abs(g.bounds[1] + 15) < 0.2 and cut.bounds[1] < -12.0)

# offene Linie mit Enter
w.set_tool("pen"); c.setFocus()
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(-30, 30))
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(0, 30))
for i in range(1, 6):
    QTest.mouseMove(vp, v(0, 30 - i * 2))
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(0, 20))
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(30, 30))
QTest.keyClick(c, Qt.Key_Return)
ln = w.doc.objects[-1]
check("Stift + Enter: offene Linie mit Anfassern", ln.kind == "line" and
      CTRL in [q[2] for q in ln.line_nodes()])
check("Linie wird gestickt", sum(len(b) for _, b in ln.stitch_blocks()) > 10)
d = Document(); d.load_json(w.doc.to_json())
check("Anfasser werden gespeichert", CTRL in [q[2] for q in d.objects[-1].line_nodes()])

# ---- Punkte-Werkzeug: Anfasser sichtbar, ziehen, glatt halten
w.scene.clearSelection(); w.items[o.id].setSelected(True)
w.set_tool("nodes"); QTest.qWait(10)
st = c._node_state()
r = st["rings"][0]
smooth = [i for i, q in enumerate(r["pts"]) if q[2] == CURVE][0]
c._node_sel = {(0, smooth)}
vis = c._visible_ctrls(st)
check("Anfasser am gewählten Punkt sichtbar", len(vis) == 2)
before = [list(q) for q in r["pts"]]
j = sorted(i for _, i in vis)[0]
c._node_sel = {(0, j)}
c.move_nodes(0, -5)
st = c._node_state(); r = st["rings"][0]
A = r["pts"][smooth]
owner, _ = c._ctrl_owner(r)
other = [k for k, an in owner.items() if an == {smooth} and k != j][0]
h1, h2 = r["pts"][j], r["pts"][other]
cross = (h1[0] - A[0]) * (h2[1] - A[1]) - (h1[1] - A[1]) * (h2[0] - A[0])
check("Glatter Punkt: Gegen-Anfasser bleibt in einer Linie", abs(cross) < 1e-6)
# Kurvenpunkt verschieben nimmt Anfasser mit
st = c._node_state(); r = st["rings"][0]
c._node_sel = {(0, smooth)}
hx = [q[:2] for q in r["pts"] if q[2] == CTRL]
c.move_nodes(3, 0)
st = c._node_state(); r = st["rings"][0]
hx2 = [q[:2] for q in r["pts"] if q[2] == CTRL]
moved = sum(1 for a, b in zip(hx, hx2) if abs(b[0] - a[0] - 3) < 0.01)
check("Kurvenpunkt verschieben: seine Anfasser wandern mit", moved == 2)
# Punkt auf Bézier-Kante einfügen: Form bleibt
area0 = o.world_geometry().area
edge = None
for k, seg in enumerate(curves.segments(r["pts"], True)):
    if len(seg) > 6:
        mid = seg[len(seg) // 2]
        wx, wy = o.to_world(*mid)
        edge = {"ri": 0, "i": k, "t": 0.5, "pt": (wx, wy)}
        break
c._insert_edge(edge)
check("Punkt auf Bézierkurve einfügen: Form bleibt gleich",
      abs(o.world_geometry().area - area0) / area0 < 0.01)
# Anfasser entfernen / hinzufügen
c._node_sel = {(0, i) for i, q in enumerate(c._node_state()["rings"][0]["pts"]) if q[2] != CTRL}
c.remove_handles()
check("Anfasser entfernen", CTRL not in [q[2] for q in o.curve[0]])
c._node_sel = {(0, i) for i, q in enumerate(c._node_state()["rings"][0]["pts"]) if q[2] != CTRL}
a0 = o.world_geometry().area
c.add_handles()
check("Anfasser hinzufügen ohne die Form zu ändern", CTRL in [q[2] for q in o.curve[0]] and
      abs(o.world_geometry().area - a0) / a0 < 0.03)
# Kurvenpunkt löschen
st = c._node_state(); n0 = len([q for q in st["rings"][0]["pts"] if q[2] != CTRL])
c._node_sel = {(0, [i for i, q in enumerate(st["rings"][0]["pts"]) if q[2] != CTRL][0])}
c.delete_nodes()
st = c._node_state()
check("Kurvenpunkt löschen nimmt seine Anfasser mit",
      len([q for q in st["rings"][0]["pts"] if q[2] != CTRL]) == n0 - 1 and
      all(len(g[1]) <= 2 for g in curves.anchor_groups(st["rings"][0]["pts"], True)))
# ---- Ebenen
from shapely.geometry import box
from stichwizard.model import EmbObject
def sq(x, color="#E53935"):
    o = EmbObject("shape"); o.set_geometry(box(x - 5, -5, x + 5, 5)); o.fill["color"] = color; return o
w.doc = Document(); w.sync_items([]); w.apply_hoop()
lp = w.layers_panel
bottom = w.doc.layers[0]["id"]
a = sq(-20); w.add_objects([a])
lp.action.emit("add", bottom)
top = w.doc.active_layer
check("Neue Ebene ist aktiv", top != bottom and len(w.doc.layers) == 2)
b = sq(0, "#1E88E5"); w.add_objects([b])
check("Neue Objekte landen in der aktiven Ebene", b.layer == top and a.layer == bottom)
lp.action.emit("activate", bottom)
c3 = sq(20, "#43A047"); w.add_objects([c3])
check("Stickreihenfolge Ebene für Ebene (unten zuerst)", [o.id for o in w.doc.objects] == [a.id, c3.id, b.id])
lp.action.emit("toggle", top)
check("Ausgeblendete Ebene: nicht sichtbar und nicht gestickt",
      not w.items[b.id].isVisible() and all(col != "#1E88E5" for col, _ in w.doc.machine_blocks()))
lp.action.emit("toggle", top)
lp.action.emit("lock", bottom)
check("Gesperrte Ebene: Objekte nicht wählbar",
      not (w.items[a.id].flags() & w.items[a.id].GraphicsItemFlag.ItemIsSelectable))
lp.action.emit("lock", bottom)
w.scene.clearSelection(); w.items[c3.id].setSelected(True)
lp.action.emit("activate", top); lp.action.emit("move_here", top)
check("Auswahl in eine andere Ebene verschieben", c3.layer == top and w.doc.objects[-1] is c3)
lp.action.emit("up", bottom)
check("Ebenen umsortieren ändert die Stickreihenfolge", w.doc.objects[-1] is a)
lp.renamed.emit(top, "Schrift")
check("Ebene umbenennen", any(L["name"] == "Schrift" for L in w.doc.layers))
d2 = Document(); d2.load_json(w.doc.to_json())
check("Ebenen werden gespeichert", [L["name"] for L in d2.layers] == [L["name"] for L in w.doc.layers]
      and d2.find(c3.id).layer == top)
w.undo()
check("Rückgängig nimmt Ebenen-Änderungen zurück", all(L["name"] != "Schrift" for L in w.doc.layers))
lp.action.emit("delete", w.doc.layers[-1]["id"])
check("Ebene löschen: Objekte bleiben erhalten", len(w.doc.layers) == 1 and len(w.doc.objects) == 3)
check("Ebenen-Reiter zeigt die Ebenen", lp.list.count() == 1)
old = Document(); old.load_json('{"objects": [{"kind": "shape", "geom_wkt": "POLYGON ((0 0, 5 0, 5 5, 0 0))"}]}')
check("Alte Projekte: eine Ebene, alles darin", len(old.layers) == 1 and old.objects[0].layer == old.layers[0]["id"])
# ---- Bibliothek
from stichwizard import controls, library
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
w.doc = Document(); w.sync_items([]); w.apply_hoop()
x1, x2 = sq(30), sq(45, "#1E88E5")
w.add_objects([x1, x2]); w.group_selected()
controls.ask_values.auto = {"name": "Zwei Quadrate", "cat": "Test"}
w.on_library_action("save_sel", "")
its = library.items()
check("Auswahl in der Bibliothek gespeichert", [n for _, n, _ in its] == ["Zwei Quadrate"] and
      os.path.exists(its[0][0]))
check("Bibliothek zeigt das Element mit Vorschaubild", w.library_panel.list.count() == 1 and
      not w.library_panel.list.item(0).icon().isNull())
path = its[0][0]
w.on_library_action("insert", path)
new = w.selected_objects()
check("Einfügen: neue Objekte in der Rahmenmitte", len(new) == 2 and all(o.id not in (x1.id, x2.id) for o in new)
      and abs((new[0].x + new[1].x) / 2) < 1.0)
check("Gruppe bleibt erhalten (eigene neue Gruppe)", new[0].group and new[0].group == new[1].group
      and new[0].group != x1.group)
controls.ask_values.auto = {"name": "Mein Design", "cat": "Designs"}
w.on_library_action("save_all", "")
check("Ganzes Design speichern, Kategorien", library.categories() == ["Designs", "Test"])
controls.ask_values.auto = {"name": "Doppel-Quadrat", "cat": "Formen"}
w.on_library_action("rename", path)
check("Umbenennen und Kategorie wechseln", any(n == "Doppel-Quadrat" and c == "Formen" for _, n, c in library.items())
      and "Test" not in library.categories())
w.library_panel.search.setText("doppel")
check("Suche in der Bibliothek", w.library_panel.list.count() == 1)
w.library_panel.search.setText("")
w.on_library_action("delete", [p for p, n, _ in library.items() if n == "Mein Design"][0])
check("Löschen", [n for _, n, _ in library.items()] == ["Doppel-Quadrat"])
controls.ask_values.auto = None
# ---- Vorlagen
from stichwizard import templates
for key, title, *_ in templates.TEMPLATES:
    objs = templates.build(key)
    d = Document(); d.objects = objs; d.apply_layer_flags()
    check(f"Vorlage »{title}« ergibt Stiche", d.stats()["stitches"] > 500)
objs = templates.build("badge", {"name": "Ben", "width": 120.0})
d = Document(); d.objects = objs; d.apply_layer_flags()
check("Vorlage passt sich an (Name, Breite 120 mm)", any(o.kind == "text" and o.text["text"] == "Ben" for o in objs)
      and abs(d.stats()["width"] - 120) < 6)
dlg = templates.TemplateDialog(w)
dlg.list.setCurrentRow(2); QTest.qWait(50)
kind, field = dlg.fields["top"]
field.setText("VEREIN"); dlg.update_preview()
check("Vorlagen-Fenster: Felder und Vorschau", dlg.preview.view.has_image() and
      any(o.kind == "text" and o.text["text"] == "VEREIN" for o in dlg.objects))
templates.TemplateDialog = lambda parent=None: dlg
dlg.exec = lambda: True
w.doc = Document(); w.sync_items([]); w.apply_hoop()
w.open_templates()
check("Vorlage wird als Gruppe eingefügt", len(w.doc.objects) >= 3 and
      len({o.group for o in w.doc.objects}) == 1 and w.doc.objects[0].group)

# ---- Schrift-Werkstatt
from stichwizard import embfont, fontmaker
fid = fontmaker.font_from_system("Test Sans", "DejaVu Sans", 10.0, "AbgW?")
info = next((f for f in embfont.font_index() if f["id"] == fid), None)
check("Schrift aus Computerschrift erscheint in der Auswahl", info and info["chars"] >= set("AbgW?"))
t = EmbObject("text"); t.text.update(text="AbgW", size=10, embfont=fid); t.fill["color"] = "#123456"
bl = t.stitch_blocks()
check("Eigene Schrift wird gestickt (in der Schriftfarbe)", bl and {c for c, _ in bl} == {"#123456"}
      and sum(len(b) for _, b in bl) > 200)
g = fontmaker.load_font(fid)["glyphs"]
check("Zeichen mit Unterlänge reicht unter die Grundlinie",
      max(y for e in g["g"]["e"] for pts in (e.get("lines") or e.get("rings") or [])
          for _, y in pts) > 1.5)
# eigenes Zeichen aus Objekten: Satinsäule + Linie
col = EmbObject("satin"); col.set_satin([[0, -10, 0], [0, 10, 0]], [[3, -10, 0], [3, 10, 0]])
col.x, col.y = 50, 0
ln = EmbObject("line"); ln.set_points([(0, 0), (10, 0)]); ln.border.update(type="triple"); ln.x, ln.y = 56, 0
fid2 = fontmaker.glyph_from_objects("Meine Hand", "I", [col, ln], 20.0)
f2 = fontmaker.load_font(fid2)
els = f2["glyphs"]["I"]["e"]
check("Eigenes Zeichen: Satinsäule und Bohnenstich übernommen", [e["t"] for e in els] == ["satin", "run"]
      and els[1]["bn"] == 1)
ys = [y for e in els for pts in (e.get("a", []), e.get("b", [])) for _, y in pts]
check("Grundlinie = Unterkante, Versalhöhe 20 mm", abs(max(ys)) < 0.05 and abs(min(ys) + 20) < 0.05)
t2 = EmbObject("text"); t2.text.update(text="II", size=20, embfont=fid2)
check("Eigene Zeichen-Schrift setzt Text", sum(len(b) for _, b in t2.stitch_blocks()) > 100)
fw = fontmaker.FontWorkshop(w, [col, ln])
check("Werkstatt-Fenster listet die eigenen Schriften", fw.fonts.count() == 2 and fw.tabs.currentIndex() == 1)
fontmaker.delete_font(fid)
check("Eigene Schrift löschen", not embfont.exists(fid))

# ---- Menüband: Designstudio-Funktionen in den Arbeitsschritt-Reitern (ab 1.15)
from PySide6.QtWidgets import QScrollArea
tabs = [w.ribbon.tabText(i) for i in range(w.ribbon.count())]
check("Designstudio-Funktionen in Erstellen/Schrift/Anordnen", "Designstudio" not in tabs
      and {"Erstellen", "Schrift", "Anordnen"} <= set(tabs))
over = []
for i in range(w.ribbon.count()):
    w.ribbon.setCurrentIndex(i); QTest.qWait(10)
    sa = w.ribbon.currentWidget(); sa = sa if isinstance(sa, QScrollArea) else sa.findChild(QScrollArea)
    if sa.widget().sizeHint().width() > 1440:
        over.append(w.ribbon.tabText(i))
check(f"Alle Reiter passen in 1440 Pixel {over}", not over)
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
