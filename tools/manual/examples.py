"""Beispielbilder »vorher → nachher« für die Anleitung (eine kleine Aufgabe je Funktion).

Läuft nach images.py in denselben Bildordner (mit eigenen, leeren Einstellungen):
  XDG_CONFIG_HOME=$T XDG_CACHE_HOME=$T XDG_DATA_HOME=$T XDG_RUNTIME_DIR=$T/rt \
  QT_QPA_PLATFORM=offscreen .venv/bin/python tools/manual/examples.py build/manual/img
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build/manual/img"))
os.makedirs(OUT, exist_ok=True)

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

app = QApplication(sys.argv)
app.setApplicationName("StickStudio")
app.setStyle("Fusion")
QMessageBox.information = staticmethod(lambda *a, **k: None)
QInputDialog.getDouble = staticmethod(lambda *a, **k: (2.0, True))
from shapely import affinity
from shapely.geometry import Point, box
from shapely.ops import unary_union
from stichwizard import controls, curves, engine, shapes
from stichwizard.engine import JUMP, STITCH, TRIM
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
from stichwizard.render import render_document

FONT = QFont("DejaVu Sans", 11)


def save(img, name):
    img.save(os.path.join(OUT, name + ".png"))
    print("Bild:", name)


def shape(geom, color="#E53935", **fill):
    o = EmbObject("shape")
    o.set_geometry(geom)
    o.fill.update(color=color, **fill)
    return o


def motif(name, size=30, **kw):
    from shapely import affinity
    g = dict(shapes.MOTIFS)[name]()
    b = g.bounds
    f = size / max(b[2] - b[0], b[3] - b[1])
    return shape(affinity.scale(g, f, f, origin=(0, 0)), **kw)


def line(pts, closed=False, **border):
    o = EmbObject("line")
    o.set_points(pts, closed)
    o.border.update(**border)
    return o


def text(t, size=14, color="#1A237E", font="Amitaclo"):
    from stichwizard import embfont
    o = EmbObject("text", t)
    o.text.update(text=t, size=size)
    o.text["embfont"] = next((f["id"] for f in embfont.font_index() if f["name"].strip() == font), "")
    o.fill["color"] = color
    return o


def render(objs, scale=8, jumps=False, margin=3, fabric="#FFFFFF"):
    d = Document()
    d.objects = [o for o in objs if o.visible]
    d.fabric = fabric
    img = render_document(d, scale, margin=margin)
    if jumps:
        blocks = d.machine_blocks()
        flat = [s for _, b in blocks for s in b]
        xs, ys = [s[0] for s in flat], [s[1] for s in flat]
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(scale, scale)
        p.translate(-(min(xs) - margin), -(min(ys) - margin))
        for a, b in zip(flat, flat[1:]):
            if b[2] == JUMP and engine.dist(a, b) > 1.6:
                p.setPen(QPen(QColor("#FF6F00"), 0.35, Qt.DashLine))
                p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
            if b[2] == TRIM:
                p.setPen(QPen(QColor("#D50000"), 0.4))
                p.drawLine(QPointF(b[0] - 1, b[1] - 1), QPointF(b[0] + 1, b[1] + 1))
                p.drawLine(QPointF(b[0] - 1, b[1] + 1), QPointF(b[0] + 1, b[1] - 1))
        p.end()
    return img


def jumps_of(objs):
    d = Document()
    d.objects = [o for o in objs if o.visible]
    flat = [s for _, b in d.machine_blocks() for s in b]
    return sum(1 for a, b in zip(flat, flat[1:]) if b[2] == JUMP and engine.dist(a, b) > 1.6)


def grid(cells, cols, cell_px=230, label_h=48, pad=14):
    """cells: [(QImage, Beschriftung)]; ein »→« zwischen Vorher/Nachher-Paaren."""
    rows = math.ceil(len(cells) / cols)
    W = cols * (cell_px + pad) + pad
    H = rows * (cell_px + label_h + pad) + pad
    out = QImage(W, H, QImage.Format_ARGB32)
    out.fill(QColor("#FFFFFF"))
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setFont(FONT)
    for k, (img, label) in enumerate(cells):
        r, c = divmod(k, cols)
        x0, y0 = pad + c * (cell_px + pad), pad + r * (cell_px + label_h + pad)
        p.setPen(QPen(QColor("#D5DAE3"), 1))
        p.setBrush(QColor("#FAFBFC"))
        p.drawRoundedRect(QRectF(x0, y0, cell_px, cell_px), 8, 8)
        if img is not None and not img.isNull():
            s = min((cell_px - 16) / img.width(), (cell_px - 16) / img.height())
            w_, h_ = img.width() * s, img.height() * s
            p.drawImage(QRectF(x0 + (cell_px - w_) / 2, y0 + (cell_px - h_) / 2, w_, h_), img)
        p.setPen(QColor("#2B2D3A"))
        p.drawText(QRectF(x0 - 4, y0 + cell_px + 4, cell_px + 8, label_h - 4),
                   Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, label)
    p.end()
    return out


# ---------------------------------------------------------------- Programm fernsteuern
w = MainWindow()
w.resize(1440, 900)
w.show()
QTest.qWait(150)
w.align_ref = "selection"


def run(objs, fn, sel=None, auto=None):
    """objs ins Design legen, sel (Standard: alle) auswählen, fn() ausführen -> sichtbare Objekte."""
    w.doc.objects = list(objs)
    w.sync_items([])
    w.scene.clearSelection()
    for o in (sel if sel is not None else objs):
        w.items[o.id].setSelected(True)
    QTest.qWait(5)
    controls.ask_values.auto = auto
    fn()
    controls.ask_values.auto = None
    return [o for o in w.doc.objects if o.visible]


def recolor(objs, colors):
    for o, c in zip(objs, colors):
        o.fill["color"] = c
    return objs


PAL = ["#E53935", "#1E88E5", "#43A047", "#FB8C00", "#8E24AA", "#00897B"]


# ---------------------------------------------------------------- Pfad-Operationen
def pair():
    a = shape(Point(0, 0).buffer(12, 48), "#E53935")
    b = shape(box(4, -9, 24, 9), "#1E88E5")
    return [a, b]


cells = []
for label, fn in (("Kombinieren", w.merge_selected), ("Ausschneiden", w.cut_selected),
                  ("Schnittmenge", lambda: w.path_op("intersect")),
                  ("Exklusion", lambda: w.path_op("exclude"))):
    before = pair()
    after = run(pair(), fn)
    cells += [(render(before, 7), f"{label}: vorher"), (render(after, 7), f"{label}: nachher")]
after = recolor(run(pair(), lambda: w.path_op("divide")), ["#43A047", "#FB8C00"])
cells += [(render(pair(), 7), "Teilen: vorher"), (render(after, 7), f"Teilen: {len(after)} Stücke")]
two = shape(unary_union([Point(-12, 0).buffer(8, 32), Point(12, 0).buffer(8, 32)]), "#8E24AA")
after = recolor(run([two], w.split_selected), PAL)
cells += [(render([two], 7), "Zerlegen: eine Form aus 2 Teilen"),
          (render(after, 7), f"Zerlegen: {len(after)} einzelne Formen")]
save(grid(cells, 4, cell_px=200), "ex_pathops")


# ---------------------------------------------------------------- Ausrichten / Verteilen
def three(xs=(-30, 0, 34), ys=(6, -8, 12)):
    return [shape(box(x - s / 2, y - s / 2, x + s / 2, y + s / 2), c)
            for x, y, s, c in zip(xs, ys, (10, 18, 13), PAL)]


base = three()
after = run(three(), lambda: w.align_selected("top"))
after2 = run(three(), lambda: w.align_selected("vcenter"))
xs = (-36, -14, 30)
ub = three(xs, (0, 0, 0))
after3 = run(three(xs, (0, 0, 0)), lambda: w.distribute_selected("x"))
save(grid([(render(base, 6), "Vorher"), (render(after, 6), "Oben ausgerichtet"),
           (render(after2, 6), "Vertikal zentriert"), (render(ub, 6), "Vorher: ungleiche Lücken"),
           (render(after3, 6), "Waagerecht verteilt")], 5, cell_px=190, label_h=50), "ex_align")


# ---------------------------------------------------------------- Erweitern, Schrumpfen, Umriss
def star():
    return motif("Stern", 30, color="#FDD835")


orig = star()
grown = run([star()], lambda: w.offset_selected(True), auto={"d": 2.0, "round": True})
grown[0].fill["color"] = "#FFE082"
shrunk = run([star()], lambda: w.offset_selected(False), auto={"d": 2.0, "round": True})
shrunk[0].fill["color"] = "#F9A825"
ring = run([motif("Herz", 24, color="#EC407A")], w.outline_selected,
           auto={"d": 2.0, "kind": "satin", "w": 2.5, "round": True})
for o in ring:
    if o.kind == "line":
        o.border["color"] = "#880E4F"
save(grid([(render([orig], 6), "Original (30 mm)"),
           (render(grown + [star()], 6), "Erweitern 2 mm (hell = neu)"),
           (render([shrunk[0]], 6), "Schrumpfen 2 mm"),
           (render(ring, 6), "Umriss: Satinrand 2,5 mm im Abstand 2 mm")], 4, cell_px=210, label_h=52),
     "ex_offset")


# ---------------------------------------------------------------- Kopien
heart = motif("Herz", 10, color="#E53935")
gridc = run([heart], w.copies_grid, auto={"cols": 4, "rows": 2, "gx": 3.0, "gy": 3.0})
petal = shape(Point(0, 0).buffer(1, 24), "#EC407A")
petal.set_geometry(affinity.scale(Point(0, 0).buffer(1, 32), 3.5, 8))
circ = run([petal], w.copies_circle, auto={"n": 8, "radius": 10.0, "rotate": True})
centre = shape(Point(0, 0).buffer(4, 32), "#FDD835")
cy = sum(o.world_geometry().centroid.y for o in circ) / len(circ)
cx = sum(o.world_geometry().centroid.x for o in circ) / len(circ)
centre.x, centre.y = cx, cy
save(grid([(render([motif("Herz", 10, color="#E53935")], 9), "Vorher: ein Herz (10 mm)"),
           (render(gridc, 6), "Raster 4 × 2, Lücke 3 mm"),
           (render([petal], 9), "Vorher: ein Blütenblatt"),
           (render(circ + [centre], 6), "Kreis: 8 Stück, Radius 10 mm + gelbe Mitte")],
          4, cell_px=210, label_h=52), "ex_copies")


# ---------------------------------------------------------------- Stern, Vieleck, Spirale
def make(auto, fn, color):
    objs = run([], fn, sel=[], auto=auto)
    for o in objs:
        if o.kind == "shape":
            o.fill["color"] = color
        else:
            o.border["color"] = color
    return objs


cells = []
for label, auto, fn, col in (
        ("Stern: 5 Ecken, Spitzen 0,45", {"polygon": False, "n": 5, "size": 30, "ratio": 0.45,
                                         "rot": 0, "round": False}, w.make_star, "#FDD835"),
        ("Stern: 12 Ecken, Spitzen 0,75", {"polygon": False, "n": 12, "size": 30, "ratio": 0.75,
                                          "rot": 0, "round": False}, w.make_star, "#FB8C00"),
        ("Vieleck: 6 Ecken", {"polygon": True, "n": 6, "size": 30, "ratio": 0.5, "rot": 0,
                              "round": False}, w.make_star, "#43A047"),
        ("Stern 6, abgerundet", {"polygon": False, "n": 6, "size": 30, "ratio": 0.55, "rot": 0,
                                 "round": True}, w.make_star, "#EC407A"),
        ("Spirale: 4 Windungen, 30 mm", {"turns": 4, "size": 30, "inner": 1}, w.make_spiral,
         "#1E88E5")):
    cells.append((render(make(auto, fn, col), 6), label))
save(grid(cells, 5, cell_px=190, label_h=50), "ex_starspiral")


# ---------------------------------------------------------------- Großes D nachzeichnen
CORNER, CURVE = curves.CORNER, curves.CURVE
H = 20.0                          # halbe Höhe
stem_a = [[-14, -H, CORNER], [-14, H, CORNER]]
stem_b = [[-7, -H, CORNER], [-7, H, CORNER]]
cx = -8.0                          # Bogen reicht 1 mm in den Strich hinein
outer, inner, rungs = [], [], []
n = 10
for k in range(n + 1):
    t = math.radians(-90 + 180 * k / n)
    po = (cx + 19 * math.cos(t), 20 * math.sin(t))
    pi = (cx + 12 * math.cos(t), 13 * math.sin(t))
    typ = CORNER if k in (0, n) else CURVE
    outer.append([po[0], po[1], typ])
    inner.append([pi[0], pi[1], typ])
    rungs.append((po, pi))


def satin(a, b, color):
    o = EmbObject("satin")
    o.set_satin(a, b)
    o.fill.update(color=color)
    return o


d_stem = satin(stem_a, stem_b, "#3949AB")
d_bow = satin(outer, inner, "#3949AB")
# links: Vorlage (grau) mit den Klickpaaren, rechts: das gestickte D
S = 9.0
tpl = QImage(int(48 * S), int(48 * S), QImage.Format_ARGB32)
tpl.fill(QColor("#FFFFFF"))
p = QPainter(tpl)
p.setRenderHint(QPainter.Antialiasing)
p.translate(21 * S, 24 * S)
p.scale(S, S)
dgeom = unary_union([box(-14, -H, -7, H), affinity.translate(
    affinity.scale(Point(0, 0).buffer(1, 64), 19, 20).difference(
        affinity.scale(Point(0, 0).buffer(1, 64), 12, 13)).intersection(box(0, -30, 30, 30)), cx, 0)])
path = QPainterPath()
for poly in getattr(dgeom, "geoms", [dgeom]):
    for ring in [poly.exterior] + list(poly.interiors):
        pts = list(ring.coords)
        path.moveTo(*pts[0])
        for q in pts[1:]:
            path.lineTo(*q)
        path.closeSubpath()
p.setPen(Qt.NoPen)
p.setBrush(QColor("#CFD3DC"))
p.drawPath(path)
num = QFont("DejaVu Sans")
num.setPixelSize(2)
p.setFont(num)


def rung(a, b, label, pos):
    p.setPen(QPen(QColor("#00897B"), 0.35))
    p.drawLine(QPointF(*a), QPointF(*b))
    p.setPen(Qt.NoPen)
    for q, col in ((a, "#E53935"), (b, "#1E88E5")):
        p.setBrush(QColor(col))
        p.drawEllipse(QPointF(*q), 0.8, 0.8)
    p.setPen(QColor("#2B2D3A"))
    p.drawText(QRectF(pos[0] - 3, pos[1] - 1.5, 6, 3), Qt.AlignCenter, label)


rung((-14, -H), (-7, -H), "S1", (-17.5, -H))
rung((-14, H), (-7, H), "S2", (-17.5, H))
for k, (po, pi) in enumerate(rungs):
    t = math.radians(-90 + 180 * k / n)
    rung(po, pi, str(k + 1), (cx + 22 * math.cos(t), 23 * math.sin(t)))
p.end()
cells = [(tpl, "1. Vorlage mit Klickpaaren: Strich S1–S2, Bogen 1–11"),
         (render([d_stem], 8), "2. Säule »Strich«: 2 Klickpaare"),
         (render([d_stem, d_bow], 8), "3. Säule »Bogen«: 11 Klickpaare, fertig")]
save(grid(cells, 3, cell_px=260, label_h=56), "ex_trace_d")


# ---------------------------------------------------------------- Linie → Satin, Mittellinie
wave = [(-24 + 4 * i, 6 * math.sin(i * 0.8)) for i in range(13)]
ln = line(wave, type="run", color="#00897B")
ln.border["width"] = 3.0
sat = run([line(wave, type="satin", color="#00897B", width=3.0)], w.line_to_satin)
ring_shape = shape(Point(0, 0).buffer(14, 64).difference(Point(0, 0).buffer(11, 64)), "#6D4C41")
cl = run([shape(Point(0, 0).buffer(14, 64).difference(Point(0, 0).buffer(11, 64)), "#6D4C41")],
         w.to_centerline)
for o in cl:
    o.border.update(type="triple", stitch_len=2.5)
save(grid([(render([line(wave, type="run", color="#00897B")], 7), "Linie (Steppstich)"),
           (render(sat, 7), "In Säulen-Satin (3 mm)"),
           (render([ring_shape], 6), "Schmale Fläche (Ring, 3 mm)"),
           (render(cl, 6), "Mittellinie als Bohnenstich")], 4, cell_px=210, label_h=52),
     "ex_satinline")


# ---------------------------------------------------------------- Redwork / Auto-Route
def flower_lines():
    out = []
    for k in range(5):
        a = math.radians(72 * k)
        pts = [(14 * math.cos(a), 14 * math.sin(a)),            # Start an der Blattspitze
               (7 * math.cos(a + 0.45) * 1.6, 7 * math.sin(a + 0.45) * 1.6), (0, 0),
               (7 * math.cos(a - 0.45) * 1.6, 7 * math.sin(a - 0.45) * 1.6),
               (14 * math.cos(a), 14 * math.sin(a))]
        out.append(line(pts, type="run", color="#C62828", stitch_len=2.0))
    stem = line([(0, 26), (2, 12), (0, 0)], type="run", color="#C62828", stitch_len=2.0)
    return out + [stem]


fl = flower_lines()
j0 = jumps_of(fl)
rw = run(flower_lines(), lambda: w.route_lines("redwork"))
j1 = jumps_of(rw)
ar = run(flower_lines(), lambda: w.route_lines("autoroute"))
j2 = jumps_of(ar)
save(grid([(render(fl, 7, jumps=True), f"Vorher: 6 Linien, {j0} Sprünge"),
           (render(rw, 7, jumps=True), f"Redwork: {j1} Sprünge, jede Strecke 2×"),
           (render(ar, 7, jumps=True), f"Auto-Route: {j2} Sprünge, nur nötige Strecken 2×")],
          3, cell_px=250, label_h=56), "ex_redwork")


# ---------------------------------------------------------------- Kleinteile entfernen
specks = [Point(x, y).buffer(0.6, 12) for x, y in ((-20, -12), (19, 13), (-18, 14), (22, -11),
                                                    (0, 15), (-23, 2))]
body = box(-15, -9, 15, 9).difference(Point(5, 0).buffer(0.7, 12))
messy = shape(unary_union([body] + specks), "#5E35B1")
clean = run([shape(unary_union([body] + specks), "#5E35B1")], w.cleanup_small)
save(grid([(render([messy], 7, jumps=True), f"Vorher: {jumps_of([messy])} Sprünge zu Fusseln"),
           (render(clean, 7, jumps=True), f"Nachher: {jumps_of(clean)} Sprünge")],
          2, cell_px=300, label_h=50), "ex_cleanup")


# ---------------------------------------------------------------- Spiegeln
leaf = motif("Blatt", 22, color="#43A047")
leaf.x = -14
m = leaf.clone()
m.x = 14
mm = run([m], lambda: w.mirror(True))
save(grid([(render([leaf], 7), "Original"), (render([leaf] + mm, 7), "Kopie, gespiegelt ↔")],
          2, cell_px=260, label_h=44), "ex_mirror")

# ---------------------------------------------------------------- Kappenrahmen & Produktvorschau
from PySide6.QtCore import QSize
from stichwizard import threads
w.doc.objects = []
w.sync_items([])
w.set_fabric("#22304A")
w.set_hoop(threads.hoop_for_size(130, 60))
cap_text = text("TEAM 26", 16, "#FFFFFF")
w.add_objects([cap_text])
w.scene.clearSelection()
w.fit_hoop()
QTest.qWait(150)
r = w.canvas.mapFromScene(w.hoop_item.sceneBoundingRect()).boundingRect()
save(w.canvas.viewport().grab(r.adjusted(-10, -10, 10, 10)).toImage(), "cap_hoop")
w.open_mockup()
QTest.qWait(200)
dlg = w._mockup
cells = [(dlg.render_image(QSize(560, 560)), "Kappe, Marine")]
heart = motif("Herz", 60, color="#E53935")
heart.border.update(type="satin", width=2.5, color="#8E0000")
anna = text("Anna", 14, "#FFFFFF")
w.set_hoop(1)
w.doc.objects = [heart, anna]
w.sync_items([])
w.commit()
for prod, col, place, label in (("shirt", "#FFFFFF", 1, "T-Shirt, Brust Mitte"),
                                ("bag", "#EDE3D1", 0, "Tragetasche"),
                                ("pillow", "#F2D7D5", 0, "Kissen 40 × 40 cm")):
    dlg.product, dlg.color, dlg.place, dlg.zoom = prod, col, place, 1.0
    cells.append((dlg.render_image(QSize(560, 560)), label))
dlg.close()
save(grid(cells, 4, cell_px=240, label_h=40), "mockups")

# ---------------------------------------------------------------- Hüllformen, Motivlinie, Schatten
from stichwizard import textfx
cells = []
for key in ("none", "arch_top", "arch_both", "barrel", "bridge", "wave", "pennant", "diamond"):
    o = EmbObject("text", "T")
    o.text.update(text="TEAM 26", size=16, embfont="barstitch_bold", env=key, env_amount=0.4)
    o.fill["color"] = "#1A237E"
    label = next(l for k, l, _ in textfx.ENVELOPES if k == key)
    cells.append((render([o], 6), label))
save(grid(cells, 4, cell_px=210, label_h=40), "ex_envelopes")

wave_pts = [(-30 + 2.5 * i, 5 * math.sin(i * 0.35)) for i in range(25)]
cells = []
for key, label in (("heart", "Herzen"), ("star", "Sterne"), ("leaf", "Blätter abwechselnd"),
                   ("flower", "Blüten"), ("scallop", "Muschelkante"), ("loop", "Schlaufen")):
    ln = line(wave_pts, type="motif", motif=key, width=7, gap=1.5, color="#C62828",
              motif_alt=key == "leaf")
    cells.append((render([ln], 7), label))
save(grid(cells, 3, cell_px=230, label_h=40), "ex_motiflines")

base = text("TEAM", 18, "#FFC107", "Barstitch Bold")
w.doc.objects = [base]
w.sync_items([base.id])
w.scene.clearSelection()
w.items[base.id].setSelected(True)
controls.ask_values.auto = {"dx": 1.5, "dy": 1.5, "kind": "fill", "color": "#111111", "cut": True}
w.shadow_selected()
controls.ask_values.auto = None
save(grid([(render([text("TEAM", 18, "#FFC107", "Barstitch Bold")], 7, fabric="#B71C1C"), "Ohne Schatten"),
           (render(list(w.doc.objects), 7, fabric="#B71C1C"), "Schatten 1,5 mm, dunkelgrau")],
          2, cell_px=300, label_h=40), "ex_shadow")

from stichwizard import multihoop
bg = shape(box(-200, -50, 200, 50), "#90CAF9")
bg.border.update(type="satin", width=3, color="#0D47A1")
big = text("FC STICH", 30, "#FFFFFF", "Barstitch Bold")
hl = motif("Herz", 50, color="#E53935")
hl.x = -150
st = motif("Stern", 45, color="#FDD835")
st.x = 150
w.doc.objects = [bg, hl, st, big]
w.doc.fabric = "#FFFFFF"
w.sync_items([])
hi = threads.hoop_for_size(190, 140)
parts = multihoop.split(w.doc, hi, 190, 140, 12, True)
save(multihoop.overview_image(w.doc, parts, 1100), "ex_multihoop")

print("fertig:", OUT)
