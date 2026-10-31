"""Bitmap nachzeichnen (wie Inkscape »Bitmap nachzeichnen«): Rasterbild -> Pfade/Stickobjekte.

Einzelner Scan:  Helligkeitsschwelle, Kantenerkennung, Mittellinie
Mehrere Scans:   Helligkeitsstufen, Farben, Graustufen

Gemeinsame Feinregler (Inkscape-Namen in Klammern): Weichzeichnen, Flecken unterdrücken
(speckles), Ecken glätten (smooth corners / alphamax), Toleranz (optimize paths), Abtastung,
Stapeln (stack scans), Hintergrund entfernen, Invertieren.

Alle Maße in mm; das Ergebnis liegt im Bildrahmen (0, 0)–(breite, höhe), y nach unten.
"""
import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtCore import QPointF, QRectF, Qt
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from . import curves
from .autodigitize import load_rgba, mask_to_geom, quantize
from .engine import polygons_of
from .model import EmbObject
from .threads import nearest_thread, rgb_to_hex

MODES = [("brightness", "Helligkeitsschwelle"), ("edges", "Kantenerkennung"),
         ("centerline", "Mittellinie (Strichzeichnung)"), ("steps", "Helligkeitsstufen"),
         ("colors", "Farben"), ("grays", "Graustufen")]
MULTI = {"steps", "colors", "grays"}
OUTPUTS = [("fill", "Flächen (Tatami)"), ("auto", "Flächen, schmale Teile als Satin"),
           ("run", "Umriss als Steppstich"), ("satin", "Umriss als Satinrand"),
           ("lines", "Mittellinien (Linien)")]

DEFAULTS = {"mode": "brightness", "threshold": 0.5, "edge": 0.25, "scans": 4, "invert": False,
            "blur": 0.0, "speckles": 1.0, "smooth": 1.0, "tolerance": 0.15, "res": 0.12,
            "stack": False, "remove_bg": True, "width": 100.0, "output": "fill",
            "line_width": 0.0, "drop_mix": False}


def _blur(a, r):
    """Kastenweichzeichner mit Radius r (Pixel), zweimal angewendet ≈ Gauß."""
    r = int(round(r))
    if r < 1:
        return a
    for _ in range(2):
        for axis in (0, 1):
            pad = [(0, 0)] * a.ndim
            pad[axis] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
            lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def _luminance(arr):
    rgb = arr[..., :3].astype(np.float32) / 255.0
    lum = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    a = arr[..., 3].astype(np.float32) / 255.0
    return lum * a + (1 - a)              # Durchsichtiges zählt als Weiß (Hintergrund)


