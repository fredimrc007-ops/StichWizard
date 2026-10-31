"""Zugausgleich bei Füllungen nur in Stichrichtung (ohne Oberfläche lauffähig).

  .venv/bin/python tools/tests/pull_comp_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shapely import affinity  # noqa: E402
from shapely.geometry import Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from stichwizard import engine  # noqa: E402
from stichwizard.engine import STITCH  # noqa: E402
from stichwizard.model import DEFAULT_FILL  # noqa: E402


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


def run():
    fails = []
    rect = box(0, 0, 20, 10)

    # 1. Stichrichtung waagrecht: nur links/rechts länger, oben/unten unverändert
    b = engine.pull_expand(rect, 0.3, 0).bounds
    if not all(near(x, y) for x, y in zip(b, (-0.3, 0, 20.3, 10))):
        fails.append(f"0°: Umriss {b}, erwartet (-0.3, 0, 20.3, 10)")
    # 2. Stichrichtung senkrecht: nur oben/unten
    b = engine.pull_expand(rect, 0.3, 90).bounds
    if not all(near(x, y) for x, y in zip(b, (0, -0.3, 20, 10.3))):
        fails.append(f"90°: Umriss {b}, erwartet (0, -0.3, 20, 10.3)")

    # 3. schräg, mit Loch: deckt sich mit vielen fein verschobenen Kopien (Minkowski-Summe)
    shape = Polygon([(0, 0), (12, 2), (9, 11), (2, 8)], [[(4, 4), (7, 4.5), (6, 7)]])
    for angle in (0, 30, 45, 117):
        got = engine.pull_expand(shape, 0.4, angle)
        dx, dy = affinity.rotate(Polygon([(1, 0), (0, 0), (0, 1)]), angle, origin=(0, 0)).exterior.coords[0]
        ref = unary_union([affinity.translate(shape, dx * t * 0.4 / 50, dy * t * 0.4 / 50)
                           for t in range(-50, 51)])
        diff = got.symmetric_difference(ref).area
        if diff > 0.02:
            fails.append(f"{angle}°: weicht um {diff:.3f} mm² von der Minkowski-Summe ab")
        if not got.is_valid:
            fails.append(f"{angle}°: ungültige Fläche")

    # 4. ganze Füllung: Stiche reichen in Stichrichtung über die Form, quer nicht
    fill = dict(DEFAULT_FILL, type="tatami", angle=0.0, pull=0.3, underlay=False)
    sts = engine.fill_with_underlay(rect, fill)
    xs = [p[0] for p in sts if p[2] == STITCH]
    ys = [p[1] for p in sts if p[2] == STITCH]
    if not (min(xs) < -0.2 and max(xs) > 20.2):
        fails.append(f"Füllung nicht in Stichrichtung verlängert: x {min(xs):.2f} … {max(xs):.2f}")
    if min(ys) < -0.05 or max(ys) > 10.05:
        fails.append(f"Füllung quer zur Stichrichtung gewachsen: y {min(ys):.2f} … {max(ys):.2f}")

    # 5. ohne Zugausgleich bleibt die Form, wie sie ist
    if not engine.pull_expand(rect, 0, 33).equals(rect):
        fails.append("pull=0 verändert die Form")
    for f in fails:
        print("FEHLER", f)
    print("OK" if not fails else f"{len(fails)} Fehler")
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
