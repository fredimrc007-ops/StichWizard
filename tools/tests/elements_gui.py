"""Test: jede Fläche für sich fertig (Unterlage, Füllung, Rand), Sprünge nur zwischen Elementen."""
import math
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from shapely.geometry import Point, box
from stichwizard import engine
from stichwizard.engine import JUMP, STITCH, TRIM
from stichwizard.model import Document, EmbObject
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)

def inner_jumps(d):
    n = 0
    for o in d.objects:
        g = o.shaped_geometry()
        isl = list(engine.polygons_of(g.buffer(0.6)))
        for _, sts in o.stitch_blocks():
            last, gap = None, False
            for s in sts:
                if s[2] == STITCH:
                    if gap and last is not None:
                        ia = next((i for i, p in enumerate(isl) if p.contains(Point(last[:2]))), None)
                        ib = next((i for i, p in enumerate(isl) if p.contains(Point(s[:2]))), None)
                        n += ia is not None and ia == ib
                    last, gap = s, False
                elif s[2] == JUMP:
                    gap = True
    return n

def element_sequence(o):
    """Reihenfolge der Elemente, die die Nadel besucht (Insel-Index je Einstich, zusammengefasst)."""
    isl = list(engine.polygons_of(o.shaped_geometry().buffer(0.6)))
    seq = []
    for _, sts in o.stitch_blocks():
        for s in sts:
            if s[2] == STITCH:
                i = next((k for k, p in enumerate(isl) if p.contains(Point(s[:2]))), None)
                if i is not None and (not seq or seq[-1] != i):
                    seq.append(i)
    return seq, len(isl)

# Schrift mit Rand in Füllfarbe: jeder Buchstabe komplett, nie zurück
d = Document()
t = EmbObject("text"); t.text.update(text="Anna Bob", size=18)
t.border.update(type="run", color=t.fill["color"]); d.objects.append(t)
seq, n = element_sequence(t)
check(f"Schriftzug: {n} Buchstaben nacheinander, jeder nur einmal besucht ({seq})", len(seq) == len(set(seq)) == n)
check("Keine Sprünge innerhalb eines Buchstabens (auch nicht zum Lochrand)", inner_jumps(d) == 0)
check("Rand ist Teil des Elements (ein Farbblock)", len(t.stitch_blocks()) == 1)
# Rand in anderer Farbe: Füllungen zusammen, dann Ränder (weniger Farbwechsel)
t.border["color"] = "#000000"; t._skey = None
check("Rand in anderer Farbe: eigener Farbblock", len(t.stitch_blocks()) == 2)
# Mehrteilige Fläche mit Loch und Unterlage
d = Document()
o = EmbObject("shape")
o.set_geometry(Point(-25, 0).buffer(12).difference(Point(-25, 0).buffer(5)).union(box(5, -10, 30, 10)))
o.border.update(type="satin", width=2, color=o.fill["color"]); d.objects.append(o)
seq, n = element_sequence(o)
check(f"Ring + Rechteck: Elemente {seq}", seq == [0, 1] or seq == [1, 0])
check("Ring + Rechteck: kein Sprung innerhalb", inner_jumps(d) == 0)
# Ende nahe am nächsten Element: Sprung zwischen den Elementen kurz
sts = o.stitch_blocks()[0][1]
jl = []
last, gap = None, False
for s in sts:
    if s[2] == STITCH:
        if gap and last is not None:
            jl.append(math.dist(last[:2], s[:2]))
        last, gap = s, False
    elif s[2] == JUMP:
        gap = True
gap_between = o.shaped_geometry().geoms[0].distance(o.shaped_geometry().geoms[1]) if hasattr(o.shaped_geometry(), "geoms") else 0
check(f"Sprung zwischen den Elementen kurz ({[round(x, 1) for x in jl]} mm, Abstand {gap_between:.1f} mm)",
      len(jl) == 1 and jl[0] < gap_between + 6)
# Fadenschnitt-Grenze
for td, expect in ((0.0, True), (50.0, False)):
    engine.TRIM_DISTANCE = td; o._skey = None
    trims = sum(1 for s in o.stitch_blocks()[0][1] if s[2] == TRIM)
    check(f"Schnitt ab {td:g} mm: {'geschnitten' if trims else 'nicht geschnitten'}", (trims > 0) == expect)
engine.TRIM_DISTANCE = 3.0
print("ERGEBNIS:", sum(ok), "/", len(ok))
