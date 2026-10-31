"""Test: Funktionen, die nach dem Ink/Stitch-Vergleich ergänzt wurden."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion')
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, fileio, embfont
from stichwizard.mainwindow import MainWindow
from stichwizard.model import EmbObject
from shapely.geometry import box, Point
OUT = sys.argv[1]
from testdata import HAFNEREI_DST
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
def add(o):
    w.add_objects([o]); return o
def n_st(o):
    return sum(1 for _, s in o.stitch_blocks() for p in s if p[2] == engine.STITCH)
def select(*objs):
    w.scene.clearSelection()
    for o in objs:
        w.items[o.id].setSelected(True)
    QTest.qWait(10)
# --- Füllarten über das Eigenschaften-Fenster
o = add(EmbObject("shape")); o.set_geometry(Point(0, 0).buffer(20)); w.rebuild([o]); select(o)
for kind in ("circular", "meander", "ripple", "gradient"):
    i = w.props.f_type.findData(kind)
    w.props.f_type.setCurrentIndex(i); w.props._apply(); QTest.qWait(10)
    cols = [c for c, _ in o.stitch_blocks()]
    check(f"Füllart {kind} wählbar und stickbar ({n_st(o)} Stiche, {len(cols)} Farbe(n))",
          i >= 0 and o.fill["type"] == kind and n_st(o) > 50 and (len(cols) == 2 if kind == "gradient" else True))
check("Farbverlauf: zweite Farbe sichtbar", w.props.c_fill.form.isRowVisible(w.props.f_color2))
# --- Rand- und Linienarten
o.fill["type"] = "none"
for t in ("zigzag", "estitch"):
    o.border.update(type=t, width=3, stitch_len=2.5); o._skey = None
    check(f"Rand {t}", n_st(o) > 30)
ln = add(EmbObject("line")); ln.set_points([(-50, 40), (-10, 30), (30, 40)])
ln.border.update(type="triple", repeats=1); ln._skey = None; a = n_st(ln)
ln.border.update(repeats=2); ln._skey = None; b = n_st(ln)
check(f"Bohnenstich: 2 Wiederholungen mehr Stiche ({a} → {b})", b > a * 1.5)
ln.border.update(type="manual"); ln._skey = None
check(f"Manueller Stich: ein Einstich je Punkt + Vernähen ({n_st(ln)})", n_st(ln) <= 3 + 8)
# --- Satinarten
sa = EmbObject("satin"); sa.x, sa.y = 40, -40
sa.set_satin([[-10, 0, 0], [10, 0, 0]], [[-10, 4, 0], [10, 4, 0]]); add(sa)
res = {}
for t in ("satin", "zigzag", "estitch"):
    sa.fill["satin_type"] = t; sa._skey = None; res[t] = n_st(sa)
check(f"Satinarten unterschiedlich {res}", len(set(res.values())) == 3)
sa.fill["satin_type"] = "satin"; sa._skey = None
# --- Stopp nach Objekt
w.doc.objects = []; w.sync_items([])
p1 = add(EmbObject("shape")); p1.set_geometry(box(-30, -10, -10, 10))
p2 = add(EmbObject("shape")); p2.set_geometry(box(10, -10, 30, 10))
p1.trim_after = "stop"
blocks = w.doc.machine_blocks()
check("Stopp nach Objekt erzeugt STOP", sum(1 for _, s in blocks for p in s if p[2] == engine.STOP) == 1)
path = os.path.join(OUT, "stop.pes"); fileio.export_file(w.doc, path)
imp = fileio.import_file(path)
check("Stopp bleibt in PES erhalten", sum(1 for b in imp.blocks for p in b["stitches"] if p[2] == engine.STOP) >= 1 or len(imp.blocks) >= 2)
p1.trim_after = "auto"
# --- Linie <-> Säulen-Satin, Richtung, Teilen
w.doc.objects = []; w.sync_items([])
l2 = add(EmbObject("line")); l2.set_points([(-40, 0), (0, -10), (40, 0)])
select(l2); w.line_to_satin()
s = w.doc.objects[-1]
check(f"Linie → Säulen-Satin ({s.kind}, {len(s.curve[0])} Paare)", s.kind == "satin" and len(s.curve[0]) == 3 and n_st(s) > 100)
first = s.stitch_blocks()[0][1][1][:2]
select(s); w.reverse_direction(); s2 = w.doc.objects[-1]
check("Richtung umkehren", s2.stitch_blocks()[0][1][1][0] * first[0] < 0)
select(s2); w.set_tool("nodes"); w.canvas._node_state(); w.canvas._node_sel = {(0, 1)}
w.cut_satin()
check(f"Satin teilen ({len(w.doc.objects)} Objekte)", len(w.doc.objects) == 2 and all(o.kind == "satin" for o in w.doc.objects))
w.set_tool("select"); select(w.doc.objects[0]); w.satin_to_line()
check("Säulen-Satin → Linie", w.doc.objects[0].kind == "line" and len(w.doc.objects[0].line_nodes()) == 2)
# --- Mittellinie
w.doc.objects = []; w.sync_items([])
t = add(EmbObject("text")); t.text.update(text="H", size=30, bold=False); w.rebuild([t])
select(t); w.to_centerline()
lines = [o for o in w.doc.objects if o.kind == "line"]
check(f"Mittellinie aus Buchstabe H ({len(lines)} Linien, Original ausgeblendet)", 1 <= len(lines) <= 6 and not t.visible)
# --- Umriss aus Stickdatei
w.open_document(HAFNEREI_DST)
st = w.doc.objects[0]; select(st); w.outline_from_stitches()
shapes = [o for o in w.doc.objects if o.kind == "shape"]
check(f"Umriss aus Stickdatei ({len(shapes)} Formen)", len(shapes) >= 1 and not st.visible)
# --- Knockdown
w.doc.objects = []; w.sync_items([])
k1 = add(EmbObject("shape")); k1.set_geometry(Point(0, 0).buffer(15))
select(k1); w.add_knockdown()
kd = w.doc.objects[0]
check("Knockdown unten, Stofffarbe, ohne Unterlage", kd.name == "Knockdown" and kd.fill["color"] == w.doc.fabric
      and not kd.fill["underlay"] and kd.world_geometry().area > k1.world_geometry().area)
# --- Dichteprüfung
w.doc.objects = []; w.sync_items([])
for r in (20, 10, 5):
    q = add(EmbObject("shape")); q.set_geometry(box(-r, -r, r, r))
w.a_density.setChecked(True); w.toggle_density()
d, mx, my, cell = w.density_grid()
core = d[int((-2 - my) / cell), int((-mx) / cell)]
check(f"Dichteprüfung: drei Lagen rot ({core:.1f} ≥ {w.DENSITY_HIGH})", w._density_item is not None and core >= w.DENSITY_HIGH)
edge = d[int((-15 - my) / cell), int((-mx) / cell)]
check(f"Eine Lage unauffällig ({edge:.1f} < {w.DENSITY_WARN})", edge < w.DENSITY_WARN)
w.a_density.setChecked(False); w.toggle_density()
check("Dichteprüfung ausblenden", w._density_item is None)
# --- Mehrfach-Export mit Namensliste
from stichwizard.multiexport import MultiExportDialog
w.doc.objects = []; w.sync_items([])
tx = add(EmbObject("text")); tx.text.update(text="Name", size=12)
dlg = MultiExportDialog(w.doc, OUT, "Shirt", ("pes", "dst"), w)
dlg.names.setPlainText("Anna\nBen\nJürgen")
dlg.run()
files = sorted(os.path.basename(f) for f in dlg.written)
check(f"Namensliste: 3 Namen × 2 Formate = {len(files)} Dateien", len(files) == 6 and "Shirt_Jürgen.pes" in files)
check("Schriftzug danach wiederhergestellt", tx.text["text"] == "Name")
# --- Einstellungen: Vernähen, Mindeststichlänge
w.doc.objects = []; w.sync_items([])
z = add(EmbObject("shape")); z.set_geometry(Point(0, 0).buffer(10)); z.fill["type"] = "meander"
engine.TIE_MODE = "normal"; z._skey = None; a = n_st(z)
engine.TIE_MODE = "none"; z._skey = None; b = n_st(z)
engine.TIE_MODE = "normal"; z._skey = None
check(f"Vernähen aus spart Stiche ({a} → {b})", b < a)
engine.MIN_STITCH = 0.0; a = w.doc.stats()["stitches"]
engine.MIN_STITCH = 1.0; b = w.doc.stats()["stitches"]
engine.MIN_STITCH = 0.0
check(f"Mindeststichlänge fasst kurze Stiche zusammen ({a} → {b})", b < a)
# --- Schriftfilter
from stichwizard.fontdialog import EmbFontDialog
fd = EmbFontDialog("", "Jürgen")
visible = sum(1 for it in fd.items.values() if not it.isHidden())
check(f"Schriftfilter »Jürgen«: {visible} von {len(fd.items)} Schriften", 0 < visible < len(fd.items))
print("ERGEBNIS:", sum(ok), "/", len(ok))
