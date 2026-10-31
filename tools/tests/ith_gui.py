"""Test (1.26): Projekt im Rahmen (ITH) – alle 10 Projekte, Arbeitsschritte mit Stopps in der
richtigen Reihenfolge, offene Kanten (Handyhülle, Füllöffnung), Export mit Stopps,
PDF-Anleitung, Speichern/Laden, Einfügen/Ersetzen/Rückgängig."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QDialog.exec = lambda self: 1           # Assistent sofort mit dem ersten Projekt bestätigen
import pyembroidery as pe
from shapely.geometry import LineString
from stichwizard import engine, fileio, ith, templates
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)


def pauses(doc):
    """Anhalten der Maschine: Farbwechsel + ausdrückliche Stopps."""
    blocks = doc.machine_blocks()
    return len(blocks) - 1 + sum(1 for _, b in blocks for s in b if s[2] == engine.STOP)


# ---- alle Projekte
bad, order_bad, text_bad = [], [], []
for key, title, *_ in ith.PROJECTS:
    objs = templates.build(key, None, ith.PROJECTS)
    d = Document(); d.objects = objs; d.color_sort = False
    info, steps = ith.project_info(objs)
    stops = sum(1 for o in objs if o.trim_after == "stop")
    colors = len({c.upper() for _, _, c in steps})
    # jeder Schritt endet mit einem Stopp (außer dem letzten); mehrfarbige Motive halten
    # zusätzlich beim Farbwechsel an
    if not info or len(steps) < 5 or stops != len(steps) - 1 or \
            not stops <= pauses(d) <= stops + colors + 2 or d.stats()["stitches"] < 1500:
        bad.append(f"{key}: {len(steps)} Schritte/{pauses(d)} Pausen")
    blocks = d.machine_blocks()
    if blocks[0][0].upper() != "#8D6E63" or blocks[-1][0].upper() != "#5D4037":
        order_bad.append(key)
    if any(len(t) < 10 for _, t, _ in steps) or not info["materials"] or not info["notes"]:
        text_bad.append(key)
check(f"Alle {len(ith.PROJECTS)} Projekte: Stopp nach jedem Schritt, genug Stiche {bad}", not bad)
d = Document(); d.objects = templates.build("coaster", None, ith.PROJECTS); d.color_sort = False
check(f"Untersetzer: genau 4 Pausen für 5 Schritte ({pauses(d)})", pauses(d) == 4)
check(f"Reihenfolge bleibt: zuerst Platzierungslinie, zuletzt Rand {order_bad}", not order_bad)
check(f"Jeder Schritt hat eine Anleitung, Material und Fertigstellen {text_bad}", not text_bad)
names = [o.name for o in templates.build("coaster", None, ith.PROJECTS)]
check(f"Objekte nach Schritten benannt {names[:2]}", names[0].startswith("1. ") and
      names[-1].startswith("5. "))

# ---- Sonderfälle
ph = templates.build("phone", None, ith.PROJECTS)
edge = ph[-1]
pts = [edge.to_world(*q) for q in edge.points]
top = min(y for _, y in pts)
check("Handyhülle: Satinrand offen (U), beide Enden oben",
      not edge.closed and edge.border["type"] == "satin" and abs(pts[0][1] - top) < 0.5
      and abs(pts[-1][1] - top) < 0.5 and max(y for _, y in pts) - top > 150)
check("Handyhülle: Maß = Handy + Dicke + 5 mm",
      abs((max(x for x, _ in pts) - min(x for x, _ in pts)) + 3.2 - (72 + 8 + 5)) < 0.6)
pl = templates.build("plush", None, ith.PROJECTS)
gap_line, close_line = pl[-2], pl[-1]
L1 = LineString([gap_line.to_world(*q) for q in gap_line.points]).length
L2 = LineString([close_line.to_world(*q) for q in close_line.points]).length
ring = ith.inset(ith.templates.motif("Herz", 110, "#000").world_geometry(), 1.6).exterior.length
check(f"Kuschelfigur: Öffnung 35 mm frei, Schließnaht überlappt ({L1:.0f} + {L2:.0f} ≈ {ring:.0f})",
      abs(ring - L1 - 35) < 3 and L2 > 60 and gap_line.trim_after == "stop")
zp = templates.build("zipper", None, ith.PROJECTS)
check("Reißverschluss-Etui: Abschlussnaht dreifach, geschlossen",
      zp[-1].border["type"] == "triple" and zp[-1].closed)
cv = templates.build("cover", {"book_w": 105, "book_h": 148, "thick": 15}, ith.PROJECTS)
d = Document(); d.objects = cv
check(f"Buchhülle A6: Breite = 2 × Buch + Rücken + 12 mm ({d.stats()['width']:.0f})",
      abs(d.stats()["width"] - (2 * 105 + 15 + 12)) < 3)

# ---- im Programm
w.doc.objects = []; w.sync_items(); w.commit()
w.open_ith()
objs = list(w.doc.objects)
info, steps = ith.project_info(objs)
check(f"Assistent fügt das Projekt ein ({info and info['title']}, {len(steps)} Schritte)",
      info and info["title"] == "Untersetzer" and len(steps) == 5)
check("Farben zusammenfassen ist für Projekte aus", not w.doc.color_sort and
      not w.a_colorsort.isChecked())
pes = os.path.join(OUT, "coaster.pes")
fileio.export_file(w.doc, pes)
pat = pe.read(pes)
cmds = sum(1 for s in pat.stitches if s[2] & pe.COMMAND_MASK in (pe.STOP, pe.COLOR_CHANGE))
check(f"PES: Maschine hält 4-mal an ({cmds})", cmds >= 4)
dst = os.path.join(OUT, "coaster.dst")
fileio.export_file(w.doc, dst)
check("DST geschrieben", os.path.getsize(dst) > 1000)
pdf = os.path.join(OUT, "anleitung.pdf")
w.export_ith_instructions(pdf)
check("PDF-Anleitung", os.path.exists(pdf) and open(pdf, "rb").read(5) == b"%PDF-"
      and os.path.getsize(pdf) > 5000)
d2 = Document(); d2.load_json(w.doc.to_json())
info2, steps2 = ith.project_info(d2.objects)
check("Speichern/Laden behält Anleitung und Stopps",
      info2 == info and steps2 == steps and [o.trim_after for o in d2.objects] ==
      [o.trim_after for o in objs])
pdf2 = os.path.join(OUT, "anleitung2.pdf")
check("Anleitung auch aus geladenem Projekt", ith.export_instructions(d2, pdf2) == 5)
# Ersetzen + Rückgängig
m = templates.motif("Herz", 30, "#E53935")
w.doc.objects = [m]; w.doc.color_sort = True; w.sync_items(); w.commit()
w.open_ith()
check("Vorhandenes Design wird (nach Rückfrage) ersetzt",
      m.id not in {o.id for o in w.doc.objects} and len(w.doc.objects) == 5)
w.undo(); QTest.qWait(5)
check("Rückgängig: altes Design in einem Schritt zurück",
      [o.id for o in w.doc.objects] == [m.id] and w.doc.color_sort)
w.grab().save(os.path.join(OUT, "ith.png"))
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
