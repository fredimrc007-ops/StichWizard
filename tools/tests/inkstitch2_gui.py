"""Test (1.9): weitere Ink/Stitch-Funktionen – Feinheiten (Unterlage, Erweitern, Zufall,
Vernähstich-Arten), Satin-Unterlage, Auto-Satin, mehrfarbiger Satin, Bohnenstich-Muster,
Farbverlauf mit mehreren Farben, Tartan, weitere Exportformate und ZIP."""
import math
import os
import sys
import zipfile
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, fileio, shapes
from stichwizard.api import ApiError, DesignAPI
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
from stichwizard.engine import JUMP, STITCH, TRIM
from shapely.geometry import MultiPoint
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
api = DesignAPI(w)

def rect(wd=30, ht=20):
    o = EmbObject("shape"); o.set_geometry(shapes.rounded_rect(wd, ht, 3)); return o
def n_st(o):
    return sum(1 for _, s in o.stitch_blocks() for p in s if p[2] == STITCH)
def pts(o):
    return [p[:2] for _, s in o.stitch_blocks() for p in s if p[2] == STITCH]
def column(x0, y0, x1, y1, half=1.5):
    o = EmbObject("satin")
    dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy); nx, ny = -dy / L * half, dx / L * half
    o.set_satin([[x0 + nx, y0 + ny, 0], [x1 + nx, y1 + ny, 0]],
                [[x0 - nx, y0 - ny, 0], [x1 - nx, y1 - ny, 0]])
    o.fill["color"] = "#E53935"
    return o
def real_jumps(doc):
    s = [p for _, b in doc.machine_blocks() for p in b]
    return sum(1 for i, p in enumerate(s) if p[2] == JUMP and i and engine.dist(p, s[i - 1]) > 1.6)

# ============ Gruppe A: Feinheiten
o = rect(); base = n_st(o)
o.fill["ul_layers"] = 2
check("Unterlage in zwei Lagen: mehr Stiche", n_st(o) > base)
o.fill.update(ul_layers=1, ul_contour=False)
check("Unterlage ohne Randlinie: weniger Stiche", n_st(o) < base)
o.fill.update(ul_contour=True, ul_spacing=4.0)
check("Größerer Unterlage-Abstand: weniger Stiche", n_st(o) < base)
o.fill.update(ul_spacing=2.2, expand=1.5, underlay=False)
xs = [p[0] for p in pts(o)]
check("Erweitern vergrößert die Füllfläche (±16,5 mm)", max(xs) > 16.0 and min(xs) < -16.0)
o.fill.update(expand=0.0, len_random=0.0)
a = pts(o)
o.fill["len_random"] = 30.0
b = pts(o)
check("Zufällige Stichlänge verändert die Einstiche", a != b)
o2 = rect(); o2.fill.update(underlay=False, len_random=30.0)
check("Zufällige Stichlänge ist reproduzierbar", pts(o2) == b)
o.fill["len_random"] = 0.0
o.border.update(type="run", len_random=0.0); r0 = pts(o)
o.border["len_random"] = 40.0
check("Zufällige Stichlänge auch für den Rand", pts(o) != r0)
o.border.update(type="none", len_random=0.0)

seq = {}
for t in ("half", "backforth", "arrow", "star", "triangle", "zigzag", "none"):
    o.fill["tie"] = t
    seq[t] = [p for _, s in o.stitch_blocks() for p in s][:12]
check("Vernähstich-Arten ergeben verschiedene Stiche", len({str(v) for v in seq.values()}) == 7)
o.fill["tie"] = "star"
star = [p for _, s in o.stitch_blocks() for p in s]
xs0, ys0 = star[1][:2]
check("Stern-Vernähen geht quer zur Richtung", any(abs(p[1] - ys0) > 0.2 and abs(p[0] - xs0) < 0.1
                                                  for p in star[1:9]))
check("Objekt-Vernähen ändert globale Einstellung nicht", engine.TIE_STYLE is None)
# erzwungenes Vernähen vor kurzen Sprüngen (2,5 mm, kein Schnitt)
def short_jump():
    out = []
    engine.connect(out, engine.running_stitch([(0, 0), (8, 0)], 2.0))
    engine.connect(out, engine.running_stitch([(10.5, 0), (18, 0)], 2.0))
    return len(out)
before = short_jump()
engine.TIE_FORCE = True
forced = short_jump()
engine.TIE_FORCE = False
check("»Auch vor kurzen Sprüngen vernähen« fügt Vernähstiche hinzu", forced > before)
o3 = rect(); o3.fill["tie_force"] = True; o3.stitch_blocks()
check("… und gilt nur für das eigene Objekt", engine.TIE_FORCE is False)

col = column(-15, 0, 15, 0, 3.5)
full = n_st(col)
col.fill["satin_ul"] = "none"
check("Satin-Unterlage »Keine«: weniger Stiche", n_st(col) < full)
col.fill["satin_ul"] = "all"
check("Satin-Unterlage »Alle drei«: mehr Stiche als automatisch (7 mm)", n_st(col) >= full)
col.fill["satin_ul"] = "auto"
p0 = pts(col)
col.fill["width_random"] = 30.0
check("Zufällige Breite verändert die Satinstiche", pts(col) != p0)
col.fill.update(width_random=0.0, spacing_random=50.0)
check("Zufälliger Abstand verändert die Satinstiche", pts(col) != p0)

