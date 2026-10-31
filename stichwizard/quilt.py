"""Quiltblock-Assistent: einen Quiltblock (Quadrat, Rechteck, Kreis, Sechseck) mit Motiv in
der Mitte und Quiltmuster drumherum – Echo-Quilting, Stippling (Mäander), Kreuzschraffur,
Konturlinien oder Spirale. Alles als Steppstich ohne Unterlage, wie es durch Oberstoff,
Vlies und Rückseite gequiltet wird. Einträge im Format von templates.TEMPLATES."""
import math

from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, box
from shapely.ops import substring, unary_union

from . import shapes, templates
from .model import EmbObject

T = lambda *a: a
FORMS = [("Quadrat", "square"), ("Rechteck", "rect"), ("Kreis", "circle"), ("Sechseck", "hex")]
MOTIFS = [("Herz", "Herz"), ("Stern", "Stern"), ("Blume", "Blume"), ("Schmetterling",
                                                                      "Schmetterling"),
          ("Blatt", "Blatt"), ("Stern 8", "Stern 8"), ("Wolke", "Wolke"), ("Anker", "Anker"),
          ("Kein Motiv", "none")]
STYLES = [("Quiltlinie (Kontur)", "outline"), ("Gestickt (gefüllt)", "filled")]
STITCHES = [("Steppstich", "run"), ("Bohnenstich (kräftig)", "triple")]


def block_geometry(p):
    w = p["width"]
    h = w if p["form"] in ("square", "circle", "hex") else p["height"]
    if p["form"] == "circle":
        return Point(0, 0).buffer(w / 2, 96)
    if p["form"] == "hex":
        g = shapes.regular(6, 25)
        b = g.bounds
        return affinity.scale(g, w / (b[2] - b[0]), w / (b[2] - b[0]), origin=(0, 0))
    return box(-w / 2, -h / 2, w / 2, h / 2)


def quilt_line(pts, p, name, closed=False):
    o = EmbObject("line", name)
    o.set_points(list(pts), closed=closed)
    o.border.update(type=p["stitch"], color=p["color"], stitch_len=p["len"])
    if p["stitch"] == "triple":
        o.border["repeats"] = 1
    return o


def _lines_of(g):
    """Alle Linienstücke einer Geometrie als Punktlisten (geschlossen erkannt)."""
    out = []
    for part in getattr(g, "geoms", [g]):
        if part.is_empty:
            continue
        if part.geom_type == "Polygon":
            out.append((list(part.exterior.coords)[:-1], True))
        elif part.geom_type in ("LineString", "LinearRing"):
            cs = list(part.coords)
            closed = len(cs) > 3 and cs[0] == cs[-1]
            out.append((cs[:-1] if closed else cs, closed))
    return out


def motif_parts(p, block):
    """(Motiv-Objekte, Motivfläche in Weltkoordinaten oder None)."""
    if p["motif"] == "none":
        return [], None
    b = block.bounds
    size = min(b[2] - b[0], b[3] - b[1]) * p["msize"] / 100.0
    m = templates.motif(p["motif"], size, p["mcolor"])
    g = m.world_geometry()
    if p["mstyle"] == "filled":
        m.border.update(type="run", color=p["mcolor"], stitch_len=2.0)
        return [m], g
    outs = [quilt_line(cs, dict(p, color=p["mcolor"]), p["motif"], closed)
            for cs, closed in _lines_of(g.boundary)]
    return outs, g


def _echo(block, motif, p):
    """Echo-Quilting: Konturen im gleichen Abstand um das Motiv, am Blockrand abgeschnitten."""
    inner = block.buffer(-p["margin"])
    out = []
    n = int(p["count"]) or 200
    for k in range(1, n + 1):
        ring = motif.buffer(p["gap"] * k, join_style=1, resolution=24)
        if ring.contains(inner):
            break
        clipped = ring.boundary.intersection(inner)
        for cs, closed in _lines_of(clipped):
            if len(cs) >= 2 and LineString(cs).length > p["gap"]:
                out.append(quilt_line(cs, p, f"Echo {k}", closed))
    return out


def _rings(area):
    out = []
    for poly in getattr(area, "geoms", [area]):
        if poly.geom_type == "Polygon":
            out += [LineString(poly.exterior.coords)] + [LineString(r.coords) for r in poly.interiors]
    return out


def _walk(ring, a, b):
    """Kürzerer Weg auf einem geschlossenen Ring von Punkt a nach Punkt b."""
    L = ring.length
    da, db = ring.project(Point(a)), ring.project(Point(b))
    fwd = (db - da) % L
    if fwd <= L - fwd:
        if da + fwd <= L:
            return list(substring(ring, da, da + fwd).coords)
        return list(substring(ring, da, L).coords) + list(substring(ring, 0, db).coords)[1:]
    back = list(_walk(ring, b, a))
    return back[::-1]


