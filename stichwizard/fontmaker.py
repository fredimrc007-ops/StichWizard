"""Schrift-Werkstatt: eigene Stickschriften erstellen.

Zwei Wege:
- aus einer Computerschrift: jedes Zeichen wird automatisch digitalisiert – schmale Striche als
  Satinstich entlang ihrer Mittellinie, breite Teile als Füllung;
- aus eigenen Zeichnungen: ausgewählte Objekte (Satinsäulen, Linien, Formen) werden als ein
  Zeichen übernommen – mit allen Einstellungen, die die Objekte haben.

Die Schriften liegen als <id>.json.gz im Benutzerordner (embfont.user_dir()) im selben Format
wie die mitgelieferten Stickschriften und erscheinen danach in der Schriftauswahl.
"""
import gzip
import json
import os
import re
import unicodedata

from shapely.geometry import Polygon
from shapely.ops import unary_union

from . import embfont
from .engine import lines_of, polygons_of

DEFAULT_CHARS = ("ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜabcdefghijklmnopqrstuvwxyzäöüß"
                 "0123456789.,:;!?-+&'\"()/€@#")
DESCENDERS = set("gjpqy,;()")


def font_id(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "schrift"
    return embfont.USER_PREFIX + s


def user_fonts():
    """[(id, name)] der eigenen Schriften."""
    return [(f["id"], f["name"]) for f in embfont.font_index()
            if f["id"].startswith(embfont.USER_PREFIX)]


def new_font(name, cap):
    return {"id": font_id(name), "name": name,
            "description": "Eigene Stickschrift (StichWizard Schrift-Werkstatt)",
            "keywords": ["eigene"], "license": "Eigene Schrift", "license_text": "",
            "size": float(cap), "min_scale": 0.5, "max_scale": 2.5,
            "leading": cap * 1.6, "space": cap * 0.35, "adv_default": None,
            "adv": {}, "kern": {}, "letter_case": "", "default_glyph": None,
            "colors": [], "glyphs": {}}


def load_font(name_or_id):
    fid = name_or_id if name_or_id.startswith(embfont.USER_PREFIX) else font_id(name_or_id)
    path = embfont.font_path(fid)
    if os.path.exists(path):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_font(font):
    with gzip.open(embfont.font_path(font["id"]), "wt", encoding="utf-8") as f:
        json.dump(font, f)
    embfont.reload()
    return font["id"]


def delete_font(fid):
    if fid.startswith(embfont.USER_PREFIX) and os.path.exists(embfont.font_path(fid)):
        os.remove(embfont.font_path(fid))
        embfont.reload()


def _r(pts):
    return [[round(x, 3), round(y, 3)] for x, y in pts]


def _set_glyph(font, ch, elements, xmin, xmax):
    w = max(0.5, xmax - xmin)
    gap = font["size"] * 0.12
    font["glyphs"][ch] = {"w": round(w, 3), "mx": 0.0, "e": elements}
    font["adv"][ch] = round(w + gap, 3)


def _shift(elements, dx, dy):
    """Elementkoordinaten verschieben (Grundlinie bei y = 0, linker Rand bei x = 0)."""
    mv = lambda pts: [[x - dx, y - dy] for x, y in pts]
    for e in elements:
        if e["t"] == "satin":
            e["a"], e["b"] = mv(e["a"]), mv(e["b"])
            e["r"] = [mv(r) for r in e["r"]]
        elif e["t"] == "fill":
            e["rings"] = [mv(r) for r in e["rings"]]
        else:
            e["lines"] = [mv(l) for l in e["lines"]]
    return elements


# ---------------------------------------------------------------- aus Objekten
def object_elements(o):
    """Ein Stickobjekt -> Elemente der Stickschrift (Weltkoordinaten)."""
    out = []
    if o.kind == "satin":
        ra, rb, rungs = o.satin_rails()
        W = lambda pts: [o.to_world(x, y) for x, y in pts]
        a, b = W(ra), W(rb)
        width = sum(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 for p, q in zip(a, b)) / max(1, len(a))
        out.append({"t": "satin", "a": _r(a), "b": _r(b), "r": [_r(W(r)) for r in rungs],
                    "sp": o.fill.get("density", 0.4), "pc": o.fill.get("pull", 0.2), "cw": True,
                    "co": width > 5, "zu": width > 2.5, "in": 0.3, "us": 3.0,
                    "mx": o.fill.get("split_len", 8.0), "c": None})
        return out
    g = o.world_geometry()
    if g is None or g.is_empty:
        return out
    if o.kind in ("shape", "text") and o.fill.get("type", "none") not in ("none", "applique"):
        for p in polygons_of(g):
            rings = [_r(p.exterior.coords)] + [_r(r.coords) for r in p.interiors]
            out.append({"t": "fill", "rings": rings, "m": "contour" if o.fill["type"] == "contour"
                        else "tatami", "an": o.fill.get("angle", 45.0) + o.rot,
                        "rs": o.fill.get("density", 0.4), "ml": o.fill.get("stitch_len", 3.0),
                        "ul": bool(o.fill.get("underlay", True)), "c": None})
    b = o.border if o.kind != "stitches" else {}
    kind = b.get("type", "none")
    if kind != "none":
        if o.kind == "line":
            lines = [_r(l.coords) for l in lines_of(g)]
        else:
            lines = []
            for p in polygons_of(g):
                lines += [_r(p.exterior.coords)] + [_r(r.coords) for r in p.interiors]
        if kind in ("satin", "zigzag"):
            out.append({"t": "zigzag", "lines": lines, "w": b.get("width", 2.0), "c": None})
        else:
            out.append({"t": "run", "lines": lines, "sl": b.get("stitch_len", 2.5), "rp": 1,
                        "bn": 1 if kind == "triple" else 0, "w": 0.0, "c": None})
    return out


def glyph_from_objects(font_name, ch, objs, cap=None):
    """Ausgewählte Objekte als Zeichen `ch` in die eigene Schrift übernehmen (legt sie an).
    Grundlinie = Unterkante der Auswahl (bei Zeichen mit Unterlänge: Oberkante + Versalhöhe).
    Liefert die Schrift-ID."""
    elements = []
    for o in objs:
        elements += object_elements(o)
    if not elements:
        raise ValueError("Die Auswahl enthält nichts, was sich sticken lässt.")
    geoms = [o.world_geometry() for o in objs if o.world_geometry() is not None]
    minx, miny, maxx, maxy = unary_union([g.buffer(0.01) for g in geoms]).bounds
    font = load_font(font_name) or new_font(font_name, cap or (maxy - miny))
    base = miny + font["size"] if ch in DESCENDERS else maxy
    _set_glyph(font, ch, _shift(elements, minx, base), minx, maxx)
    return save_font(font)


# ---------------------------------------------------------------- aus Computerschrift
def _char_geometry(family, ch, cap, bold=False, italic=False):
    """Umriss eines Zeichens als Polygon(e) in mm, Grundlinie bei y = 0, Versalhöhe = cap."""
    from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath
    f = QFont(family)
    f.setPixelSize(200)
    f.setBold(bold)
    f.setItalic(italic)
    fm = QFontMetricsF(f)
    scale = cap / (fm.capHeight() or 140)
    path = QPainterPath()
    path.addText(0, 0, f, ch)
    polys = []
    for sub in path.toSubpathPolygons():
        pts = [(p.x() * scale, p.y() * scale) for p in sub]
        if len(pts) >= 3:
            polys.append(Polygon(pts).buffer(0))
    geom = None
    for p in sorted(polys, key=lambda q: -q.area):     # gerade/ungerade: Löcher (z. B. »o«)
        geom = p if geom is None else geom.symmetric_difference(p)
    adv = fm.horizontalAdvance(ch) * scale
    return geom, adv


def glyph_from_char(family, ch, cap, bold=False, italic=False, style="auto", density=0.4):
    """Elemente eines Zeichens: schmale Striche (bis ~cap/5 breit) als Satin entlang der
    Mittellinie, breite Teile als Tatami-Füllung. style: "auto" | "satin" | "fill"."""
    from .centerline import centerlines
    geom, adv = _char_geometry(family, ch, cap, bold, italic)
    if geom is None or geom.is_empty:
        return None, adv, None
    elements = []
    limit = max(1.2, cap / 4.5)
    for p in polygons_of(geom):
        if p.area < 0.2:
            continue
        width = 2 * p.area / max(p.length, 1e-6)
        if style == "fill" or (style == "auto" and width > limit):
            rings = [_r(p.exterior.coords)] + [_r(r.coords) for r in p.interiors]
            elements.append({"t": "fill", "rings": rings, "m": "tatami", "an": 45.0,
                             "rs": density, "ml": 3.0, "ul": True, "c": None})
            continue
        lines = centerlines(p)
        if not lines:
            rings = [_r(p.exterior.coords)] + [_r(r.coords) for r in p.interiors]
            elements.append({"t": "fill", "rings": rings, "m": "tatami", "an": 45.0,
                             "rs": density, "ml": 3.0, "ul": True, "c": None})
            continue
        elements.append({"t": "zigzag", "lines": [_r(l) for l in lines],
                         "w": round(max(0.8, width * 1.05), 2), "c": None})
    return elements, adv, geom.bounds


def font_from_system(name, family, cap=10.0, chars=DEFAULT_CHARS, bold=False, italic=False,
                     style="auto", density=0.4, progress=None):
    """Eigene Stickschrift aus einer installierten Computerschrift erzeugen. Liefert die ID."""
    font = new_font(name, cap)
    font["description"] = f"Aus der Computerschrift »{family}« erzeugt (Schrift-Werkstatt)"
    for k, ch in enumerate(dict.fromkeys(chars)):
        if progress:
            progress(k, len(chars))
        if ch.isspace():
            continue
        elements, adv, bounds = glyph_from_char(family, ch, cap, bold, italic, style, density)
        if not elements:
            continue
        minx, maxx = bounds[0], bounds[2]          # Außenkante des Umrisses, nicht der Mittellinie
        _set_glyph(font, ch, _shift(elements, minx, 0.0), minx, maxx)
        font["adv"][ch] = round(max(adv - minx, maxx - minx) + cap * 0.06, 3)
    if not font["glyphs"]:
        raise ValueError("Aus dieser Schrift ließ sich kein Zeichen erzeugen.")
    font["default_glyph"] = "?" if "?" in font["glyphs"] else None
    return save_font(font)


# ---------------------------------------------------------------- Fenster
def FontWorkshop(parent=None, selection=None):
    """Schrift-Werkstatt: Reiter »Aus Computerschrift« und »Eigene Zeichen« plus Verwaltung."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                                   QFontComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                                   QListWidget, QMessageBox, QPushButton, QTabWidget, QVBoxLayout,
                                   QWidget)
    from . import icons
    from .controls import SliderSpin, ZoomPanel

    class _Dlg(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle("Schrift-Werkstatt – eigene Stickschriften")
            self.setWindowIcon(icons.icon("text"))
            self.resize(1100, 680)
            self.created = None
            root = QHBoxLayout(self)
            tabs = QTabWidget()
            tabs.setFixedWidth(430)
            self.tabs = tabs
            root.addWidget(tabs)
            self.preview = ZoomPanel("Vorschau", "Hier erscheint eine Probe der Schrift.")
            root.addWidget(self.preview, 1)

            # --- aus Computerschrift
            t1 = QWidget()
            f = QFormLayout(t1)
            intro = QLabel("Jedes Zeichen einer installierten Schrift wird automatisch digitalisiert: "
                           "schmale Striche als Satinstich, breite Teile als Füllung. Danach steht "
                           "die Schrift in der Stickschrift-Auswahl.")
            intro.setWordWrap(True)
            intro.setObjectName("muted")
            f.addRow(intro)
            self.name = QLineEdit("Meine Schrift")
            f.addRow("Name", self.name)
            self.family = QFontComboBox()
            self.family.setCurrentFont(QFont("DejaVu Sans"))
            f.addRow("Computerschrift", self.family)
            row = QHBoxLayout()
            self.bold = QCheckBox("Fett")
            self.italic = QCheckBox("Kursiv")
            row.addWidget(self.bold)
            row.addWidget(self.italic)
            row.addStretch()
            rw = QWidget()
            rw.setLayout(row)
            f.addRow("", rw)
            self.cap = SliderSpin(5.0, 40.0, 0.5, 1, " mm", value=10.0)
            self.cap.setToolTip("Höhe der Großbuchstaben, für die die Schrift ausgelegt wird")
            f.addRow("Versalhöhe", self.cap)
            self.style = QComboBox()
            for t, k in (("Automatisch (Satin + Füllung)", "auto"), ("Alles Satin", "satin"),
                         ("Alles Füllung", "fill")):
                self.style.addItem(t, k)
            f.addRow("Stickart", self.style)
            self.chars = QLineEdit(DEFAULT_CHARS)
            f.addRow("Zeichen", self.chars)
            self.sample = QLineEdit("Hallo StichWizard 123")
            f.addRow("Probetext", self.sample)
            make = QPushButton("Schrift erzeugen und speichern")
            make.setObjectName("primary")
            make.clicked.connect(self.make_from_system)
            f.addRow(make)
            tabs.addTab(t1, "Aus Computerschrift")

            # --- eigene Zeichen
            t2 = QWidget()
            g = QFormLayout(t2)
            how = QLabel("So entsteht eine Schrift aus eigenen Zeichnungen:\n"
                         "1. Ein Zeichen zeichnen – z. B. mit dem Säulen-Satin-Werkzeug, dem "
                         "Bézier-Stift oder als Form.\n"
                         "2. Alle Teile des Zeichens auswählen, Fenster öffnen.\n"
                         "3. Schrift und Zeichen angeben, übernehmen.\n"
                         "Die Unterkante der Auswahl ist die Grundlinie (bei g, j, p, q, y die "
                         "Oberkante plus Versalhöhe). Satinsäulen, Linien und Füllungen behalten "
                         "ihre Einstellungen.")
            how.setWordWrap(True)
            how.setObjectName("muted")
            g.addRow(how)
            self.own_font = QComboBox()
            self.own_font.setEditable(True)
            g.addRow("Schrift", self.own_font)
            self.char = QLineEdit()
            self.char.setMaxLength(1)
            self.char.setPlaceholderText("z. B. A")
            g.addRow("Zeichen", self.char)
            self.own_cap = SliderSpin(5.0, 60.0, 0.5, 1, " mm", value=20.0)
            self.own_cap.setToolTip("Nur für eine neue Schrift: Versalhöhe Ihrer Zeichnungen")
            g.addRow("Versalhöhe (neu)", self.own_cap)
            self.sel_info = QLabel()
            self.sel_info.setObjectName("muted")
            g.addRow(self.sel_info)
            take = QPushButton("Auswahl als Zeichen übernehmen")
            take.setObjectName("primary")
            take.clicked.connect(self.take_selection)
            g.addRow(take)
            tabs.addTab(t2, "Eigene Zeichen")

            # --- verwalten
            t3 = QWidget()
            h = QVBoxLayout(t3)
            self.fonts = QListWidget()
            self.fonts.currentRowChanged.connect(lambda _: self.show_font())
            h.addWidget(self.fonts, 1)
            dele = QPushButton("Schrift löschen")
            dele.clicked.connect(self.delete_font)
            h.addWidget(dele)
            tabs.addTab(t3, "Meine Schriften")

            bb = QDialogButtonBox(QDialogButtonBox.Close)
            bb.rejected.connect(self.reject)
            bb.button(QDialogButtonBox.Close).setText("Schließen")
            root.addWidget(bb, 0, Qt.AlignBottom)
            self.selection = list(selection or [])
            self.sel_info.setText(f"{len(self.selection)} Objekt(e) ausgewählt." if self.selection
                                  else "Nichts ausgewählt – zuerst im Design die Teile des Zeichens "
                                       "auswählen, dann dieses Fenster öffnen.")
            self.refresh_fonts()
            if self.selection:
                tabs.setCurrentIndex(1)

        def refresh_fonts(self):
            cur = self.own_font.currentText()
            self.own_font.clear()
            self.fonts.clear()
            for fid, name in user_fonts():
                self.own_font.addItem(name)
                it = __import__("PySide6.QtWidgets", fromlist=["QListWidgetItem"]).QListWidgetItem(
                    f"{name}  ({len(load_font(fid)['glyphs'])} Zeichen)")
                it.setData(Qt.UserRole, fid)
                self.fonts.addItem(it)
            self.own_font.setCurrentText(cur or (self.own_font.itemText(0) if self.own_font.count()
                                                 else "Meine Handschrift"))

        def show_sample(self, fid, text):
            from .autodigitize import render_frame
            from .model import EmbObject
            o = EmbObject("text")
            info = next((x for x in embfont.font_index() if x["id"] == fid), None)
            size = info["size"] if info else 10.0
            o.text.update(text=text or "Abc", size=size, embfont=fid)
            o.fill["color"] = "#1565C0"
            xs, ys = [], []
            for _, b in o.world_blocks():
                xs += [p[0] for p in b]
                ys += [p[1] for p in b]
            if not xs:
                self.preview.view.clear("Keine Zeichen für diesen Text vorhanden.")
                return
            o.x, o.y = -min(xs) + 3, -min(ys) + 3
            self.preview.view.set_image(render_frame([o], max(xs) - min(xs) + 6, max(ys) - min(ys) + 6,
                                                     max_px=2400), keep_view=False)

        def make_from_system(self):
            from PySide6.QtWidgets import QApplication
            name = self.name.text().strip() or "Meine Schrift"
            if load_font(name) and QMessageBox.question(
                    self, "Schrift-Werkstatt", f"»{name}« gibt es schon. Ersetzen?") != QMessageBox.Yes:
                return
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                fid = font_from_system(name, self.family.currentFont().family(), self.cap.value(),
                                       self.chars.text() or DEFAULT_CHARS, self.bold.isChecked(),
                                       self.italic.isChecked(), self.style.currentData())
            except ValueError as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.information(self, "Schrift-Werkstatt", str(e))
                return
            QApplication.restoreOverrideCursor()
            self.created = fid
            self.refresh_fonts()
            self.show_sample(fid, self.sample.text())

        def take_selection(self):
            ch = self.char.text()
            name = self.own_font.currentText().strip()
            if not ch or not name:
                QMessageBox.information(self, "Schrift-Werkstatt", "Bitte Schrift und Zeichen angeben.")
                return
            if not self.selection:
                QMessageBox.information(self, "Schrift-Werkstatt",
                                        "Zuerst im Design die Teile des Zeichens auswählen.")
                return
            try:
                fid = glyph_from_objects(name, ch, self.selection, self.own_cap.value())
            except ValueError as e:
                QMessageBox.information(self, "Schrift-Werkstatt", str(e))
                return
            self.created = fid
            self.refresh_fonts()
            font = load_font(fid)
            self.show_sample(fid, "".join(sorted(font["glyphs"]))[:30])
            self.sel_info.setText(f"»{ch}« in »{name}« übernommen – {len(font['glyphs'])} Zeichen "
                                  "in der Schrift.")

        def show_font(self):
            it = self.fonts.currentItem()
            if it:
                font = load_font(it.data(Qt.UserRole))
                self.show_sample(it.data(Qt.UserRole), "".join(list(font["glyphs"])[:24]))

        def delete_font(self):
            it = self.fonts.currentItem()
            if not it:
                return
            if QMessageBox.question(self, "Schrift-Werkstatt",
                                    f"»{it.text().split('  (')[0]}« löschen? Schriftzüge, die sie "
                                    "verwenden, lassen sich danach nicht mehr berechnen.") == QMessageBox.Yes:
                delete_font(it.data(Qt.UserRole))
                self.refresh_fonts()
                self.preview.view.clear("")

    return _Dlg()