def _sobel(lum):
    p = np.pad(lum, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    m = np.hypot(gx, gy)
    return m / max(1e-6, float(m.max()))


def _clean(geom, min_area):
    """Flecken unterdrücken: kleine Teile und kleine Löcher entfernen."""
    out = []
    for p in polygons_of(geom):
        if p.area < min_area:
            continue
        holes = [r for r in p.interiors if Polygon(r).area >= min_area]
        out.append(Polygon(p.exterior, holes))
    return unary_union(out) if out else None


def _rings(geom, opts):
    """Geometrie -> Pfade mit Ecken/Rundungen (Ecken glätten = 0: nur Ecken, wie Pixel)."""
    if opts["smooth"] <= 0.01:
        return curves.polygon_rings(geom.simplify(opts["tolerance"]))
    angle = 20.0 + 60.0 * min(opts["smooth"], 1.33) / 1.33
    return curves.auto_geometry_rings(geom, opts["tolerance"], angle)


def _mean_color(arr, mask):
    px = arr[mask]
    if len(px) == 0:
        return "#1A1A1A"
    return rgb_to_hex(*px[:, :3].mean(0))


def _scans(arr, opts):
    """Masken je Scan: [(maske, farbe-hex)] in Stickreihenfolge – von hell nach dunkel."""
    mode = opts["mode"]
    alpha = arr[..., 3] > 128
    lum = _blur(_luminance(arr), opts["blur"])
    if opts["invert"] and mode not in ("colors",):
        lum = 1.0 - lum
    if mode in ("brightness", "centerline"):
        m = (lum < opts["threshold"]) & alpha
        return [(m, _mean_color(arr, m))]
    if mode == "edges":
        m = (_sobel(lum) > opts["edge"]) & alpha
        return [(m, _mean_color(arr, (lum < 0.5) & alpha) if m.any() else "#1A1A1A")]
    n = max(2, int(opts["scans"]))
    if mode == "colors":
        a2 = arr.copy()
        if opts["blur"] >= 1:
            for c in range(3):
                a2[..., c] = np.clip(_blur(arr[..., c].astype(np.float32), opts["blur"]), 0, 255)
        labels, centers = quantize(a2, n, drop=bool(opts.get("drop_mix", False)))
        order = np.argsort([c[:3] @ np.array([0.2126, 0.7152, 0.0722]) for c in centers])
        scans = [(labels == i, rgb_to_hex(*centers[i])) for i in order]
    else:
        # gleichmäßige Helligkeitsstufen; Graustufen bekommen graue Garne, Stufen die Bildfarbe
        edges = np.linspace(0, 1, n + 1)
        edges[0], edges[-1] = -1, 2
        scans = []
        for i in range(n):
            m = (lum >= edges[i]) & (lum < edges[i + 1]) & alpha
            g = int(np.clip(lum[m].mean() if m.any() else (i + 0.5) / n, 0, 1) * 255)
            col = _mean_color(arr, m) if mode == "steps" else rgb_to_hex(g, g, g)
            scans.append((m, col))
    if opts["remove_bg"] and len(scans) > 1:
        # Hintergrund = Scan, der den Bildrand überwiegend bedeckt
        border = lambda m: np.concatenate([m[0], m[-1], m[:, 0], m[:, -1]]).mean()
        b = max(range(len(scans)), key=lambda i: border(scans[i][0]))
        if border(scans[b][0]) > 0.35:
            scans.pop(b)
    if opts["stack"]:
        # Stapeln (wie Inkscape): jede Stufe reicht unter alle dunkleren – keine Lücken
        acc = np.zeros(arr.shape[:2], bool)
        out = []
        for m, col in scans:
            acc = acc | m
            out.append((acc.copy(), col))
        scans = out
    return scans[::-1]                      # hell zuerst sticken, Dunkles liegt oben


def trace(img, opts=None, progress=None):
    """QImage -> {"w", "h", "layers": [{"color", "geom", "rings", "lines"}], "nodes"}.
    Je Scan eine Ebene; geom ist die Fläche nach dem Glätten (wie sie gestickt wird)."""
    o = dict(DEFAULTS, **(opts or {}))
    width = float(o["width"])
    res = max(0.04, float(o["res"]))
    arr = load_rgba(img, width / res)
    h, w = arr.shape[:2]
    px = width / w
    o["blur"] = o["blur"] / px if o["blur"] else 0.0       # mm -> Pixel
    scans = _scans(arr, o)
    layers, nodes = [], 0
    min_area = max(0.0, float(o["speckles"]))
    for k, (mask, col) in enumerate(scans):
        if progress:
            progress(k / max(1, len(scans)))
        if not mask.any():
            continue
        geom = mask_to_geom(mask, px, max(0.02, o["tolerance"] * 0.5))
        geom = _clean(geom, min_area) if geom is not None else None
        if geom is None or geom.is_empty:
            continue
        lay = {"color": col, "geom": geom, "rings": None, "lines": None}
        if o["mode"] in ("centerline",) or o["output"] == "lines":
            from .centerline import centerlines
            lines = [ln for ln in centerlines(geom, step=max(0.2, px * 2), prune=1.5)
                     if len(ln) >= 2 and LineString(ln).length >= max(1.0, min_area ** 0.5)]
            lines = [list(LineString(ln).simplify(o["tolerance"]).coords) for ln in lines]
            lay["lines"] = lines
            nodes += sum(len(ln) for ln in lines)
        else:
            rings = _rings(geom, o)
            if not rings:
                continue
            lay["rings"] = rings
            lay["geom"] = curves.rings_geometry(rings)
            nodes += sum(len(r) for r in rings)
        layers.append(lay)
    return {"w": width, "h": width * h / w, "layers": layers, "nodes": nodes, "px": px}


def _shape_from_rings(rings, name):
    o = EmbObject("shape", name)
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    o.x, o.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    o.set_curve([[[x - o.x, y - o.y, t] for x, y, t in r] for r in rings])
    return o


def make_objects(result, opts=None):
    """Ergebnis -> Stickobjekte (im Bildrahmen). Je Ebene eine Form bzw. Linien."""
    o = dict(DEFAULTS, **(opts or {}))
    out = []
    angles = [45, 135, 0, 90, 30, 120, 60, 150]
    lw = float(o.get("line_width") or 0)
    for i, lay in enumerate(result["layers"]):
        col = lay["color"]
        tname, _ = nearest_thread(col)
        if lay["lines"] is not None:
            for ln in lay["lines"]:
                e = EmbObject("line", f"Nachgezeichnet {i + 1} ({tname})")
                e.set_points(ln, closed=False)
                if lw >= 0.8:
                    e.border.update(type="satin", width=lw, color=col)
                else:
                    e.border.update(type="run", stitch_len=2.0, color=col)
                out.append(e)
            continue
        rings = lay["rings"]
        mode = o["output"]
        if mode == "auto":
            thin, wide = [], []
            for p in polygons_of(lay["geom"]):
                (thin if 2 * p.area / max(p.length, 1e-6) < 3.0 else wide).append(p)
            parts = []
            if wide:
                parts.append((curves.auto_geometry_rings(unary_union(wide), o["tolerance"])
                              if len(thin) else rings, "tatami"))
            if thin:
                parts.append((curves.auto_geometry_rings(unary_union(thin), o["tolerance"]), "satin"))
        else:
            parts = [(rings, "tatami")]
        for rr, kind in parts:
            if not rr:
                continue
            s = _shape_from_rings(rr, f"Nachgezeichnet {i + 1} ({tname})")
            s.fill.update(color=col, angle=0 if kind == "satin" else angles[i % len(angles)])
            if mode in ("run", "satin"):
                s.fill["type"] = "none"
                s.border.update(type="run" if mode == "run" else "satin", color=col,
                                width=lw if lw >= 0.8 else 2.5, stitch_len=2.0)
            else:
                s.fill.update(type=kind, pull=0.2)
            out.append(s)
    return out


def render_preview(result, base=None, view="areas", scale=None):
    """Vorschau als QImage. view: areas (Flächen) | outline (Konturen und Knoten über dem
    Original). base: Originalbild (QImage) für die Kontur-Ansicht."""
    w_mm, h_mm = result["w"], result["h"]
    if scale is None:
        scale = max(2.0, min(14.0, 2400 / max(w_mm, h_mm, 1)))
    img = QImage(max(1, int(w_mm * scale)), max(1, int(h_mm * scale)), QImage.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    if view == "outline" and base is not None:
        p.setOpacity(0.45)
        p.drawImage(img.rect(), base)
        p.setOpacity(1.0)
    p.scale(scale, scale)

    def path_of(geom):
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        for poly in polygons_of(geom):
            for ring in [poly.exterior] + list(poly.interiors):
                c = list(ring.coords)
                path.moveTo(QPointF(*c[0]))
                for q in c[1:]:
                    path.lineTo(QPointF(*q))
                path.closeSubpath()
        return path
    for lay in result["layers"]:
        col = QColor(lay["color"])
        if lay["lines"] is not None:
            pen = QPen(col if view == "areas" else QColor("#E53935"), 0.5 if view == "areas" else 0)
            pen.setCosmetic(view != "areas")
            p.setPen(pen)
            for ln in lay["lines"]:
                p.drawPolyline([QPointF(*q) for q in ln])
            continue
        path = path_of(lay["geom"])
        if view == "areas":
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawPath(path)
        else:
            pen = QPen(QColor("#E53935"), 0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
    if view == "outline":           # Knoten: Ecke = Quadrat, Rundung = Punkt
        p.setPen(Qt.NoPen)
        r = 1.6 / scale
        for lay in result["layers"]:
            for ring in lay["rings"] or []:
                for x, y, t in ring:
                    p.setBrush(QColor("#1565C0") if t == curves.CURVE else QColor("#E53935"))
                    if t == curves.CURVE:
                        p.drawEllipse(QPointF(x, y), r, r)
                    else:
                        p.drawRect(QRectF(x - r, y - r, 2 * r, 2 * r))
    p.end()
    return img


# ------------------------------------------------------------------- Dialog
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,  # noqa: E402
                               QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)


class TraceDialog(QDialog):
    """Bitmap nachzeichnen: links alle Regler, rechts Original und Ergebnis (gekoppelt
    zoombar). Ergebnis als Flächen, als Konturen mit Knoten über dem Original oder als Stiche."""

    def __init__(self, parent=None, hoop_w=130, template=None):
        """template: (QImage, breite_mm) einer geladenen Vorlage oder None."""
        from .autodigitize import IMAGE_EXTS
        from .controls import SliderSpin, ZoomPanel
        super().__init__(parent)
        self.setWindowTitle("Bitmap nachzeichnen")
        self.resize(1320, 820)
        self._exts = IMAGE_EXTS
        self.img = None
        self.result = None
        self.objects = []
        self.template = template
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.pick = QPushButton("Bild wählen …")
        self.pick.setObjectName("primary")
        self.pick.clicked.connect(self.choose)
        self.file_label = QLabel("Noch kein Bild gewählt (PNG, JPG, BMP, GIF, SVG)")
        self.file_label.setObjectName("muted")
        top.addWidget(self.pick)
        top.addWidget(self.file_label, 1)
        self.linked = QCheckBox("Ansichten koppeln")
        self.linked.setChecked(True)
        self.linked.toggled.connect(self._link)
        top.addWidget(self.linked)
        v.addLayout(top)

        mid = QHBoxLayout()
        # ---- Regler
        side = QWidget()
        f = QFormLayout(side)
        f.setLabelAlignment(Qt.AlignLeft)
        self.form = f

        def head(text):
            lab = QLabel(text)
            lab.setObjectName("cardTitle")
            f.addRow(lab)
            return lab
        head("Erkennung")
        self.mode = QComboBox()
        for i, (key, label) in enumerate(MODES):
            if key == "steps":
                self.mode.insertSeparator(self.mode.count())
            self.mode.addItem(label, key)
        self.mode.setToolTip("Einzelner Scan: eine Fläche (Schwelle, Kanten, Mittellinie).\n"
                             "Mehrere Scans: je Helligkeitsstufe, Farbe oder Graustufe eine Fläche.")
        f.addRow("Modus", self.mode)
        self.threshold = SliderSpin(0, 100, 1, 0, " %", value=50, ends=("dunkel", "hell"))
        self.threshold.setToolTip("Bildpunkte dunkler als diese Helligkeit werden zur Fläche")
        f.addRow("Helligkeitsschwelle", self.threshold)
        self.edge = SliderSpin(1, 100, 1, 0, " %", value=25, ends=("mehr Kanten", "weniger"))
        self.edge.setToolTip("Wie stark ein Helligkeitssprung sein muss, um als Kante zu zählen")
        f.addRow("Kantenschwelle", self.edge)
        self.scans = SliderSpin(2, 16, 1, integer=True, value=4)
        self.scans.setToolTip("Anzahl der Stufen bzw. Farben – jede wird eine eigene Fläche")
        f.addRow("Anzahl Scans", self.scans)
        self.invert = QCheckBox("Invertieren (Helles nachzeichnen)")
        f.addRow("", self.invert)
        self.drop_mix = QCheckBox("Kantenfarben zusammenfassen")
        self.drop_mix.setToolTip("Farben, die nur an Kanten als Mischung zweier Farben vorkommen "
                                 "(Kantenglättung), der Nachbarfarbe zuschlagen. Achtung: kann auch "
                                 "echte Zwischentöne (z. B. Grau zwischen Schwarz und Weiß) schlucken.")
        f.addRow("", self.drop_mix)
        self.stack = QCheckBox("Scans stapeln")
        self.stack.setToolTip("Wie in Inkscape: jede Fläche reicht unter die dunkleren – keine "
                              "Lücken, aber mehr Stiche. Ohne Haken liegen die Flächen nebeneinander.")
        f.addRow("", self.stack)
        self.remove_bg = QCheckBox("Hintergrund entfernen")
        self.remove_bg.setChecked(True)
        self.remove_bg.setToolTip("Den Scan weglassen, der den Bildrand überwiegend bedeckt")
        f.addRow("", self.remove_bg)

        head("Feinheiten")
        self.blur = SliderSpin(0, 2.0, 0.05, 2, " mm", value=0.0)
        self.blur.setToolTip("Bild vorher weichzeichnen – glättet Rauschen und JPEG-Artefakte")
        f.addRow("Weichzeichnen", self.blur)
        self.speckles = SliderSpin(0, 25, 0.1, 1, " mm²", value=1.0)
        self.speckles.setToolTip("Flecken unterdrücken: Teile und Löcher kleiner als diese Fläche "
                                 "entfallen (0 = alles behalten)")
        f.addRow("Flecken unterdrücken", self.speckles)
        self.smooth = SliderSpin(0, 1.33, 0.01, 2, "", value=1.0, ends=("eckig", "rund"))
        self.smooth.setToolTip("Ecken glätten: 0 = nur Eckpunkte (genau wie die Pixel), höher = "
                               "mehr Rundungen, nur noch deutliche Knicke bleiben Ecken")
        f.addRow("Ecken glätten", self.smooth)
        self.tolerance = SliderSpin(0.02, 1.0, 0.01, 2, " mm", value=0.15, invert=True,
                                    ends=("weniger Knoten", "genauer"))
        self.tolerance.setToolTip("Pfade optimieren: so weit darf der Pfad vom Bild abweichen. "
                                  "Kleiner = genauer, aber mehr Knoten")
        f.addRow("Toleranz", self.tolerance)
        self.res = SliderSpin(0.04, 0.4, 0.01, 2, " mm", value=0.12, invert=True,
                              ends=("schneller", "feiner"))
        self.res.setToolTip("Abtastung: so viele mm entspricht ein Bildpunkt beim Nachzeichnen")
        f.addRow("Abtastung", self.res)

        head("Ergebnis")
        self.width = SliderSpin(10, 400, 1, 0, " mm", value=min(100, hoop_w - 10))
        self.width.setToolTip("Breite des Motivs im Stickrahmen")
        f.addRow("Breite im Rahmen", self.width)
        self.align = QCheckBox("Genau auf die Vorlage legen")
        self.align.setToolTip("Das Ergebnis liegt deckungsgleich über der geladenen Vorlage")
        f.addRow("", self.align)
        self.output = QComboBox()
        for key, label in OUTPUTS:
            self.output.addItem(label, key)
        f.addRow("Sticken als", self.output)
        self.line_width = SliderSpin(0, 8, 0.1, 1, " mm", value=0.0)
        self.line_width.setSpecialValueText("Steppstich")
        self.line_width.setToolTip("Linien/Umriss: 0 = Steppstich, sonst Satin in dieser Breite")
        f.addRow("Linienbreite", self.line_width)
        self.info = QLabel()
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        f.addRow(self.info)
        row = QHBoxLayout()
        self.live = QCheckBox("Live-Vorschau")
        self.live.setChecked(True)
        self.refresh_btn = QPushButton("Aktualisieren")
        self.refresh_btn.clicked.connect(self.update_preview)
        row.addWidget(self.live)
        row.addStretch()
        row.addWidget(self.refresh_btn)
        f.addRow(row)
        scroll = QScrollArea()
        scroll.setWidget(side)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(450)
        mid.addWidget(scroll)
        # ---- Ansichten
        self.orig_panel = ZoomPanel("Original", "Bild wählen …")
        self.prev_panel = ZoomPanel("Ergebnis", "Hier erscheint das Nachgezeichnete.\n"
                                    "Mausrad = zoomen, Ziehen = verschieben,\nDoppelklick = einpassen")
        self.orig, self.prev = self.orig_panel.view, self.prev_panel.view
        self.view = QComboBox()
        self.view.addItem("Flächen", "areas")
        self.view.addItem("Konturen + Knoten", "outline")
        self.view.addItem("Stiche", "stitches")
        self.view.setToolTip("Konturen + Knoten: rote Pfade über dem Original, Ecken rot, Rundungen blau – "
                             "zum genauen Einstellen hineinzoomen")
        self.view.currentIndexChanged.connect(self._show)
        self.prev_panel.layout().itemAt(0).layout().insertWidget(1, self.view)
        for pnl in (self.orig_panel, self.prev_panel):
            pnl.setMinimumWidth(300)
            mid.addWidget(pnl, 1)
        v.addLayout(mid, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)                 # erst rechnen, wenn der Regler ruht
        self.timer.timeout.connect(self.update_preview)
        for w in (self.threshold, self.edge, self.scans, self.blur, self.speckles, self.smooth,
                  self.tolerance, self.res, self.width, self.line_width):
            w.valueChanged.connect(self._changed)
        for w in (self.invert, self.drop_mix, self.stack, self.remove_bg):
            w.toggled.connect(self._changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.output.currentIndexChanged.connect(self._changed)
        self.align.toggled.connect(self._align_changed)
        self._link(True)
        self.align.setVisible(template is not None)
        self._mode_changed()
        if template is not None:
            self.align.setChecked(True)
            self.set_image(template[0], "Geladene Vorlage")

    # ------------------------------------------------------------ Einstellungen
    def options(self):
        return {"mode": self.mode.currentData(), "threshold": self.threshold.value() / 100.0,
                "edge": self.edge.value() / 100.0, "scans": int(self.scans.value()),
                "invert": self.invert.isChecked(), "drop_mix": self.drop_mix.isChecked(),
                "stack": self.stack.isChecked(), "remove_bg": self.remove_bg.isChecked(),
                "blur": self.blur.value(), "speckles": self.speckles.value(),
                "smooth": self.smooth.value(), "tolerance": self.tolerance.value(),
                "res": self.res.value(), "width": self.width.value(),
                "output": "lines" if self.mode.currentData() == "centerline"
                else self.output.currentData(), "line_width": self.line_width.value()}

    def _row(self, w, on):
        self.form.setRowVisible(w, on)

    def _mode_changed(self, *_):
        m = self.mode.currentData()
        multi = m in MULTI
        self._row(self.threshold, m in ("brightness", "centerline"))
        self._row(self.edge, m == "edges")
        self._row(self.scans, multi)
        self._row(self.invert, m != "colors")
        self._row(self.drop_mix, m == "colors")
        self._row(self.stack, multi)
        self._row(self.remove_bg, multi)
        self._row(self.output, m != "centerline")
        lab = self.form.labelForField(self.scans)
        if lab:
            lab.setText("Anzahl Farben" if m == "colors" else "Anzahl Stufen")
        self._out_rows()
        self._changed()

    def _out_rows(self):
        out = self.options()["output"]
        self._row(self.line_width, out in ("run", "satin", "lines"))

    def _align_changed(self, on):
        if on and self.template is not None:
            self.width.setValue(self.template[1])
        self.width.setEnabled(not on)
        self._changed()

    def _changed(self, *_):
        self._out_rows()
        if self.live.isChecked():
            self.timer.start()

    # ------------------------------------------------------------------ Bild
    def _link(self, on):
        if on:
            self.orig.link(self.prev)
        else:
            self.orig.unlink()

    def choose(self):
        exts = " ".join(f"*.{e} *.{e.upper()}" for e in self._exts)
        path, _ = QFileDialog.getOpenFileName(self, "Bild öffnen", "",
                                              f"Bilder und Vektorgrafiken ({exts})")
        if path:
            self.load(path)

    def load(self, path):
        from .autodigitize import load_image
        img = load_image(path, 2000)
        if img is None or img.isNull():
            self.file_label.setText("Bild konnte nicht geladen werden.")
            return
        self.align.setChecked(False)
        self.align.setVisible(False)
        self.set_image(img, path)

    def set_image(self, img, label):
        self.img = img
        self.file_label.setText(label)
        self.orig.set_image(img, keep_view=False)
        self.update_preview()

    # --------------------------------------------------------------- Rechnen
    def update_preview(self):
        if self.img is None:
            return
        self.timer.stop()
        self.setCursor(Qt.WaitCursor)
        try:
            opts = self.options()
            self.result = trace(self.img, opts)
            self.objects = make_objects(self.result, opts)
            self._show()
        finally:
            self.unsetCursor()

    def _show(self, *_):
        r = self.result
        if r is None:
            return
        view = self.view.currentData()
        if view == "stitches" and self.objects:
            from .autodigitize import render_frame
            self.prev.set_image(render_frame(self.objects, r["w"], r["h"]))
        else:
            self.prev.set_image(render_preview(r, self.img, view))
        n_lines = sum(len(l["lines"] or []) for l in r["layers"])
        parts = sum(len(polygons_of(l["geom"])) for l in r["layers"] if l["rings"])
        txt = (f"{len(r['layers'])} Ebene(n) · {parts} Fläche(n)" +
               (f" · {n_lines} Linie(n)" if n_lines else "") +
               f" · {r['nodes']:,} Knoten · {r['w']:.0f} × {r['h']:.0f} mm")
        if view == "stitches":
            n = sum(1 for o in self.objects for _, b in o.stitch_blocks() for p in b if p[2] == 0)
            txt += f" · ca. {n:,} Stiche"
        self.info.setText(txt.replace(",", "."))
