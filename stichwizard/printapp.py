"""Druck-Applikation: ein Bild (gemalt im Mal-Atelier oder geladen) wird auf bedruckbaren Stoff
gedruckt und als Applikation aufgestickt – Platzierungslinie, Heftstich, Satinrand.

Objektart »print«: das Bild selbst (PNG, base64 in o.image), Größe in mm in fill["print_w"],
fill["print_h"]. Es wird angezeigt, aber nicht gestickt. Dazu gehört eine Form mit Füllart
»Applikation« und fill["print"] = True (kein Stoff-Farbfeld in der Ansicht), in derselben Gruppe.
Die Druckvorlage (PDF, 1:1) enthält das Bild mit Platzierungs- und Schnittlinie."""
import uuid

from shapely import affinity
from shapely.geometry import Point, box
from shapely.ops import unary_union

OUTLINES = [("Abgerundetes Rechteck", "rect"), ("Oval", "oval"), ("Umriss des Motivs", "motif")]
_cache = {}


# ------------------------------------------------------------------ Bild
def to_b64(img):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba.toBase64()).decode("ascii")


def image_of(o):
    """QImage des Druck-Objekts (zwischengespeichert)."""
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QImage
    key = o.image
    if key not in _cache:
        if len(_cache) > 24:
            _cache.clear()
        _cache[key] = QImage.fromData(QByteArray.fromBase64(key.encode("ascii")), "PNG")
    return _cache[key]


def size(o):
    return float(o.fill.get("print_w", 50.0)), float(o.fill.get("print_h", 50.0))


def geometry(o):
    w, h = size(o)
    return box(-w / 2, -h / 2, w / 2, h / 2)


def paint(p, o, world=False):
    """Bild zeichnen (Objektrahmen bzw. mit world=True auf der Arbeitsfläche)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter
    img = image_of(o)
    if img.isNull():
        return
    w, h = size(o)
    p.save()
    if world:
        p.translate(o.x, o.y)
    p.rotate(o.rot)
    p.scale(o.sx, o.sy)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.drawImage(QRectF(-w / 2, -h / 2, w, h), img)
    p.restore()


def make(img, w_mm, h_mm, name="Druckbild"):
    from .model import EmbObject
    o = EmbObject("print", name)
    o.image = to_b64(img)
    o.fill.update(type="none", print_w=float(w_mm), print_h=float(h_mm))
    o.border["type"] = "none"
    return o


# --------------------------------------------------------------- Umriss
def _mask(img, step_mm, w_mm, h_mm):
    """Belegte Pixel (nicht durchsichtig, nicht fast weiß) als bool-Raster (Zeilen, Spalten)."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    cols = max(4, int(round(w_mm / step_mm)))
    rows = max(4, int(round(h_mm / step_mm)))
    s = img.convertToFormat(QImage.Format_RGBA8888).scaled(cols, rows, Qt.IgnoreAspectRatio,
                                                           Qt.SmoothTransformation)
    a = np.frombuffer(s.constBits(), np.uint8, s.bytesPerLine() * rows).reshape(rows, -1)
    a = a[:, :cols * 4].reshape(rows, cols, 4)
    return (a[..., 3] > 60) & (a[..., :3].min(axis=2) < 235), cols, rows


def outline(img, w_mm, h_mm, mode="rect", margin=1.2):
    """Applikationsumriss (Mitte des Bilds = 0,0, mm)."""
    if mode == "oval":
        return affinity.scale(Point(0, 0).buffer(1, 128), w_mm / 2 - 1, h_mm / 2 - 1)
    if mode == "motif":
        step = 0.5
        m, cols, rows = _mask(img, step, w_mm, h_mm)
        boxes = []
        for y in range(rows):
            row = m[y]
            x = 0
            while x < cols:
                if row[x]:
                    x0 = x
                    while x < cols and row[x]:
                        x += 1
                    boxes.append(box(x0 * step - w_mm / 2, y * step - h_mm / 2,
                                     x * step - w_mm / 2, (y + 1) * step - h_mm / 2))
                x += 1
        if boxes:
            g = unary_union(boxes).buffer(margin + 1.0, join_style=1).buffer(-1.0, join_style=1)
            g = g.simplify(0.25)
            parts = [q for q in getattr(g, "geoms", [g]) if q.area > 30]
            if parts:
                # Löcher füllen: der gedruckte Stoff liegt als Ganzes auf
                from shapely.geometry import Polygon
                return unary_union([Polygon(q.exterior) for q in parts])
    r = min(4.0, w_mm / 4, h_mm / 4)
    return box(-w_mm / 2 + 1, -h_mm / 2 + 1, w_mm / 2 - 1, h_mm / 2 - 1).buffer(-r).buffer(r, 16)


def applique(o_print, mode, color, width=3.0):
    """Applikationsform zum Druckbild (gleiche Lage, gleiche Gruppe)."""
    from .model import EmbObject
    w, h = size(o_print)
    g = outline(image_of(o_print), w, h, mode)
    g = affinity.scale(g, o_print.sx, o_print.sy, origin=(0, 0))
    g = affinity.rotate(g, o_print.rot, origin=(0, 0))
    a = EmbObject("shape", "Druck-Applikation")
    a.set_geometry(affinity.translate(g, o_print.x, o_print.y))
    a.fill.update(type="applique", color="#FFFFFF", pattern="run", print=True, print_outline=mode,
                  knockout=False)
    a.border.update(type="satin", color=color, width=width)
    if not o_print.group:
        o_print.group = uuid.uuid4().hex[:8]
    a.group = o_print.group
    return a


