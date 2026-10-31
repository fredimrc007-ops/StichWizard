"""Rahmen & Schnörkel: Zierrahmen, Bogenkanten, Wellenrahmen, Perlenkreise, Schnörkel-
Trenner, Eckschnörkel und Ranken – alles rechnerisch erzeugt, frei in Größe, Stichart und
Farbe. Einträge im Format von templates.TEMPLATES (für templates.TemplateDialog)."""
import math

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon

from . import shapes
from .model import EmbObject

STITCHES = [("Satinstich", "satin"), ("Bohnenstich", "triple"), ("Steppstich", "run"),
            ("Zickzack", "zigzag")]


# ------------------------------------------------------------------ Bausteine
def bezier(p0, p1, p2, p3, n=40):
    out = []
    for k in range(n + 1):
        t = k / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def scroll(length, curl, turns=1.15, bow=0.0, inner=0.28, res=60):
    """Schnörkel im lokalen Rahmen: beginnt bei (0, 0) in Richtung +x, schwingt sanft
    (bow, mm) und rollt sich am Ende nach oben (−y) ein (Spirale, Radius curl → curl·inner)."""
    pts = bezier((0, 0), (length / 3, bow), (2 * length / 3, 0), (length, 0), 30)
    cx, cy = length, -curl
    for k in range(1, res + 1):
        t = k / res
        phi = math.radians(360 * turns * t)
        rho = curl * (1 - (1 - inner) * t)
        th = math.pi / 2 - phi
        pts.append((cx + rho * math.cos(th), cy + rho * math.sin(th)))
    return pts


def xform(pts, angle=0.0, dx=0.0, dy=0.0, mx=False, my=False, scale=1.0):
    """Punkte spiegeln (an der y- bzw. x-Achse), drehen (Grad), skalieren, verschieben."""
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    out = []
    for x, y in pts:
        x, y = (-x if mx else x) * scale, (-y if my else y) * scale
        out.append((x * ca - y * sa + dx, x * sa + y * ca + dy))
    return out


def line(pts, color, stitch="satin", width=2.0, closed=False, name="Schnörkel"):
    o = EmbObject("line", name)
    o.set_points(pts, closed=closed)
    o.border.update(type=stitch, color=color, width=width, stitch_len=2.2)
    if stitch == "triple":
        o.border["repeats"] = 1
    return o


def blob(geom, color, name="Zierform", fill_type="satin"):
    o = EmbObject("shape", name)
    o.set_geometry(geom)
    o.fill.update(color=color, type=fill_type, angle=30.0)
    o.border["type"] = "none"
    return o


def motif(name, size, color, x=0.0, y=0.0, rot=0.0):
    g = dict(shapes.MOTIFS)[name]()
    b = g.bounds
    f = size / max(b[2] - b[0], b[3] - b[1])
    g = affinity.scale(g, f, f, origin=(0, 0))
    g = affinity.rotate(g, rot, origin=(0, 0))
    b = g.bounds
    g = affinity.translate(g, x - (b[0] + b[2]) / 2, y - (b[1] + b[3]) / 2)
    return blob(g, color, name, "tatami")


def ring_points(form, w, h, r=0.0, res=240):
    """Geschlossener Umriss (Rechteck, abgerundet, Oval, Kreis) im Uhrzeigersinn, Start oben
    in der Mitte."""
    if form in ("oval", "circle"):
        hh = w if form == "circle" else h
        return [(w / 2 * math.sin(2 * math.pi * k / res), -hh / 2 * math.cos(2 * math.pi * k / res))
                for k in range(res)]
    r = min(r, w / 2, h / 2)
    g = Polygon([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])
    if r > 0:
        g = g.buffer(-r, join_style=2).buffer(r, 32)
    ring = list(g.exterior.coords)[:-1]
    if not g.exterior.is_ccw:          # mathematisch gegen = auf dem Bildschirm im Uhrzeigersinn
        ring = ring[::-1]
    i = min(range(len(ring)), key=lambda k: (round(ring[k][1], 2), abs(ring[k][0])))
    ring = ring[i:] + ring[:i]
    # gleichmäßig nachverdichten (für Wellen und Bögen)
    ln = LineString(ring + [ring[0]])
    return [ln.interpolate(ln.length * k / res).coords[0] for k in range(res)]