# Eigenschaften-Karte
w.doc.objects = [rect()]; w.sync_items([w.doc.objects[0].id]); p = w.props
p.set_object(w.doc.objects[0])
fm = p.c_fine.form
check("Karte »Feinheiten« für Flächen sichtbar", p.c_fine.isVisible() and fm.isRowVisible(p.x_ulangle)
      and fm.isRowVisible(p.x_tie) and not fm.isRowVisible(p.x_satinul))
p.x_ullayers.setCurrentIndex(1); p.x_tie.setCurrentIndex(p.x_tie.findData("arrow"))
p.x_expand.setValue(0.5); p._apply()
f = w.doc.objects[0].fill
check("Feinheiten werden übernommen", f["ul_layers"] == 2 and f["tie"] == "arrow" and f["expand"] == 0.5)
c2 = column(-10, 0, 10, 0); w.doc.objects.append(c2); w.sync_items([c2.id]); p.set_object(c2)
check("Satinsäule: Satin-Unterlage und Zufall sichtbar", fm.isRowVisible(p.x_satinul)
      and fm.isRowVisible(p.x_widthrand) and not fm.isRowVisible(p.x_ulangle))

# ============ Gruppe B
w.doc.objects = []
cols = [column(-15, -15, -15, 15), column(15, 15, 15, -15), column(-15, 0, 15, 0)]
w.doc.objects += cols; w.sync_items([c.id for c in cols])
j0 = real_jumps(w.doc)
w.auto_satin()
check(f"Auto-Satin: H ohne Sprünge ({j0} → {real_jumps(w.doc)})", j0 > 0 and real_jumps(w.doc) == 0)
check("Auto-Satin: alle Säulen in einer Gruppe",
      len({o.fill.get('autosatin') for o in w.doc.objects}) == 1)
trims = sum(1 for _, b in w.doc.machine_blocks() for s in b if s[2] == TRIM)
check("Auto-Satin: keine Fadenschnitte", trims == 0)
# Satinlinie mit Säule
w.doc.objects = []
ln = EmbObject("line"); ln.set_points([(0, -15), (0, 15)]); ln.border.update(type="satin", width=3, color="#E53935")
ln.x = -15
c3 = column(15, 15, 15, -15); c4 = column(-15, 0, 15, 0)
w.doc.objects += [ln, c3, c4]; w.sync_items([ln.id, c3.id, c4.id])
w.auto_satin()
check("Auto-Satin auch mit Satinlinien", real_jumps(w.doc) == 0)

from stichwizard.widgets import MultiSatinDialog
MultiSatinDialog.exec = lambda self: True
w.doc.objects = [column(-15, 0, 15, 0, 4)]; w.sync_items([w.doc.objects[0].id])
w.multicolor_satin()
check("Mehrfarbiger Satin: drei Streifen", len(w.doc.objects) == 3 and
      len({o.fill["color"] for o in w.doc.objects}) == 3)
ys = [sorted(p[1] for p in pts(o)) for o in w.doc.objects]
mid = [sum(v) / len(v) for v in ys]
ys = ys if mid[0] < mid[2] else ys[::-1]
check("Streifen liegen nebeneinander (mit Überlappung)",
      ys[0][0] < ys[1][0] < ys[2][0] and ys[0][-1] > ys[1][0])

r = engine.running_stitch([(0, 0), (20, 0)], 2.0, True, repeats=1)
rp = engine.running_stitch([(0, 0), (20, 0)], 2.0, True, repeats=[1, 0])
check("Bohnenstich-Muster »1 0«: abwechselnd dreifach/einfach", len(rp) == 1 + 10 + 5 * 2 and len(r) == 31)
check("Muster-Text wird gelesen", engine.bean_pattern("2, 0 x 1") == [2, 0, 1] and
      engine.bean_pattern("") is None)
ln2 = EmbObject("line"); ln2.set_points([(0, 0), (20, 0)]); ln2.border.update(type="triple", stitch_len=2.0)
k1 = n_st(ln2); ln2.border["bean_pattern"] = "2 0 0"
check("Bohnenstich-Muster an der Linie", n_st(ln2) != k1)

# ============ Gruppe C
g = rect(40, 30); g.fill.update(type="gradient", color="#E53935", color2="#1E88E5",
                                 gradient_colors=["#FFEB3B", "#43A047"])
