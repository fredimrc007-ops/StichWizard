"""Test: Sprünge logisch verteilt – Reihenfolge als ganzer Weg geplant (tour.py) statt immer nur
zum nächstgelegenen Teil (gleichfarbige Objekte, Teilflächen einer Form, importierte Stickdateien)."""
import itertools
import math
import os
import random
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
from shapely.geometry import MultiPolygon, Point, box
from stichwizard import engine, help as shelp, tour
from stichwizard.engine import JUMP, STITCH, TRIM
from stichwizard.model import Document
from stichwizard.optimize import optimize_blocks
from stichwizard.templates import shape
from testdata import STICK_DIR
OUT = sys.argv[1]
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)


def jumps(sts):
    """Sprunglängen innerhalb einer Stichliste."""
    out, last, broken = [], None, False
    for x, y, f in sts:
        if f == STITCH:
            if broken and last is not None:
                out.append(math.hypot(x - last[0], y - last[1]))
            last, broken = (x, y), False
        else:
            broken = True
    return out


# ---- Wegplanung selbst: exakt (bis 9 Teile) und mit Bedingungen
rnd = random.Random(3)
exact = True
for t in range(25):
    n = rnd.randint(3, 7)
    P = [(rnd.random() * 60, rnd.random() * 60) for _ in range(n)]
    c = lambda i, j: math.dist(P[i], P[j])
    pred = [set() for _ in range(n)]
    pred[2].add(0)
    end = 1 if t % 2 else None
    seq = tour.order(n, c, pred=pred, end=end)
    L = lambda q: sum(c(a, b) for a, b in zip(q, q[1:]))
    allowed = [q for q in itertools.permutations(range(n))
               if q.index(0) < q.index(2) and (end is None or q[-1] == end)]
    exact &= tuple(seq) in allowed and abs(L(seq) - min(map(L, allowed))) < 1e-6
check("Kürzester Gesamtweg exakt gefunden (mit »vorher sticken« und festem letzten Teil)", exact)
P = [(rnd.random() * 100, rnd.random() * 100) for _ in range(60)]
c = lambda i, j: math.dist(P[i], P[j])
seq = tour.order(60, c)
L = sum(c(a, b) for a, b in zip(seq, seq[1:]))
check(f"Viele Teile: Weg {sum(c(i, i + 1) for i in range(59)):.0f} → {L:.0f} mm",
      sorted(seq) == list(range(60)) and L < 0.4 * sum(c(i, i + 1) for i in range(59)))
check("Widersprüchliche Bedingungen: kein Ergebnis statt falscher Reihenfolge",
      tour.order(3, c, pred=[{1}, {0}, set()]) is None)

# ---- Teilflächen einer Form: kein liegengebliebenes Teil (Nächster-Nachbar wäre 0→6→16→-8)
sq = lambda x: box(x - 1, -1, x + 1, 1)
parts = [sq(0), sq(6), sq(-8), sq(16)]
plan = engine._planned(parts, (0, 0))
xs = [round(p.centroid.x) for p in plan]
check(f"Teilflächen geplant {xs} statt [0, 6, 16, -8]", xs == [0, -8, 6, 16])
o = shape(MultiPolygon(parts), "#1565C0")
o.fill["start"] = [0.0, 0.0]
o.fill["underlay"] = False
js = jumps(o.stitch_blocks()[0][1])
planned = engine._planned
def nearest_only(parts, pos, last=None):          # bisheriges Verfahren zum Vergleich
    rest, out = list(parts), []
    while rest:
        ref = Point(pos) if not out else out[-1]
        out.append(rest.pop(min(range(len(rest)), key=lambda k: rest[k].distance(ref))))
    return out + ([last] if last is not None else [])
engine._planned = nearest_only
o2 = shape(MultiPolygon(parts), "#1565C0")
o2.fill.update(start=[0.0, 0.0], underlay=False)
old_js = jumps(o2.stitch_blocks()[0][1])
engine._planned = planned
check(f"Form mit 4 Teilen: Sprünge zusammen {sum(old_js):.0f} → {sum(js):.0f} mm",
      len(js) == 3 and sum(js) < sum(old_js) - 3)
