"""Encore: die Auswahl als Muster wiederholen – im Kreis, im Bogen, auf einer Linie, als
Rechteck- oder Formrahmen oder entlang einer eigenen Linie (wie »Encore« in Profi-
Sticksoftware). Liefert Einträge für templates.TemplateDialog (mit Live-Vorschau)."""
import math
import uuid

from shapely import affinity
from shapely.geometry import LineString, Point

from . import shapes


def bounds(objs):
    """Weltrahmen der Objekte (Stiche bzw. Steine) – (minx, miny, maxx, maxy)."""
    xs, ys = [], []
    for o in objs:
        for _, b in o.world_blocks():
            xs += [p[0] for p in b]
            ys += [p[1] for p in b]
        if o.kind == "stones" or not xs:
            g = o.world_geometry()
            if g is not None and not g.is_empty:
                b = g.bounds
                xs += [b[0], b[2]]
                ys += [b[1], b[3]]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return min(xs), min(ys), max(xs), max(ys)


def on_polyline(pts, n, closed):
    """n Stellen in gleichem Abstand auf einem Polygonzug: [(x, y, winkel°)].
    Geschlossen: gleichmäßig rundherum ab dem ersten Punkt; offen: von Anfang bis Ende."""
    ring = list(pts) + ([pts[0]] if closed and pts[0] != pts[-1] else [])
    ln = LineString(ring)
    L = ln.length
    if L <= 0 or n < 1:
        return []
    if closed:
        ds = [L * k / n for k in range(n)]
    elif n == 1:
        ds = [L / 2]
    else:
        ds = [L * k / (n - 1) for k in range(n)]
    out = []
    eps = min(0.5, L / 200)
    for d in ds:
        p = ln.interpolate(d)
        a = ln.interpolate(max(0.0, d - eps))
        b = ln.interpolate(min(L, d + eps))
        if closed and d - eps < 0:
            a = ln.interpolate(L - eps)
        ang = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        out.append((p.x, p.y, ang))
    return out


def circle_pts(cx, cy, r, a0=0.0, a1=360.0, res=180):
    """Kreis(bogen) im Uhrzeigersinn, 0° = oben."""
    out = []
    for k in range(res + 1):
        t = math.radians(a0 + (a1 - a0) * k / res)
        out.append((cx + r * math.sin(t), cy - r * math.cos(t)))
    return out


def arrange(sel, places, rotate=True, mirror=False, scales=None):
    """Kopien der Auswahl an die Stellen [(x, y, winkel)] setzen (Mitte der Auswahl auf die
    Stelle). mirror: jede zweite Kopie gespiegelt; scales: Größenfaktor je Kopie.
    Alle Kopien bilden zusammen eine Gruppe."""
    from .canvas import transform_objects
    b = bounds(sel)
    c0 = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    gid = uuid.uuid4().hex[:8]
    out = []
    for i, (x, y, ang) in enumerate(places):
        clones = [o.clone() for o in sel]
        if mirror and i % 2:
            for o in clones:
                o.sx = -o.sx
                o.x = 2 * c0[0] - o.x
                o.rot = (-o.rot) % 360
        f = scales[i] if scales else 1.0
        transform_objects(clones, c0, scale=f, angle=ang if rotate else 0.0)
        for o in clones:
            o.x += x - c0[0]
            o.y += y - c0[1]
            o.group = gid
        out += clones
    return out


def _ramp(n, end_pct):
    """Größenverlauf: erste Kopie 100 %, letzte end_pct %."""
    if n <= 1 or abs(end_pct - 100) < 0.5:
        return None
    return [1.0 + (end_pct / 100.0 - 1.0) * k / (n - 1) for k in range(n)]


SHAPES = [("Herz", "heart"), ("Stern", "star"), ("Oval", "oval"), ("Raute", "diamond"),
          ("Sechseck", "hex"), ("Tropfen", "drop"), ("Wolke", "cloud")]


