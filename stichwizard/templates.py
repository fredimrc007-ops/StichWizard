"""Design-Vorlagen: fertige, anpassbare Layouts (Namensschild, Wappen, Emblem, Kranz,
Monogramm, Aufnäher). Jede Vorlage beschreibt ihre Felder und baut daraus Objekte um (0, 0)."""
import math

from shapely import affinity
from shapely.geometry import Point, Polygon

from . import shapes
from .model import EmbObject

FONTS = {"block": "Geneva Simple Sans", "script": "Amitaclo", "script2": "Allegria 20",
         "mono": "Caesarus SC FI", "small": "Ink/Stitch Small Font"}
FONT_CHOICES = [("Blockschrift", "block"), ("Schreibschrift", "script"),
                ("Schreibschrift fein", "script2")]


def _font_id(key):
    from . import embfont
    name = FONTS.get(key, key)
    return next((f["id"] for f in embfont.font_index() if f["name"].strip() == name), "")


def _font_range(key):
    from . import embfont
    name = FONTS.get(key, key)
    f = next((f for f in embfont.font_index() if f["name"].strip() == name), None)
    return (f["min"], f["max"]) if f else (6.0, 60.0)


def fit(o, max_w, max_h=None, font="block"):
    """Schriftzug in die verfügbare Breite (und Höhe) einpassen: erst kleiner setzen (bis zur
    kleinsten empfohlenen Größe der Stickschrift), dann notfalls schmaler skalieren."""
    xs, ys = [], []
    for _, b in o.stitch_blocks():
        xs += [p[0] for p in b]
        ys += [p[1] for p in b]
    if not xs:
        return o
    wid, hei = max(xs) - min(xs), max(ys) - min(ys)
    f = min(1.0, max_w / max(wid, 1e-6), (max_h / max(hei, 1e-6)) if max_h else 1.0)
    if f < 1.0:
        lo = _font_range(font)[0]
        size = o.text["size"]
        new = max(lo, size * f)
        o.text["size"] = new
        rest = f * size / new
        if rest < 0.999:
            o.sx = o.sy = rest            # kleiner als die Mindestgröße: gleichmäßig verkleinern
    return o


def text(t, height, color, font="block", x=0.0, y=0.0, path=None, flip=False, max_w=None,
         max_h=None):
    lo, hi = _font_range(font)
    o = EmbObject("text", t[:24] or "Text")
    o.text.update(text=t or " ", size=max(lo, min(hi, height)), embfont=_font_id(font))
    o.fill["color"] = color
    o.x, o.y = x, y
    if max_w:
        fit(o, max_w, max_h, font)
    if path:
        o.text["path"] = [[px - x, py - y] for px, py in path]
        o.text["path_align"] = "center"
        o.text["path_flip"] = flip
    return o


def shape(geom, fill, border=None, width=3.0, name="Form", fill_type="tatami", angle=45.0):
    o = EmbObject("shape", name)
    o.set_geometry(geom)
    o.fill.update(color=fill, type=fill_type, angle=angle)
    if border:
        o.border.update(type="satin", color=border, width=width)
    return o


def motif(name, size, color, x=0.0, y=0.0, rot=0.0, border=None):
    g = dict(shapes.MOTIFS)[name]()
    b = g.bounds
    f = size / max(b[2] - b[0], b[3] - b[1])
    g = affinity.scale(g, f, f, origin=(0, 0))
    o = shape(g, color, border, 1.2, name)
    o.x, o.y, o.rot = x, y, rot
    return o


def arc(r, a0, a1, n=40, cy=0.0):
    """Punkte auf einem Kreisbogen (Grad, 0° = rechts, im Uhrzeigersinn wie y nach unten)."""
    return [(r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


# ---------------------------------------------------------------- Vorlagen
def name_badge(p):
    w, h = p["width"], p["width"] * 0.38
    plate = shape(shapes.rounded_rect(w, h, h * 0.25), p["bg"], p["border"], 3.0, "Schild",
                  angle=0)
    name = text(p["name"], h * 0.55, p["color"], p["font"], max_w=w - h * 0.5)
    out = [plate, name]
    if p["sub"]:
        name.y = -h * 0.08
        out.append(text(p["sub"], max(6.0, h * 0.18), p["color"], "block", 0, h * 0.3))
    return out


def shield(p):
    w = p["width"]
    h = w * 1.2
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h * 0.05)]
    pts += [(w / 2 * math.cos(t), h * 0.05 + (h * 0.45) * math.sin(t))
            for t in [k * math.pi / 24 for k in range(1, 24)]]
    pts += [(-w / 2, h * 0.05)]
    sh = shape(Polygon(pts), p["bg"], p["border"], 3.5, "Wappen", angle=135)
    out = [sh]
    if p["star"]:
        out.append(motif("Stern", w * 0.28, p["accent"], 0, -h * 0.22))
    out.append(text(p["top"], w * 0.17, p["color"], "block", 0, h * 0.05 if p["star"] else -h * 0.1,
                    max_w=w * 0.8))
    if p["bottom"]:
        out.append(text(p["bottom"], w * 0.11, p["color"], "block", 0, h * 0.25))
    return out