def _normal_out(ring, i):
    a, b = ring[i - 1], ring[(i + 1) % len(ring)]
    tx, ty = b[0] - a[0], b[1] - a[1]
    L = math.hypot(tx, ty) or 1.0
    return ty / L, -tx / L          # Uhrzeigersinn (y nach unten): rechts = außen


# ---------------------------------------------------------------- Schnörkel
def corner_piece(size, color, stitch, width):
    """Eckschnörkel für die linke obere Ecke (Ecke bei 0,0, Schnörkel rollen nach innen)."""
    L = size * 0.7
    c = size * 0.15
    top = xform(scroll(L, c, 1.15, bow=size * 0.04), my=True)       # Oberkante, rollt nach unten
    left = xform(scroll(L, c, 1.15, bow=-size * 0.04), angle=90)    # linke Kante, rollt nach rechts
    o = size * 0.07
    diag = xform(scroll(size * 0.28, size * 0.08, 1.1), angle=45, dx=o, dy=o)
    return [line(top, color, stitch, width), line(left, color, stitch, width),
            line(diag, color, stitch, width)]


def divider(p):
    W = p["width"]
    col, st, wd = p["color"], p["stitch"], p["line_w"]
    m = W * 0.09                      # Platz für das Mittelmotiv
    out = []
    for side in (False, True):        # rechts, dann gespiegelt links
        main = scroll(W / 2 - m - W * 0.06, W * 0.055, 1.2, bow=-W * 0.025)
        main = xform(main, dx=m)
        low = scroll(W * 0.22, W * 0.04, 1.1, bow=W * 0.02)
        low = xform(low, my=True, dx=m + W * 0.02, dy=W * 0.005)
        for pts in (main, low):
            out.append(line(xform(pts, mx=side), col, st, wd))
    if p["center"] != "none":
        out.append(motif(p["center"], m * 1.5, p["accent"]))
    return out


def corner(p):
    s = p["size"]
    out = corner_piece(s, p["color"], p["stitch"], p["line_w"])
    for o in out:
        o.x -= s / 2
        o.y -= s / 2
    if p["dot"]:
        out.append(motif("Herz", s * 0.12, p["accent"], -s / 2 + s * 0.2, -s / 2 + s * 0.2, -45))
    return out


def heart_scroll(p):
    s = p["size"]
    out = []
    for side in (False, True):
        # linke Herzhälfte: Spitze → Bauch → Bogen oben, dann nach innen eingerollt
        pts = bezier((0, 0.45), (-0.1, 0.3), (-0.5, 0.15), (-0.5, -0.12))
        pts += bezier((-0.5, -0.12), (-0.5, -0.32), (-0.4, -0.42), (-0.22, -0.42))[1:]
        pts = [(x * s, y * s) for x, y in pts]
        pts += xform(scroll(0.01, s * 0.13, 1.15, inner=0.3), my=True,
                     dx=-0.22 * s, dy=-0.42 * s)[1:]
        out.append(line(xform(pts, mx=side), p["color"], p["stitch"], p["line_w"],
                        name="Herzschnörkel"))
    if p["center"] != "none":
        out.append(motif(p["center"], s * 0.18, p["accent"], 0, s * 0.12))
    return out


def vine(p):
    L = p["length"]
    amp = p["amp"]
    n = int(p["waves"])
    pts = [(-L / 2 + L * k / 400, amp * math.sin(2 * math.pi * n * k / 400)) for k in range(401)]
    out = [line(pts, p["color"], p["stitch"], p["line_w"], name="Ranke")]
    leaf = shapes.leaf()
    b = leaf.bounds
    f = p["leaf"] / max(b[2] - b[0], b[3] - b[1])
    leaf = affinity.scale(leaf, f, f, origin=(0, 0))
    for k in range(2 * n):
        t = (k + 0.5) / (2 * n)
        x = -L / 2 + L * t
        y = amp * math.sin(2 * math.pi * n * t)
        up = y < 0
        g = affinity.rotate(leaf, (-35 if up else 145), origin=(0, 0))
        gb = g.bounds
        g = affinity.translate(g, x - (gb[0] + gb[2]) / 2,
                               y + (-1 if up else 1) * (p["leaf"] * 0.45) - (gb[1] + gb[3]) / 2)
        out.append(blob(g, p["accent"], "Blatt"))
    return out


