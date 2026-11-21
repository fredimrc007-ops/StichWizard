"""Test: automatischer Ein-/Ausstieg (»Closest Join«), Verbindungen unter dem nächsten Objekt,
Stickschrift rückwärts und Kappen-Reihenfolge von der Mitte nach außen."""
import math
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
from shapely.geometry import Point
from stichwizard import embfont, engine, templates
from stichwizard.engine import STITCH
from stichwizard.model import Document, scan_gaps
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)


def gaps(doc):
    g = [x for _, s in doc.machine_blocks() for x in scan_gaps(s)]
    return len(g), sum(x[4] for x in g), sum(math.dist(x[2], x[3]) for x in g)


def chain(aj):
    d = Document()
    d.auto_join = aj
    for k in range(6):          # Kette sich überlappender Kreise in einer Farbe
        o = templates.shape(Point(0, 0).buffer(8), "#AA0000", None, name=f"K{k}")
        o.x, o.y = k * 13, (k % 2) * 6
        d.objects.append(o)
    return d


old, new = gaps(chain(False)), gaps(chain(True))
check(f"Überlappende Kreise: Sprünge {old[0]} → {new[0]}, Schnitte {old[1]} → {new[1]}",
      new[0] == 0 and new[1] == 0 and old[0] >= 4)

# verdeckte Verbindung liegt innerhalb der gleichfarbigen Kreise
d = chain(True)
blk = d.machine_blocks()
area = engine.merge_union([o.world_geometry() for o in d.objects]).buffer(0.5)
pts = [s for _, b in blk for s in b if s[2] == STITCH]
check("Alle Stiche (auch Verbindungen) liegen auf den Formen",
      all(area.contains(Point(p[:2])) for p in pts))

# stabil: zweiter Aufruf rechnet nichts neu
keys = [o._skey for o in d.objects]
d.machine_blocks()
check("Zweiter Durchlauf ohne Neuberechnung", keys == [o._skey for o in d.objects])

# verstreute Punkte: kürzere Sprünge
def dots(aj):
    d = Document()
    d.auto_join = aj
    for k in range(10):
        o = templates.shape(Point(0, 0).buffer(6 + k % 3 * 2), "#1565C0", None, name=f"P{k}")
        o.x, o.y = -45 + (k % 5) * 22, -15 + (k // 5) * 30
        d.objects.append(o)
    return d
a, b = gaps(dots(False)), gaps(dots(True))
check(f"Getrennte Punkte: Sprunglänge {a[2]:.0f} → {b[2]:.0f} mm", b[2] < a[2] * 0.6 and b[0] <= a[0])

# eigener Startpunkt geht vor
d = chain(True)
d.objects[2].fill["start"] = [0.0, 7.5]
blk = d.machine_blocks()
o = d.objects[2]
first = next(s for s in o.world_blocks()[0][1] if s[2] == STITCH)
check("Eigener Startpunkt bleibt", math.dist(first[:2], (o.x, o.y + 7.5)) < 2.0)

# Stickschrift rückwärts, wenn die Nadel vom Textende kommt
fid = next((f for f in ("geneva_simple", "barstitch_bold") if embfont.exists(f)), None)
if fid:
    d = Document()
    t1 = templates.text("ABC", 12, "#0D47A1", x=0, y=0)
    t1.text["embfont"] = fid
    t2 = templates.text("DEF", 12, "#0D47A1", x=0, y=20)
    t2.text["embfont"] = fid
    d.objects = [t1, t2]
    d.color_sort = False
    d.machine_blocks()
    s1 = [s for s in t1.world_blocks()[0][1] if s[2] == STITCH]
    s2 = [s for s in t2.world_blocks()[0][1] if s[2] == STITCH]
    check("Zweite Zeile beginnt am nahen Ende (rückwärts)",
          math.dist(s1[-1][:2], s2[0][:2]) < 15 and s2[0][0] > s2[-1][0])
else:
    check("Stickschrift vorhanden", False)

# Kappe: von der Mitte nach außen, von unten nach oben
d = Document()
d.fabric_type = "cap"
engine.FABRIC = "cap"
for k, x in enumerate((-40, -20, 0, 20, 40)):
    o = templates.shape(Point(0, 0).buffer(6), "#222222", None, name=f"C{k}")
    o.x, o.y = x, 0
    d.objects.append(o)
d.machine_blocks()
order = [oid for oid, _, _ in d.last_order]
names = [d.find(i).name for i in order]
dist_c = [abs(d.find(i).x) for i in order]
check(f"Kappe: Reihenfolge von der Mitte nach außen ({' '.join(names)})",
      dist_c == sorted(dist_c))
o = d.objects[0]
st = [s for s in o.world_blocks()[0][1] if s[2] == STITCH]
check("Kappe: Teil beginnt unten bzw. zur Mitte hin", st[0][1] > o.y - 1 and st[0][0] > o.x - 1)
d.cap_center = False
d.machine_blocks()
check("Kappe: abschaltbar (dann kürzester Weg)", [d.find(i).name for i, _, _ in d.last_order] != names)
engine.FABRIC = "standard"

# Speichern/Laden
d = Document()
d.auto_join, d.cap_center = False, False
e = Document()
e.load_json(d.to_json())
check("Einstellungen werden gespeichert", e.auto_join is False and e.cap_center is False)
e.load_json(Document().to_json())
check("Standard: an", e.auto_join and e.cap_center)

print(f"{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