def round_emblem(p):
    d = p["diameter"]
    r = d / 2
    ring = shape(Point(0, 0).buffer(r, 64), p["bg"], p["border"], 3.5, "Emblem", angle=30)
    th = max(6.0, d * 0.11)
    rt = r - 4.5 - th * 0.85
    out = [ring]
    out.append(text(p["top"], th, p["color"], "block", 0, 0, arc(rt, 200, 340), flip=False))
    if p["bottom"]:
        out.append(text(p["bottom"], th * 0.85, p["color"], "block", 0, 0,
                        arc(r - 4.0 - th * 0.2, 160, 20), flip=False))
    if p["center"] != "none":
        out.append(motif(p["center"], d * 0.32, p["accent"], 0, 0))
    return out


def wreath(p):
    d = p["diameter"]
    r = d / 2
    out = []
    n = int(p["leaves"])
    for k in range(n):
        a = 360.0 * k / n
        if 75 < a % 360 < 105:              # unten offen lassen (wie ein Kranz mit Schleife)
            continue
        x, y = r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
        out.append(motif("Blatt", d * 0.2, p["leaf"], x, y, a + 90))
    out.append(motif("Herz", d * 0.12, p["accent"], 0, r))
    out.append(text(p["text"], d * 0.24, p["color"], p["font"], 0, 0))
    return out


def monogram(p):
    d = p["diameter"]
    ring = EmbObject("line", "Ring")
    pts = arc(d / 2, 0, 360, 72)[:-1]
    ring.set_points(pts, closed=True)
    ring.border.update(type="satin", width=2.0, color=p["ring"])
    out = [ring]
    out.append(text(p["letter"][:2].upper(), d * 0.55, p["color"], "mono", 0, -d * 0.02))
    for x in (-d * 0.36, d * 0.36):
        out.append(motif("Stern 8", d * 0.1, p["ring"], x, 0))
    if p["name"]:
        out.append(text(p["name"], max(10.0, d * 0.13), p["color"], "script2", 0, d / 2 + d * 0.14))
    return out


def patch(p):
    w = p["width"]
    form = p["form"]
    if form == "oval":
        g = affinity.scale(Point(0, 0).buffer(1, 64), w / 2, w * 0.32)
        h = w * 0.64
    elif form == "round":
        g = Point(0, 0).buffer(w / 2, 64)
        h = w
    else:
        h = w * 0.55
        g = shapes.rounded_rect(w, h, 4)
    base = shape(g, p["bg"], p["border"], 4.0, "Aufnäher", angle=0)
    base.fill["underlay_first"] = True
    return [base, text(p["text"], min(h * 0.4, w * 0.18), p["color"], p["font"], max_w=w * 0.72,
                       max_h=h * 0.5)]


def birth(p):
    w = p["width"]
    out = [motif("Mond", w * 0.17, p["accent"], -w * 0.38, -w * 0.13),
           motif("Stern", w * 0.08, p["accent"], -w * 0.25, -w * 0.2),
           motif("Stern", w * 0.06, p["accent"], w * 0.36, -w * 0.15)]
    name = text(p["name"], w * 0.24, p["color"], "script", 0, 0, max_w=w * 0.7)
    out.append(name)
    hs = max(4.0, w * 0.07)
    y = w * 0.17
    for line in (p["date"], p["info"]):
        if line:
            out.append(text(line, hs, p["color2"], "small", 0, y, max_w=w * 0.9))
            y += hs * 1.6
    return out


