"""Erzeugt alle Bilder für die Anleitung (Bildschirmfotos und Stick-Beispiele).

Aufruf (mit eigenen, leeren Einstellungen – die echten bleiben unberührt):
  T=$(mktemp -d); mkdir -p $T/rt; chmod 700 $T/rt
  XDG_CONFIG_HOME=$T XDG_CACHE_HOME=$T XDG_DATA_HOME=$T XDG_RUNTIME_DIR=$T/rt \
  QT_QPA_PLATFORM=offscreen .venv/bin/python tools/manual/images.py build/manual/img
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build/manual/img"))
os.makedirs(OUT, exist_ok=True)

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QRadialGradient, QBrush
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox, QScrollArea

app = QApplication(sys.argv)
app.setApplicationName("StickStudio")
app.setApplicationDisplayName("StichWizard")
app.setStyle("Fusion")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard.__main__ import apply_light_palette, install_translations
apply_light_palette(app)
install_translations(app)
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from stichwizard import engine, icons, shapes, style
from stichwizard.engine import JUMP, STITCH, TRIM
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
from stichwizard.render import render_document

FONT = QFont("DejaVu Sans", 11)


def save(img, name):
    img.save(os.path.join(OUT, name + ".png"))
    print("Bild:", name)


# ---------------------------------------------------------------- Bausteine
def shape(geom, color="#E53935", **fill):
    o = EmbObject("shape")
    o.set_geometry(geom)
    o.fill.update(color=color, **fill)
    return o


def rect(w, h, r=1.5, **kw):
    return shape(shapes.rounded_rect(w, h, r), **kw)


def motif(name, size=30, **kw):
    fn = dict(shapes.MOTIFS)[name]
    o = EmbObject("shape", name)
    g = fn()
    from shapely import affinity
    b = g.bounds
    f = size / max(b[2] - b[0], b[3] - b[1])
    o.set_geometry(affinity.scale(g, f, f, origin=(0, 0)))
    o.fill.update(**kw)
    return o


def line(pts, **border):
    o = EmbObject("line")
    o.set_points(pts)
    o.border.update(**border)
    return o


def column(pts_a, pts_b, color="#1E88E5", **fill):
    o = EmbObject("satin")
    o.set_satin([[x, y, 0] for x, y in pts_a], [[x, y, 0] for x, y in pts_b])
    o.fill.update(color=color, **fill)
    return o


def text(t, font="", size=14, color="#1A237E", **kw):
    o = EmbObject("text", t)
    o.text.update(text=t, size=size, **kw)
    if font:
        from stichwizard import embfont
        fid = next((f["id"] for f in embfont.font_index() if f["name"].strip() == font), "")
        o.text["embfont"] = fid
    o.fill["color"] = color
    return o


def doc_of(objs, fabric="#FFFFFF", fabric_type="standard"):
    d = Document()
    d.objects = list(objs)
    d.fabric = fabric
    d.fabric_type = fabric_type
    return d


def render(objs, scale=8, fabric="#FFFFFF", jumps=False, margin=3):
    d = doc_of(objs, fabric)
    img = render_document(d, scale, margin=margin)
    if jumps:
        blocks = d.machine_blocks()
        xs = [s[0] for _, b in blocks for s in b]
        ys = [s[1] for _, b in blocks for s in b]
        minx, miny = min(xs) - margin, min(ys) - margin
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(scale, scale)
        p.translate(-minx, -miny)
        flat = [s for _, b in blocks for s in b]
        for a, b in zip(flat, flat[1:]):
            if b[2] == JUMP and engine.dist(a, b) > 1.6:
                pen = QPen(QColor("#FF6F00"), 0.35, Qt.DashLine)
                p.setPen(pen)
                p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
            if b[2] == TRIM:
                p.setPen(QPen(QColor("#D50000"), 0.4))
                p.drawLine(QPointF(b[0] - 1, b[1] - 1), QPointF(b[0] + 1, b[1] + 1))
                p.drawLine(QPointF(b[0] - 1, b[1] + 1), QPointF(b[0] + 1, b[1] - 1))
        p.end()
    return img


def stats(objs):
    d = doc_of(objs)
    blocks = d.machine_blocks()
    flat = [s for _, b in blocks for s in b]
    n = sum(1 for s in flat if s[2] == STITCH)
    j = sum(1 for a, b in zip(flat, flat[1:]) if b[2] == JUMP and engine.dist(a, b) > 1.6)
    return n, j


def grid(cells, cols, cell_px=230, label_h=44, pad=14, bg="#FFFFFF"):
    """cells: [(QImage, Beschriftung)] -> ein Bild mit Beschriftungen."""
    rows = math.ceil(len(cells) / cols)
    W = cols * (cell_px + pad) + pad
    H = rows * (cell_px + label_h + pad) + pad
    out = QImage(W, H, QImage.Format_ARGB32)
    out.fill(QColor(bg))
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
        if not img.isNull():
            s = min((cell_px - 16) / img.width(), (cell_px - 16) / img.height())
            w, h = img.width() * s, img.height() * s
            p.drawImage(QRectF(x0 + (cell_px - w) / 2, y0 + (cell_px - h) / 2, w, h), img)
        p.setPen(QColor("#2B2D3A"))
        p.drawText(QRectF(x0 - 4, y0 + cell_px + 4, cell_px + 8, label_h - 4),
                   Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, label)
    p.end()
    return out


def side_by_side(left, right, l_label, r_label, cell=420):
    return grid([(left, l_label), (right, r_label)], 2, cell_px=cell, label_h=50)


# ---------------------------------------------------------------- Programmsymbol
save(icons.app_logo(512).toImage(), "logo")

# ---------------------------------------------------------------- Beispiel-Design
def example_design():
    heart = motif("Herz", 46, color="#E53935", type="tatami", angle=45)
    heart.border.update(type="satin", width=2.5, color="#8E0000")
    heart.y = -8
    name = text("Anna", font="Amitaclo", size=13, color="#FFFFFF")
    name.y = -9
    star1 = motif("Stern", 13, color="#FDD835", type="tatami", angle=0)
    star1.border.update(type="satin", width=1.5, color="#F57F17")
    star1.x, star1.y = -32, -24
    star2 = star1.clone()
    star2.x, star2.y = 32, -24
    wave = line([(-34, 22), (-17, 17), (0, 22), (17, 27), (34, 22)], type="triple", color="#1E88E5",
                stitch_len=2.5)
    return [star1, star2, wave, heart, name]


# ---------------------------------------------------------------- Bildschirmfotos
w = MainWindow()
w.resize(1440, 900)
w.show()
QTest.qWait(200)
objs = example_design()
w.doc.objects = objs
w.sync_items([objs[3].id])
w.commit()
w.fit_hoop()
QTest.qWait(300)
save(w.grab().toImage(), "screen_main")

ribbon_h = w.ribbon.geometry().bottom() + 2
for i in range(w.ribbon.count()):
    w.ribbon.setCurrentIndex(i)
    QTest.qWait(80)
    name = w.ribbon.tabText(i).replace(" ", "_").lower()
    save(w.grab().toImage().copy(0, 0, 1440, ribbon_h), "ribbon_" + name)
w.ribbon.setCurrentIndex(0)
QTest.qWait(50)

# Eigenschaften einer Form (oben und unten)
w.props.set_object(objs[3])
QTest.qWait(150)
pg = w.props.mapTo(w, w.props.rect().topLeft())
save(w.grab().toImage().copy(pg.x(), pg.y(), w.props.width(), w.props.height()), "props_top")
sb = w.props.verticalScrollBar()
sb.setValue(sb.maximum())
QTest.qWait(100)
save(w.grab().toImage().copy(pg.x(), pg.y(), w.props.width(), w.props.height()), "props_bottom")
sb.setValue(0)

# Gruppe
w.scene.clearSelection()
for o in objs[:3]:
    w.items[o.id].setSelected(True)
w.group_selected()
w.scene.clearSelection()
w.items[objs[0].id].setSelected(True)
QTest.qWait(200)
save(w.grab().toImage().copy(0, ribbon_h, 1440, 900 - ribbon_h - 40), "screen_group")
w.ungroup_selected()

# Objektliste
w.scene.clearSelection()
w.side.setCurrentIndex(1) if hasattr(w.side, "setCurrentIndex") else None
QTest.qWait(120)
save(w.side.grab().toImage(), "panel_objects")
if hasattr(w.side, "setCurrentIndex"):
    w.side.setCurrentIndex(2)
    QTest.qWait(120)
    save(w.side.grab().toImage(), "panel_motifs")
    w.side.setCurrentIndex(0)

# Dichteprüfung: drei Flächen übereinander
keep_objs = list(w.doc.objects)
dens = [rect(60, 50, 3, color="#90CAF9"), rect(40, 34, 3, color="#42A5F5"),
        rect(22, 18, 3, color="#1565C0")]
w.doc.objects = dens
w.sync_items([])
w.commit()
w.a_density.setChecked(True)
w.toggle_density()
QTest.qWait(200)
cg = w.canvas.mapTo(w, w.canvas.rect().topLeft())
save(w.grab().toImage().copy(cg.x(), cg.y(), w.canvas.width(), w.canvas.height()), "screen_density")
w.a_density.setChecked(False)
w.toggle_density()
w.doc.objects = keep_objs
w.sync_items([])
w.commit()

# Simulator & Optimierer
from stichwizard.optimizer_dialog import OptimizerDialog
dlg = OptimizerDialog(w)
dlg.resize(1360, 860)
dlg.show()
QTest.qWait(500)
save(dlg.grab().toImage(), "screen_simulator")
dlg.close()

# Einstellungen
from stichwizard.prefs import SettingsDialog
sd = SettingsDialog(w.prefs, w, w.action_catalog())
sd.resize(720, 620)
sd.show()
for i in range(sd.tabs.count()):
    sd.tabs.setCurrentIndex(i)
    QTest.qWait(80)
    save(sd.grab().toImage(), "settings_" + sd.tabs.tabText(i).replace(" ", "_").lower())
sd.reject()

# Stickschrift-Auswahl
from stichwizard.fontdialog import EmbFontDialog
fd = EmbFontDialog("", "Anna", w)
fd.resize(900, 640)
fd.show()
QTest.qWait(600)
save(fd.grab().toImage(), "dialog_fonts")
fd.reject()

# Fotostich (Testbild: Kreise mit Verlauf)
img = QImage(400, 400, QImage.Format_RGB32)
img.fill(QColor("#F5E6C8"))
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
g = QRadialGradient(QPointF(170, 160), 170)
g.setColorAt(0, QColor("#FFD54F"))
g.setColorAt(0.6, QColor("#F57C00"))
g.setColorAt(1, QColor("#5D4037"))
p.setBrush(QBrush(g))
p.setPen(Qt.NoPen)
p.drawEllipse(QPointF(200, 200), 160, 160)
p.setBrush(QColor("#2E7D32"))
p.drawEllipse(QPointF(280, 90), 55, 30)
p.end()
photo_path = os.path.join(OUT, "_photo_input.png")
img.save(photo_path)
from stichwizard.photostitch import PhotoStitchDialog
ps = PhotoStitchDialog(w)
if hasattr(ps, "load"):
    try:
        ps.load(photo_path)
    except Exception:
        pass
ps.resize(1000, 680)
ps.show()
QTest.qWait(1200)
save(ps.grab().toImage(), "dialog_photo")
ps.reject()

# Bild-Assistent (Testbild), hineingezoomt mit Stich-Vorschau
from stichwizard.autodigitize import DigitizeDialog
dd = DigitizeDialog(w)
dd.resize(1180, 760)
dd.show()
dd.load(photo_path)
QTest.qWait(300)
dd.show_mode.setCurrentIndex(1)
QTest.qWait(300)
dd.prev.zoom_by(2.5)
QTest.qWait(200)
save(dd.grab().toImage(), "dialog_digitize")
dd.reject()

# ---- Designstudio
from stichwizard.curves import CORNER, CTRL, CURVE
w.doc.objects = []
w.sync_items([])
leaf = EmbObject("shape", "Blatt")
w._set_world_curve(leaf, [[[-25, 10, CORNER], [-25, -12, CTRL], [10, -22, CTRL], [25, -5, CURVE],
                           [32, 3, CTRL], [5, 22, CTRL]]])
leaf.fill.update(color="#43A047", angle=30)
w.add_objects([leaf])
w.set_tool("nodes")
st = w.canvas._node_state()
w.canvas._node_sel = {(0, 3)}
w.fit_rect = None
w.canvas.fit_rect(w.items[leaf.id].sceneBoundingRect().adjusted(-15, -15, 15, 15))
QTest.qWait(200)
cg = w.canvas.mapTo(w, w.canvas.rect().topLeft())
save(w.grab().toImage().copy(cg.x(), cg.y(), w.canvas.width(), w.canvas.height()), "ds_bezier")
w.set_tool("select")
lp = w.layers_panel
lp.action.emit("add", w.doc.active_layer)
lp.renamed.emit(w.doc.active_layer, "Schrift")
w.side.setCurrentWidget(lp)
QTest.qWait(150)
save(w.side.grab().toImage(), "ds_layers")
w.side.setCurrentWidget(w.props)
from stichwizard import templates as _tpl
td = _tpl.TemplateDialog(w)
td.show()
td.list.setCurrentRow(2)
QTest.qWait(400)
save(td.grab().toImage(), "ds_templates")
td.close()
cells = []
for key, title, *_ in _tpl.TEMPLATES:
    cells.append((render(_tpl.build(key), 5), title))
save(grid(cells, 4, cell_px=220), "ds_template_grid")
from stichwizard import fontmaker
fw = fontmaker.FontWorkshop(w)
fw.show()
fw.make_from_system()
QTest.qWait(300)
save(fw.grab().toImage(), "ds_fontshop")
fw.close()
fontmaker.delete_font(fontmaker.font_id("Meine Schrift"))
w.doc.objects = []
w.sync_items([])

# Mehrfach-Export
from stichwizard.multiexport import MultiExportDialog
me = MultiExportDialog(w.doc, OUT, "Namensschild", parent=w)
me.show()
QTest.qWait(100)
save(me.grab().toImage(), "dialog_multiexport")
me.reject()

# Dunkles Farbschema
w.prefs.set("ui_theme", "dark")
w.apply_ui()
QTest.qWait(300)
save(w.grab().toImage().scaled(1080, 675, Qt.KeepAspectRatio, Qt.SmoothTransformation), "screen_dark")
w.prefs.set("ui_theme", "light")
w.apply_ui()
QTest.qWait(100)

# ---------------------------------------------------------------- Stick-Beispiele
save(render(example_design(), 10), "ex_design")

# Füllarten
cells = []
from stichwizard.widgets import FILL_TYPES, TATAMI_PATTERNS
for label, key in FILL_TYPES:
    if key in ("none",):
        continue
    o = rect(30, 30, 3, color="#00897B", type=key, angle=45 if key != "tartan" else 0)
    if key == "guided":
        o.fill["guide"] = [[-15, 6], [-7, -6], [0, 0], [7, 6], [15, -4]]
    if key == "gradient":
        o.fill.update(color="#1E88E5", color2="#FDD835", gradient_colors=["#E53935"])
    if key == "applique":
        o.border.update(width=3, color="#6A1B9A")
        o.fill["color"] = "#B39DDB"
    cells.append((render([o], 8), label))
save(grid(cells, 4), "fills")

# Tatami-Einstichmuster (große Stichlänge, damit das Muster sichtbar ist)
cells = []
for label, key in TATAMI_PATTERNS:
    o = rect(26, 26, 1, color="#C62828", pattern=key, angle=0, underlay=False, stitch_len=3.5)
    cells.append((render([o], 12), label))
save(grid(cells, 5, cell_px=200), "patterns")

# Ränder und Linienarten
cells = []
for label, key in (("Steppstich", "run"), ("Bohnenstich (dreifach)", "triple"),
                   ("Satinstich", "satin"), ("Zickzack", "zigzag"), ("E-Stich", "estitch"),
                   ("Manuell", "manual")):
    o = line([(0, 0), (12, -8), (24, 4), (36, -6)], type=key, color="#283593", width=3,
             stitch_len=2.5 if key != "manual" else 2.5)
    cells.append((render([o], 9), label))
o = line([(0, 0), (12, -8), (24, 4), (36, -6)], type="triple", color="#283593", bean_pattern="2 0 0")
cells.append((render([o], 9), "Bohnenstich-Muster »2 0 0«"))
o = line([(0, 0), (12, -8), (24, 4), (36, -6)], type="run", color="#283593", len_random=40)
cells.append((render([o], 9), "Zufällige Stichlänge 40 %"))
save(grid(cells, 4, cell_px=220), "lines")

# Satin-Ecken
a = line([(0, 0), (25, 0), (25, 20), (5, 8)], type="satin", width=4, color="#283593", corner="none")
b = line([(0, 0), (25, 0), (25, 20), (5, 8)], type="satin", width=4, color="#283593", corner="mitre")
save(side_by_side(render([a], 12), render([b], 12), "Einfach: Garnstau innen, Lücke außen",
                  "Gehrung: Fächer um die Ecke, innen verkürzt"), "satin_corners")

# Satinsäulen-Arten
wave_a = [(x, 3 + 2 * math.sin(x / 6)) for x in range(-20, 21, 4)]
wave_b = [(x, -3 + 2 * math.sin(x / 6)) for x in range(-20, 21, 4)]
cells = []
for label, kw in (("Satin", {}), ("Zickzack-Satin", {"satin_type": "zigzag"}),
                  ("E-Stich", {"satin_type": "estitch"}),
                  ("Zufällige Breite 30 %", {"width_random": 30.0}),
                  ("Kurve mit kurzen Stichen", {}), ("Mehrfarbig (3 Streifen)", None)):
    if label.startswith("Kurve"):
        arc_a = [(14 * math.cos(t / 10 * math.pi), 14 * math.sin(t / 10 * math.pi)) for t in range(11)]
        arc_b = [(8 * math.cos(t / 10 * math.pi), 8 * math.sin(t / 10 * math.pi)) for t in range(11)]
        cells.append((render([column(arc_a, arc_b, short_inset=30.0)], 9), label))
        continue
    if kw is None:
        parts = []
        for i, col in enumerate(("#E53935", "#FDD835", "#1E88E5")):
            t0, t1 = max(0, i / 3 - 0.05), min(1, (i + 1) / 3 + 0.05)
            lerp = lambda p, q, t: (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
            parts.append(column([lerp(p, q, t0) for p, q in zip(wave_a, wave_b)],
                                [lerp(p, q, t1) for p, q in zip(wave_a, wave_b)], color=col,
                                underlay=i == 0))
        cells.append((render(parts, 9), label))
        continue
    cells.append((render([column(wave_a, wave_b, **kw)], 9), label))
save(grid(cells, 3, cell_px=260), "satin_types")

# Auto-Satin: vorher / nachher
def h_columns():
    def col(x0, y0, x1, y1, h=1.6):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        nx, ny = -dy / L * h, dx / L * h
        return column([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny)], [(x0 - nx, y0 - ny), (x1 - nx, y1 - ny)],
                      color="#6A1B9A")
    return [col(-12, -15, -12, 15), col(12, 15, 12, -15), col(-12, 0, 12, 0)]
before = h_columns()
nb, jb = stats(before)
w.doc.objects = h_columns()
w.sync_items([o.id for o in w.doc.objects])
w.auto_satin()
after = list(w.doc.objects)
na, ja = stats(after)
save(side_by_side(render(before, 10, jumps=True), render(after, 10, jumps=True),
                  f"Vorher: {jb} Sprünge (orange)", f"Auto-Satin: {ja} Sprünge – Wege unter den Säulen"),
     "autosatin")

# Farbverlauf und Tartan
cells = []
g2 = rect(34, 26, 2, type="gradient", color="#1E88E5", color2="#FDD835", angle=0)
g4 = rect(34, 26, 2, type="gradient", color="#4A148C", color2="#E91E63",
          gradient_colors=["#FF9800", "#FFEB3B"], angle=0)
cells += [(render([g2], 8), "Verlauf 2 Farben"), (render([g4], 8), "Verlauf 4 Farben")]
for name in ("Royal Stewart", "Black Watch", "Buchanan"):
    t = rect(34, 26, 2, type="tartan", angle=0, tartan=[list(x) for x in engine.TARTAN_PRESETS[name]])
    cells.append((render([t], 8), "Tartan " + name))
save(grid(cells, 5, cell_px=210), "gradient_tartan")

# Applikation
ap = motif("Herz", 40, type="applique", color="#F8BBD0")
ap.border.update(width=3, color="#AD1457")
save(render([ap], 9), "applique")

# 3D-Puff
pc = column([(-20, 4), (-6, 6), (6, 6), (20, 4)], [(-20, -4), (-6, -2), (6, -2), (20, -4)],
            color="#00838F")
plain = render([pc], 10)
pc2 = column([(-20, 4), (-6, 6), (6, 6), (20, 4)], [(-20, -4), (-6, -2), (6, -2), (20, -4)],
             color="#00838F", puff=True, satin_ul="center", density=0.25, auto_spacing=False,
             pull=0.0, split_len=15.0, short_inset=0.0)
save(side_by_side(plain, render([pc2], 10), "Normale Satinsäule",
                  "3D-Puff: dichter, Endkappen an beiden Enden"), "puff")

# Überlappung entfernen: vorher/nachher (Stichansicht als Linien)
QInputDialog.getDouble = staticmethod(lambda *a, **k: (1.0, True))
def overlap_objs():
    low = rect(50, 34, 2, color="#43A047", angle=0)
    top = rect(36, 24, 4, color="#FDD835", angle=90)
    return [low, top]
ov = overlap_objs()
n0, _ = stats(ov)
w.doc.objects = overlap_objs()
w.sync_items([])
w.remove_overlaps()
ov2 = list(w.doc.objects)
n1, _ = stats(ov2)
hidden = [ov2[0]]
save(side_by_side(render(ov, 8), render(hidden, 8),
                  f"Design vorher: {n0:,} Stiche".replace(",", "."),
                  f"Nachher: {n1:,} Stiche (gelbe Fläche hier ausgeblendet)".replace(",", ".")),
     "overlap")

# Stoffarten: Dichte im Vergleich (Ausschnitt)
cells = []
for key in ("standard", "towel", "leather"):
    engine.FABRIC = key
    o = rect(24, 16, 1, color="#5D4037", angle=0)
    n = sum(1 for _, b in o.stitch_blocks() for s in b if s[2] == STITCH)
    cells.append((render([o], 12), f"{engine.FABRIC_PROFILES[key]['name']}\n{n:,} Stiche".replace(",", ".")))
engine.FABRIC = "standard"
save(grid(cells, 3, cell_px=260, label_h=56), "fabrics")

# Kurvenanpassung
circ = [(5 * math.cos(t / 60 * 2 * math.pi), 5 * math.sin(t / 60 * 2 * math.pi)) for t in range(61)]
engine.CURVE_TOL = 0.0
c0 = line(circ, type="run", stitch_len=3.0, color="#283593")
im0 = render([c0], 22)
engine.CURVE_TOL = 0.2
c1 = line(circ, type="run", stitch_len=3.0, color="#283593")
im1 = render([c1], 22)
save(side_by_side(im0, im1, "Ohne Kurvenanpassung: eckig", "Mit Kurvenanpassung: rund"), "curves")

# Unterlage: Lagen
cells = []
for label, kw in (("Ohne Unterlage", {"underlay": False}), ("Eine Lage + Randlinie", {}),
                  ("Zwei Lagen (gekreuzt)", {"ul_layers": 2})):
    o = rect(26, 18, 1, color="#90CAF9", angle=45, density=1.6, **kw)   # locker: Unterlage sichtbar
    cells.append((render([o], 10), label))
save(grid(cells, 3, cell_px=240), "underlay")

# Vernähstiche (stark vergrößert)
cells = []
for key in ("half", "backforth", "arrow", "star", "triangle", "zigzag"):
    old = engine.TIE_STYLE
    engine.TIE_STYLE = key
    pts = []
    engine.connect(pts, engine.running_stitch([(0, 0), (8, 0)], 2.5))
    engine.TIE_STYLE = old
    img = QImage(300, 140, QImage.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(30, 70)
    p.scale(30, 30)
    p.setPen(QPen(QColor("#1565C0"), 0.07))
    for a, b in zip(pts, pts[1:]):
        p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
    p.setBrush(QColor("#D50000"))
    p.setPen(Qt.NoPen)
    for s in pts:
        p.drawEllipse(QPointF(s[0], s[1]), 0.07, 0.07)
    p.end()
    label = dict((k, l) for l, k in engine.TIE_NAMES)[key]
    cells.append((img, label))
save(grid(cells, 3, cell_px=220), "ties")

# Element für Element / Sprünge im Beispiel
save(render(example_design(), 8, jumps=True), "ex_jumps")

# Schriften
cells = []
for name in ("Amitaclo", "Allegria 55", "Apex Lake"):
    t = text("Stich", font=name, size=14, color="#1A237E")
    cells.append((render([t], 8), name))
t = text("Stich", size=14, color="#1A237E")
cells.append((render([t], 8), "Computerschrift (automatisch)"))
save(grid(cells, 4, cell_px=230), "fonts")

# Text an Pfad
arc = [(-30 + 3 * i, -0.06 * (3 * i - 30) ** 2 + 8) for i in range(21)]
t = text("Text am Bogen", font="Amitaclo", size=8, color="#C62828")
t.text["path"] = arc
save(render([t], 9), "textpath")

# Beispiel: Namensschild Schritt für Schritt
step1 = rect(70, 26, 6, color="#FFF3E0", type="tatami", angle=0)
step1.border.update(type="satin", width=3, color="#E65100")
n1_ = text("Mia", font="Amitaclo", size=14, color="#E65100")
save(render([step1], 7), "step_badge1")
save(render([step1, n1_], 7), "step_badge2")

# Beispiel: Applikation mit Name
ap2 = rect(60, 40, 8, type="applique", color="#B2DFDB")
ap2.border.update(width=3, color="#00695C")
n2 = text("Ben", font="Amitaclo", size=14, color="#004D40")
save(render([ap2, n2], 7), "ex_applique_name")

# Beispiel: Puff-Kappe
cap_letters = text("CAP", font="Amitaclo", size=20, color="#FAFAFA")
save(render([cap_letters], 8, fabric="#22304A"), "ex_cap")

# ---------------------------------------------------------------- Verzieren & Assistenten (1.24–1.31)
from stichwizard import (crossstitch, encore, familytree, ith, machinesend, ornaments, printapp,
                         quilt, spiro, stones, video, wordsculpt)
from stichwizard import templates as _tpl
from stichwizard.crossdialog import CrossDialog
from stichwizard.paintdialog import PaintDialog
from stichwizard.stitcheditor import StitchEditor


def built(key, tpls, vals=None, context=True):
    objs = _tpl.build(key, vals, tpls)
    return objs if context else [o for o in objs if not getattr(o, "_context", False)]


def tpl_grid(tpls, cols, scale, name, cell_px=220, context=True):
    cells = [(render(built(k, tpls, context=context), scale), t) for k, t, *_ in tpls]
    save(grid(cells, cols, cell_px=cell_px), name)


def dialog_shot(tpls, title, icon, name, row=0, thumbs=False):
    td = _tpl.TemplateDialog(w, tpls, title, icon, thumbs=thumbs)
    td.show()
    td.list.setCurrentRow(row)
    QTest.qWait(500)
    save(td.grab().toImage(), name)
    td.close()


tpl_grid(ornaments.ORNAMENTS, 3, 2.4, "orn_grid", cell_px=240)
heart = motif("Herz", 16, color="#D81B60")
enc, _ = encore.encore_templates([heart])
tpl_grid(enc, 5, 1.8, "encore_grid", cell_px=200)
dialog_shot(enc, "Encore – Muster wiederholen", "encore", "dialog_encore")
star = motif("Stern", 40, color="#1E88E5")
st_t = stones.stone_templates([star])
save(grid([(render([star], 6), "Ausgangsform")] +
          [(render([star] + built(k, st_t, context=False), 6), t) for k, t, *_ in st_t], 4,
          cell_px=220), "stones_grid")
tpl_grid(spiro.SPIRO, 4, 2.2, "spiro_grid")
ws = wordsculpt.sculpt_templates([])
save(side_by_side(render(built("shape", ws, {"shape": "Herz"}), 4),
                  render(built("shape", ws, {"shape": "Stern"}), 4),
                  "Herzform", "Sternform", cell=380), "wordsculpt")
tpl_grid(ith.PROJECTS, 5, 1.3, "ith_grid", cell_px=200)
dialog_shot(ith.PROJECTS, "Projekt im Rahmen", "ith", "dialog_ith", thumbs=True)
tpl_grid(quilt.quilt_templates(), 5, 1.4, "quilt_grid", cell_px=200)
save(side_by_side(render(built("pedigree", familytree.FAMILY), 2.2),
                  render(built("tree", familytree.FAMILY), 2.2),
                  "Ahnentafel", "Familienbaum", cell=440), "family")

# Kreuzstich aus einem Bild
src = QImage(300, 300, QImage.Format_ARGB32)
src.fill(QColor("#FFFFFF"))
pp = QPainter(src)          # ohne Kantenglättung: sonst werden Mischfarben zu Garnfarben
pp.setPen(Qt.NoPen)
pp.setBrush(QColor("#2E7D32"))
pp.drawEllipse(QRectF(40, 170, 110, 60))
pp.drawEllipse(QRectF(150, 170, 110, 60))
pp.setBrush(QColor("#C62828"))
for k in range(6):
    a = k * math.pi / 3
    pp.drawEllipse(QPointF(150 + 55 * math.cos(a), 120 + 55 * math.sin(a)), 42, 42)
pp.setBrush(QColor("#F9A825"))
pp.drawEllipse(QPointF(150, 120), 34, 34)
pp.end()
cells_, pal, rows = crossstitch.from_image(src, 36, 3)
cdata = crossstitch.new(36, rows, 2.5, pal)
cdata["cells"] = [list(c) for c in cells_]
cd = CrossDialog(w, cdata, "#FFFFFF", (130, 180))
cd.show()
QTest.qWait(300)
save(cd.grab().toImage(), "dialog_cross")
cd.close()
co = EmbObject("cross")
co.cross = cdata
save(render([co], 5), "cross_ex")

# Mal-Atelier und Druck-Applikation
pd = PaintDialog(w, None, (90, 70))
pa = QPainter(pd.img)
pd.filled.setChecked(True)
for col, tool, a, b in (("#FFF59D", "rect", (40, 40), (680, 520)),
                        ("#FB8C00", "ellipse", (220, 120), (500, 400)),
                        ("#E53935", "ellipse", (300, 200), (420, 320))):
    pd.set_color(col)
    pd.set_tool(tool)
    pd.draw_shape(pa, QPointF(*a), QPointF(*b))
pa.end()
pd.set_color("#1E88E5")
pd.set_tool("brush")
for x in range(80, 640, 40):
    pd.stroke(QPointF(x, 470), QPointF(x + 30, 450))
pd.show()
QTest.qWait(300)
save(pd.grab().toImage(), "dialog_paint")
pd.close()
art = QImage(400, 400, QImage.Format_ARGB32)
art.fill(Qt.transparent)
pp = QPainter(art)
pp.setRenderHint(QPainter.Antialiasing)
pp.setPen(Qt.NoPen)
gr = QRadialGradient(200, 200, 170)
gr.setColorAt(0, QColor("#FFF176"))
gr.setColorAt(0.6, QColor("#FFB300"))
gr.setColorAt(1, QColor("#E65100"))
pp.setBrush(QBrush(gr))
pp.drawEllipse(QRectF(40, 40, 320, 320))
pp.setBrush(QColor("#5D4037"))
pp.drawEllipse(QRectF(140, 150, 30, 40))
pp.drawEllipse(QRectF(230, 150, 30, 40))
pp.setPen(QPen(QColor("#5D4037"), 14, Qt.SolidLine, Qt.RoundCap))
pp.setBrush(Qt.NoBrush)
pp.drawArc(QRectF(130, 170, 140, 110), 200 * 16, 140 * 16)
pp.end()
po = printapp.make(art, 50, 50)
ap = printapp.applique(po, "motif", "#3E2723", 3.0)
save(side_by_side(render([po], 8), render([po, ap], 8), "Druckbild (auf Stoff gedruckt)",
                  "mit Applikationsrand gestickt"), "print_applique")

# Skizzenstich
curve = [(16 * math.sin(t) ** 3, -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t)
                                    - math.cos(4 * t))) for t in [i * math.pi / 60 for i in range(121)]]
plain = line(curve, type="run", stitch_len=2.0, color="#37474F")
sk = line(curve, type="sketch", width=1.6, repeats=2, stitch_len=2.0, color="#37474F")
save(side_by_side(render([plain], 9), render([sk], 9), "Steppstich", "Skizzenstich (Bleistift)"),
     "sketch")

# Stich-Editor, An Maschine senden, Video
d_ex = doc_of(example_design())
blocks = [{"color": c, "stitches": [list(s) for s in st]} for c, st in d_ex.machine_blocks() if st]
ed = StitchEditor(w, blocks)
ed.show()
QTest.qWait(200)
ed.view.fit()
ed.set_current((1, 40))
QTest.qWait(150)
save(ed.grab().toImage(), "dialog_stitcheditor")
ed.close()
_drives, _free = machinesend.removable_drives, machinesend._free
machinesend.removable_drives = lambda: [("/run/media/anna/STICKMASCHINE", "STICKMASCHINE")]
machinesend._free = lambda p: 7.6e9
sd_ = machinesend.SendDialog(w, {"name": "Brother Innov-is", "format": "pes"}, "Emblem", [],
                             "12.480 Stiche · 4 Farben · 92 × 88 mm")
sd_.show()
QTest.qWait(150)
save(sd_.grab().toImage(), "dialog_send")
sd_.close()
machinesend.removable_drives, machinesend._free = _drives, _free
from stichwizard.threads import thread_name
fr = video._Frames(d_ex, (960, 540), show_hoop=False, thread_name=thread_name)
fr.advance(int(fr.total * 0.62))
save(fr.frame(), "video_frame")

print("fertig:", OUT)
