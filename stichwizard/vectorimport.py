"""Vektorgrafiken öffnen: Adobe Illustrator (.ai, PDF-kompatibel gespeichert) und PDF.

Gelesen werden alle Pfade (Füllungen und Konturen) samt Farben – so wie Illustrator sie
zeichnet: Transformationen (cm, q/Q), Bézierkurven (c, v, y), Rechtecke (re), Füllregeln
(gerade/ungerade bzw. nonzero), Graustufen, RGB, CMYK und Schmuckfarben (Separation mit
Ersatzfarbe) sowie eingebettete Form-XObjects. Text, der nicht in Pfade umgewandelt wurde,
und eingebettete Bilder werden gezählt und im Dialog gemeldet, aber nicht übernommen.

Ergebnis in mm, y nach unten, Ursprung oben links an der Grafik.
"""
import math

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .engine import polygons_of

VECTOR_EXTS = ["ai", "pdf"]
PT = 25.4 / 72.0          # mm je PDF-Punkt


class VectorError(Exception):
    pass


# ------------------------------------------------------------------- Farben
def _hex(r, g, b):
    c = lambda v: max(0, min(255, int(round(v * 255))))
    return "#{:02X}{:02X}{:02X}".format(c(r), c(g), c(b))


def _cmyk(c, m, y, k):
    return _hex((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))


def _from_components(vals):
    vals = [float(v) for v in vals]
    if len(vals) >= 4:
        return _cmyk(*vals[:4])
    if len(vals) == 3:
        return _hex(*vals)
    if len(vals) == 1:
        return _hex(vals[0], vals[0], vals[0])
    return "#000000"


def _resolve(o):
    try:
        return o.get_object()
    except AttributeError:
        return o


class _ColorSpace:
    """Farbraum aus /ColorSpace-Ressource: wandelt Werte (sc/scn) in Hex-Farben."""

    def __init__(self, spec):
        self.kind, self.n, self.alt, self.fn = "device", None, None, None
        spec = _resolve(spec)
        if isinstance(spec, list) or hasattr(spec, "__iter__") and not isinstance(spec, (str, bytes)) \
                and not hasattr(spec, "keys"):
            items = [_resolve(x) for x in spec]
            name = str(items[0]) if items else ""
            if name in ("/Separation", "/DeviceN"):
                self.kind = "sep"
                self.alt = _ColorSpace(items[2]) if len(items) > 2 else None
                self.fn = _resolve(items[3]) if len(items) > 3 else None
            elif name == "/ICCBased":
                n = _resolve(items[1]).get("/N", 3) if len(items) > 1 else 3
                self.n = int(n)
            elif name == "/Indexed":
                self.kind = "indexed"
            elif name in ("/CalRGB", "/Lab"):
                self.n = 3
            elif name == "/CalGray":
                self.n = 1
        else:
            name = str(spec)
            self.n = {"/DeviceGray": 1, "/G": 1, "/DeviceRGB": 3, "/RGB": 3,
                      "/DeviceCMYK": 4, "/CMYK": 4}.get(name)

    def color(self, vals):
        vals = [float(v) for v in vals if isinstance(v, (int, float)) or _isnum(v)]
        if self.kind == "sep":
            t = vals[0] if vals else 1.0
            fn = self.fn
            if fn is not None and hasattr(fn, "get") and fn.get("/FunctionType") == 2:
                c0 = [float(x) for x in fn.get("/C0", [0.0])]
                c1 = [float(x) for x in fn.get("/C1", [1.0])]
                n = float(fn.get("/N", 1))
                alt = [a + (t ** n) * (b - a) for a, b in zip(c0, c1)]
                return self.alt.color(alt) if self.alt else _from_components(alt)
            return _hex(1 - t, 1 - t, 1 - t)           # unbekannte Funktion: als Grauton
        if self.kind == "indexed":
            return "#000000"
        return _from_components(vals)


