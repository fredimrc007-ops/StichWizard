"""Test (1.4): Text an Pfad, geführte Füllung, Redwork/Auto-Route, Start-/Endpunkt, Satin-Feinheiten."""
import math
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from collections import Counter
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion')
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, embfont, help as shelp
from stichwizard.mainwindow import MainWindow, RibbonButton
from stichwizard.model import EmbObject
from shapely.geometry import LineString, Point, box
OUT = sys.argv[1]
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
c = w.canvas; vp = c.viewport(); v = lambda x, y: c.mapFromScene(QPointF(x, y))
def add(o):
    w.add_objects([o]); return o
def clear():
    w.doc.objects = []; w.sync_items([])
def select(*objs):
    w.scene.clearSelection()
    for o in objs:
        w.items[o.id].setSelected(True)
    QTest.qWait(10)
def world_sts(o):
    return [s for _, b in o.world_blocks() for s in b if s[2] == engine.STITCH]
def jumps_inside(o):
    return sum(1 for _, b in o.stitch_blocks() for s in b[1:] if s[2] in (engine.JUMP, engine.TRIM))
def line(pts, name="Linie"):
    o = EmbObject("line", name); o.set_points(pts); o.border.update(type="run", stitch_len=2.5)
    return add(o)
def visible_row(card, widget):
    return card.form.isRowVisible(widget)
# --- Oberfläche: alle neuen Knöpfe im Menüband
buttons = {b.defaultAction() for b in w.findChildren(RibbonButton)}
for a in (w.a_textpath, w.a_guided, w.a_detach, w.a_redwork, w.a_autoroute, w.a_startpt,
          w.a_endpt, w.a_clearpts):
    check(f"Menüband: »{a.text().replace(chr(10), ' ')}«", a in buttons)

# ============ 1. Schriftzug entlang Pfad
clear()
path = [(-45, 10), (-15, -12), (15, -12), (45, 10)]
ln = line(path)
t = add(EmbObject("text")); t.text.update(text="Sticken", size=9, bold=True); t.x, t.y = 0, 40
w.rebuild([t])
select(t, ln); w.a_textpath.trigger()
guide = LineString(path)
g = t.world_geometry()
check("Text an Pfad: Linie übernommen", ln not in w.doc.objects and t.text.get("path"))
check(f"Computerschrift liegt auf dem Pfad (Abstand {g.distance(guide):.2f} mm)",
      g.distance(guide) < 1.5 and guide.buffer(9 * 1.6).contains(g))
check("Buchstaben stehen oberhalb der Linie (links der Laufrichtung)",
      g.centroid.y < guide.interpolate(guide.project(g.centroid)).y)
select(t); w.props.refresh()
check("Eigenschaften: Zeile »Am Pfad« sichtbar, Bogen ausgeblendet",
      visible_row(w.props.c_text, w.props.t_prow) and not visible_row(w.props.c_text, w.props.t_arc))
xc = t.world_geometry().centroid.x
w.props.t_palign.setCurrentIndex(w.props.t_palign.findData("start")); w.props._apply()
check(f"Ausrichtung »Am Anfang« schiebt den Text nach links ({xc:.1f} → "
      f"{t.world_geometry().centroid.x:.1f})", t.world_geometry().centroid.x < xc - 5)
w.props.t_pflip.setChecked(True); w.props._apply()
g2 = t.world_geometry()
check("»Andere Seite«: Text unter der Linie",
      g2.centroid.y > guide.interpolate(guide.project(g2.centroid)).y)
w.props.t_pflip.setChecked(False); w.props.t_palign.setCurrentIndex(1); w.props._apply()
# Stickschrift
fid = next(f["id"] for f in embfont.font_index() if not embfont.missing_chars(f, "Sticken")
           and f["min"] <= 12 <= f["max"] + 10)
t.text.update(embfont=fid, size=max(12, embfont.font_index()[0]["min"])); w.rebuild([t])
sts = world_sts(t)
far = max(guide.distance(Point(s[:2])) for s in sts)
check(f"Stickschrift am Pfad ({len(sts)} Stiche, max. {far:.1f} mm von der Linie)",
      len(sts) > 300 and far < t.text["size"] * 1.8)
snap = w.doc.to_json()
w.doc.load_json(snap)
t = w.doc.objects[-1]
check("Pfad wird gespeichert", t.text.get("path") and len(t.text["path"]) == 4)
w.sync_items([t.id]); select(t); w.a_detach.trigger()
check("Pfad lösen: Linie wieder da, Text gerade",
      not t.text.get("path") and any(o.kind == "line" for o in w.doc.objects))

# ============ 2. Geführte Füllung
clear()
sh = add(EmbObject("shape")); sh.set_geometry(box(-30, -20, 30, 20))
sh.fill.update(underlay=False, density=0.5)
gl = line([(-30, 0), (-10, -10), (10, 10), (30, 0)])
select(sh, gl); w.a_guided.trigger()
check("Geführte Füllung zugeordnet", sh.fill["type"] == "guided" and sh.fill.get("guide")
      and gl not in w.doc.objects)
