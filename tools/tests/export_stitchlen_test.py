"""Export darf breite Satinstiche nicht zerschneiden (ohne Oberfläche lauffähig).

  .venv/bin/python tools/tests/export_stitchlen_test.py

Stiche bis 12,1 mm müssen in allen Maschinenformaten unverändert ankommen, längere werden geteilt.
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pyembroidery as pe  # noqa: E402

from stichwizard import fileio  # noqa: E402
from stichwizard.engine import STITCH  # noqa: E402

FORMATS = ["pes", "dst", "jef", "exp", "vp3", "xxx", "u01"]


def longest_and_count(path):
    pat = pe.read(path)
    # Stiche und Sprünge: pyembroidery teilt zu lange Stiche in Sprünge + Stich auf
    pts = [(x, y) for x, y, c in pat.stitches if c & pe.COMMAND_MASK in (pe.STITCH, pe.JUMP)]
    longest = max(math.dist(a, b) for a, b in zip(pts, pts[1:])) / 10.0
    return longest, len(pts)


def run():
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        for width in (7.5, 8.0, 10.0, 12.0):
            # Satin-Zickzack: 10 Stiche der Breite »width« mm, 0,4 mm Vorschub
            sts = [[(i % 2) * width, i * 0.4, STITCH] for i in range(11)]
            pattern = fileio.build_pattern(None, [("#E53935", sts)])
            for ext in FORMATS:
                path = os.path.join(tmp, f"t.{ext}")
                fileio._write(pattern, path, ext)
                longest, n = longest_and_count(path)
                if longest < width - 0.15:
                    fails.append(f"{ext}: {width} mm geteilt (längster Schritt {longest:.2f} mm, {n} Nadelpositionen)")
        # zu lange Stiche müssen weiterhin aufgeteilt werden. VP3 ausgenommen: pyembroidery
        # schreibt den eingefügten Sprung dort nicht (liest sich als ein 15-mm-Stich zurück)
        sts = [[0, 0, STITCH], [15.0, 0, STITCH]]
        pattern = fileio.build_pattern(None, [("#000000", sts)])
        for ext in (e for e in FORMATS if e != "vp3"):
            path = os.path.join(tmp, f"long.{ext}")
            fileio._write(pattern, path, ext)
            longest, _ = longest_and_count(path)
            if longest > fileio.MAX_STITCH_MM + 0.15:
                fails.append(f"{ext}: 15-mm-Stich nicht geteilt (längster Schritt {longest:.2f} mm)")
    for f in fails:
        print("FEHLER", f)
    print("OK" if not fails else f"{len(fails)} Fehler")
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