def _isnum(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------------- Pfade
def _mul(a, b):
    """Matrizen [a b c d e f] verketten: erst a, dann b."""
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _apply(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def _cubic(p0, p1, p2, p3, step):
    ln = math.dist(p0, p1) + math.dist(p1, p2) + math.dist(p2, p3)
    n = max(2, min(120, int(ln / step) + 1))
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


class _State:
    def __init__(self):
        self.ctm = [1, 0, 0, 1, 0, 0]
        self.fill = "#000000"
        self.stroke = "#000000"
        self.fill_cs = _ColorSpace("/DeviceGray")
        self.stroke_cs = _ColorSpace("/DeviceGray")
        self.width = 1.0
        self.clip = None          # Schnittmaske (Gerätekoordinaten), z. B. um ein Bild

    def copy(self):
        s = _State()
        s.__dict__.update(self.__dict__)
        s.ctm = list(self.ctm)
        return s


def _read_stream(reader, contents, resources, base, items, info, depth=0):
    from pypdf.generic import ContentStream
    if depth > 8:
        return
    cs = ContentStream(contents, reader)
    st = base.copy()
    stack = []
    subpaths, cur = [], []
    res = _resolve(resources) or {}
    colorspaces = _resolve(res.get("/ColorSpace", {})) or {}
    xobjects = _resolve(res.get("/XObject", {})) or {}
    step = 0.4 / PT                         # Kurven auf ~0,4 mm genau abtasten (vor CTM)

    def scale():
        m = st.ctm
        return math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0

    def space(name):
        name = str(name)
        if name in colorspaces:
            return _ColorSpace(colorspaces[name])
        return _ColorSpace(name)

    def finish():
        if cur and len(cur) > 1:
            subpaths.append(cur[:])

    clip_next = [False]

    def emit(fill, stroke, evenodd, close_all=False):
        finish()
        paths = [[_apply(st.ctm, x, y) for x, y in sp] for sp in subpaths if len(sp) >= 2]
        if clip_next[0]:
            clip_next[0] = False
            rings = [p for p in paths if len(p) >= 3]
            # nur echte Formen merken – ein achsparalleles Rechteck ist meist der
            # Zeichenflächenrand bzw. der Bildrand und keine Maske
            if rings and not (len(rings) == 1 and _is_box(rings[0])):
                st.clip = rings
        if fill:
            rings = [p for p in paths if len(p) >= 3]
            if rings:
                items.append({"kind": "fill", "color": st.fill, "rings": rings, "evenodd": evenodd})
        if stroke and paths:
            items.append({"kind": "stroke", "color": st.stroke, "paths": paths,
                          "closed": [close_all or (math.dist(p[0], p[-1]) < 1e-6) for p in paths],
                          "width": st.width * scale()})
        subpaths.clear()
        cur.clear()

    start = None
    for operands, op in cs.operations:
        op = op.decode("latin-1") if isinstance(op, bytes) else op
        try:
            if op == "q":
                stack.append(st.copy())
            elif op == "Q":
                if stack:
                    st = stack.pop()
            elif op == "cm":
                st.ctm = _mul([float(v) for v in operands], st.ctm)
            elif op == "m":
                finish()
                cur[:] = [(float(operands[0]), float(operands[1]))]
                start = cur[0]
            elif op == "l":
                cur.append((float(operands[0]), float(operands[1])))
            elif op in ("c", "v", "y"):
                v = [float(x) for x in operands]
                p0 = cur[-1] if cur else (0.0, 0.0)
                if op == "c":
                    p1, p2, p3 = (v[0], v[1]), (v[2], v[3]), (v[4], v[5])
                elif op == "v":
                    p1, p2, p3 = p0, (v[0], v[1]), (v[2], v[3])
                else:
                    p1, p2, p3 = (v[0], v[1]), (v[2], v[3]), (v[2], v[3])
                if not cur:
                    cur.append(p0)
                cur.extend(_cubic(p0, p1, p2, p3, step / max(scale(), 1e-6) * 1.0))
            elif op == "h":
                if cur and start is not None and cur[-1] != start:
                    cur.append(start)
            elif op == "re":
                finish()
                x, y, w, h = (float(v) for v in operands)
                cur[:] = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
                finish()
                cur.clear()
            elif op in ("f", "F"):
                emit(True, False, False)
            elif op == "f*":
                emit(True, False, True)
            elif op in ("B", "b"):
                emit(True, True, False, op == "b")
            elif op in ("B*", "b*"):
                emit(True, True, True, op == "b*")
            elif op == "S":
                emit(False, True, False)
            elif op == "s":
                emit(False, True, False, True)
            elif op == "n":
                emit(False, False, False)
            elif op in ("W", "W*"):
                clip_next[0] = True
            elif op == "w":
                st.width = float(operands[0])
            elif op == "g":
                st.fill, st.fill_cs = _from_components(operands), _ColorSpace("/DeviceGray")
            elif op == "G":
                st.stroke, st.stroke_cs = _from_components(operands), _ColorSpace("/DeviceGray")
            elif op == "rg":
                st.fill, st.fill_cs = _from_components(operands), _ColorSpace("/DeviceRGB")
            elif op == "RG":
                st.stroke, st.stroke_cs = _from_components(operands), _ColorSpace("/DeviceRGB")
            elif op == "k":
                st.fill, st.fill_cs = _from_components(operands), _ColorSpace("/DeviceCMYK")
            elif op == "K":
                st.stroke, st.stroke_cs = _from_components(operands), _ColorSpace("/DeviceCMYK")
            elif op == "cs":
                st.fill_cs = space(operands[0])
            elif op == "CS":
                st.stroke_cs = space(operands[0])
            elif op in ("sc", "scn"):
                st.fill = st.fill_cs.color([v for v in operands if _isnum(v)])
            elif op in ("SC", "SCN"):
                st.stroke = st.stroke_cs.color([v for v in operands if _isnum(v)])
            elif op == "BT":
                info["text"] += 1
            elif op == "sh":
                info["shading"] += 1
            elif op == "INLINE IMAGE":
                info["images"] += 1
            elif op == "Do":
                xo = _resolve(xobjects.get(str(operands[0])))
                if xo is None:
                    continue
                sub = str(xo.get("/Subtype", ""))
                if sub == "/Image":
                    if st.clip:
                        # Bild mit Schnittmaske (z. B. Logo als maskierte Bitmap): die Maske
                        # ist die Form, die Farbe kommt aus dem Bild
                        items.append({"kind": "fill", "color": _image_color(xo, colorspaces),
                                      "rings": st.clip, "evenodd": False})
                    else:
                        info["images"] += 1
                elif sub == "/Form":
                    inner = st.copy()
                    if "/Matrix" in xo:
                        inner.ctm = _mul([float(v) for v in xo["/Matrix"]], st.ctm)
                    _read_stream(reader, xo, xo.get("/Resources", res), inner, items, info,
                                 depth + 1)
        except (ValueError, IndexError, TypeError, ZeroDivisionError):
            continue                      # einzelner kaputter Befehl: überspringen


def _is_box(ring):
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    box_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    return box_area <= 0 or Polygon(ring).buffer(0).area >= 0.98 * box_area


def _image_color(xo, colorspaces):
    """Mittlere Druckfarbe eines Bildes (nur die eingefärbten Bildpunkte)."""
    try:
        import numpy as np
        cs = _ColorSpace(xo.get("/ColorSpace", "/DeviceGray"))
        if int(xo.get("/BitsPerComponent", 8)) != 8:
            return "#000000"
        n = 1 if cs.kind == "sep" else (cs.n or 1)
        a = np.frombuffer(xo.get_data(), np.uint8).astype(np.float32) / 255.0
        a = a[:len(a) // n * n].reshape(-1, n)
        if cs.kind == "sep":
            ink = a[:, 0][a[:, 0] > 0.05]
            return cs.color([float(ink.mean()) if len(ink) else 1.0])
        if n == 1:
            ink = a[:, 0][a[:, 0] < 0.95]
            v = float(ink.mean()) if len(ink) else 0.0
            return _hex(v, v, v)
        return _from_components(list(a.mean(0)))
    except Exception:
        return "#000000"


def page_count(path):
    from pypdf import PdfReader
    return len(PdfReader(path).pages)


def read(path, page=0):
    """Liest eine Seite -> {"items", "w", "h", "info", "pages"}; Koordinaten in mm,
    y nach unten, Ursprung oben links am Inhalt (nicht an der Zeichenfläche)."""
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise VectorError("Zum Öffnen von AI/PDF fehlt das Python-Paket »pypdf«.") from e
    with open(path, "rb") as f:
        head = f.read(1024)
    if b"%PDF" not in head:
        raise VectorError("Diese Datei ist nicht PDF-kompatibel gespeichert. In Illustrator "
                          "»Speichern unter« mit Haken bei »PDF-kompatible Datei erstellen« "
                          "speichern – oder als PDF oder SVG exportieren.")
    try:
        reader = PdfReader(path, strict=False)
        pg = reader.pages[max(0, min(page, len(reader.pages) - 1))]
    except Exception as e:
        raise VectorError(f"Datei konnte nicht gelesen werden: {e}") from e
    items, info = [], {"text": 0, "images": 0, "shading": 0}
    contents = pg.get_contents()
    if contents is not None:
        _read_stream(reader, contents, pg.get("/Resources", {}), _State(), items, info)
    out = []
    for it in items:                      # PDF-Punkte -> mm, y nach unten
        conv = lambda pts: [(x * PT, -y * PT) for x, y in pts]
        if it["kind"] == "fill":
            it["rings"] = [conv(r) for r in it["rings"]]
        else:
            it["paths"] = [conv(p) for p in it["paths"]]
            it["width"] *= PT
        out.append(it)
    pts = [p for it in out for r in it.get("rings", it.get("paths", [])) for p in r]
    if not pts:
        return {"items": [], "w": 0.0, "h": 0.0, "info": info, "pages": len(reader.pages)}
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
    for it in out:
        key = "rings" if it["kind"] == "fill" else "paths"
        it[key] = [[(x - x0, y - y0) for x, y in r] for r in it[key]]
    return {"items": out, "w": x1 - x0, "h": y1 - y0, "info": info, "pages": len(reader.pages)}


# --------------------------------------------------------------- Geometrie
def _fill_geom(it):
    geom = None
    for r in it["rings"]:
        p = Polygon(r)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or p.area < 1e-4:
            continue
        geom = p if geom is None else geom.symmetric_difference(p)
    return geom


def layers(data, scale=1.0, merge=True, hide=True, drop_white=True, strokes=True):
    """Gelesene Elemente -> Ebenen [{"kind", "color", "geom" | "paths", "width"}] in mm.
    hide: was später darübergemalt wird, aus früheren Flächen herausnehmen (wie es aussieht;
    nichts wird doppelt gestickt). drop_white: weiße Flächen weglassen (= Stoff bleibt frei).
    merge: gleichfarbige Flächen zusammenfassen."""
    from shapely import affinity
    fills = []
    for it in data["items"]:
        if it["kind"] == "fill":
            g = _fill_geom(it)
            if g is not None and not g.is_empty:
                fills.append([it["color"], affinity.scale(g, scale, scale, origin=(0, 0))])
    if hide:
        for i in range(len(fills) - 1, -1, -1):
            later = unary_union([g for _, g in fills[i + 1:]]) if i + 1 < len(fills) else None
            if later is not None and not later.is_empty and fills[i][1].intersects(later):
                fills[i][1] = fills[i][1].difference(later)
    white = lambda c: all(int(c[k:k + 2], 16) >= 0xF0 for k in (1, 3, 5))
    out = []
    for col, g in fills:
        if drop_white and white(col):
            continue
        g = unary_union([p for p in polygons_of(g) if p.area > 0.05])
        if g.is_empty:
            continue
        if merge:
            same = next((o for o in out if o["kind"] == "fill" and o["color"] == col), None)
            if same is not None:
                same["geom"] = same["geom"].union(g)
                continue
        out.append({"kind": "fill", "color": col, "geom": g})
    if strokes:
        for it in data["items"]:
            if it["kind"] != "stroke" or (drop_white and white(it["color"])):
                continue
            paths = [[(x * scale, y * scale) for x, y in p] for p in it["paths"]]
            out.append({"kind": "stroke", "color": it["color"], "paths": paths,
                        "closed": it["closed"], "width": it["width"] * scale})
    return out


def make_objects(lays, fill="tatami"):
    """Ebenen -> Stickobjekte (Formen bzw. Linien). fill: tatami | auto (schmale Teile Satin)."""
    from .model import EmbObject
    from .threads import nearest_thread
    objs = []
    angles = [45, 135, 0, 90, 30, 120]
    for i, lay in enumerate(lays):
        name, _ = nearest_thread(lay["color"])
        if lay["kind"] == "fill":
            parts = [(lay["geom"], "tatami")]
            if fill == "auto":
                thin = [p for p in polygons_of(lay["geom"]) if 2 * p.area / max(p.length, 1e-6) < 3.0]
                wide = [p for p in polygons_of(lay["geom"]) if 2 * p.area / max(p.length, 1e-6) >= 3.0]
                parts = [(unary_union(wide), "tatami"), (unary_union(thin), "satin")]
            for g, kind in parts:
                if g.is_empty:
                    continue
                o = EmbObject("shape", f"Vektor {i + 1} ({name})")
                o.set_geometry(g.simplify(0.02))
                o.fill.update(color=lay["color"], type=kind, pull=0.2,
                              angle=0 if kind == "satin" else angles[i % len(angles)])
                objs.append(o)
        else:
            for pts, closed in zip(lay["paths"], lay["closed"]):
                line = LineString(pts).simplify(0.02)
                c = list(line.coords)
                if len(c) < 2 or line.length < 0.5:
                    continue
                if closed and len(c) > 3 and math.dist(c[0], c[-1]) < 1e-6:
                    c = c[:-1]
                o = EmbObject("line", f"Kontur {i + 1} ({name})")
                o.set_points(c, closed=closed and len(c) >= 3)
                w = lay["width"]
                if w >= 1.0:
                    o.border.update(type="satin", width=min(w, 8.0), color=lay["color"])
                else:
                    o.border.update(type="run", stitch_len=2.0, color=lay["color"])
                objs.append(o)
    return objs


def render(lays, w_mm, h_mm, px_per_mm=8.0, bg=None):
    """Ebenen als Bild (für Vorschau, Vorlage, Bild-Assistent, Bitmap nachzeichnen)."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
    img = QImage(max(1, int(w_mm * px_per_mm)), max(1, int(h_mm * px_per_mm)), QImage.Format_ARGB32)
    img.fill(QColor(bg) if bg else Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(px_per_mm, px_per_mm)
    for lay in lays:
        col = QColor(lay["color"])
        if lay["kind"] == "fill":
            path = QPainterPath()
            path.setFillRule(Qt.OddEvenFill)
            for poly in polygons_of(lay["geom"]):
                for ring in [poly.exterior] + list(poly.interiors):
                    c = list(ring.coords)
                    path.moveTo(QPointF(*c[0]))
                    for q in c[1:]:
                        path.lineTo(QPointF(*q))
                    path.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawPath(path)
        else:
            p.setPen(QPen(col, max(0.15, lay["width"]), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            for pts, closed in zip(lay["paths"], lay["closed"]):
                qp = [QPointF(*q) for q in pts]
                (p.drawPolygon if closed else p.drawPolyline)(qp)
    p.end()
    return img


def load_as_image(path, size=1600):
    """AI/PDF als Bild (transparenter Hintergrund, längste Seite = size Pixel)."""
    data = read(path)
    if not data["items"]:
        return None
    lays = layers(data, 1.0, merge=False, hide=False, drop_white=False)
    return render(lays, data["w"], data["h"], size / max(data["w"], data["h"], 1e-6))


# ------------------------------------------------------------------- Dialog
from PySide6.QtCore import Qt as _Qt, QTimer as _QTimer  # noqa: E402
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,  # noqa: E402
                               QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QVBoxLayout)


class VectorImportDialog(QDialog):
    """AI/PDF übernehmen: Vorschau, Größe, Seite und wie Flächen/Konturen übernommen werden."""

    def __init__(self, path, parent=None, hoop=(130, 180)):
        from .controls import SliderSpin, ZoomPanel
        super().__init__(parent)
        import os
        self.setWindowTitle(f"Vektorgrafik übernehmen – {os.path.basename(path)}")
        self.resize(1080, 760)
        self.path = path
        self.hoop = hoop
        self.data = None
        self.lays = []
        self.objects = []
        v = QHBoxLayout(self)
        self.panel = ZoomPanel("Vorschau", "")
        v.addWidget(self.panel, 1)
        side = QVBoxLayout()
        f = QFormLayout()
        self.page = QSpinBox()
        self.page.setMinimum(1)
        self.page.setToolTip("Zeichenfläche bzw. Seite der Datei")
        f.addRow("Seite", self.page)
        self.width = SliderSpin(5, 500, 1, 1, " mm", value=100)
        self.width.setToolTip("Breite des Motivs im Stickrahmen (Seitenverhältnis bleibt)")
        f.addRow("Breite", self.width)
        row = QHBoxLayout()
        self.b_orig = QPushButton("Originalgröße")
        self.b_fit = QPushButton("In den Rahmen")
        row.addWidget(self.b_orig)
        row.addWidget(self.b_fit)
        f.addRow("", row)
        self.hide_cb = QCheckBox("Verdeckte Teile weglassen")
        self.hide_cb.setChecked(True)
        self.hide_cb.setToolTip("Was in der Grafik darüberliegt, wird darunter nicht gestickt – "
                                "kein doppelter Stich, keine Garnhäufung")
        self.white_cb = QCheckBox("Weiße Flächen weglassen (Stoff bleibt frei)")
        self.white_cb.setChecked(True)
        self.merge_cb = QCheckBox("Gleiche Farben zu einer Fläche zusammenfassen")
        self.merge_cb.setChecked(True)
        self.stroke_cb = QCheckBox("Konturen als Linien übernehmen")
        self.stroke_cb.setChecked(True)
        self.stroke_cb.setToolTip("Kontur ab 1 mm Breite als Satin, sonst als Steppstich")
        for cb in (self.hide_cb, self.white_cb, self.merge_cb, self.stroke_cb):
            f.addRow("", cb)
        self.fill = QComboBox()
        self.fill.addItem("Tatami", "tatami")
        self.fill.addItem("Automatisch (schmale Teile Satin)", "auto")
        f.addRow("Flächen als", self.fill)
        side.addLayout(f)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setObjectName("muted")
        side.addWidget(self.info)
        side.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        side.addWidget(bb)
        v.addLayout(side)
        self.timer = _QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.update_preview)
        self.width.valueChanged.connect(self.timer.start)
        for cb in (self.hide_cb, self.white_cb, self.merge_cb, self.stroke_cb):
            cb.toggled.connect(self.timer.start)
        self.page.valueChanged.connect(self._load)
        self.b_orig.clicked.connect(lambda: self.data and self.width.setValue(self.data["w"]))
        self.b_fit.clicked.connect(self._fit)
        self._load()

    def _fit(self):
        if self.data and self.data["w"] > 0:
            w, h = self.hoop
            self.width.setValue(round(min(w * 0.9, h * 0.9 * self.data["w"] / max(self.data["h"], 1e-6)), 1))

    def _load(self, *_):
        self.data = read(self.path, self.page.value() - 1)
        self.page.blockSignals(True)
        self.page.setMaximum(max(1, self.data["pages"]))
        self.page.blockSignals(False)
        self.page.setEnabled(self.data["pages"] > 1)
        w, h = self.hoop
        d = self.data
        if d["w"] > 0:
            if d["w"] <= w * 0.9 and d["h"] <= h * 0.9:
                self.width.setValue(round(d["w"], 1))
            else:
                self._fit()
        self.update_preview()

    def options(self):
        return dict(merge=self.merge_cb.isChecked(), hide=self.hide_cb.isChecked(),
                    drop_white=self.white_cb.isChecked(), strokes=self.stroke_cb.isChecked())

    def update_preview(self):
        d = self.data
        self.timer.stop()
        if not d or d["w"] <= 0:
            self.lays = []
            self.panel.view.clear("Keine Pfade gefunden.")
            self.info.setText("In dieser Datei wurden keine Vektorpfade gefunden." + self._warn())
            return
        scale = self.width.value() / d["w"]
        self.lays = layers(d, scale, **self.options())
        wmm, hmm = d["w"] * scale, d["h"] * scale
        self.panel.view.set_image(render(self.lays, wmm, hmm, max(2.0, 1400 / max(wmm, hmm)),
                                         bg="#FFFFFF"))
        nf = sum(1 for l in self.lays if l["kind"] == "fill")
        ns = sum(len(l["paths"]) for l in self.lays if l["kind"] == "stroke")
        cols = len({l["color"] for l in self.lays})
        self.info.setText((f"{wmm:.1f} × {hmm:.1f} mm (Original {d['w']:.1f} × {d['h']:.1f} mm)"
                           ).replace(".", ",") +
                          f"<br>{nf} Fläche(n), {ns} Linie(n), {cols} Farbe(n)" + self._warn())

    def _warn(self):
        i = self.data["info"] if self.data else {}
        w = []
        if i.get("text"):
            w.append(f"{i['text']} Textblock/-blöcke (in Illustrator vorher »In Pfade umwandeln«)")
        if i.get("images"):
            w.append(f"{i['images']} eingebettete(s) Bild(er) – dafür den Bild-Assistenten nehmen")
        if i.get("shading"):
            w.append(f"{i['shading']} Verlauf/Verläufe")
        return ("<br><span style='color:#C62828'>Nicht übernommen: " + "; ".join(w) + "</span>") if w else ""

    def accept(self):
        self.objects = make_objects(self.lays, self.fill.currentData())
        super().accept()