blocks = g.stitch_blocks()
check("Farbverlauf mit 4 Farben", [c for c, _ in blocks] == ["#E53935", "#1E88E5", "#FFEB3B", "#43A047"])
g.fill["gradient_reverse"] = True
check("Mehrfarbiger Verlauf umkehrbar", len(g.stitch_blocks()) == 4)
t = rect(40, 30); t.fill.update(type="tartan")
tb = t.stitch_blocks()
nc = len({c.upper() for c, _ in tb})
check(f"Tartan: Kette und Schuss je Farbe ({len(tb)} Blöcke, {nc} Farben)", len(tb) == 2 * nc and nc == 5)
area = MultiPoint([p for _, s in tb for p in s[:]]).convex_hull.area
check("Tartan deckt die Fläche", area > 0.85 * 40 * 30)
t.fill.update(tartan=[["#000000", 4], ["#FFFFFF", 4]])
check("Eigene Tartan-Streifen", {c for c, _ in t.stitch_blocks()} == {"#000000", "#FFFFFF"})

w.doc.objects = []
res = api.call("add_shape", {"shape": "rect", "width": 30, "height": 20, "fill_type": "tartan",
                             "fill": {"tartan": "Black Watch"}})
ob = w.doc.find(res["id"])
check("API: Tartan-Vorlage", ob.fill["type"] == "tartan" and ob.fill["tartan"][0][0] == "#0B3D2E")
api.call("update_object", {"id": ob.id, "changes": {"fill": {"ul_layers": 2, "tie": "star",
                                                              "expand": 9, "len_random": 20}}})
check("API: Feinheiten (mit Begrenzung)", ob.fill["ul_layers"] == 2 and ob.fill["tie"] == "star"
      and ob.fill["expand"] == 3.0 and ob.fill["len_random"] == 20.0)
try:
    api.call("update_object", {"id": ob.id, "changes": {"fill": {"tie": "knoten"}}}); bad = False
except ApiError:
    bad = True
check("API: unbekannte Vernähart abgelehnt", bad)

# ============ Tatami-Einstichmuster (1.9.1)
from stichwizard.widgets import TATAMI_PATTERNS as UI_PATTERNS
check("15 Tatami-Muster in der Auswahl", len(UI_PATTERNS) == 15 and
      {k for _, k in UI_PATTERNS} == set(engine.TATAMI_PATTERNS))
seen, lens_ok = set(), True
for _, key in UI_PATTERNS:
    pq = rect(30, 30); pq.fill.update(pattern=key, angle=0, underlay=False, pull=0, stitch_len=3.0)
    sts = [p for _, b in pq.stitch_blocks() for p in b]
    ls = [engine.dist(a, b) for a, b in zip(sts, sts[1:]) if a[2] == b[2] == STITCH and
          engine.dist(a, b) > 0.05]
    lens_ok = lens_ok and min(ls) >= 0.25 and max(ls) <= 3.0 * 1.35
    seen.add(str(sorted(round(p[0], 2) for p in sts[200:400])))
check("Alle Muster: Stichlängen zwischen 0,25 mm und 1,35 × Stichlänge", lens_ok)
check("Jedes Muster setzt die Einstiche anders", len(seen) == 15)
api.call("update_object", {"id": ob.id, "changes": {"fill_type": "tatami", "pattern": "scales"}})
check("API: neues Muster »scales«", ob.fill["pattern"] == "scales")

# ============ Gruppe D: Export
d = Document(); e = rect(); e.border.update(type="satin"); d.objects = [e]
okfmt = True
for ext in ("tbf", "pmv", "csv", "txt", "json", "gcode", "col", "edr", "inf"):
    path = os.path.join(OUT, "t." + ext)
    fileio.export_file(d, path, True)
    okfmt = okfmt and os.path.getsize(path) > 0
check("Export TBF, PMV, CSV, TXT, JSON, G-Code, Farblisten", okfmt)
zp = os.path.join(OUT, "t.zip"); fileio.export_file(d, zp, True)
names = zipfile.ZipFile(zp).namelist()
check("ZIP enthält die Maschinenformate", {"t.pes", "t.dst", "t.jef", "t.exp", "t.vp3"} <= set(names))
back = fileio.import_file(os.path.join(OUT, "t.tbf"))
check("TBF lässt sich wieder öffnen", back is not None)
from stichwizard.multiexport import MultiExportDialog
dlg = MultiExportDialog(d, OUT, "Paket", chosen=("pes", "jef"))
dlg.as_zip.setChecked(True); dlg.run()
check("Mehrfach-Export als ZIP", dlg.written == [os.path.join(OUT, "Paket.zip")] and
      sorted(zipfile.ZipFile(dlg.written[0]).namelist()) == ["Paket.jef", "Paket.pes"])

# ============ Speichern / Laden
d2 = Document(); x = rect(); x.fill.update(type="tartan", ul_layers=2, tie="zigzag",
                                           tartan=[["#123456", 3], ["#FFFFFF", 2]])
d2.objects = [x]
d3 = Document(); d3.load_json(d2.to_json())
y = d3.objects[0]
check("Neue Einstellungen werden gespeichert", y.fill["tie"] == "zigzag" and y.fill["ul_layers"] == 2
      and y.fill["tartan"][0] == ["#123456", 3])
old = Document(); old.load_json('{"app": "StickStudio", "version": 1, "objects": [{"kind": "shape", '
                                '"geom_wkt": "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"}]}')
check("Alte Projekte bekommen Standardwerte", old.objects[0].fill["tie"] == "auto" and
      old.objects[0].border["bean_pattern"] == "")

print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
