"""Gestaltungsfunktionen nach dem Vorbild von Inkscape: Pfad-Operationen, Ausrichten und
Verteilen, Versatz, Mehrfach-Kopien (Raster, Kreis) sowie Stern-, Vieleck- und Spiralformen.
Alles in Weltkoordinaten (mm), ohne Qt – die Befehle im Hauptfenster rufen diese Funktionen auf."""
import math

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .engine import polygons_of

MIN_AREA = 0.3          # mm² – kleinere Splitter fallen weg


def _clean(geom):
    polys = [p for p in polygons_of(geom) if p.area >= MIN_AREA]
    return unary_union(polys) if polys else None


# ---------------------------------------------------------------- Pfad-Operationen
def intersection(geoms):
    """Schnittmenge aller Formen (nur was alle gemeinsam haben)."""
    g = geoms[0]
    for h in geoms[1:]:
        g = g.intersection(h)
    return _clean(g)


def exclusion(geoms):
    """Exklusiv-Oder: was genau einmal bzw. ungerade oft bedeckt ist."""
    g = geoms[0]
    for h in geoms[1:]:
        g = g.symmetric_difference(h)
    return _clean(g)


def division(bottom, cutters):
    """Teilen: die untere Form an den Umrissen der oberen in Stücke schneiden (wie Inkscape
    »Division«). Liefert die Teile von innen nach außen sortiert."""
    pieces = [bottom]
    for c in cutters:
        nxt = []
        for p in pieces:
            for part in (p.intersection(c), p.difference(c)):
                part = _clean(part)
                if part is not None:
                    nxt.extend(q for q in polygons_of(part))
        pieces = nxt
    return pieces


# ---------------------------------------------------------------- Ausrichten / Verteilen
ALIGN_MODES = [("left", "Linksbündig"), ("hcenter", "Horizontal zentrieren"),
               ("right", "Rechtsbündig"), ("top", "Oben"), ("vcenter", "Vertikal zentrieren"),
               ("bottom", "Unten")]


def align_offsets(rects, mode, ref):
    """rects: [(minx, miny, maxx, maxy)], ref: Bezugsrechteck -> [(dx, dy)] je Objekt."""
    out = []
    for x0, y0, x1, y1 in rects:
        dx = dy = 0.0
        if mode == "left":
            dx = ref[0] - x0
        elif mode == "right":
            dx = ref[2] - x1
        elif mode == "hcenter":
            dx = (ref[0] + ref[2]) / 2 - (x0 + x1) / 2
        elif mode == "top":
            dy = ref[1] - y0
        elif mode == "bottom":
            dy = ref[3] - y1
        elif mode == "vcenter":
            dy = (ref[1] + ref[3]) / 2 - (y0 + y1) / 2
        out.append((dx, dy))
    return out


def distribute_offsets(rects, axis="x", gap=None):
    """Gleichmäßig verteilen: gleiche Abstände zwischen den Objekten; das erste und letzte
    bleiben stehen (gap=None) bzw. fester Abstand gap (mm) ab dem ersten."""
    i0, i1 = (0, 2) if axis == "x" else (1, 3)
    order = sorted(range(len(rects)), key=lambda k: rects[k][i0])
    sizes = [rects[k][i1] - rects[k][i0] for k in order]
    out = [(0.0, 0.0)] * len(rects)
    if len(rects) < 2:
        return out
    start = rects[order[0]][i0]
    if gap is None:
        span = rects[order[-1]][i1] - start
        gap = (span - sum(sizes)) / (len(rects) - 1)
    pos = start
    for k, size in zip(order, sizes):
        d = pos - rects[k][i0]
        out[k] = (d, 0.0) if axis == "x" else (0.0, d)
        pos += size + gap
    return out


# ---------------------------------------------------------------- Versatz
def offset(geom, d, round_corners=True):
    """Fläche um d mm erweitern (d > 0) bzw. schrumpfen (d < 0)."""
    g = geom.buffer(d, join_style=1 if round_corners else 2, mitre_limit=3.0)
    return _clean(g)