# ------------------------------------------------------------------- Rahmen
def frame_flourish(p):
    w, h = p["width"], p["height"]
    out = [line(ring_points(p["form"], w, h, p["radius"]), p["color"], p["stitch"], p["line_w"],
                closed=True, name="Rahmen")]
    if p["corners"]:
        s = min(w, h) * 0.38
        inset = p["line_w"] + 2.0
        for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
            parts = corner_piece(s, p["accent"], p["stitch2"], max(1.0, p["line_w"] * 0.6))
            for o in parts:
                pts = [o.to_world(*q) for q in o.points]
                pts = xform(pts, angle=90 * k)
                cx, cy = sx * (w / 2 - inset), sy * (h / 2 - inset)
                if p["form"] in ("oval", "circle"):
                    cx, cy = cx * 0.62, cy * 0.62
                o.set_points([(x + cx, y + cy) for x, y in pts])
            out += parts
    return out


def scallop(p):
    w, h = p["width"], p["height"]
    ring = ring_points(p["form"], w, h, p["radius"], 600)
    per = LineString(ring + [ring[0]]).length
    n = max(6, int(round(per / p["scallop"])))
    ln = LineString(ring + [ring[0]])
    anchors = [ln.interpolate(per * k / n).coords[0] for k in range(n)]
    pts = []
    for k in range(n):
        a, b = anchors[k], anchors[(k + 1) % n]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        r = math.hypot(b[0] - a[0], b[1] - a[1]) / 2
        tx, ty = (b[0] - a[0]) / (2 * r or 1), (b[1] - a[1]) / (2 * r or 1)
        nx, ny = ty, -tx                   # außen
        if p["inward"]:
            nx, ny = -nx, -ny
        for j in range(16):
            t = math.pi * j / 16
            pts.append((mx - r * math.cos(t) * tx + r * math.sin(t) * nx,
                        my - r * math.cos(t) * ty + r * math.sin(t) * ny))
    out = [line(pts, p["color"], p["stitch"], p["line_w"], closed=True, name="Bogenkante")]
    if p["inner"]:
        out.append(line(ring_points(p["form"], w - 2 * p["inner_gap"], h - 2 * p["inner_gap"],
                                    max(0.0, p["radius"] - p["inner_gap"])),
                        p["accent"], "triple", 1.0, closed=True, name="Innenlinie"))
    return out


def wave(p):
    w, h = p["width"], p["height"]
    ring = ring_points(p["form"], w, h, p["radius"], 900)
    per = LineString(ring + [ring[0]]).length
    n = max(4, int(round(per / p["wave"])))
    pts = []
    acc = 0.0
    for i, (x, y) in enumerate(ring):
        if i:
            acc += math.hypot(x - ring[i - 1][0], y - ring[i - 1][1])
        nx, ny = _normal_out(ring, i)
        a = p["amp"] / 2 * math.sin(2 * math.pi * n * acc / per)
        pts.append((x + nx * a, y + ny * a))
    out = [line(pts, p["color"], p["stitch"], p["line_w"], closed=True, name="Wellenrahmen")]
    if p["second"]:
        pts2 = []
        acc = 0.0
        for i, (x, y) in enumerate(ring):
            if i:
                acc += math.hypot(x - ring[i - 1][0], y - ring[i - 1][1])
            nx, ny = _normal_out(ring, i)
            a = -p["amp"] / 2 * math.sin(2 * math.pi * n * acc / per)
            pts2.append((x + nx * a, y + ny * a))
        out.append(line(pts2, p["accent"], p["stitch"], p["line_w"], closed=True,
                        name="Wellenrahmen 2"))
    return out