left = engine._planned([sq(20), sq(0), sq(10)], None)
ends = engine._planned([sq(20), sq(0), sq(10)], None, last=sq(-10))
check("Ohne Startpunkt links beginnen, Endpunkt-Teil zuletzt",
      [round(p.centroid.x) for p in left] == [0, 10, 20] and
      [round(p.centroid.x) for p in ends] == [20, 10, 0, -10])

# ---- Gleichfarbige Objekte: oben → Mitte → unten statt Mitte → oben → quer nach unten
doc = Document()
mid = shape(box(-8, -4, 8, 4), "#1565C0", name="Mitte")
top = shape(box(-10, -26, 10, -18), "#1565C0", name="Oben")
bottom = shape(box(-25, 18, 25, 26), "#1565C0", name="Unten")
red = shape(box(30, -12, 40, -2), "#C62828", name="Rot")
doc.objects = [red, mid, top, bottom]       # bisher: Mitte zuerst (erstes in der Liste)
blocks = doc.machine_blocks()
names = [doc.find(oid).name for oid, _, c in doc.last_order if c == "#1565C0"]
blue = next(s for c, s in blocks if c == "#1565C0")
check(f"Gleiche Farbe als ganzer Weg: {names} (vorher Mitte zuerst)",
      names in (["Oben", "Mitte", "Unten"], ["Unten", "Mitte", "Oben"]))
check(f"Kein Sprung quer übers Motiv (längster {max(jumps(blue)):.0f} mm)", max(jumps(blue)) < 30)
doc.order_mode = "manual"
doc.machine_blocks()
check("»Von Hand«: Reihenfolge der Objektliste bleibt",
      [doc.find(oid).name for oid, _, c in doc.last_order if c == "#1565C0"] == ["Mitte", "Oben", "Unten"])

# ---- Importierte Stickdatei: Teile neu geordnet, kein Fadenschnitt am Farbwechsel
def run(x):
    return [(x, 0.0, JUMP)] + [(x + k * 0.4, 0.0, STITCH) for k in range(4)]
far = [(100.0, 0.0, JUMP), (100.0, 0.0, STITCH), (101.0, 0.0, STITCH)]
mixed = sum((run(x) for x in (0, 6, -8, 16)), [])
res, st = optimize_blocks([("#C62828", far), ("#1565C0", mixed)])
blue = res[1][1]
L = sum(jumps(blue))
check(f"Stickdatei: Sprungwege {sum(jumps(mixed)):.0f} → {L:.0f} mm bei {st['jumps_after']} Sprüngen",
      st["jumps_after"] == 3 and L < 30)
head = blue[:next(k for k, p in enumerate(blue) if p[2] == STITCH)]
check("Kein zusätzlicher Fadenschnitt beim Farbwechsel", not any(p[2] == TRIM for p in head))

# ---- Hilfe
check("Hilfe erklärt die geplante Reihenfolge", "ganzer Weg" in shelp.GUIDE)

# ---- echtes Projekt (nur lesend), falls vorhanden: »Des« → »is« → »Passt!«
real = os.path.join(STICK_DIR, "Stickdateien", "Des is Passt-Kappe 1.0.stickproj")
if os.path.exists(real):
    d = Document()
    d.load_json(open(real, encoding="utf-8").read())
    bl = d.machine_blocks()
    text = [d.find(oid) for oid, _, c in d.last_order if c.upper() == "#1565C0"]
    ys = [t.world_geometry().centroid.y for t in text]
    longest = max(j for _, s in bl for j in jumps(s))
    check(f"Kappe: Textzeilen von oben nach unten, längster Sprung {longest:.0f} mm",
          ys == sorted(ys) and longest < 30)
print("ERGEBNIS:", sum(ok), "/", len(ok))
