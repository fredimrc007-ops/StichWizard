"""Strass & Perlen: Steine entlang einer Kontur oder als Flächenfüllung setzen und als
Schablone (SVG/PDF, 1:1) für Strassfolie oder Schneideplotter ausgeben.

Steine werden nicht gestickt – ein Strass-Objekt (kind »stones«) hat keine Stiche, nur
Mittelpunkte (points, Objektkoordinaten) und eine Steingröße (fill["stone"], mm)."""
import math

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

# übliche Hotfix-Strassgrößen (SS = »stone size«) mit Durchmesser in mm
SIZES = [("SS6 · 2,0 mm", 2.0), ("SS10 · 2,8 mm", 2.8), ("SS12 · 3,0 mm", 3.0),
         ("SS16 · 3,9 mm", 3.9), ("SS20 · 4,7 mm", 4.7), ("SS30 · 6,4 mm", 6.4)]
STYLES = [("Kristall (funkelnd)", "crystal"), ("Perle (Perlmutt)", "pearl"),
          ("Matt (Nailhead)", "matt")]
HOLE_EXTRA = 0.4        # Schablonenloch etwas größer als der Stein (mm)


def stone_size(o):
    return float(o.fill.get("stone", 2.8))


def geometry(o):
    """Steine als Kreisflächen (Objektkoordinaten) – für Auswahl, Rahmen und Ausrichten."""
    r = stone_size(o) / 2
    if not o.points:
        return Polygon()
    return unary_union([Point(p[0], p[1]).buffer(r, 16) for p in o.points])


def world_centers(o):
    """Steinmittelpunkte auf der Arbeitsfläche (mit Skalierung/Drehung des Objekts)."""
    return [o.to_world(p[0], p[1]) for p in o.points]


def make(centers, size, color, style="crystal", name=None):
    """Strass-Objekt aus Mittelpunkten (Weltkoordinaten)."""
    from .model import EmbObject
    o = EmbObject("stones", name or ("Perlen" if style == "pearl" else "Strass"))
    o.set_points([list(c) for c in centers] or [[0.0, 0.0]])
    o.fill.update(type="none", color=color, stone=float(size), stone_style=style)
    o.border["type"] = "none"
    return o


# ------------------------------------------------------------------ Anordnen
def _spaced(line, step, closed):
    """Punkte im gleichen Abstand entlang einer Linie (geschlossen: gleichmäßig verteilt)."""
    L = line.length
    if L <= 0:
        return []
    if closed:
        n = max(3, int(round(L / step)))
        return [line.interpolate(L * k / n).coords[0] for k in range(n)]
    n = max(1, int(math.floor(L / step)))
    d = (L - n * step) / 2           # Rest gleichmäßig an beiden Enden
    return [line.interpolate(d + k * step).coords[0] for k in range(n + 1)]


def along(geom, size, gap, inset=0.0):
    """Steine entlang der Kontur(en) einer Fläche bzw. entlang einer Linie.
    inset: Steinreihe um so viele mm nach innen versetzen (Flächen)."""
    step = size + gap
    out = []
    if geom.geom_type in ("LineString", "MultiLineString", "LinearRing"):
        lines = list(getattr(geom, "geoms", [geom]))
        for ln in lines:
            closed = ln.is_ring or (ln.coords[0] == ln.coords[-1])
            out += _spaced(ln, step, closed)
        return out
    g = geom.buffer(-inset, join_style=1) if inset > 0 else geom
    for poly in getattr(g, "geoms", [g]):
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        for ring in [poly.exterior, *poly.interiors]:
            out += _spaced(LineString(ring.coords), step, True)
    return out


