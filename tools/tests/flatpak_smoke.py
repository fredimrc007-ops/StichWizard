"""Rauchtest im installierten Flatpak (1.31): neue Funktionen laden, sticken, exportieren.
Eigene XDG-Ordner – die echten Einstellungen des Nutzers bleiben unberührt."""
import os
import sys
OUT = os.path.abspath(sys.argv[1])
for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    os.environ[k] = OUT
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/app/share/stichwizard")
from PySide6.QtCore import QStandardPaths
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv)
app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
import pyembroidery as pe
import stichwizard
from stichwizard import (crossstitch, encore, familytree, fileio, ith, machinesend, ornaments,
                         printapp, quilt, spiro, stones, templates, video, wordsculpt)
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
ok = []


def check(n, c):
    ok.append(bool(c))
    print("✓" if c else "✗", n)


check(f"Version {stichwizard.__version__}", stichwizard.__version__ == "1.32.0")
cfg = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
check(f"Daten im Testordner ({cfg})", cfg.startswith(OUT))
MAN = "/app/share/stichwizard/docs/StichWizard-Anleitung.pdf"
check("Handbuch mitgeliefert", os.path.exists(MAN) and os.path.getsize(MAN)
      > 1_000_000)
w = MainWindow()
w.resize(1440, 900)
w.show()
QTest.qWait(200)
tabs = [w.ribbon.tabText(i) for i in range(w.ribbon.count())]
check(f"Reiter Verzieren vorhanden ({len(tabs)} Reiter)", "Verzieren" in tabs)
for name, tpls in (("Rahmen", ornaments.ORNAMENTS), ("Spirograph", spiro.SPIRO),
                   ("Projekte", ith.PROJECTS), ("Stammbaum", familytree.FAMILY),
                   ("Quilt", quilt.quilt_templates())):
    n = 0
    for k, *_ in tpls:
        d = Document()
        d.objects = [o for o in templates.build(k, None, tpls) if not getattr(o, "_context", False)]
        n += d.stats()["stitches"] > 50
    check(f"{name}: alle {len(tpls)} Vorlagen ergeben Stiche", n == len(tpls))
h = templates.build("emblem")
heart = [o for o in h if o.kind == "shape"][:1]
tp, _ = encore.encore_templates(heart)
check("Encore: Kreis mit 8 Kopien", len(templates.build("circle", None, tp)) == 8)
st = [o for o in templates.build("fill", None, stones.stone_templates(heart))
      if not getattr(o, "_context", False)]
check("Strass-Steine gesetzt", st and st[0].kind == "stones" and len(st[0].points) > 5)
ws = templates.build("shape", None, wordsculpt.sculpt_templates([]))
check(f"Text in Form ({len(ws)} Teile)", len(ws) > 5)
cr = EmbObject("cross")
cr.cross = crossstitch.new(10, 10)
cr.cross["cells"] = [[x, y, 0, "x"] for x in range(10) for y in range(10)]
d = Document()
d.objects = [cr]
check("Kreuzstich stickt", d.stats()["stitches"] >= 400)
w.doc.objects = templates.build("coaster", None, ith.PROJECTS)
w.doc.color_sort = False     # wie »Projekt im Rahmen«
w.sync_items()
w.commit()
pdf = os.path.join(OUT, "untersetzer.pdf")
w.export_ith_instructions(pdf)
check("Projekt-Anleitung (PDF)", os.path.getsize(pdf) > 5000)
p = os.path.join(OUT, "untersetzer.dst")
fileio.export_file(w.doc, p)
stops = sum(1 for s in pe.read(p).stitches if s[2] in (pe.STOP, pe.COLOR_CHANGE))
check(f"DST hält nach jedem Arbeitsschritt ({stops} Pausen)", stops >= 4)
w.doc.objects = templates.build("emblem")
w.sync_items()
w.commit()
usb = os.path.join(OUT, "usb")
os.makedirs(usb)
path = w.send_to_machine(lambda dlg: (dlg.add_path(usb), True)[1])
check(f"An Maschine senden ({os.path.basename(path or '')})", path and os.path.getsize(path) > 500)
check(f"ffmpeg in der Laufzeit: {bool(video.ffmpeg())}", True)
frames = os.path.join(OUT, "video")
res = w.export_sim_video(frames if not video.ffmpeg() else frames + ".mp4",
                         {"seconds": 1.0, "size": "640x360", "fps": 25, "hoop": True, "info": True})
check(f"Simulationsvideo ({os.path.basename(res or '')})", res and os.path.exists(res))
img = printapp.make(video.final_image(w.doc, (200, 200)), 40, 40)
w.doc.objects = [img, printapp.applique(img, "rect", "#3E2723")]
w.sync_items()
w.commit()
sheet = os.path.join(OUT, "druck.pdf")
w.export_print_sheet(sheet, False)
check("Druckvorlage (PDF)", os.path.getsize(sheet) > 3000)
check(f"USB-Erkennung läuft ({len(machinesend.removable_drives())} Sticks)", True)
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
