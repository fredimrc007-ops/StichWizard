"""Test (1.24): Reiter »Verzieren« – Encore, Rahmen & Schnörkel, Strass & Perlen samt
Schablone (SVG/PDF), Speichern/Laden, Export und Rückgängig."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
QDialog.exec = lambda self: 1           # Vorschau-Fenster sofort mit der ersten Einstellung bestätigen
import pyembroidery as pe
from stichwizard import encore, engine, fileio, ornaments, stones, templates
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
from stichwizard.render import render_document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)


def stitches(objs):
    return sum(1 for o in objs for _, b in o.stitch_blocks() for s in b if s[2] == engine.STITCH)


def setdoc(*objs):
    w.doc.objects = list(objs)
    w.sync_items([o.id for o in objs])
    w.commit()                          # Ausgangszustand für Rückgängig
    QTest.qWait(5)


def select(*objs):
    w.scene.clearSelection()
    for o in objs:
        w.items[o.id].setSelected(True)
    QTest.qWait(5)


# ---- Reiter
tabs = [w.ribbon.tabText(i) for i in range(w.ribbon.count())]
check(f"Reiter »Verzieren« vorhanden {tabs}", "Verzieren" in tabs)

# ---- Rahmen & Schnörkel: alle Einträge bauen und sticken
bad = []
for key, title, *_ in ornaments.ORNAMENTS:
    objs = templates.build(key, None, ornaments.ORNAMENTS)
    d = Document(); d.objects = objs
    st = d.stats()
    if stitches(objs) < 150 or not (10 < st["width"] < 300):
        bad.append(f"{key}:{stitches(objs)}/{st['width']:.0f}")
check(f"Alle {len(ornaments.ORNAMENTS)} Rahmen/Schnörkel sticken sinnvoll {bad}", not bad)
setdoc()
w.open_ornaments()
objs = list(w.doc.objects)
check("Rahmen einfügen: als eine Gruppe", len(objs) > 1 and len({o.group for o in objs}) == 1)
w.undo(); QTest.qWait(5)
check("Rahmen: Rückgängig entfernt alles", not w.doc.objects)

# ---- Encore
m = templates.motif("Blatt", 12, "#43A047", 0, 0)
setdoc(m)
select(m)
w.open_encore()
objs = list(w.doc.objects)
check(f"Encore Kreis: 8 Kopien statt des Originals ({len(objs)})",
      len(objs) == 8 and m.id not in {o.id for o in objs})
b = encore.bounds(objs)
check(f"Encore Kreis: um die alte Mitte angeordnet {b}", abs((b[0] + b[2]) / 2) < 2 and
      abs((b[1] + b[3]) / 2) < 2)
check("Encore: Kopien als Gruppe", len({o.group for o in objs}) == 1 and objs[0].group)
w.undo(); QTest.qWait(5)
check("Encore: Rückgängig bringt das Original zurück",
      [o.id for o in w.doc.objects] == [m.id])
tpls, motif = encore.encore_templates([m])
bad = [k for k, *_ in tpls if len(templates.build(k, None, tpls)) < 2]
check(f"Encore: alle Modi erzeugen Kopien {bad}", not bad)
ln = EmbObject("line", "Pfad"); ln.set_points([(-50, 20), (0, -10), (50, 20)])
m2 = templates.motif("Herz", 8, "#E53935", 0, 30)
setdoc(ln, m2)
select(ln, m2)
w.open_encore()
objs = list(w.doc.objects)
check(f"Encore entlang Linie: Linie bleibt, 7 Herzen ({len(objs)})",
      ln in objs and len(objs) == 8 and m2 not in objs)
hearts = [o for o in objs if o is not ln]
on_line = all(ln.world_geometry().distance(
    __import__("shapely.geometry", fromlist=["Point"]).Point(o.x, o.y)) < 0.6 for o in hearts)
check("Encore entlang Linie: Herzen sitzen auf der Linie", on_line)

# ---- Strass & Perlen
heart = templates.motif("Herz", 60, "#C2185B", 0, 0)
setdoc(heart)
select(heart)
w.open_stones()
st = [o for o in w.doc.objects if o.kind == "stones"]
check(f"Strass entlang der Kontur ({len(st[0].points) if st else 0} Steine)",
      len(st) == 1 and len(st[0].points) > 30)
s = st[0]
g = heart.world_geometry()
inside = all(g.buffer(0.5).contains(__import__("shapely.geometry", fromlist=["Point"]).Point(
    *p)) for p in stones.world_centers(s))
check("Strass: alle Steine auf der Form", inside)
check("Strass: keine Stiche, Stickstiche unverändert", not s.stitch_blocks())
pts = stones.fill(g, 2.8, 0.6)
check(f"Strass-Füllung: Waben ohne Überlappung ({len(pts)})",
      len(pts) > 100 and min(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                             for i, a in enumerate(pts[:60]) for b in pts[i + 1:]) >= 3.39)
select(s); QTest.qWait(5)
w.props.set_object(s)
check("Eigenschaften zeigen die Karte »Strass & Perlen«",
      w.props.c_stones.isVisibleTo(w.props) and not w.props.c_border.isVisibleTo(w.props))
w.props.s_size.setCurrentIndex(w.props.s_size.findData(4.7))
check("Eigenschaften: Steingröße ändern", abs(s.fill["stone"] - 4.7) < 1e-6)
item = w.items[s.id]
check("Strass: Auswahlrahmen umfasst die Steine", item.stitch_rect().width() > 50)
img = render_document(w.doc, 4)
check("Strass: PNG-Bild enthält die Steine", img.width() > 200)
# Speichern / Laden
d2 = Document(); d2.load_json(w.doc.to_json())
s2 = [o for o in d2.objects if o.kind == "stones"]
check("Strass: Speichern und Laden", s2 and s2[0].points == s.points and s2[0].fill["stone"] == 4.7)
# Stickdatei: Steine stören den Export nicht
pes = os.path.join(OUT, "strass.pes")
fileio.export_file(w.doc, pes)
pat = pe.read(pes)
n = sum(1 for x in pat.stitches if x[2] == pe.STITCH)
check(f"Export PES mit Strass: nur die Stiche der Form ({n})", abs(n - stitches([heart])) < 60)
# Schablonen
svg = os.path.join(OUT, "strass.svg")
pdf = os.path.join(OUT, "strass.pdf")
n1 = stones.export_svg(w.doc, svg)
n2 = stones.export_pdf(w.doc, pdf)
txt = open(svg, encoding="utf-8").read()
check(f"Schablone SVG: ein Loch je Stein ({n1})", txt.count("<circle") == len(s.points) == n1)
check("Schablone SVG in Millimetern, Loch = Stein + 0,4 mm",
      'mm"' in txt and f'r="{(4.7 + 0.4) / 2:.3f}"' in txt)
check("Schablone PDF geschrieben", n2 == n1 and os.path.getsize(pdf) > 1000 and
      open(pdf, "rb").read(5) == b"%PDF-")
w.undo(); QTest.qWait(5)
w.undo(); QTest.qWait(5)
check("Strass: Rückgängig entfernt die Steine",
      not any(o.kind == "stones" for o in w.doc.objects))
w.grab().save(os.path.join(OUT, "verzieren.png"))
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