def fill(geom, size, gap, pattern="hex", angle=0.0, margin=None):
    """Steine als Flächenfüllung: versetztes (hex) oder gerades Raster, ganz innerhalb."""
    if geom.geom_type in ("LineString", "MultiLineString", "LinearRing"):
        return []
    r = size / 2
    area = geom.buffer(-(r + (gap / 2 if margin is None else margin)), join_style=1)
    if area.is_empty:
        return []
    step = size + gap
    c = area.centroid
    rot = affinity.rotate(area, -angle, origin=c)
    minx, miny, maxx, maxy = rot.bounds
    dy = step * (math.sqrt(3) / 2 if pattern == "hex" else 1.0)
    out = []
    from shapely.prepared import prep
    pa = prep(rot)
    row = 0
    y = miny
    while y <= maxy + 1e-6:
        off = step / 2 if pattern == "hex" and row % 2 else 0.0
        x = minx + off
        while x <= maxx + 1e-6:
            if pa.contains(Point(x, y)):
                out.append((x, y))
            x += step
        y += dy
        row += 1
    if angle:
        ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        out = [(c.x + (x - c.x) * ca - (y - c.y) * sa, c.y + (x - c.x) * sa + (y - c.y) * ca)
               for x, y in out]
    return out


def source_geometry(objs):
    """Weltgeometrie der Auswahl: Flächen/Schrift als Flächen, Linien als Linien."""
    parts = []
    for o in objs:
        g = o.world_geometry()
        if g is None or g.is_empty or o.kind == "stones":
            continue
        parts.append(g)
    if not parts:
        return None
    polys = [g for g in parts if g.geom_type in ("Polygon", "MultiPolygon")]
    if polys:
        return unary_union(polys)
    return unary_union(parts)


