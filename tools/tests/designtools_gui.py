"""Test (1.18): Hüllformen, einzelne Buchstaben, Motivstich-Linie, Schatten, Mehrfach-Rahmung,
Lineal/Messen, Garnvorrat, Schneidedatei."""
import math
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from shapely.geometry import box
import pyembroidery as pe
from stichwizard import controls, engine, multihoop, textfx, threads
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)


def stitches(o):
    return sum(1 for _, b in o.stitch_blocks() for s in b if s[2] == engine.STITCH)


def setdoc(*objs):
    w.doc.objects = list(objs)
    w.sync_items([o.id for o in objs])
    QTest.qWait(5)


# ---- Hüllformen
for font in ("barstitch_bold", ""):
    kind = "Stickschrift" if font else "Computerschrift"
    base = EmbObject("text", "T"); base.text.update(text="TEAM", size=20, embfont=font)
    g0 = base.local_geometry()
    bad = []
    for key, _, _ in textfx.ENVELOPES[1:]:
        o = EmbObject("text", "T"); o.text.update(text="TEAM", size=20, embfont=font, env=key,
                                                env_amount=0.5)
        g = o.local_geometry()
        if stitches(o) < 100 or g.symmetric_difference(g0).area < 0.1 * g0.area:
            bad.append(key)
    check(f"{kind}: alle Hüllformen verformen und sticken {bad}", not bad)
o = EmbObject("text", "T"); o.text.update(text="TEAM", size=20, embfont="barstitch_bold",
                                        env="arch_top", env_amount=0.5)
oc = o.letter_centers()
check("Bogen oben: mittlere Buchstaben höher als die äußeren", oc[1][3] < oc[0][3] and oc[2][3] < oc[3][3])
t = EmbObject("text", "T"); t.text.update(text="TEAM", size=20, embfont="barstitch_bold")
setdoc(t)
w.set_envelope("barrel")
check("Menü Hüllform setzt die Form am gewählten Schriftzug", t.text["env"] == "barrel")
check("Eigenschaften zeigen die Hüllform", w.props.t_env.currentData() == "barrel")

# ---- einzelne Buchstaben
for font in ("barstitch_bold", ""):
    t = EmbObject("text", "T"); t.text.update(text="TEAM", size=20, embfont=font)
    setdoc(t)
    before = t.letter_centers()
    w.on_letter_moved(t, 2, 3.0, -4.0)
    after = t.letter_centers()
    d = [(round(b[2] - a[2], 2), round(b[3] - a[3], 2)) for a, b in zip(before, after)]
    check(f"{'Stickschrift' if font else 'Computerschrift'}: nur »A« verschoben {d}",
          d[2] == (3.0, -4.0) and all(x == (0.0, 0.0) for i, x in enumerate(d) if i != 2))
check("Versatz gespeichert", t.text["letters"] == {"2": [3.0, -4.0, 0.0, 100.0]})
check("Eigenschaften: Buchstabe 3 gewählt mit Versatz",
      w.props.l_pick.currentData() == 2 and abs(w.props.l_dx.value() - 3.0) < 1e-6)
w.props.l_rot.setValue(20); w.props._apply()
check("Drehung über die Eigenschaften", t.text["letters"]["2"][2] == 20)
w.props._letter_reset(True)
check("Alle Buchstaben zurücksetzen", not t.text["letters"])
# auf der Arbeitsfläche ziehen (Punkte-Werkzeug)
w.set_tool("nodes"); QTest.qWait(20)
c = w.canvas; vp = c.viewport()
pts = c._letter_state()["pts"]
check("Anfasser für jeden Buchstaben", len(pts) == 4)
a = c.mapFromScene(pts[0][2]); b = c.mapFromScene(pts[0][2] + QPointF(0, -5))
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, a); QTest.mouseMove(vp, b)
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, b); QTest.qWait(30)
dy = t.text.get("letters", {}).get("0", [0, 0])[1]
check(f"Buchstabe auf der Arbeitsfläche hochgezogen (dy {dy:.1f})", -6 < dy < -4)
w.set_tool("select")

# ---- Motivstich-Linie
bad = []
for key, _, _ in engine.LINE_MOTIFS:
    ln = EmbObject("line"); ln.set_points([(-40, 0), (40, 0)])
    ln.border.update(type="motif", motif=key, width=8, gap=2)
    n = stitches(ln)
    ys = [s_[1] for _, b_ in ln.stitch_blocks() for s_ in b_]
    if n < 30 or max(ys) - min(ys) < 2:
        bad.append(key)
check(f"Alle Motive sticken entlang der Linie {bad}", not bad)
h = EmbObject("shape"); h.set_geometry(box(-20, -20, 20, 20)); h.border.update(type="motif", motif="scallop", width=5)
check("Motivstich auch als Rand einer Form", stitches(h) > 100)
ln = EmbObject("line"); ln.set_points([(-40, 0), (40, 0)])
ln.border.update(type="motif", motif="heart", width=8, gap=2, motif_alt=True)
ys = [s[1] for _, b in ln.stitch_blocks() for s in b]
check("Abwechselnd oben/unten", min(ys) < -4 and max(ys) > 4)
setdoc(ln)
check("Eigenschaften: Motiv-Felder sichtbar", w.props.c_border.form.isRowVisible(w.props.b_motif))