def _shape_ring(kind, size):
    """Umriss einer Rahmenform (Mitte 0,0, Breite ≈ size) als Punktliste, Start oben."""
    if kind == "oval":
        g = Point(0, 0).buffer(1, 128)
        g = affinity.scale(g, size / 2, size / 2 * 0.7)
    elif kind == "diamond":
        g = shapes.regular(4, 25)
    elif kind == "hex":
        g = shapes.regular(6, 25)
    else:
        g = {"heart": shapes.heart, "star": lambda: shapes.star(5, 25, 12),
             "drop": shapes.drop, "cloud": shapes.cloud}[kind]()
    b = g.bounds
    f = size / max(b[2] - b[0], b[3] - b[1], 1e-6)
    g = affinity.scale(g, f, f, origin=(0, 0))
    b = g.bounds
    g = affinity.translate(g, -(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2)
    ring = list(g.exterior.coords)[:-1]
    if not g.exterior.is_ccw:          # y nach unten: im Uhrzeigersinn auf dem Bildschirm
        ring = ring[::-1]
    top = min(range(len(ring)), key=lambda i: (round(ring[i][1], 3), abs(ring[i][0])))
    return ring[top:] + ring[:top]


def encore_templates(sel):
    """Einträge für templates.TemplateDialog. Die Auswahl wird ersetzt; eine ausgewählte
    Linie dient beim Modus »Entlang Linie« als Pfad und bleibt erhalten (_context)."""
    path_obj = next((o for o in sel if o.kind == "line"), None)
    motif = [o for o in sel if o is not path_obj] if path_obj is not None and len(sel) > 1 else sel
    b = bounds(motif)
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    w, h = max(1.0, b[2] - b[0]), max(1.0, b[3] - b[1])
    size = max(w, h)

    def circle(p):
        n = int(p["n"])
        pts = circle_pts(cx, cy, p["radius"], p["start"], p["start"] + 360.0)
        places = on_polyline(pts[:-1], n, True)
        return arrange(motif, places, p["rotate"], p["mirror"])

    def arc(p):
        n = int(p["n"])
        span = p["span"]
        r = p["radius"]
        if p["down"]:       # Bogen nach unten offen (wie ein Lächeln)
            pts = circle_pts(cx, cy - r, r, 180 - span / 2, 180 + span / 2)[::-1]
            places = [(x, y, a + 180) for x, y, a in on_polyline(pts, n, False)]
        else:
            pts = circle_pts(cx, cy + r, r, -span / 2, span / 2)
            places = on_polyline(pts, n, False)
        return arrange(motif, places, p["rotate"], p["mirror"], _ramp(n, p["end"]))

    def line(p):
        n = int(p["n"])
        a = math.radians(p["angle"])
        d = p["gap"] + w
        L = d * (n - 1)
        places = []
        for k in range(n):
            t = -L / 2 + k * d
            off = p["wave"] * (1 if k % 2 else -1) / 2 if p["wave"] else 0.0
            places.append((cx + t * math.cos(a) - off * math.sin(a),
                           cy + t * math.sin(a) + off * math.cos(a), p["angle"]))
        return arrange(motif, places, True, p["mirror"], _ramp(n, p["end"]))

    def rect(p):
        W, H = p["width"], p["height"]
        ring = [(cx - W / 2, cy - H / 2), (cx + W / 2, cy - H / 2), (cx + W / 2, cy + H / 2),
                (cx - W / 2, cy + H / 2)]
        if p["corners"]:          # Ecken besetzen: je Seite gleich viele, Ecken zuerst
            per = max(1, int(p["n"]) // 4)
            places = []
            for i in range(4):
                a, c = ring[i], ring[(i + 1) % 4]
                ang = math.degrees(math.atan2(c[1] - a[1], c[0] - a[0]))
                for k in range(per):
                    t = k / per
                    places.append((a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t, ang))
        else:
            places = on_polyline(ring, int(p["n"]), True)
        return arrange(motif, places, p["rotate"], p["mirror"])

    def shape(p):
        ring = [(cx + x, cy + y) for x, y in _shape_ring(p["shape"], p["size"])]
        places = on_polyline(ring, int(p["n"]), True)
        return arrange(motif, places, p["rotate"], p["mirror"])

    def along(p):
        if path_obj is None or len(sel) < 2:
            return [o.clone() for o in sel]
        g = path_obj.world_geometry()
        pts = list(g.coords) if g.geom_type == "LineString" else list(g.geoms[0].coords)
        closed = bool(path_obj.closed)
        if closed and pts[0] == pts[-1]:
            pts = pts[:-1]
        places = on_polyline(pts, int(p["n"]), closed)
        if p["offset"]:
            places = [(x - p["offset"] * math.sin(math.radians(a)),
                       y + p["offset"] * math.cos(math.radians(a)), a) for x, y, a in places]
        out = arrange(motif, places, p["rotate"], p["mirror"],
                      None if closed else _ramp(len(places), p["end"]))
        ctx = path_obj.clone()
        ctx._context = True
        return [ctx] + out

    T = lambda *a: a
    R = max(8.0, round(size * 1.3, 0))
    mirror = T("mirror", "Jede zweite Kopie spiegeln", "check", False)
    rotate = T("rotate", "Kopien mitdrehen (folgen der Richtung)", "check", True)
    end = T("end", "Größe der letzten Kopie", "num", 30.0, 200.0, 5.0, 0, " %", 100.0)
    out = [
        ("circle", "Kreis", "Kopien gleichmäßig im Kreis um die Mitte der Auswahl – Blüten, "
         "Kränze, Mandalas.",
         [T("n", "Anzahl", "int", 2, 48, 8),
          T("radius", "Radius", "num", 3.0, 200.0, 0.5, 1, " mm", R),
          T("start", "Startwinkel", "num", 0.0, 360.0, 1.0, 0, "°", 0.0), rotate, mirror], circle),
        ("arc", "Bogen", "Kopien auf einem Kreisbogen – über oder unter einem Schriftzug, "
         "mit Größenverlauf.",
         [T("n", "Anzahl", "int", 2, 40, 5),
          T("radius", "Radius", "num", 5.0, 300.0, 0.5, 1, " mm", round(R * 1.6, 0)),
          T("span", "Bogenwinkel", "num", 20.0, 340.0, 5.0, 0, "°", 140.0),
          T("down", "Bogen nach unten (wie ein Lächeln)", "check", False), rotate, mirror, end],
         arc),
        ("line", "Linie / Bordüre", "Kopien in einer Reihe – Säume, Bordüren, Borten. "
         "»Zickzack« versetzt jede zweite Kopie.",
         [T("n", "Anzahl", "int", 2, 60, 6),
          T("gap", "Abstand zwischen Kopien", "num", -20.0, 100.0, 0.5, 1, " mm",
            round(max(1.0, w * 0.2), 1)),
          T("angle", "Richtung", "num", -90.0, 90.0, 1.0, 0, "°", 0.0),
          T("wave", "Zickzack", "num", 0.0, 60.0, 0.5, 1, " mm", 0.0), mirror, end], line),
        ("rect", "Rechteck-Rahmen", "Kopien rund um ein Rechteck – Rahmen für Bilder, Schilder, "
         "Kissen.",
         [T("n", "Anzahl", "int", 4, 80, 16),
          T("width", "Breite", "num", 10.0, 400.0, 1.0, 0, " mm", round(R * 4.0, 0)),
          T("height", "Höhe", "num", 10.0, 400.0, 1.0, 0, " mm", round(R * 2.8, 0)),
          T("corners", "Ecken besetzen (je Seite gleich viele)", "check", True), rotate, mirror],
         rect),
        ("shape", "Form-Rahmen", "Kopien auf dem Umriss einer Form: Herz, Stern, Oval, Raute, "
         "Sechseck, Tropfen, Wolke.",
         [T("shape", "Form", "choice", SHAPES, "heart"), T("n", "Anzahl", "int", 3, 80, 14),
          T("size", "Größe", "num", 10.0, 400.0, 1.0, 0, " mm", round(R * 4.0, 0)), rotate, mirror],
         shape),
    ]
    if path_obj is not None and len(sel) > 1:
        out.insert(0, ("along", "Entlang der Linie", "Kopien gleichmäßig auf der ausgewählten "
                       "Linie verteilt (die Linie bleibt als Hilfslinie erhalten).",
                       [T("n", "Anzahl", "int", 2, 80, 7),
                        T("offset", "Abstand zur Linie", "num", -50.0, 50.0, 0.5, 1, " mm", 0.0),
                        rotate, mirror, end], along))
    return out, motif
