"""Test (1.28): Quiltblock-Assistent (Echo, Stippling, Kreuzschraffur, Konturlinien, Spirale,
um eine Auswahl) und Stammbaum-Assistent (Ahnentafel, Familienbaum)."""
import math
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
QDialog.exec = lambda self: 1
from shapely.geometry import LineString, Point
from stichwizard import engine, familytree, quilt, templates
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)


def stitched(objs):
    return [p for o in objs for _, b in o.world_blocks() for p in b if p[2] == engine.STITCH]


def world_lines(o):
    return [o.to_world(*q) for q in o.points]


# ---- Quiltblock
tp = quilt.quilt_templates()
bad = []
for key, *_ in tp:
    objs = templates.build(key, None, tp)
    pts = stitched(objs)
    d = Document(); d.objects = objs
    st = d.stats()
    block = quilt.block_geometry(templates.defaults(next(t for t in tp if t[0] == key)))
    outside = sum(1 for x, y, _ in pts if not block.buffer(0.6).contains(Point(x, y)))
    if len(pts) < 500 or outside or abs(st["width"] - 120) > 1.5:
        bad.append(f"{key}:{len(pts)}/{outside} außen/{st['width']:.0f}")
check(f"Alle Quiltmuster sticken im 120-mm-Block {bad}", not bad)
ul = [o for o in templates.build("stipple", None, tp) if o.kind == "shape"]
check("Quiltflächen ohne Unterlage und ohne Zugausgleich",
      ul and all(not o.fill["underlay"] and o.fill["pull"] == 0 for o in ul))
heart = templates.motif("Herz", 54, "#000").world_geometry()
for key in ("echo", "hatch", "spiral"):
    objs = templates.build(key, None, tp)
    qs = [o for o in objs if o.name not in ("Herz", "Blockrand")]
    near = min(heart.exterior.distance(Point(x, y)) for x, y, _ in stitched(qs))
    check(f"{key}: Quiltlinien halten Abstand zum Motiv ({near:.1f} mm)", near > 2.4)
hl = [o for o in templates.build("hatch", None, tp) if o.name.endswith("Schraffur")]
seglen = [math.dist(a, b) for o in hl for a, b in zip(world_lines(o), world_lines(o)[1:])]
check(f"Kreuzschraffur: wenige durchgehende Wege ({len(hl)}) statt vieler Stücke", len(hl) < 25)
sp = [o for o in templates.build("spiral", None, tp) if o.name.endswith("Spirale")]
first = world_lines(sp[0])[0] if sp else (99, 99)
check("Spirale beginnt nahe der Blockmitte", min(math.dist(world_lines(o)[0], (0, 0)) for o in sp) < 40)
ech = [o for o in templates.build("echo", {"count": 3}, tp) if o.name.startswith("Echo")]
check(f"Echo: genau 3 Ringe ({len(ech)})", len(ech) == 3 and all(o.closed for o in ech))
circ = templates.build("echo", {"form": "circle", "motif": "none"}, tp)
check("Ohne Motiv: Konturlinien vom Rand nach innen", any(o.kind == "shape" and
                                                         o.fill["type"] == "ripple" for o in circ))
# um eine Auswahl
star = templates.motif("Stern", 50, "#FDD835", 30, 20)
w.doc.objects = [star]; w.sync_items(); w.commit()
w.scene.clearSelection(); w.items[star.id].setSelected(True); QTest.qWait(5)
w.open_quilt()
objs = list(w.doc.objects)
new = [o for o in objs if o is not star]
b = Document(); b.objects = new
bb = b.stats()["bounds"]
check(f"Um die Auswahl: Stern bleibt, Block um ihn herum ({len(new)} Teile)",
      star in objs and new and abs((bb[0] + bb[2]) / 2 - 30) < 3 and abs((bb[1] + bb[3]) / 2 - 20) < 3)
check("Um die Auswahl: nichts über dem Stern gequiltet",
      all(not star.world_geometry().buffer(1.5).contains(Point(x, y)) for x, y, _ in stitched(new)))
w.undo(); QTest.qWait(5)
check("Quiltblock: Rückgängig", [o.id for o in w.doc.objects] == [star.id])

# ---- Stammbaum: Ahnentafel
objs = templates.build("pedigree", None, familytree.FAMILY)
texts = [o for o in objs if o.kind == "text"]
names = " ".join(o.text["text"] for o in texts)
check("Ahnentafel: alle Namen und Jahre",
      all(n in names for n in ("Lena", "Paul", "Tom", "Anna", "Karl", "Ruth", "1984", "2018")))
by = {o.text["text"]: o for o in texts}
check("Generationen übereinander: Großeltern > Eltern > Kinder",
      by["Karl"].y < by["Tom"].y < by["Lena"].y)
check("Eltern mittig über ihren Kindern",
      abs((by["Tom"].x + by["Anna"].x) / 2 - (by["Lena"].x + by["Paul"].x) / 2) < 0.5)
check("Großeltern mittig über ihrem Kind (Vater)",
      abs((by["Karl"].x + by["Erika"].x) / 2 - by["Tom"].x) < 0.5)
frames = [o for o in objs if o.name == "Rahmen"]
fg = [o.world_geometry().convex_hull for o in frames]
overl = sum(1 for i in range(len(fg)) for j in range(i + 1, len(fg)) if fg[i].intersects(fg[j]))
check(f"Ahnentafel: {len(frames)} Rahmen, keiner überlappt ({overl})", len(frames) == 8 and not overl)
g3 = templates.build("pedigree", {"great": "A, B, C, D, E, F, G, H"}, familytree.FAMILY)
g3t = {o.text["text"]: o for o in g3 if o.kind == "text"}
check("Mit Urgroßeltern: 4. Generation ganz oben", g3t["A"].y < g3t["Karl"].y)
# Familienbaum
objs = templates.build("tree", None, familytree.FAMILY)
frames = [o for o in objs if o.name == "Rahmen"]
fg = [o.world_geometry().convex_hull for o in frames]
overl = sum(1 for i in range(len(fg)) for j in range(i + 1, len(fg)) if fg[i].intersects(fg[j]))
check(f"Familienbaum: 7 Namensrahmen ohne Überlappung ({overl})", len(frames) == 7 and not overl)
branches = [o for o in objs if o.name == "Ast"]
cross = sum(1 for br in branches for f in frames
            if LineString(world_lines(br)).buffer(1.0).intersection(f.world_geometry().convex_hull
                                                                    .buffer(-1.5)).area > 0.5)
check(f"Äste kreuzen keinen fremden Namensrahmen ({cross})", cross == 0)
check("Stamm gefüllt, Titel vorhanden", any(o.name == "Stamm" and o.fill["type"] == "tatami"
                                           for o in objs) and any(o.kind == "text" and
                                           o.text["text"] == "Familie Berger" for o in objs))
w.doc.objects = []; w.sync_items(); w.commit()
w.open_family()
check("Stammbaum einfügen (als Gruppe)", len(w.doc.objects) > 20 and
      len({o.group for o in w.doc.objects}) == 1)
w.grab().save(os.path.join(OUT, "quilt.png"))
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