def beads(p):
    w = p["width"]
    h = w if p["form"] == "circle" else p["height"]
    out = [line(ring_points(p["form"], w, h, p["radius"]), p["color"], p["stitch"], p["line_w"],
                closed=True, name="Rahmen")]
    gap = p["gap"]
    ring = ring_points(p["form"], w + 2 * gap, h + 2 * gap, p["radius"] + gap if p["radius"] else 0,
                       800)
    ln = LineString(ring + [ring[0]])
    n = int(p["count"])
    for k in range(n):
        x, y = ln.interpolate(ln.length * k / n).coords[0]
        if p["dot"] == "Punkt":
            out.append(blob(Point(x, y).buffer(p["dot_size"] / 2, 24), p["accent"], "Punkt"))
        else:
            out.append(motif(p["dot"], p["dot_size"], p["accent"], x, y))
    return out


def double_frame(p):
    w, h = p["width"], p["height"]
    g = p["gap"]
    return [line(ring_points(p["form"], w, h, p["radius"]), p["color"], p["stitch"], p["line_w"],
                 closed=True, name="Außenrahmen"),
            line(ring_points(p["form"], w - 2 * g, h - 2 * g, max(0.0, p["radius"] - g)),
                 p["accent"], p["stitch2"], max(0.8, p["line_w"] * 0.5), closed=True,
                 name="Innenrahmen")]


# ------------------------------------------------------------------ Einträge
T = lambda *a: a
FORMS = [("Rechteck", "rect"), ("Oval", "oval"), ("Kreis", "circle")]
CENTER = [("Herz", "Herz"), ("Raute", "Raute"), ("Stern", "Stern"), ("Blume", "Blume"),
          ("Kein Motiv", "none")]


def _size(w=120.0, h=80.0):
    return [T("form", "Form", "choice", FORMS, "rect"),
            T("width", "Breite", "num", 20.0, 400.0, 1.0, 0, " mm", w),
            T("height", "Höhe", "num", 20.0, 400.0, 1.0, 0, " mm", h),
            T("radius", "Eckenrundung", "num", 0.0, 60.0, 0.5, 1, " mm", 6.0)]


def _stitch(default="satin", width=2.0):
    return [T("stitch", "Stichart", "choice", STITCHES, default),
            T("line_w", "Breite (Satin)", "num", 0.8, 8.0, 0.1, 1, " mm", width)]