def wedding(p):
    w = p["width"]
    heart = EmbObject("line", "Herz")
    g = dict(shapes.MOTIFS)["Herz"]()
    b = g.bounds
    f = w / max(b[2] - b[0], b[3] - b[1])
    g = affinity.scale(g, f, f, origin=(0, 0))
    heart.set_points(list(g.exterior.coords)[:-1], closed=True)
    heart.border.update(type="satin", width=2.0, color=p["heart"])
    x0, y0, x1, y1 = g.bounds
    cy = y0 + (y1 - y0) * 0.42                 # Mitte des breiten Herz-Teils
    th = (y1 - y0) * 0.17
    out = [heart]
    out.append(text(p["name1"], th, p["color"], "script2", 0, cy - th * 0.95, max_w=w * 0.62))
    out.append(text("&", th * 0.7, p["heart"], "script2", 0, cy + th * 0.1))
    out.append(text(p["name2"], th, p["color"], "script2", 0, cy + th * 1.15, max_w=w * 0.5))
    if p["date"]:
        out.append(text(p["date"], max(4.0, w * 0.06), p["color"], "small", 0, y1 + w * 0.08,
                        max_w=w * 0.8))
    return out


def banner(p):
    w, h = p["width"], p["width"] * 0.2
    k = h * 0.6
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2 - k, 0), (w / 2, h / 2), (-w / 2, h / 2),
           (-w / 2 + k, 0)]
    band = shape(Polygon(pts), p["bg"], p["border"], 2.0, "Schriftband", angle=0)
    return [band, text(p["text"], h * 0.55, p["color"], p["font"], max_w=w - 2 * k - 6,
                       max_h=h * 0.7)]


def border_strip(p):
    n = int(p["count"])
    L = p["length"]
    step = L / max(1, n - 1) if n > 1 else 0
    out = []
    wave = [(x, 2.0 * math.sin(x / max(step, 1) * math.pi)) for x in
            [(-L / 2) + L * k / 120 for k in range(121)]]
    ln = EmbObject("line", "Ranke")
    ln.set_points(wave)
    ln.border.update(type="triple", color=p["line"], stitch_len=2.5)
    out.append(ln)
    for k in range(n):
        x = -L / 2 + k * step
        out.append(motif(p["motif"], p["size"], p["color"], x, 0))
    return out


def heart_name(p):
    w = p["width"]
    heart = motif("Herz", w, p["bg"])
    heart.border.update(type="satin", width=2.5, color=p["border"])
    return [heart, text(p["name"], w * 0.22, p["color"], p["font"], 0, -w * 0.06, max_w=w * 0.6)]


def frame_corners(p):
    w, h = p["width"], p["width"] * 0.62
    fr = EmbObject("line", "Rahmen")
    fr.set_points([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)], closed=True)
    fr.border.update(type="satin", width=2.0, color=p["frame"])
    out = [fr]
    for x in (-w / 2, w / 2):
        for y in (-h / 2, h / 2):
            out.append(motif("Stern 8", w * 0.1, p["accent"], x, y))
    lines = [t for t in p["text"].split("/") if t.strip()]
    th = min(h * 0.3, (h - 10) / max(1, len(lines)) / 1.25)
    y0 = -(len(lines) - 1) * th * 0.65
    for i, t in enumerate(lines):
        out.append(text(t.strip(), th, p["color"], p["font"], 0, y0 + i * th * 1.3,
                        max_w=w - 16, max_h=th * 1.3))
    return out


