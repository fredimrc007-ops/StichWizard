"""Stammbaum-Assistent: Ahnentafel (Kind → Eltern → Großeltern → Urgroßeltern, Namen in
Rahmen mit Verbindungslinien) oder Familienbaum (Stamm, Äste, Namen in der Krone).
Namen mit »/« bekommen eine zweite, kleinere Zeile (z. B. Geburtsjahr).
Einträge im Format von templates.TEMPLATES."""
import math

from shapely.geometry import Polygon

from . import templates
from .model import EmbObject
from .ornaments import bezier, ring_points

T = lambda *a: a
FRAMES = [("Abgerundet", "rounded"), ("Oval", "oval"), ("Rechteck", "rect"), ("Ohne Rahmen", "none")]
LINES = [("Satinstich (schmal)", "satin"), ("Bohnenstich", "triple"), ("Steppstich", "run")]


def _names(text, limit):
    return [n.strip() for n in text.split(",")][:limit] if text.strip() else []


def _line(pts, p, name, closed=False, color=None):
    o = EmbObject("line", name)
    o.set_points(list(pts), closed=closed)
    st = p["lstitch"]
    o.border.update(type=st, color=color or p["lcolor"], width=1.4, stitch_len=2.2)
    if st == "triple":
        o.border["repeats"] = 1
    return o


def _label(name, p, size):
    """Schriftzüge eines Namens (zweite Zeile kleiner) – (objekte, breite, höhe) um (0, 0)."""
    lines = [s.strip() for s in name.split("/") if s.strip()][:2]
    objs, ws, hs = [], [], []
    for i, t in enumerate(lines):
        o = templates.text(t, size * (1.0 if i == 0 else 0.7), p["color"], p["font"])
        w, h = o.local_size()
        objs.append(o)
        ws.append(w)
        hs.append(h)
    gap = size * 0.3
    total = sum(hs) + gap * (len(hs) - 1)
    y = -total / 2
    for o, h in zip(objs, hs):
        o.y = y + h / 2
        y += h + gap
    return objs, max(ws or [0]), total


class _Person:
    def __init__(self, name, p, size):
        self.objs, self.w, self.h = _label(name, p, size)
        self.x = self.y = 0.0
        self.fw = self.fh = 0.0

    def place(self, x, y):
        for o in self.objs:
            o.x += x - self.x
            o.y += y - self.y
        self.x, self.y = x, y

    def top(self):
        return self.x, self.y - self.fh / 2

    def bottom(self):
        return self.x, self.y + self.fh / 2


def _frame(person, p):
    if p["frame"] == "none":
        return None
    w, h = person.fw, person.fh
    if p["frame"] == "oval":
        pts = ring_points("oval", w * 1.12, h * 1.25, res=120)
    else:
        pts = ring_points("rect", w, h, min(h * 0.45, 6.0) if p["frame"] == "rounded" else 0.0, 160)
    o = _line([(x + person.x, y + person.y) for x, y in pts], p, "Rahmen", True, p["fcolor"])
    o.border.update(type=p["fstitch"], width=1.6)
    return o


def _center(objs):
    xs, ys = [], []
    for o in objs:
        g = o.world_geometry()
        if g is not None and not g.is_empty:
            b = g.bounds
            xs += [b[0], b[2]]
            ys += [b[1], b[3]]
    if not xs:
        return objs
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for o in objs:
        o.x -= cx
        o.y -= cy
    return objs