def outline_rings(geom, distance=2.0, round_corners=True):
    """Außenkontur(en) im Abstand `distance` um die Form(en) – z. B. als Patch-Rand.
    Liefert geschlossene Punktlisten (ohne Wiederholung des Startpunkts)."""
    g = unary_union(geom).buffer(distance, join_style=1 if round_corners else 2, mitre_limit=3.0)
    rings = []
    for p in polygons_of(g):
        pts = list(p.exterior.simplify(0.05).coords)[:-1]
        if len(pts) >= 3:
            rings.append(pts)
    return rings


# ---------------------------------------------------------------- Mehrfach-Kopien
def grid_offsets(w, h, cols, rows, gap_x=5.0, gap_y=5.0):
    """Positionen (dx, dy) für ein Raster aus cols × rows Kopien (das Original ist (0, 0))."""
    return [(c * (w + gap_x), r * (h + gap_y)) for r in range(rows) for c in range(cols)
            if (r, c) != (0, 0)]


def circle_offsets(n, radius, rotate=True, start_angle=0.0):
    """n Kopien im Kreis: das Original steht oben, der Kreismittelpunkt liegt `radius` mm
    darunter. Liefert [(dx, dy, drehung)] für die n − 1 Kopien."""
    out = []
    for k in range(1, n):
        a = math.radians(start_angle + 360.0 * k / n)
        dx = radius * math.sin(a)
        dy = radius - radius * math.cos(a)
        out.append((dx, dy, 360.0 * k / n if rotate else 0.0))
    return out


# ---------------------------------------------------------------- Formen
def star(points=5, r_outer=20.0, ratio=0.45, rounding=0.0, polygon=False, rotation=0.0):
    """Stern (bzw. regelmäßiges Vieleck mit polygon=True) als Polygon um (0, 0).
    ratio: innerer/äußerer Radius, rounding: 0…1 runde Spitzen."""
    pts = []
    n = max(3, int(points))
    for k in range(n * (1 if polygon else 2)):
        a = math.radians(rotation - 90 + (360.0 / n) * (k if polygon else k / 2))
        r = r_outer if polygon or k % 2 == 0 else r_outer * ratio
        pts.append((r * math.cos(a), r * math.sin(a)))
    poly = Polygon(pts)
    if rounding > 0:
        r = rounding * r_outer * (0.25 if not polygon else 0.35)
        poly = poly.buffer(-r, join_style=1).buffer(r, join_style=1)
    return poly


def spiral(turns=3.0, r_inner=1.0, r_outer=20.0, step=0.5):
    """Archimedische Spirale als Punktliste (für eine Linie)."""
    total = 2 * math.pi * turns
    pts, t = [], 0.0
    while t <= total:
        r = r_inner + (r_outer - r_inner) * t / total
        pts.append((r * math.cos(t), r * math.sin(t)))
        t += step / max(r, 0.5)
    return pts


def regular_shape_curve(points, r_outer, ratio, polygon, rotation=0.0, rounded=False):
    """Stern/Vieleck als Knotenliste [[x, y, typ]] – mit rounded als Rundungspunkte (glatter
    Stern wie in Inkscape »abgerundet«), sonst als Ecken."""
    from .curves import CORNER, CURVE
    n = max(3, int(points))
    out = []
    for k in range(n * (1 if polygon else 2)):
        a = math.radians(rotation - 90 + (360.0 / n) * (k if polygon else k / 2))
        r = r_outer if polygon or k % 2 == 0 else r_outer * ratio
        out.append([r * math.cos(a), r * math.sin(a), CURVE if rounded else CORNER])
    return out


def bounds_of(geoms):
    xs0, ys0, xs1, ys1 = zip(*[g.bounds for g in geoms])
    return min(xs0), min(ys0), max(xs1), max(ys1)


def line_length(pts):
    return LineString(pts).length if len(pts) > 1 else 0.0
