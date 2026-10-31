"""Spirograph: Kurven wie mit dem Zahnrad-Zeichenspielzeug (Innen-/Außenrad), Rosetten und
Guilloche-Ringe – als Stepp-, Bohnen- oder schmale Satinlinie, auf Wunsch in mehreren
gedrehten Lagen mit zwei Farben. Einträge im Format von templates.TEMPLATES."""
import math

from .model import EmbObject

STITCHES = [("Steppstich", "run"), ("Bohnenstich", "triple"), ("Satinstich (schmal)", "satin")]


def hypotrochoid(R, r, d, res=24):
    """Rad (r Zähne) rollt innen im Ring (R Zähne); Stift im Abstand d (Anteil von r)."""
    R, r = int(R), int(r)
    if r >= R:
        r = R - 1
    turns = r // math.gcd(R, r)
    n = max(200, int(turns * res * 12))
    k = (R - r) / r
    dd = d * r
    return [((R - r) * math.cos(t) + dd * math.cos(k * t),
             (R - r) * math.sin(t) - dd * math.sin(k * t))
            for t in (2 * math.pi * turns * i / n for i in range(n))]


def epitrochoid(R, r, d, res=24):
    """Rad rollt außen am Ring."""
    R, r = int(R), int(r)
    turns = r // math.gcd(R, r)
    n = max(200, int(turns * res * 12))
    k = (R + r) / r
    dd = d * r
    return [((R + r) * math.cos(t) - dd * math.cos(k * t),
             (R + r) * math.sin(t) - dd * math.sin(k * t))
            for t in (2 * math.pi * turns * i / n for i in range(n))]


def rose(n, m, inner=0.0, res=400):
    """Rosette r = inner + (1 − inner)·|cos(n/m · θ)| – n Blätter (bei ungeradem n/m)."""
    n, m = int(n), int(m)
    g = math.gcd(n, m)
    n, m = n // g, m // g
    period = math.pi * m if (n * m) % 2 else 2 * math.pi * m
    N = int(res * m * 2)
    out = []
    for i in range(N):
        th = period * i / N
        rr = inner + (1 - inner) * math.cos(n / m * th)
        out.append((rr * math.cos(th), rr * math.sin(th)))
    return out


def guilloche(waves, depth, res=720):
    """Wellenring r = 1 + depth·sin(waves·θ)."""
    return [((1 + depth * math.sin(waves * th)) * math.cos(th),
             (1 + depth * math.sin(waves * th)) * math.sin(th))
            for th in (2 * math.pi * i / res for i in range(res))]


def _fit(pts, size):
    m = max(max(abs(x), abs(y)) for x, y in pts) or 1.0
    f = size / 2 / m
    return [(x * f, y * f) for x, y in pts]


def _rot(pts, a):
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [(x * ca - y * sa, x * sa + y * ca) for x, y in pts]


def _lines(pts, p, sym=1, name="Spirograph"):
    """Lagen: um 360/(sym·lagen) gedreht, Farben abwechselnd."""
    layers = int(p.get("layers", 1))
    out = []
    for k in range(layers):
        o = EmbObject("line", f"{name} {k + 1}" if layers > 1 else name)
        o.set_points(_rot(pts, k * 360.0 / (sym * layers)), closed=True)
        col = p["color"] if k % 2 == 0 or not p.get("two") else p["color2"]
        st = p["stitch"]
        o.border.update(type=st, color=col, width=p.get("line_w", 1.2), stitch_len=p["len"])
        if st == "triple":
            o.border["repeats"] = 1
        out.append(o)
    return out