T = lambda *a: a       # (schlüssel, beschriftung, art, …) – wie controls.ask_values
TEMPLATES = [
    ("badge", "Namensschild", "Abgerundetes Schild mit Satinrand und Namen – für Taschen, "
     "Handtücher, Kindergarten.", [
         T("name", "Name", "text", "Mia"), T("sub", "Zusatzzeile", "text", ""),
         T("font", "Schrift", "choice", FONT_CHOICES, "script"),
         T("width", "Breite", "num", 40.0, 160.0, 5.0, 0, " mm", 80.0),
         T("bg", "Grundfarbe", "color", "#FFF3E0"), T("border", "Rand", "color", "#E65100"),
         T("color", "Schriftfarbe", "color", "#E65100")], name_badge),
    ("shield", "Wappen / Abzeichen", "Schild mit Rand, Stern und zwei Textzeilen – Verein, "
     "Schule, Feuerwehr.", [
         T("top", "Text", "text", "TEAM"), T("bottom", "Untere Zeile", "text", "2026"),
         T("star", "Stern oben", "check", True),
         T("width", "Breite", "num", 40.0, 150.0, 5.0, 0, " mm", 70.0),
         T("bg", "Grundfarbe", "color", "#1A237E"), T("border", "Rand", "color", "#FDD835"),
         T("color", "Schriftfarbe", "color", "#FFFFFF"), T("accent", "Sternfarbe", "color", "#FDD835")],
     shield),
    ("emblem", "Rund-Emblem", "Runder Aufnäher mit Text oben und unten im Bogen und einem Motiv "
     "in der Mitte.", [
         T("top", "Text oben", "text", "STICHWIZARD"), T("bottom", "Text unten", "text", "SEIT 2026"),
         T("center", "Motiv", "choice", [("Stern", "Stern"), ("Herz", "Herz"), ("Blume", "Blume"),
                                         ("Anker", "Anker"), ("Kein Motiv", "none")], "Stern"),
         T("diameter", "Durchmesser", "num", 50.0, 160.0, 5.0, 0, " mm", 90.0),
         T("bg", "Grundfarbe", "color", "#2E7D32"), T("border", "Rand", "color", "#FFFFFF"),
         T("color", "Schriftfarbe", "color", "#FFFFFF"), T("accent", "Motivfarbe", "color", "#FDD835")],
     round_emblem),
    ("wreath", "Blätterkranz", "Kranz aus Blättern mit Herz und Namen in der Mitte – Hochzeit, "
     "Geburt, Geschenke.", [
         T("text", "Text", "text", "Lea"), T("font", "Schrift", "choice", FONT_CHOICES, "script"),
         T("leaves", "Blätter", "int", 8, 30, 16),
         T("diameter", "Durchmesser", "num", 50.0, 160.0, 5.0, 0, " mm", 80.0),
         T("leaf", "Blattfarbe", "color", "#43A047"), T("accent", "Herzfarbe", "color", "#E53935"),
         T("color", "Schriftfarbe", "color", "#6D4C41")], wreath),
    ("monogram", "Monogramm", "Initiale im Ring mit Ziersternen und optionalem Namen.", [
         T("letter", "Buchstabe(n)", "text", "M"), T("name", "Name darunter", "text", ""),
         T("diameter", "Durchmesser", "num", 40.0, 140.0, 5.0, 0, " mm", 60.0),
         T("ring", "Ringfarbe", "color", "#B8860B"), T("color", "Schriftfarbe", "color", "#5D4037")],
     monogram),
    ("patch", "Aufnäher", "Gefüllter Aufnäher (rechteckig, rund oder oval) mit dickem Satinrand "
     "und Text.", [
         T("text", "Text", "text", "ROCK"), T("font", "Schrift", "choice", FONT_CHOICES, "block"),
         T("form", "Form", "choice", [("Rechteckig", "rect"), ("Rund", "round"), ("Oval", "oval")], "oval"),
         T("width", "Breite", "num", 40.0, 160.0, 5.0, 0, " mm", 80.0),
         T("bg", "Grundfarbe", "color", "#212121"), T("border", "Rand", "color", "#E53935"),
         T("color", "Schriftfarbe", "color", "#FFFFFF")], patch),
    ("birth", "Geburt", "Babyname mit Mond und Sternen, Datum und Gewicht/Größe – für Spucktücher, "
     "Decken, Kissen.", [
         T("name", "Name", "text", "Emma"), T("date", "Datum", "text", "12.03.2026"),
         T("info", "Gewicht / Größe", "text", "3.420 g / 51 cm"),
         T("width", "Breite", "num", 50.0, 160.0, 5.0, 0, " mm", 90.0),
         T("color", "Namensfarbe", "color", "#5C6BC0"), T("color2", "Textfarbe", "color", "#7986CB"),
         T("accent", "Mond & Sterne", "color", "#FDD835")], birth),
    ("wedding", "Hochzeit", "Zwei Namen mit »&« und Datum in einem Herz aus Satin.", [
         T("name1", "Name 1", "text", "Anna"), T("name2", "Name 2", "text", "Tom"),
         T("date", "Datum", "text", "20.06.2026"),
         T("width", "Breite", "num", 50.0, 160.0, 5.0, 0, " mm", 90.0),
         T("heart", "Herzfarbe", "color", "#C2185B"), T("color", "Schriftfarbe", "color", "#5D4037")],
     wedding),
    ("banner", "Schriftband", "Band mit eingeschnittenen Enden und Text – Überschriften, Slogans.", [
         T("text", "Text", "text", "WILLKOMMEN"), T("font", "Schrift", "choice", FONT_CHOICES, "block"),
         T("width", "Breite", "num", 50.0, 200.0, 5.0, 0, " mm", 110.0),
         T("bg", "Bandfarbe", "color", "#C62828"), T("border", "Rand", "color", "#8E0000"),
         T("color", "Schriftfarbe", "color", "#FFFFFF")], banner),
    ("border", "Bordüre", "Reihe aus Motiven auf einer Ranke – für Säume, Handtuchkanten, Borten.", [
         T("motif", "Motiv", "choice", [("Herz", "Herz"), ("Stern", "Stern"), ("Blume", "Blume"),
                                        ("Blatt", "Blatt"), ("Stern 8", "Stern 8")], "Blume"),
         T("count", "Anzahl", "int", 2, 20, 6),
         T("length", "Länge", "num", 40.0, 300.0, 5.0, 0, " mm", 150.0),
         T("size", "Motivgröße", "num", 5.0, 40.0, 1.0, 0, " mm", 14.0),
         T("color", "Motivfarbe", "color", "#E91E63"), T("line", "Rankenfarbe", "color", "#43A047")],
     border_strip),
    ("heartname", "Herz mit Name", "Gefülltes Herz mit Satinrand und Namen darauf.", [
         T("name", "Name", "text", "Ida"), T("font", "Schrift", "choice", FONT_CHOICES, "script"),
         T("width", "Breite", "num", 40.0, 160.0, 5.0, 0, " mm", 70.0),
         T("bg", "Herzfarbe", "color", "#E53935"), T("border", "Rand", "color", "#8E0000"),
         T("color", "Schriftfarbe", "color", "#FFFFFF")], heart_name),
    ("frame", "Rahmen mit Zierecken", "Satinrahmen mit Sternen in den Ecken und einem Spruch – "
     "Zeilen mit »/« trennen.", [
         T("text", "Text (Zeilen mit /)", "text", "Home / sweet home"),
         T("font", "Schrift", "choice", FONT_CHOICES, "script"),
         T("width", "Breite", "num", 50.0, 200.0, 5.0, 0, " mm", 110.0),
         T("frame", "Rahmenfarbe", "color", "#6D4C41"), T("accent", "Eckenfarbe", "color", "#FFB300"),
         T("color", "Schriftfarbe", "color", "#6D4C41")], frame_corners),
]