# -------------------------------------------------------------- Druckvorlage
def prints_of(doc):
    """[(druckobjekt, [applikationsformen])] aller sichtbaren Druckbilder."""
    out = []
    for o in doc.objects:
        if o.kind == "print" and o.visible and doc.layer_shown(o):
            app = [a for a in doc.objects if a.kind == "shape" and a.fill.get("print")
                   and a.group and a.group == o.group]
            out.append((o, app))
    return out


def export_sheet(doc, path, mirror=False, allowance=5.0):
    """Druckvorlage als PDF in Originalgröße: je Druckbild eine A4-Seite mit Bild,
    Platzierungslinie (gestrichelt), Schnittlinie (Zugabe) und 20-mm-Prüfquadrat.
    mirror: spiegeln (für Transferpapier)."""
    from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPainterPath, \
        QPdfWriter, QPen
    items = prints_of(doc)
    if not items:
        raise ValueError("Im Design ist kein Druckbild.")
    wr = QPdfWriter(path)
    wr.setPageSize(QPageSize(QPageSize.A4))
    wr.setPageMargins(QMarginsF(8, 8, 8, 8), QPageLayout.Millimeter)
    wr.setResolution(300)
    wr.setTitle("StichWizard Druckvorlage")
    p = QPainter(wr)
    dpmm = wr.resolution() / 25.4
    page = wr.pageLayout().paintRectPixels(wr.resolution())
    pw, ph = page.width() / dpmm, page.height() / dpmm
    for i, (o, apps) in enumerate(items):
        if i:
            wr.newPage()
        p.setPen(QColor("#000000"))
        p.setFont(QFont("DejaVu Sans", 10, QFont.Bold))
        p.drawText(QRectF(0, 0, page.width(), 6 * dpmm), Qt.AlignLeft,
                   f"Druckvorlage {i + 1}/{len(items)} – in Originalgröße (100 %) auf bedruckbaren "
                   f"Stoff drucken" + (" · gespiegelt" if mirror else ""))
        p.setFont(QFont("DejaVu Sans", 8))
        p.drawText(QRectF(0, 6 * dpmm, page.width(), 10 * dpmm), Qt.AlignLeft | Qt.TextWordWrap,
                   "Gestrichelt: Platzierungslinie (so liegt der Stoff unter dem Satinrand). "
                   f"Durchgezogen: hier ausschneiden ({allowance:.0f} mm Zugabe), nach dem "
                   "Heftstich dicht an der Naht zurückschneiden.")
        # Prüfquadrat 20 × 20 mm (Text in Gerätepixeln, damit die Schriftgröße stimmt)
        sq = QRectF(0, 18 * dpmm, 20 * dpmm, 20 * dpmm)
        p.setPen(QPen(QColor("#000000"), 0.2 * dpmm))
        p.drawRect(sq)
        p.setFont(QFont("DejaVu Sans", 7))
        p.drawText(sq, Qt.AlignCenter, "20 mm")
        p.save()
        p.scale(dpmm, dpmm)
        cx, cy = pw / 2 + 10, (ph + 40) / 2
        p.translate(cx, cy)
        if mirror:
            p.scale(-1, 1)
        q = o.clone()
        q.x = q.y = 0.0
        paint(p, q)
        for a in apps:
            g = affinity.translate(a.world_geometry(), -o.x, -o.y)
            for poly in getattr(g, "geoms", [g]):
                for ring, pen in ((poly.exterior, QPen(QColor("#555555"), 0.3, Qt.DashLine)),
                                  (poly.buffer(allowance, join_style=1).exterior,
                                   QPen(QColor("#000000"), 0.3))):
                    path = QPainterPath()
                    cs = list(ring.coords)
                    path.moveTo(QPointF(*cs[0]))
                    for c in cs[1:]:
                        path.lineTo(QPointF(*c))
                    p.setPen(pen)
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
        p.restore()
    p.end()
    return len(items)


# ------------------------------------------------------------- Malen: Füllen
def flood_mask(arr, x, y, tol=24):
    """Zusammenhängende Pixel mit ähnlicher Farbe wie (x, y) – Zeilenläufe statt Pixel für
    Pixel, daher auch bei großen Bildern schnell. arr: (h, w, 4) uint8. Liefert bool-Maske."""
    import numpy as np
    h, w = arr.shape[:2]
    ref = arr[y, x].astype(int)
    diff = np.abs(arr.astype(int) - ref).max(axis=2)
    sim = diff <= tol
    runs = []                          # je Zeile: Liste (x0, x1) zusammenhängender ähnlicher Pixel
    for yy in range(h):
        row = sim[yy]
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        runs.append(list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0])))
    out = np.zeros((h, w), bool)
    start = next(((a, b) for a, b in runs[y] if a <= x < b), None)
    if start is None:
        return out
    seen = {(y, start[0])}
    todo = [(y, start)]
    while todo:
        yy, (a, b) = todo.pop()
        out[yy, a:b] = True
        for ny in (yy - 1, yy + 1):
            if 0 <= ny < h:
                for c, d in runs[ny]:
                    if c < b and d > a and (ny, c) not in seen:
                        seen.add((ny, c))
                        todo.append((ny, (c, d)))
    return out
