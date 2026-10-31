"""Schrift-Effekte: Hüllformen (Envelopes) und einzeln verschobene Buchstaben.

Hüllformen verbiegen einen ganzen Schriftzug in eine Form – Bogen oben/unten, Fass, Brücke,
Welle, Wimpel … wie »Envelope« in Hatch/Wilcom oder PE-Design. Die Verformung wird auf die
Konturen bzw. Satin-Schienen angewandt, die Stiche danach neu berechnet – die Dichte bleibt also
richtig, auch wenn Buchstaben breiter oder schmaler werden.
"""
import math

# (Schlüssel, Name, Beschreibung)
ENVELOPES = [
    ("none", "Keine", "Schriftzug gerade"),
    ("arch_top", "Bogen oben", "Oberkante wölbt sich nach oben, Unterkante bleibt gerade"),
    ("arch_bottom", "Bogen unten", "Unterkante wölbt sich nach unten"),
    ("barrel", "Fass", "Oben nach oben, unten nach unten – Mitte am höchsten"),
    ("bridge", "Brücke", "Oberkante gerade, Unterkante als Bogen nach oben"),
    ("arch_both", "Doppelbogen", "Ober- und Unterkante als Bogen nach oben (wie auf einer Kappe)"),
    ("pinch", "Taille", "Mitte eingeschnürt, Enden hoch"),
    ("diamond", "Raute", "Spitz zur Mitte hin höher"),
    ("wave", "Welle", "S-förmig auf und ab"),
    ("pennant", "Wimpel", "Wird nach rechts niedriger"),
    ("pennant_l", "Wimpel links", "Wird nach links niedriger"),
    ("slant", "Rampe", "Steigt nach rechts an, Buchstaben bleiben senkrecht"),
]
ENVELOPE_KEYS = [k for k, _, _ in ENVELOPES]


def densify(pts, step=0.8):
    """Polygonzug mit Zwischenpunkten (max. Abstand step), damit gerade Strecken mitbiegen."""
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = int(d / step)
        for k in range(1, n + 1):
            t = k / (n + 1)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        out.append(b)
    return out


def make_warp(kind, amount, bounds):
    """Abbildung (x, y) -> (x, y) für eine Hüllform. amount: Stärke 0 … 1 (Anteil der Höhe),
    bounds: (minx, miny, maxx, maxy) des Schriftzugs. y zeigt nach unten (wie im Programm)."""
    if not kind or kind == "none" or not amount:
        return None
    minx, miny, maxx, maxy = bounds
    W = max(maxx - minx, 1e-6)
    H = max(maxy - miny, 1e-6)
    cx = (minx + maxx) / 2
    a = float(amount) * H

    def uv(x, y):
        return (x - cx) / (W / 2), (y - miny) / H        # u: -1 … 1, v: 0 oben … 1 unten

    def bump(u):
        return max(0.0, 1.0 - u * u)

    if kind == "arch_top":
        return lambda x, y: (x, y - a * bump(uv(x, y)[0]) * (1 - uv(x, y)[1]))
    if kind == "arch_bottom":
        return lambda x, y: (x, y + a * bump(uv(x, y)[0]) * uv(x, y)[1])
    if kind == "barrel":
        return lambda x, y: (x, y + a * bump(uv(x, y)[0]) * (uv(x, y)[1] - (1 - uv(x, y)[1])) * 0.5)
    if kind == "bridge":
        return lambda x, y: (x, y - a * bump(uv(x, y)[0]) * uv(x, y)[1])
    if kind == "arch_both":
        return lambda x, y: (x, y - a * bump(uv(x, y)[0]))
    if kind == "pinch":
        return lambda x, y: (x, y + a * bump(uv(x, y)[0]) * ((1 - uv(x, y)[1]) - uv(x, y)[1]) * 0.5)
    if kind == "diamond":
        def f(x, y):
            u, v = uv(x, y)
            k = max(0.0, 1.0 - abs(u))
            return x, y + a * k * (v - (1 - v)) * 0.5
        return f
    if kind == "wave":
        return lambda x, y: (x, y - a * 0.5 * math.sin(math.pi * uv(x, y)[0]))
    if kind in ("pennant", "pennant_l"):
        cy = (miny + maxy) / 2

        def f(x, y):
            u = uv(x, y)[0]
            t = (u + 1) / 2 if kind == "pennant" else (1 - u) / 2      # 0 … 1 zur kleinen Seite
            k = 1.0 - min(0.9, float(amount)) * t
            return x, cy + (y - cy) * k
        return f
    if kind == "slant":
        return lambda x, y: (x, y - a * uv(x, y)[0] * 0.5)
    return None


def warp_points(pts, warp, step=0.8, dense=True):
    if warp is None:
        return list(pts)
    src = densify(pts, step) if dense else pts
    return [warp(x, y) for x, y in src]


def warp_geometry(geom, warp, step=0.6):
    """Shapely-Geometrie verformen (Kanten werden vorher unterteilt)."""
    if warp is None or geom is None or geom.is_empty:
        return geom
    from shapely import segmentize
    from shapely.ops import transform
    g = segmentize(geom, step)
    return transform(lambda xs, ys, zs=None: tuple(zip(*[warp(x, y) for x, y in zip(xs, ys)])),
                     g).buffer(0)


# ---------------------------------------------------------------- einzelne Buchstaben
def letter_map(letters):
    """Text-Eintrag »letters« ({"3": [dx, dy, drehung, größe%]} oder Liste) -> {index: (…)}."""
    out = {}
    if isinstance(letters, dict):
        items = letters.items()
    elif isinstance(letters, (list, tuple)):
        items = ((it[0], it[1:]) for it in letters if len(it) >= 5)
    else:
        return out
    for k, v in items:
        try:
            dx, dy, rot, sc = (float(v[0]), float(v[1]), float(v[2]), float(v[3]))
        except (TypeError, ValueError, IndexError):
            continue
        if dx or dy or rot or sc != 100.0:
            out[int(k)] = (dx, dy, rot, sc)
    return out


def letters_key(letters):
    """Hashbare Form für Zwischenspeicher (lru_cache)."""
    return tuple(sorted((i,) + tuple(v) for i, v in letter_map(letters).items()))


def letter_transform(adj, center):
    """Abbildung für einen Buchstaben: um seine Mitte drehen/skalieren, dann verschieben."""
    dx, dy, rot, sc = adj
    cx, cy = center
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    k = sc / 100.0

    def f(x, y):
        lx, ly = (x - cx) * k, (y - cy) * k
        return cx + lx * c - ly * s + dx, cy + lx * s + ly * c + dy
    return f