def build_hypo(p):
    pts = _fit(hypotrochoid(p["R"], p["r"], p["d"] / 100.0), p["size"])
    return _lines(pts, p, int(p["R"]) // math.gcd(int(p["R"]), int(p["r"])) or 1)


def build_epi(p):
    pts = _fit(epitrochoid(p["R"], p["r"], p["d"] / 100.0), p["size"])
    return _lines(pts, p, int(p["R"]) // math.gcd(int(p["R"]), int(p["r"])) or 1)


def build_rose(p):
    pts = _fit(rose(p["n"], p["m"], p["inner"] / 100.0), p["size"])
    return _lines(pts, p, int(p["n"]), "Rosette")


def build_guilloche(p):
    out = []
    rings = int(p["rings"])
    for k in range(rings):
        sc = 1.0 - k * p["step"] / 100.0
        if sc <= 0.05:
            break
        pts = _fit(guilloche(p["waves"], p["depth"] / 100.0), p["size"])
        pts = _rot([(x * sc, y * sc) for x, y in pts], k * p["phase"])
        q = dict(p, layers=1, color=p["color"] if k % 2 == 0 or not p["two"] else p["color2"])
        out += _lines(pts, q, 1, f"Guilloche {k + 1}")
    return out


T = lambda *a: a


def _common(size=90.0, layers=1):
    return [T("size", "Durchmesser", "num", 15.0, 300.0, 1.0, 0, " mm", size),
            T("layers", "Lagen (gedreht)", "int", 1, 8, layers),
            T("stitch", "Stichart", "choice", STITCHES, "run"),
            T("len", "Stichlänge", "num", 1.0, 4.0, 0.1, 1, " mm", 2.0),
            T("line_w", "Breite (Satin)", "num", 0.6, 3.0, 0.1, 1, " mm", 1.2),
            T("two", "Zwei Farben abwechselnd", "check", True),
            T("color", "Farbe 1", "color", "#3949AB"), T("color2", "Farbe 2", "color", "#E91E63")]


SPIRO = [
    ("hypo", "Innenrad", "Ein Zahnrad rollt innen in einem Ring – klassische Spirograph-Blüten. "
     "Ring- und Radzähne bestimmen die Zahl der Schleifen, der Stiftabstand ihre Form.",
     [T("R", "Zähne Ring", "int", 20, 160, 96), T("r", "Zähne Rad", "int", 8, 150, 42),
      T("d", "Stiftabstand", "num", 10.0, 150.0, 1.0, 0, " %", 85.0), *_common()], build_hypo),
    ("epi", "Außenrad", "Ein Zahnrad rollt außen um einen Ring – Schleifen nach außen, "
     "wie Blütenkränze.",
     [T("R", "Zähne Ring", "int", 10, 160, 60), T("r", "Zähne Rad", "int", 4, 120, 22),
      T("d", "Stiftabstand", "num", 10.0, 150.0, 1.0, 0, " %", 100.0), *_common()], build_epi),
    ("rose", "Rosette", "Mathematische Rose: Blütenblätter aus einer einzigen Linie, "
     "mit mehreren Lagen gefüllt wie eine Mandala-Blüte.",
     [T("n", "Blätter (Zähler)", "int", 1, 15, 5), T("m", "Nenner", "int", 1, 9, 1),
      T("inner", "Innenkreis", "num", 0.0, 60.0, 1.0, 0, " %", 0.0), *_common(80.0, 3)],
     build_rose),
    ("guilloche", "Guilloche-Ring", "Wellenringe ineinander, jeweils leicht versetzt – wie die "
     "Muster auf Banknoten und Uhrzifferblättern.",
     [T("waves", "Wellen", "int", 3, 40, 16),
      T("depth", "Wellenhöhe", "num", 2.0, 40.0, 1.0, 0, " %", 9.0),
      T("rings", "Ringe", "int", 1, 12, 6),
      T("step", "Ringabstand", "num", 0.0, 20.0, 0.5, 1, " %", 0.0),
      T("phase", "Versatz je Ring", "num", 0.0, 30.0, 0.5, 1, "°", 3.75),
      *[c for c in _common(90.0) if c[0] != "layers"]], build_guilloche),
]