def defaults(tpl):
    out = {}
    for key, _, kind, *args in tpl[3]:
        out[key] = args[-1] if kind in ("choice",) else args[0] if kind in ("text", "check", "color") \
            else args[-1] if kind == "int" else args[5]
    return out


def build(key, params=None, templates=None):
    tpl = next(t for t in (templates or TEMPLATES) if t[0] == key)
    p = defaults(tpl)
    p.update(params or {})
    return tpl[4](p)


# ---------------------------------------------------------------- Fenster
def _thumb(key, size=84, templates=None):
    from PySide6.QtGui import QIcon, QPixmap
    from .model import Document
    from .render import render_document
    d = Document()
    d.objects = build(key, templates=templates)
    d.apply_layer_flags()
    st = d.stats()
    img = render_document(d, max(1.0, size / max(st["width"], st["height"], 1)), margin=1,
                          transparent=True)
    return QIcon(QPixmap.fromImage(img))


def TemplateDialog(parent=None, templates=None, title="Design-Vorlagen", icon="star",
                   ok_text="Einfügen", thumbs=True):
    """Vorlagen-Fenster: links die Vorlagen, in der Mitte ihre Felder, rechts die Vorschau.
    templates: eigene Liste im Format von TEMPLATES (z. B. Encore, Rahmen & Schnörkel)."""
    templates = templates or TEMPLATES
    from PySide6.QtCore import QSize, Qt, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                                   QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                                   QVBoxLayout, QWidget)
    from . import icons
    from .autodigitize import render_frame
    from .controls import SliderSpin, ZoomPanel
    from .widgets import ColorButton

    class _Dlg(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setWindowIcon(icons.icon(icon))
            self.resize(1180, 720)
            self.objects = []
            root = QHBoxLayout(self)
            self.list = QListWidget()
            self.list.setIconSize(QSize(64, 64))
            self.list.setFixedWidth(230)
            for key, name, desc, *_ in templates:
                it = QListWidgetItem(_thumb(key, templates=templates) if thumbs else QIcon(), name)
                it.setData(Qt.UserRole, key)
                it.setToolTip(desc)
                self.list.addItem(it)
            root.addWidget(self.list)
            mid = QVBoxLayout()
            self.desc = QLabel()
            self.desc.setWordWrap(True)
            self.desc.setObjectName("muted")
            mid.addWidget(self.desc)
            self.form_box = QWidget()
            self.form = QFormLayout(self.form_box)
            mid.addWidget(self.form_box)
            mid.addStretch()
            self.info = QLabel()
            self.info.setObjectName("muted")
            mid.addWidget(self.info)
            bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            bb.button(QDialogButtonBox.Ok).setText(ok_text)
            bb.accepted.connect(self.accept)
            bb.rejected.connect(self.reject)
            mid.addWidget(bb)
            mw = QWidget()
            mw.setLayout(mid)
            mw.setFixedWidth(380)
            root.addWidget(mw)
            self.preview = ZoomPanel("Vorschau", "")
            root.addWidget(self.preview, 1)
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.setInterval(250)
            self.timer.timeout.connect(self.update_preview)
            self.list.currentRowChanged.connect(self._load)
            self.fields = {}
            self.list.setCurrentRow(0)

        def _load(self, row):
            tpl = templates[row]
            self.key = tpl[0]
            self.desc.setText(tpl[2])
            while self.form.rowCount():
                self.form.removeRow(0)
            self.fields = {}
            for key, label, kind, *args in tpl[3]:
                if kind == "text":
                    w = QLineEdit(args[0])
                    w.textChanged.connect(self.timer.start)
                elif kind == "num":
                    w = SliderSpin(*args[:5], value=args[5])
                    w.valueChanged.connect(self.timer.start)
                elif kind == "int":
                    w = SliderSpin(args[0], args[1], 1, integer=True, value=args[2])
                    w.valueChanged.connect(self.timer.start)
                elif kind == "check":
                    w = QCheckBox(label)
                    w.setChecked(args[0])
                    w.toggled.connect(self.timer.start)
                elif kind == "color":
                    w = ColorButton(args[0])
                    w.colorChanged.connect(lambda _c: self.timer.start())
                else:
                    w = QComboBox()
                    for t, d in args[0]:
                        w.addItem(t, d)
                    w.setCurrentIndex(max(0, w.findData(args[1])))
                    w.currentIndexChanged.connect(self.timer.start)
                self.fields[key] = (kind, w)
                self.form.addRow("" if kind == "check" else label, w)
            self.update_preview()

        def values(self):
            out = {}
            for k, (kind, w) in self.fields.items():
                out[k] = (w.text() if kind == "text" else w.value() if kind in ("num", "int")
                          else w.isChecked() if kind == "check" else w.color if kind == "color"
                          else w.currentData())
            return out

        def update_preview(self):
            from .model import Document
            self.objects = build(self.key, self.values(), templates)
            d = Document()
            d.objects = self.objects
            d.apply_layer_flags()
            st = d.stats()
            xs, ys = [], []
            for o in self.objects:
                for _, b in o.world_blocks():
                    xs += [p[0] for p in b]
                    ys += [p[1] for p in b]
                if o.kind in ("stones", "print"):   # Steine und Druckbilder haben keine Stiche
                    b = o.world_geometry().bounds
                    xs += [b[0], b[2]]
                    ys += [b[1], b[3]]
            if xs:
                m = 4
                for o in self.objects:          # Vorschau im Rahmen (0,0)-(w,h) zeichnen
                    o.x -= min(xs) - m
                    o.y -= min(ys) - m
                img = render_frame(self.objects, max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m,
                                   max_px=1600)
                for o in self.objects:
                    o.x += min(xs) - m
                    o.y += min(ys) - m
                self.preview.view.set_image(img)
            self.info.setText(f"{st['width']:.0f} × {st['height']:.0f} mm · {st['stitches']:,} Stiche · "
                              f"{st['colors']} Farbe(n) · ca. {st['minutes']:.0f} min".replace(",", "."))

    return _Dlg()