# ------------------------------------------------------------------- Zeichnen
def paint(p, o, world=False):
    """Steine mit QPainter zeichnen (Objektrahmen bzw. mit world=True auf der Arbeitsfläche)."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QBrush, QColor, QPen, QRadialGradient
    from PySide6.QtCore import Qt
    r = stone_size(o) / 2 * (abs(o.sx) + abs(o.sy)) / 2
    base = QColor(o.fill.get("color", "#E0E0E0"))
    style = o.fill.get("stone_style", "crystal")
    pts = world_centers(o) if world else [o.shaped_point(q) for q in o.points]
    rim = QPen(base.darker(150), r * 0.12)
    for x, y in pts:
        g = QRadialGradient(QPointF(x - r * 0.35, y - r * 0.35), r * 1.4)
        if style == "pearl":
            g.setColorAt(0.0, QColor("#FFFFFF"))
            g.setColorAt(0.45, base.lighter(115))
            g.setColorAt(1.0, base.darker(125))
        elif style == "matt":
            g.setColorAt(0.0, base.lighter(130))
            g.setColorAt(1.0, base.darker(140))
        else:
            g.setColorAt(0.0, QColor("#FFFFFF"))
            g.setColorAt(0.25, base.lighter(160))
            g.setColorAt(0.7, base)
            g.setColorAt(1.0, base.darker(170))
        p.setPen(rim)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(x, y), r, r)
        if style == "crystal":           # Facetten-Glanz
            p.setPen(QPen(QColor(255, 255, 255, 170), r * 0.08))
            p.drawLine(QPointF(x - r * 0.55, y), QPointF(x + r * 0.55, y))
            p.drawLine(QPointF(x, y - r * 0.55), QPointF(x, y + r * 0.55))
            p.setPen(Qt.NoPen)


# ------------------------------------------------------------------ Schablone
def collect(doc):
    """[(x, y, durchmesser, farbe, stil)] aller sichtbaren Steine im Dokument."""
    out = []
    for o in doc.objects:
        if o.kind != "stones" or not o.visible or not doc.layer_shown(o):
            continue
        d = stone_size(o) * (abs(o.sx) + abs(o.sy)) / 2
        for x, y in world_centers(o):
            out.append((x, y, d, o.fill.get("color", "#E0E0E0"), o.fill.get("stone_style", "crystal")))
    return out


def summary(stones):
    """Stückliste: {(durchmesser, farbe, stil): anzahl}."""
    out = {}
    for _, _, d, col, st in stones:
        k = (round(d, 1), col.upper(), st)
        out[k] = out.get(k, 0) + 1
    return out


def _size_name(d):
    return next((n.split(" ·")[0] for n, s in SIZES if abs(s - d) < 0.05), f"{d:.1f} mm")


def export_svg(doc, path, extra=HOLE_EXTRA, hoop=True):
    """Schablone als SVG in mm (1:1): ein Kreis je Stein (Lochgröße = Stein + extra),
    dazu Rahmenmitte als Kreuz und optional der Stickrahmen als Hilfslinie."""
    stones = collect(doc)
    if not stones:
        raise ValueError("Im Design sind keine Strass-Steine.")
    xs = [s[0] for s in stones]
    ys = [s[1] for s in stones]
    m = 10.0
    hoop_w, hoop_h = doc.hoop_size
    hw, hh = hoop_w / 2, hoop_h / 2
    minx, miny = min(min(xs) - m, -hw if hoop else 1e9), min(min(ys) - m, -hh if hoop else 1e9)
    maxx, maxy = max(max(xs) + m, hw if hoop else -1e9), max(max(ys) + m, hh if hoop else -1e9)
    W, H = maxx - minx, maxy - miny
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" '
           f'viewBox="{minx:.3f} {miny:.3f} {W:.3f} {H:.3f}">',
           '<title>StichWizard Strass-Schablone (1:1)</title>']
    if hoop:
        out.append(f'<rect x="{-hw:.2f}" y="{-hh:.2f}" width="{hoop_w:.2f}" '
                   f'height="{hoop_h:.2f}" fill="none" stroke="#999999" stroke-width="0.2" '
                   'stroke-dasharray="2 2"/>')
    out.append('<path d="M -4 0 H 4 M 0 -4 V 4" stroke="#999999" stroke-width="0.2"/>')
    for (d, col, st), n in sorted(summary(stones).items()):
        out.append(f'<g id="{_size_name(d)}-{col[1:]}-{st}" fill="none" stroke="#000000" '
                   f'stroke-width="0.1"><desc>{n} × {_size_name(d)} {col} {st}</desc>')
        for x, y, dd, c, s in stones:
            if round(dd, 1) == d and c.upper() == col and s == st:
                out.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{(dd + extra) / 2:.3f}"/>')
        out.append('</g>')
    out.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return len(stones)


def export_pdf(doc, path, extra=HOLE_EXTRA):
    """Schablone als PDF in Originalgröße (ggf. auf mehrere A4-Seiten verteilt) mit
    Prüfquadrat 20 × 20 mm und Stückliste."""
    from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
    stones = collect(doc)
    if not stones:
        raise ValueError("Im Design sind keine Strass-Steine.")
    w = QPdfWriter(path)
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
    w.setResolution(600)
    w.setTitle("StichWizard Strass-Schablone")
    p = QPainter(w)
    dpmm = w.resolution() / 25.4
    page = w.pageLayout().paintRectPixels(w.resolution())
    pw, ph = page.width() / dpmm, page.height() / dpmm
    xs = [s[0] for s in stones]
    ys = [s[1] for s in stones]
    m = 6.0
    minx, miny, maxx, maxy = min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m
    head = 28.0                          # oben Platz für Titel, Prüfquadrat und Stückliste
    tiles_x = max(1, math.ceil((maxx - minx) / pw))
    tiles_y = max(1, math.ceil((maxy - miny) / (ph - head)))
    first = True
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            if not first:
                w.newPage()
            first = False
            # Text in Gerätepixeln (Schriftgrößen in Punkt), Formen danach in Millimetern
            M = lambda *v: QRectF(*(a * dpmm for a in v))
            p.setPen(QColor("#000000"))
            p.setFont(QFont("DejaVu Sans", 10, QFont.Bold))
            p.drawText(M(0, 0, pw, 6), Qt.AlignLeft,
                       f"Strass-Schablone (1:1) – Seite {ty * tiles_x + tx + 1}/{tiles_x * tiles_y}"
                       f" · beim Drucken nicht skalieren")
            p.setPen(QPen(QColor("#000000"), 0.2 * dpmm))
            p.drawRect(M(0, 7, 20, 20))
            p.setFont(QFont("DejaVu Sans", 7))
            p.drawText(M(0, 7, 20, 20), Qt.AlignCenter, "20 mm")
            p.setFont(QFont("DejaVu Sans", 8))
            items = sorted(summary(stones).items())
            for i, ((d, col, st), n) in enumerate(items[:6]):
                p.drawText(M(26, 7 + i * 3.4, pw - 26, 3.4), Qt.AlignLeft | Qt.AlignVCenter,
                           f"{n} × {_size_name(d)}  {col}  {dict((v, k) for k, v in STYLES)[st]}")
            p.save()
            p.scale(dpmm, dpmm)
            ox = minx + tx * pw
            oy = miny + ty * (ph - head)
            p.translate(0, head)
            p.setClipRect(QRectF(0, 0, pw, ph - head))
            p.translate(-ox, -oy)
            p.setPen(QPen(QColor("#999999"), 0.15, Qt.DashLine))
            p.drawLine(QPointF(-4, 0), QPointF(4, 0))
            p.drawLine(QPointF(0, -4), QPointF(0, 4))
            p.setPen(QPen(QColor("#000000"), 0.12))
            for x, y, d, col, st in stones:
                p.setBrush(QColor(col).lighter(150))
                p.drawEllipse(QPointF(x, y), (d + extra) / 2, (d + extra) / 2)
            p.restore()
    p.end()
    return len(stones)


# --------------------------------------------------------- Dialog (Vorschau)
def stone_templates(sel):
    """Einträge für templates.TemplateDialog: Steine um/auf die Auswahl setzen.
    Die Auswahl selbst steht als Kontext in der Vorschau (Attribut _context)."""
    src = source_geometry(sel)
    is_line = src is not None and src.geom_type in ("LineString", "MultiLineString")

    def ctx():
        out = []
        for o in sel:
            c = o.clone()
            c._context = True
            out.append(c)
        return out

    def build(p):
        if src is None:
            return ctx()
        size = p["size"]
        gap = p["gap"]
        if p["mode"] == "fill" and not is_line:
            pts = fill(src, size, gap, p["pattern"], p["angle"])
        elif p["mode"] == "both" and not is_line:
            outline = along(src, size, gap, inset=size / 2 + 0.3)
            inner = fill(src.buffer(-(size + gap * 1.5), join_style=1), size, gap, p["pattern"],
                         p["angle"], margin=0.0)
            pts = outline + inner
        else:
            pts = along(src, size, gap, inset=p["inset"] if not is_line else 0.0)
        out = ctx() if p["show"] else []
        if pts:
            out.append(make(pts, size, p["color"], p["style"]))
        return out

    T = lambda *a: a
    common = [T("size", "Steingröße", "choice", [(n, s) for n, s in SIZES], 2.8),
              T("gap", "Abstand", "num", 0.0, 10.0, 0.1, 1, " mm", 0.6),
              T("style", "Art", "choice", STYLES, "crystal"),
              T("color", "Farbe", "color", "#E8F4FF"),
              T("show", "Auswahl in der Vorschau zeigen", "check", True)]
    return [
        ("outline", "Entlang der Kontur", "Eine Steinreihe folgt dem Umriss der Auswahl "
         "(bei Linien: der Linie). »Einzug« schiebt die Reihe nach innen.",
         [T("mode", "Anordnung", "choice", [("Kontur", "outline")], "outline"),
          T("inset", "Einzug", "num", 0.0, 10.0, 0.1, 1, " mm", 1.6), *common], build),
        ("fill", "Fläche füllen", "Die ganze Fläche mit Steinen füllen – versetzt (dicht wie "
         "Bienenwaben) oder als gerades Raster.",
         [T("mode", "Anordnung", "choice", [("Fläche", "fill")], "fill"),
          T("pattern", "Raster", "choice", [("Versetzt (Waben)", "hex"), ("Gerade", "grid")], "hex"),
          T("angle", "Winkel", "num", 0.0, 90.0, 1.0, 0, "°", 0.0), *common], build),
        ("both", "Kontur und Fläche", "Außen eine saubere Steinreihe, innen gefüllt.",
         [T("mode", "Anordnung", "choice", [("Kontur + Fläche", "both")], "both"),
          T("pattern", "Raster", "choice", [("Versetzt (Waben)", "hex"), ("Gerade", "grid")], "hex"),
          T("angle", "Winkel", "num", 0.0, 90.0, 1.0, 0, "°", 0.0), *common], build),
    ]