# --------------------------------------------------------------- Ahnentafel
def pedigree(p):
    size = p["text_h"]
    gens = [_names(p["children"], 6), _names(p["parents"], 2), _names(p["grand"], 4),
            _names(p["great"], 8)]
    while len(gens) > 1 and not any(gens[-1]):
        gens.pop()
    G = len(gens) - 1
    pad_x, pad_y = size * 0.9, size * 0.6
    people = []                   # [gen][index] -> _Person oder None
    for g, names in enumerate(gens):
        slots = len(names) if g == 0 else 2 ** g
        row = []
        for i in range(slots):
            n = names[i] if i < len(names) else ""
            row.append(_Person(n, p, size) if n else None)
        people.append(row)
    fw = [max([q.w for q in row if q] or [size * 3]) + 2 * pad_x for row in people]
    fh = max(q.h for row in people for q in row if q) + 2 * pad_y
    for g, row in enumerate(people):
        for q in row:
            if q:
                q.fw, q.fh = fw[g], fh
    gap = p["hgap"]
    vstep = fh + p["vgap"]
    # x-Positionen: oberste Generation gleichmäßig, darunter jeweils mittig unter den Eltern
    xs = [[0.0] * len(row) for row in people]
    if G >= 1:
        n = 2 ** G
        step = max([fw[G] + gap] + [(fw[g] + gap) / 2 ** (G - g) for g in range(1, G + 1)])
        xs[G] = [(i - (n - 1) / 2) * step for i in range(n)]
        for g in range(G - 1, 0, -1):
            xs[g] = [(xs[g + 1][2 * i] + xs[g + 1][2 * i + 1]) / 2 for i in range(2 ** g)]
    kids = len(people[0])
    xs[0] = [(i - (kids - 1) / 2) * (fw[0] + gap) for i in range(kids)]
    out = []
    for g, row in enumerate(people):
        y = -g * vstep
        for i, q in enumerate(row):
            if q:
                q.place(xs[g][i], y)
                fr = _frame(q, p)
                if fr:
                    out.append(fr)
                out += q.objs
    # Verbindungslinien: Eltern → Querbalken → Kind (bzw. Kinder)
    for g in range(1, G + 1):
        for i in range(len(people[g - 1]) if g > 1 else 1):
            pa = [people[g][2 * i], people[g][2 * i + 1]] if g > 1 else people[1][:2]
            pa = [q for q in pa if q]
            kids_here = [people[g - 1][i]] if g > 1 else [q for q in people[0] if q]
            kids_here = [q for q in kids_here if q]
            if not pa or not kids_here:
                continue
            ymid = -g * vstep + fh / 2 + p["vgap"] / 2
            for q in pa:
                out.append(_line([q.bottom(), (q.x, ymid)], p, "Linie"))
            xm = sum(q.x for q in pa) / len(pa)
            if len(pa) == 2:
                out.append(_line([(pa[0].x, ymid), (pa[1].x, ymid)], p, "Linie"))
            if len(kids_here) == 1:
                k = kids_here[0]
                out.append(_line([(xm, ymid), (k.x, ymid), k.top()] if abs(k.x - xm) > 0.5
                                 else [(xm, ymid), k.top()], p, "Linie"))
            else:
                ylow = ymid + p["vgap"] / 4
                out.append(_line([(xm, ymid), (xm, ylow)], p, "Linie"))
                out.append(_line([(kids_here[0].x, ylow), (kids_here[-1].x, ylow)], p, "Linie"))
                for k in kids_here:
                    out.append(_line([(k.x, ylow), k.top()], p, "Linie"))
    if p["title"].strip():
        t = templates.text(p["title"].strip(), size * 1.5, p["tcolor"], p["font"])
        t.y = fh / 2 + p["vgap"] + size
        out.append(t)
    return _center(out)


