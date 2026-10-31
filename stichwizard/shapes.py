"""Motiv-Bibliothek: fertige Formen als shapely-Geometrie (ca. 50 mm groß)."""
import math

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union


def _circle(x, y, r, res=48):
    return Point(x, y).buffer(r, resolution=res)


def heart():
    pts = []
    for i in range(200):
        t = 2 * math.pi * i / 200
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * 1.6, -y * 1.6))
    return Polygon(pts)


def star(n=5, r1=25, r2=10.5):
    pts = []
    for i in range(n * 2):
        r = r1 if i % 2 == 0 else r2
        a = math.pi * i / n - math.pi / 2
        pts.append((r * math.cos(a), r * math.sin(a)))
    return Polygon(pts)


def regular(n, r=25):
    return Polygon([(r * math.cos(2 * math.pi * i / n - math.pi / 2),
                     r * math.sin(2 * math.pi * i / n - math.pi / 2)) for i in range(n)])


def flower():
    petals = [_circle(14 * math.cos(2 * math.pi * i / 6), 14 * math.sin(2 * math.pi * i / 6), 11)
              for i in range(6)]
    return unary_union(petals + [_circle(0, 0, 12)]).difference(_circle(0, 0, 6))


def cloud():
    parts = [_circle(-14, 4, 11), _circle(0, -4, 15), _circle(15, 3, 11),
             box(-14, 4, 15, 15)]
    return unary_union(parts)


def moon():
    return _circle(0, 0, 24).difference(_circle(11, -6, 20))


def bolt():
    return Polygon([(4, -26), (-14, 4), (-2, 4), (-6, 26), (14, -6), (2, -6), (8, -26)])


def paw():
    pad = affinity.scale(_circle(0, 9, 12), 1.15, 0.9)
    toes = [affinity.scale(_circle(x, y, 5.5), 0.85, 1.1)
            for x, y in ((-15, -5), (-6, -15), (6, -15), (15, -5))]
    return unary_union([pad] + toes)


def leaf():
    pts = []
    for i in range(101):
        t = i / 100
        pts.append((-24 + 48 * t, -13 * math.sin(math.pi * t) ** 0.8 * (1 - 0.25 * t)))
    for i in range(101):
        t = 1 - i / 100
        pts.append((-24 + 48 * t, 9 * math.sin(math.pi * t) ** 0.9 * (1 - 0.25 * t)))
    lf = Polygon(pts).buffer(0)
    vein = LineString([(-20, -1), (0, -1.5), (20, -0.5)]).buffer(0.7)
    stem = LineString([(-23, 0), (-29, 4)]).buffer(1.4)
    return affinity.rotate(unary_union([lf.difference(vein), stem]), -30, origin=(0, 0))


def rounded_rect(w=50, h=34, r=7):
    return box(-w / 2 + r, -h / 2 + r, w / 2 - r, h / 2 - r).buffer(r, resolution=24)


def ring():
    return _circle(0, 0, 25).difference(_circle(0, 0, 17))


def drop():
    pts = []
    for i in range(160):
        t = 2 * math.pi * i / 160
        x = 18 * math.sin(t) * (1 - math.cos(t)) / 2 * 1.6
        y = -25 * math.cos(t)
        pts.append((x, y))
    return Polygon(pts).buffer(0)


def house():
    return unary_union([box(-18, -2, 18, 24), Polygon([(-25, 0), (0, -24), (25, 0)])]) \
        .difference(box(-5, 10, 5, 24)).difference(box(8, 4, 14, 10))


def butterfly():
    wings = []
    for sgn in (-1, 1):
        wings.append(affinity.rotate(affinity.scale(_circle(sgn * 13, -8, 12), 1, 0.85), sgn * 20, origin=(0, 0)))
        wings.append(affinity.scale(_circle(sgn * 10, 12, 8), 1, 1.1))
    body = affinity.scale(_circle(0, 0, 3), 1, 7)
    return unary_union(wings + [body])


def anchor():
    shaft = box(-2, -18, 2, 18)
    top = _circle(0, -21, 5).difference(_circle(0, -21, 2.5))
    bar = box(-11, -12, 11, -8)
    arc = _circle(0, 4, 20).difference(_circle(0, 4, 16)).intersection(box(-30, 10, 30, 40))
    tips = [Polygon([(-24, 8), (-15, 12), (-22, 16)]), Polygon([(24, 8), (15, 12), (22, 16)])]
    return unary_union([shaft, top, bar, arc] + tips)


MOTIFS = [
    ("Herz", heart), ("Stern", star), ("Kreis", lambda: _circle(0, 0, 25, 64)),
    ("Quadrat", lambda: box(-25, -25, 25, 25)), ("Abgerundet", rounded_rect),
    ("Dreieck", lambda: regular(3, 28)), ("Sechseck", lambda: regular(6)),
    ("Raute", lambda: affinity.scale(regular(4), 0.75, 1.0)), ("Blume", flower),
    ("Wolke", cloud), ("Mond", moon), ("Blitz", bolt), ("Pfote", paw),
    ("Blatt", leaf), ("Ring", ring), ("Tropfen", drop), ("Haus", house),
    ("Schmetterling", butterfly), ("Anker", anchor),
    ("Stern 8", lambda: star(8, 25, 15)),
]