# ---- Schatten
t = EmbObject("text", "T"); t.text.update(text="ABC", size=20, embfont="barstitch_bold")
setdoc(t)
controls.ask_values.auto = {"dx": 1.5, "dy": 1.5, "kind": "fill", "color": "#111111", "cut": True}
w.shadow_selected()
controls.ask_values.auto = None
sh = w.doc.objects[0]
check("Schatten liegt dahinter (wird zuerst gestickt)", sh.name == "Schatten" and w.doc.objects[1] is t)
check("Schatten versetzt nach rechts unten",
      sh.world_geometry().bounds[2] > t.world_geometry().bounds[2] + 1.0)
check("Verdeckter Teil ausgespart", sh.world_geometry().area < t.world_geometry().area * 0.8)

# ---- Mehrfach-Rahmung
bg = EmbObject("shape", "Hintergrund"); bg.set_geometry(box(-200, -50, 200, 50))
s1 = EmbObject("shape", "links"); s1.set_geometry(box(-170, -20, -140, 20)); s1.fill["color"] = "#E53935"
s2 = EmbObject("shape", "rechts"); s2.set_geometry(box(140, -20, 170, 20)); s2.fill["color"] = "#43A047"
setdoc(bg, s1, s2)
hi = threads.hoop_for_size(190, 140)
parts = multihoop.split(w.doc, hi, 190, 140, 12, True)
check(f"400 mm breit in 190er Rahmen: 3 Teile ({len(parts)})", len(parts) == 3)
check("Jeder Teil passt in den Rahmen",
      all((lambda st: st["width"] <= 190.5 and st["height"] <= 140.5)(p["doc"].stats()) for p in parts))
names = [[o.name for o in p["doc"].objects] for p in parts]
check("Kleine Formen bleiben ganz (links in Teil 1, rechts in Teil 3)",
      "links" in names[0] and "rechts" in names[-1])
marks = [sum(1 for n in ns if n.startswith("Passmarke")) for ns in names]
check(f"Passmarken: je Nachbarpaar 2, in beiden Teilen {marks}", marks == [2, 4, 2])
check("Passmarke am Ende von Teil 1 und am Anfang von Teil 2",
      names[0][-1].startswith("Passmarke") and names[1][0].startswith("Passmarke"))
total = sum(round(o.world_geometry().area) for p in parts for o in p["doc"].objects
            if o.name.startswith("Hintergrund"))
check(f"Großer Hintergrund zerschnitten, Fläche bleibt (~40.000 mm², {total})", 39500 < total < 41500)
from stichwizard.multihoop import MultiHoopDialog
dlg = MultiHoopDialog(w)
dlg.hoop.setCurrentIndex(dlg.hoop.findData(hi))
files = dlg.export_parts(OUT, "dst")
check("Teile und Übersicht exportiert", len(files) == 4 and all(os.path.getsize(f) > 100 for f in files))
dlg.close()
small = EmbObject("shape"); small.set_geometry(box(-20, -20, 20, 20))
setdoc(small)
check("Kleines Design: eine Rahmung", len(multihoop.split(w.doc, hi, 190, 140)) == 1)

# ---- Lineal und Messen
check("Lineal ist an", w.canvas.show_rulers and w.a_rulers.isChecked())
w.a_rulers.trigger()
check("Lineal aus und gespeichert", not w.canvas.show_rulers and w.prefs.get("rulers") is False)
w.a_rulers.trigger()
w.set_tool("measure"); QTest.qWait(20)
c = w.canvas; vp = c.viewport()
a = c.mapFromScene(QPointF(-30, 0)); b = c.mapFromScene(QPointF(30, 0))
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, a); QTest.mouseMove(vp, b)
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, b); QTest.qWait(20)
m = c._measure
check(f"Messen: ca. 60 mm ({w.lbl_tip.text()})", abs(math.hypot(m[1].x() - m[0].x(), m[1].y() - m[0].y()) - 60) < 1.5
      and "Gemessen" in w.lbl_tip.text())
w.set_tool("select")

# ---- Garnvorrat
w.prefs.set("thread_stock", [{"chart": "", "num": "", "name": "Rot", "color": "#C62828"},
                             {"chart": "", "num": "", "name": "Blau", "color": "#1565C0"}])
r1 = EmbObject("shape"); r1.set_geometry(box(-10, -10, 0, 0)); r1.fill["color"] = "#FF1744"
r2 = EmbObject("shape"); r2.set_geometry(box(5, 5, 15, 15)); r2.fill["color"] = "#2979FF"
setdoc(r1, r2)
w.snap_to_stock()
check("Design auf Garnvorrat umgestellt", r1.fill["color"] == "#C62828" and r2.fill["color"] == "#1565C0")

# ---- Schneidedatei
ap = EmbObject("shape", "Herz-Stoff"); ap.set_geometry(box(-25, -15, 25, 15)); ap.fill["type"] = "applique"
setdoc(ap)
path = w.export_cutfile(os.path.join(OUT, "schnitt.svg"), 1.0)
svg = open(path, encoding="utf-8").read()
check("Schneidedatei in Millimetern mit einer Form", 'mm"' in svg and svg.count("<path") == 1)
check("Zugabe 1 mm: Breite 50 + 2 + Rand", 'width="62.00mm"' in svg)

# ---- Menüband passt
over = []
for i in range(w.ribbon.count()):
    w.ribbon.setCurrentIndex(i); QTest.qWait(10)
    sa = w.ribbon.currentWidget(); sa = sa if isinstance(sa, QScrollArea) else sa.findChild(QScrollArea)
    if sa.widget().sizeHint().width() > 1440:
        over.append((w.ribbon.tabText(i), sa.widget().sizeHint().width()))
check(f"Alle Reiter passen in 1440 Pixel {over}", not over)
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