def mean_angle(o, x0, x1):
    sts = [s for _, b in o.stitch_blocks() for s in b if s[2] == engine.STITCH]
    angs = []
    for p, q in zip(sts, sts[1:]):
        if x0 < (p[0] + q[0]) / 2 < x1 and -15 < p[1] < 15 and math.dist(p[:2], q[:2]) > 1.5:
            a = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
            a = (a + 90) % 180 - 90
            angs.append(a)
    return sum(angs) / max(1, len(angs))
mid, left = mean_angle(sh, -6, 6), mean_angle(sh, -28, -14)
check(f"Reihen folgen der Linie (Mitte {mid:.0f}°, links {left:.0f}°)", 30 < mid < 60 and -40 < left < -12)
select(sh); w.props.refresh()
check("Eigenschaften: Stichart »Geführte Füllung«, Führungslinie sichtbar",
      w.props.f_type.currentData() == "guided" and visible_row(w.props.c_fill, w.props.f_guide_row))
n1 = sum(1 for _, b in sh.stitch_blocks() for s in b if s[2] == engine.STITCH)
w.props.f_density.setValue(0.8); w.props._apply()
n2 = sum(1 for _, b in sh.stitch_blocks() for s in b if s[2] == engine.STITCH)
check(f"Reihenabstand wirkt ({n1} → {n2} Stiche)", n2 < n1 * 0.8)
sh.rot = 90; sh._skey = None
turned = mean_angle(sh, -12, 12)
check(f"Drehen dreht die Führung mit (Mitte {mid:.0f}° → {turned:.0f}°)", turned < -5 and mid - turned > 40)
sh.rot = 0; sh._skey = None
select(sh); w.a_detach.trigger()
check("Führungslinie herauslösen", not sh.fill.get("guide") and sh.fill["type"] == "tatami"
      and sum(o.kind == "line" for o in w.doc.objects) == 1)

# ============ 3. Redwork / Auto-Route
def grid():
    clear()
    return [line([(-30, -10), (30, -10)]), line([(-30, 10), (30, 10)]),
            line([(-20, -20), (-20, 20)]), line([(0, -20), (0, 20)]), line([(20, -20), (20, 9.7)])]
def uses(o):
    pts = [o.to_world(*p) for p in o.points]
    cnt = Counter()
    for a, b in zip(pts, pts[1:]):
        cnt[tuple(sorted(((round(a[0], 1), round(a[1], 1)), (round(b[0], 1), round(b[1], 1)))))] += 1
    return cnt, sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
src = grid(); total = sum(o.world_geometry().length for o in src)
w.select_all(); w.a_redwork.trigger()
res = [o for o in w.doc.objects if o.kind == "line"]
cnt, ln_r = uses(res[0])
sts = world_sts(res[0])
holes = len({(round(s[0], 2), round(s[1], 2)) for s in sts})
check(f"Redwork: 5 Linien → {len(res)} Weg, ohne Sprung", len(res) == 1 and jumps_inside(res[0]) == 0)
check(f"Redwork: jede Strecke genau zweimal ({ln_r:.0f} = 2 × {total:.0f} mm)",
      max(cnt.values()) == 2 and abs(ln_r - 2 * total) < 3)
p0, p1 = res[0].to_world(*res[0].points[0]), res[0].to_world(*res[0].points[-1])
check("Redwork endet am Anfang", math.dist(p0, p1) < 0.01)
check(f"Hin- und Rückweg in denselben Einstichen ({holes} Einstichstellen bei {len(sts)} Stichen)",
      holes < len(sts) * 0.6 and res[0].border.get("corners"))
src = grid()
w.select_all(); w.a_autoroute.trigger()
res = [o for o in w.doc.objects if o.kind == "line"]
cnt, ln_a = uses(res[0])
check(f"Auto-Route: ein Weg ohne Sprung, höchstens zweimal je Strecke ({ln_a:.0f} mm)",
      len(res) == 1 and jumps_inside(res[0]) == 0 and max(cnt.values()) <= 2 and total - 1 < ln_a < ln_r)
clear(); a = line([(-30, 0), (-10, 0)]); b = line([(10, 0), (30, 0)]); x = line([(-20, -5), (-20, 5)])
w.select_all(); w.a_autoroute.trigger()
check("Getrennte Linien → getrennte Wege", sum(o.kind == "line" for o in w.doc.objects) == 2)
w.undo()
check("Rückgängig stellt die Linien wieder her", sum(o.kind == "line" for o in w.doc.objects) == 3)

# ============ 4. Start-/Endpunkt
clear()
sq = add(EmbObject("shape")); sq.set_geometry(box(-25, -15, 25, 15))
select(sq); w.a_startpt.trigger()
check("Startpunkt-Werkzeug aktiv", c.tool == "pick")
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(22, 12)); QTest.qWait(10)
check("Klick setzt den Startpunkt", sq.fill.get("start") and c.tool == "select")
first = world_sts(sq)[0]
check(f"Fläche beginnt am Startpunkt ({first[0]:.1f}, {first[1]:.1f})", math.dist(first[:2], (22, 12)) < 3.5)
select(sq); w.props.refresh()
check("Eigenschaften zeigen Start ✓", visible_row(w.props.c_fill, w.props.f_pts_row)
      and "Start ✓" in w.props.f_pts.text())