def chain(area, segs, max_walk=None):
    """Linienstücke (in Stickreihenfolge) zu durchgehenden Wegen verbinden: liegt das Ende
    eines Stücks und der Anfang des nächsten auf demselben Rand, läuft der Weg am Rand
    entlang (wie beim Quilten in einem Zug); sonst beginnt ein neuer Weg."""
    rings = _rings(area)
    paths = []
    for seg in segs:
        if paths:
            a, b = paths[-1][-1], seg[0]
            ring = next((r for r in rings if r.distance(Point(a)) < 0.05 and
                         r.distance(Point(b)) < 0.05), None)
            if ring is not None:
                walk = _walk(ring, a, b)
                if max_walk is None or LineString(walk).length <= max_walk:
                    paths[-1] += walk[1:] + list(seg[1:])
                    continue
        paths.append(list(seg))
    return paths


def _segments(g):
    return [list(part.coords) for part in getattr(g, "geoms", [g])
            if not part.is_empty and part.geom_type == "LineString" and part.length > 0.3]


def hatch(area, gap, angle, cross=True):
    """Schraffur von Rand zu Rand (eine oder zwei Richtungen), Reihe für Reihe im Zickzack."""
    out = []
    c = area.centroid
    R = math.hypot(area.bounds[2] - area.bounds[0], area.bounds[3] - area.bounds[1])
    for ang in ([angle, angle + 90] if cross else [angle]):
        segs = []
        n = int(R / gap) + 1
        for k, i in enumerate(range(-n, n + 1)):
            ln = LineString([(-R, i * gap), (R, i * gap)])
            ln = affinity.translate(affinity.rotate(ln, ang, origin=(0, 0)), c.x, c.y)
            parts = sorted(_segments(area.intersection(ln)),
                           key=lambda q: (q[0][0] - c.x) * math.cos(math.radians(ang)) +
                           (q[0][1] - c.y) * math.sin(math.radians(ang)))
            if k % 2:
                parts = [q[::-1] for q in reversed(parts)]
            segs += parts
        out += chain(area, segs, max_walk=gap * 3)
    return out


def spiral(area, gap, center):
    """Archimedische Spirale von der Blockmitte nach außen, an Motiv und Rand geschnitten."""
    R = max(math.hypot(x - center[0], y - center[1]) for x, y in
            [(area.bounds[0], area.bounds[1]), (area.bounds[2], area.bounds[3]),
             (area.bounds[0], area.bounds[3]), (area.bounds[2], area.bounds[1])])
    pts = []
    th = 0.0
    while gap * th / (2 * math.pi) < R:
        r = gap * th / (2 * math.pi)
        pts.append((center[0] + r * math.cos(th), center[1] + r * math.sin(th)))
        th += min(0.3, 1.2 / max(r, 0.5))
    sp = LineString(pts)
    parts = area.intersection(sp)
    segs = [list(q.coords) for q in getattr(parts, "geoms", [parts])
            if not q.is_empty and q.geom_type == "LineString"]
    segs.sort(key=lambda q: sp.project(Point(q[0])))
    return chain(area, segs, max_walk=gap * 2.5)


def _filled(area, p, kind, **extra):
    o = EmbObject("shape", "Quiltfläche")
    o.set_geometry(area)
    o.fill.update(type=kind, color=p["color"], underlay=False, underlay_auto=False, pull=0.0,
                  stitch_len=p["len"], auto_spacing=False, knockout=False, **extra)
    o.border["type"] = "none"
    return o


def build(p, kind, motif_geom=None, keep=()):
    block = block_geometry(p)
    if motif_geom is not None:              # um eine ausgewählte Form quilten
        c = motif_geom.centroid
        block = affinity.translate(block, c.x, c.y)
        mobjs, mg = [], motif_geom
    else:
        mobjs, mg = motif_parts(p, block)
    out = []
    if p["ditch"]:
        for cs, closed in _lines_of(block.boundary):
            out.append(quilt_line(cs, p, "Blockrand", closed))
    area = block.buffer(-p["margin"])
    if mg is not None:
        area = area.difference(mg.buffer(p["clear"], join_style=1))
    if kind == "echo":
        if mg is None:                       # ohne Motiv: Echo vom Blockrand nach innen
            out.append(_filled(area, p, "ripple", size=p["gap"] * 2))
        else:
            out += _echo(block, mg.buffer(p["clear"], join_style=1), p)
    elif kind == "stipple":
        out.append(_filled(area, p, "meander", size=p["size"]))
    elif kind == "hatch":
        out += [quilt_line(q, p, "Schraffur") for q in hatch(area, p["gap"], p["angle"])]
    elif kind == "contour":
        out.append(_filled(area, p, "ripple", size=p["gap"] * 2))
    elif kind == "spiral":
        c = block.centroid
        out += [quilt_line(q, p, "Spirale") for q in spiral(area, p["gap"], (c.x, c.y))]
    return list(keep) + out + mobjs