# ------------------------------------------------------------- Familienbaum
def tree(p):
    size = p["text_h"]
    names = _names(p["names"], 16)
    H = p["height"]
    trunk_top = -H * 0.05
    base = H * 0.45
    tw = H * 0.09
    trunk = Polygon([(-tw, base), (-tw * 0.55, trunk_top), (tw * 0.55, trunk_top), (tw, base),
                     (tw * 2.2, base + tw * 0.6), (-tw * 2.2, base + tw * 0.6)])
    trunk = trunk.buffer(tw * 0.4, join_style=1).buffer(-tw * 0.4, join_style=1)
    t = EmbObject("shape", "Stamm")
    t.set_geometry(trunk)
    t.fill.update(type="tatami", color=p["trunk"], angle=90.0)
    t.border["type"] = "none"
    out = [t]
    n = len(names)
    labels = []
    for nm in names:
        q = _Person(nm, p, size)
        q.fw, q.fh = q.w + 2 * size * 0.9, q.h + 2 * size * 0.6
        labels.append(q)
    # Krone: zwei versetzte Reihen im gleichen Raster – unten m Namen, oben die übrigen genau
    # über den Lücken der unteren Reihe; ihre Äste laufen unter der unteren Reihe entlang und
    # dann senkrecht durch die Lücke nach oben (kreuzen keinen Namensrahmen)
    m = (n + 2) // 2 if n > 2 else n
    top = n - m
    cell = max([q.fw for q in labels] or [10.0]) + (size * 4.0 if p["leaves"] else size * 1.4)
    fh = max([q.fh for q in labels] or [10.0])
    row_step = fh + size * 1.6
    y0 = trunk_top - row_step * 0.8
    for j in range(m):
        labels[j].place((j - (m - 1) / 2) * cell, y0)
    gaps = [(j + 0.5 - (m - 1) / 2) * cell for j in range(m - 1)]
    first = (len(gaps) - top) // 2
    for j in range(top):
        labels[m + j].place(gaps[first + j], y0 - row_step)
    sx, sy = 0.0, trunk_top + tw
    low = y0 + fh / 2 + size * 0.9          # unter der unteren Reihe
    for k, q in enumerate(labels):          # Ast vom Stamm zur Namensplakette (sanft gebogen)
        ex, ey = q.bottom()
        if k < m:
            pts = bezier((sx, sy), (sx, (sy + ey) / 2), (ex, sy + (ey - sy) * 0.3), (ex, ey), 30)
        else:
            pts = bezier((sx, sy), (sx, (sy + low) / 2), (ex, sy + (low - sy) * 0.4), (ex, low), 30)
            pts.append((ex, ey))
        br = _line(pts, p, "Ast", color=p["trunk"])
        br.border.update(type="satin", width=2.2)
        out.append(br)
    if p["leaves"]:
        from .ornaments import motif as orn_motif
        for i, q in enumerate(labels):
            for s in (-1, 1):
                out.append(orn_motif("Blatt", size * 1.1, p["leaf"], q.x + s * (q.fw / 2 + size * 0.6),
                                     q.y + size * 0.5, rot=s * 35 + 180 * (s < 0)))
    for q in labels:
        fr = _frame(q, p)
        if fr:
            out.append(fr)
        out += q.objs
    if p["title"].strip():
        tt = templates.text(p["title"].strip(), size * 1.4, p["tcolor"], p["font"])
        tt.y = base + tw * 0.6 + size * 1.6
        out.append(tt)
    return _center(out)


# ------------------------------------------------------------------ Einträge
COMMON = [T("font", "Schrift", "choice", templates.FONT_CHOICES, "block"),
          T("text_h", "Schrifthöhe", "num", 5.0, 16.0, 0.5, 1, " mm", 6.0),
          T("frame", "Rahmen", "choice", FRAMES, "rounded"),
          T("fstitch", "Rahmen-Stichart", "choice", LINES, "triple"),
          T("lstitch", "Linien-Stichart", "choice", LINES, "triple"),
          T("color", "Namensfarbe", "color", "#3E2723"),
          T("fcolor", "Rahmenfarbe", "color", "#8D6E63"),
          T("lcolor", "Linienfarbe", "color", "#5D4037"),
          T("tcolor", "Titelfarbe", "color", "#2E7D32")]

FAMILY = [
    ("pedigree", "Ahnentafel", "Kind(er) unten, darüber Eltern, Großeltern und Urgroßeltern – "
     "jeweils mit Komma trennen (Vater, Mutter …). »Name / 1950« gibt eine zweite Zeile.",
     [T("title", "Titel", "text", "Unsere Familie"),
      T("children", "Kind(er)", "text", "Lena / 2015, Paul / 2018"),
      T("parents", "Eltern", "text", "Tom / 1984, Anna / 1986"),
      T("grand", "Großeltern", "text", "Karl, Erika, Hans, Ruth"),
      T("great", "Urgroßeltern (optional)", "text", ""),
      T("hgap", "Abstand nebeneinander", "num", 2.0, 30.0, 0.5, 1, " mm", 5.0),
      T("vgap", "Abstand der Generationen", "num", 6.0, 40.0, 0.5, 1, " mm", 12.0), *COMMON],
     pedigree),
    ("tree", "Familienbaum", "Baum mit Stamm und Ästen, die Namen hängen in der Krone (zwei "
     "versetzte Reihen) – bis zu 16 Namen, mit Komma getrennt; die ersten stehen unten.",
     [T("title", "Titel (am Stamm)", "text", "Familie Berger"),
      T("names", "Namen", "text", "Mama, Papa, Lena, Paul, Oma, Opa, Mia"),
      T("height", "Baumhöhe", "num", 80.0, 300.0, 1.0, 0, " mm", 150.0),
      T("leaves", "Blätter an den Namen", "check", True),
      T("trunk", "Stamm & Äste", "color", "#6D4C41"), T("leaf", "Blattfarbe", "color", "#7CB342"),
      *COMMON], tree),
]