w.props.action.emit("pick_end")
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(-22, -12)); QTest.qWait(10)
last = world_sts(sq)[-1]
check(f"Fläche endet am Endpunkt ({last[0]:.1f}, {last[1]:.1f})", math.dist(last[:2], (-22, -12)) < 1.0)
sq.border.update(type="run"); sq._skey = None; w.rebuild([sq])
check("Mit Rand: endet trotzdem nahe am Endpunkt", math.dist(world_sts(sq)[-1][:2], (-22, -12)) < 3.5)
sa = EmbObject("satin"); sa.x, sa.y = 0, 40
sa.set_satin([[-20, 0, 0], [20, 0, 0]], [[-20, 5, 0], [20, 5, 0]]); add(sa)
f0 = world_sts(sa)[0]
select(sa); w.a_startpt.trigger(); QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(20, 42.5))
f1, l1 = world_sts(sa)[0], world_sts(sa)[-1]
check(f"Satinsäule beginnt rechts (vorher x={f0[0]:.0f}, jetzt x={f1[0]:.0f}, Ende x={l1[0]:.0f})",
      f0[0] < 0 < f1[0] and l1[0] < 0)
select(sa); w.a_endpt.trigger(); QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(20, 42.5))
l2 = world_sts(sa)[-1]
check(f"Start und Ende rechts: Unterlage hin, Satin zurück (Ende x={l2[0]:.0f})", l2[0] > 15)
select(sa); w.a_clearpts.trigger()
check("Start/Ende entfernen", not sa.fill.get("start") and not sa.fill.get("end"))
w.undo()
check("Rückgängig: Punkte wieder da", w.doc.find(sa.id).fill.get("start") is not None)

# ============ 5. Satin: kurze Stiche, Zufalls-Split
clear()
A = [[12 * math.cos(k * math.pi / 8), 12 * math.sin(k * math.pi / 8), 1] for k in range(9)]
B = [[5 * math.cos(k * math.pi / 8), 5 * math.sin(k * math.pi / 8), 1] for k in range(9)]
cs = EmbObject("satin"); cs.set_satin(B, A); cs.fill["underlay"] = False; add(cs)
select(cs); w.props.refresh()
check("Eigenschaften: kurze Stiche und Teilung sichtbar",
      all(visible_row(w.props.c_fill, x) for x in (w.props.f_short, w.props.f_split, w.props.f_splitrand)))
def inner(o):
    sts = [s for _, b in o.stitch_blocks() for s in b if s[2] == engine.STITCH]
    return sum(1 for s in sts if 5.3 < math.hypot(s[0], s[1]) < 7.5)
w.props.f_short.setValue(0); w.props._apply(); a0 = inner(cs)
w.props.f_short.setValue(25); w.props._apply(); a1 = inner(cs)
check(f"Kurze Stiche an der Innenkurve ({a0} → {a1} eingerückte Einstiche)", a0 <= 4 and a1 > a0 + 20)
ws = EmbObject("satin"); ws.x = 0; ws.y = 0
ws.set_satin([[-20, -10, 0], [20, -10, 0]], [[-20, 10, 0], [20, 10, 0]]); ws.fill["underlay"] = False
add(ws); select(ws); w.props.refresh()
def splits(o):
    sts = [s for _, b in o.stitch_blocks() for s in b if s[2] == engine.STITCH]
    return [s[1] for s in sts if -8.5 < s[1] < 8.5]
w.props.f_split.setValue(7.0); w.props._apply()
regular = splits(ws)
top = [s for _, b in ws.stitch_blocks() for s in b if s[2] == engine.STITCH]
longest = max(math.dist(p[:2], q[:2]) for p, q in zip(top, top[1:]))
check(f"Breite Säule geteilt (längster Stich {longest:.1f} mm ≤ 7 mm)", longest <= 7.2)
w.props.f_splitrand.setChecked(True); w.props._apply()
rand = splits(ws)
spread = lambda ys: len({round(y, 1) for y in ys})
check(f"Zufalls-Split: Teilungspunkte gestreut ({spread(regular)} → {spread(rand)} Höhen)",
      ws.fill["split_random"] and spread(rand) > spread(regular) * 3)

# ============ Hilfe und README
readme = open(os.path.join(__file__.rsplit("/tools/", 1)[0], "README.md"), encoding="utf-8").read()
for word in ("Text an Pfad", "Geführte Füllung", "Redwork", "Auto-Route", "Startpunkt", "Kurze Stiche",
             "Zufällig teilen"):
    check(f"Hilfe und README erklären »{word}«", word in shelp.GUIDE and word in readme)
print("ERGEBNIS:", sum(ok), "/", len(ok))