ORNAMENTS = [
    ("frame_flourish", "Zierrahmen mit Eckschnörkeln", "Rahmen (Rechteck, Oval oder Kreis) mit "
     "eingerollten Schnörkeln in allen vier Ecken.",
     [*_size(), *_stitch(), T("corners", "Eckschnörkel", "check", True),
      T("stitch2", "Stichart Schnörkel", "choice", STITCHES, "triple"),
      T("color", "Rahmenfarbe", "color", "#6D4C41"), T("accent", "Schnörkelfarbe", "color", "#B8860B")],
     frame_flourish),
    ("scallop", "Bogenkante", "Rahmen aus aneinandergereihten Bögen (Muschelkante) – nach außen "
     "oder innen, auf Wunsch mit Innenlinie.",
     [*_size(), *_stitch(), T("scallop", "Bogengröße", "num", 4.0, 40.0, 0.5, 1, " mm", 12.0),
      T("inward", "Bögen nach innen", "check", False),
      T("inner", "Innenlinie", "check", True),
      T("inner_gap", "Abstand Innenlinie", "num", 2.0, 30.0, 0.5, 1, " mm", 6.0),
      T("color", "Bogenfarbe", "color", "#AD1457"), T("accent", "Innenlinie", "color", "#F48FB1")],
     scallop),
    ("wave", "Wellenrahmen", "Rahmen als Welle – einfach oder doppelt gegenläufig (Zopf-Effekt).",
     [*_size(), *_stitch("triple", 1.5),
      T("wave", "Wellenlänge", "num", 4.0, 60.0, 0.5, 1, " mm", 14.0),
      T("amp", "Wellenhöhe", "num", 1.0, 20.0, 0.5, 1, " mm", 5.0),
      T("second", "Zweite Welle gegenläufig", "check", True),
      T("color", "Farbe", "color", "#1565C0"), T("accent", "Farbe 2. Welle", "color", "#64B5F6")],
     wave),
    ("beads", "Rahmen mit Punkten", "Rahmenlinie, außen begleitet von Punkten, Herzen oder Sternen.",
     [*_size(110.0, 110.0), *_stitch("satin", 1.8),
      T("count", "Anzahl", "int", 4, 120, 36),
      T("gap", "Abstand zur Linie", "num", 1.0, 20.0, 0.5, 1, " mm", 4.0),
      T("dot", "Motiv", "choice", [("Punkt", "Punkt"), ("Herz", "Herz"), ("Stern", "Stern"),
                                    ("Blume", "Blume"), ("Raute", "Raute")], "Punkt"),
      T("dot_size", "Motivgröße", "num", 1.5, 15.0, 0.1, 1, " mm", 2.6),
      T("color", "Rahmenfarbe", "color", "#2E7D32"), T("accent", "Motivfarbe", "color", "#FFB300")],
     beads),
    ("double", "Doppelrahmen", "Zwei Rahmenlinien im Abstand – außen kräftig, innen fein.",
     [*_size(), *_stitch("satin", 2.5),
      T("gap", "Abstand", "num", 1.0, 30.0, 0.5, 1, " mm", 4.0),
      T("stitch2", "Stichart innen", "choice", STITCHES, "triple"),
      T("color", "Außen", "color", "#37474F"), T("accent", "Innen", "color", "#90A4AE")],
     double_frame),
    ("divider", "Schnörkel-Trenner", "Symmetrischer Schnörkel mit Mittelmotiv – als Überschrift, "
     "unter Namen oder als Trennlinie.",
     [T("width", "Breite", "num", 30.0, 300.0, 1.0, 0, " mm", 120.0), *_stitch("triple", 1.4),
      T("center", "Mittelmotiv", "choice", CENTER, "Herz"),
      T("color", "Schnörkelfarbe", "color", "#5D4037"), T("accent", "Motivfarbe", "color", "#C62828")],
     divider),
    ("corner", "Eckschnörkel", "Einzelner Schnörkel für eine Ecke – mit Encore oder Spiegeln "
     "in alle Ecken setzen.",
     [T("size", "Größe", "num", 15.0, 200.0, 1.0, 0, " mm", 60.0), *_stitch("triple", 1.4),
      T("dot", "Herz in der Ecke", "check", True),
      T("color", "Schnörkelfarbe", "color", "#5D4037"), T("accent", "Herzfarbe", "color", "#C62828")],
     corner),
    ("heart", "Herz aus Schnörkeln", "Zwei eingerollte Schnörkel bilden ein Herz.",
     [T("size", "Größe", "num", 20.0, 200.0, 1.0, 0, " mm", 70.0), *_stitch("satin", 1.8),
      T("center", "Motiv in der Mitte", "choice", CENTER, "none"),
      T("color", "Farbe", "color", "#C2185B"), T("accent", "Motivfarbe", "color", "#F48FB1")],
     heart_scroll),
    ("vine", "Ranke mit Blättern", "Wellenranke mit Blättern abwechselnd oben und unten – "
     "für Säume und Borten.",
     [T("length", "Länge", "num", 30.0, 400.0, 1.0, 0, " mm", 150.0),
      T("waves", "Wellen", "int", 1, 20, 4),
      T("amp", "Wellenhöhe", "num", 1.0, 40.0, 0.5, 1, " mm", 8.0),
      T("leaf", "Blattgröße", "num", 3.0, 40.0, 0.5, 1, " mm", 11.0), *_stitch("triple", 1.4),
      T("color", "Rankenfarbe", "color", "#33691E"), T("accent", "Blattfarbe", "color", "#7CB342")],
     vine),
]