def _common(gap=6.0):
    return [T("form", "Blockform", "choice", FORMS, "square"),
            T("width", "Breite", "num", 40.0, 300.0, 1.0, 0, " mm", 120.0),
            T("height", "Höhe (Rechteck)", "num", 40.0, 300.0, 1.0, 0, " mm", 90.0),
            T("motif", "Motiv in der Mitte", "choice", MOTIFS, "Herz"),
            T("msize", "Motivgröße", "num", 15.0, 80.0, 1.0, 0, " %", 45.0),
            T("mstyle", "Motiv als", "choice", STYLES, "outline"),
            T("clear", "Abstand ums Motiv", "num", 0.0, 15.0, 0.5, 1, " mm", 3.0),
            T("margin", "Abstand zum Blockrand", "num", 0.0, 20.0, 0.5, 1, " mm", 4.0),
            T("ditch", "Blockrand mitquilten", "check", True),
            T("stitch", "Stichart", "choice", STITCHES, "run"),
            T("len", "Stichlänge", "num", 1.5, 4.0, 0.1, 1, " mm", 2.5),
            T("color", "Quiltfarbe", "color", "#6D4C41"),
            T("mcolor", "Motivfarbe", "color", "#C2185B")]


def quilt_templates(sel=None):
    """Einträge für templates.TemplateDialog; sel: ausgewählte Objekte (werden umquiltet)."""
    sel_geom = None
    if sel:
        parts = [o.world_geometry() for o in sel if o.world_geometry() is not None]
        parts = [g if g.geom_type in ("Polygon", "MultiPolygon") else g.buffer(1.0)
                 for g in parts if not g.is_empty]
        if parts:
            sel_geom = unary_union(parts)
    G = lambda d: T("gap", "Linienabstand", "num", 2.0, 25.0, 0.5, 1, " mm", d)
    out = [
        ("echo", "Echo-Quilting", "Linien im gleichen Abstand rund um das Motiv – wie Wellen "
         "um einen Stein im Wasser.",
         [*_common(), G(6.0), T("count", "Anzahl Echos (0 = bis zum Rand)", "int", 0, 60, 0)],
         lambda p: build(p, "echo")),
        ("stipple", "Stippling (Mäander)", "Eine verschlungene Linie, die sich nie kreuzt und "
         "die ganze Fläche um das Motiv ausfüllt – der Klassiker beim Freihandquilten.",
         [*_common(), T("size", "Mäandergröße", "num", 6.0, 40.0, 1.0, 0, " mm", 16.0)],
         lambda p: build(p, "stipple")),
        ("hatch", "Kreuzschraffur", "Rautengitter um das Motiv – lässt das Motiv plastisch "
         "hervortreten.",
         [*_common(), G(10.0), T("angle", "Winkel", "num", 0.0, 90.0, 1.0, 0, "°", 45.0)],
         lambda p: build(p, "hatch")),
        ("contour", "Konturlinien", "Linien folgen dem Blockrand und dem Motiv nach innen.",
         [*_common(), G(5.0)], lambda p: build(p, "contour")),
        ("spiral", "Spirale", "Eine Spirale über den ganzen Block, das Motiv bleibt frei.",
         [*_common(), G(5.0)], lambda p: build(p, "spiral")),
    ]
    if sel_geom is not None:
        def around(p):
            ctx = []
            for o in sel:
                c = o.clone()
                c._context = True
                ctx.append(c)
            return build(p, p["style"], sel_geom, ctx)
        b = sel_geom.bounds
        common = [c for c in _common() if c[0] not in ("motif", "msize", "mstyle", "mcolor")]
        common = [T("width", "Breite", "num", 40.0, 300.0, 1.0, 0, " mm",
                    round(max(60.0, (b[2] - b[0]) * 1.8))) if c[0] == "width" else c
                  for c in common]
        out.insert(0, ("around", "Um die Auswahl quilten", "Die ausgewählte Stickerei bleibt, "
                       "drumherum entsteht der Quiltblock.",
                       [T("style", "Quiltmuster", "choice",
                          [("Echo", "echo"), ("Stippling", "stipple"), ("Kreuzschraffur", "hatch"),
                           ("Konturlinien", "contour")], "echo"),
                        *common, G(6.0), T("size", "Mäandergröße", "num", 6.0, 40.0, 1.0, 0,
                                           " mm", 16.0),
                        T("angle", "Winkel (Schraffur)", "num", 0.0, 90.0, 1.0, 0, "°", 45.0),
                        T("count", "Anzahl Echos (0 = bis zum Rand)", "int", 0, 60, 0)], around))
    return out
