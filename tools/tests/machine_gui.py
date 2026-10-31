"""Test (1.17): Maschinenprofile – Rahmen, Format, Tempo, ausdrückliche Stopps, Nadelplan."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
shown = []
QMessageBox.information = staticmethod(lambda *a, **k: shown.append(a[2] if len(a) > 2 else ""))
import pyembroidery as pe
from stichwizard import controls, engine, machines, model, threads
from stichwizard.mainwindow import MainWindow
from stichwizard.model import EmbObject
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)

check("Ohne Maschine: keine ausdrücklichen Stopps", not engine.EXPLICIT_STOPS and w.machine() is None)
check("Profil TEXI IRIS 10 vorhanden", machines.get("texi_iris10")["needles"] == 10)

# ---- Texi wählen
w.set_machine("texi_iris10"); QTest.qWait(20)
names = [h[0] for h in threads.HOOPS]
check("Texi-Rahmen in der Liste (190 × 140, 310 × 210)",
      "Texi – 190 × 140 mm" in names and "Texi – 310 × 210 mm" in names)
check("Standardrahmen 190 × 140 gewählt (leeres Design)", w.doc.hoop_size == (190, 140))
check("Exportformat DST", w.prefs.get("export_format") == "dst")
check("Tempo für die Stickzeit 800", w.prefs.get("speed") == 800 and model.STITCHES_PER_MINUTE == 800)
check("Mehrnadel: ausdrückliche Stopps an", engine.EXPLICIT_STOPS)
check("Statusleiste zeigt die Maschine", "TEXI" in w.lbl_machine.text())
check("Nadelempfehlung mit Nadelsystem", "DBxK5 75/11" in machines.needle_for(w.machine(), "standard"))
check("Jersey: Kugelspitze", "Kugelspitze" in machines.needle_for(w.machine(), "jersey"))

# ---- Puff mit Farbwechsel: Stopp muss in der Datei stehen
gold = EmbObject("text", "SEIT"); gold.text.update(text="SEIT 2026", size=10); gold.fill["color"] = "#F2B33D"
gold.y = 15
team = EmbObject("text", "TEAM"); team.text.update(text="TEAM", size=22); team.fill["color"] = "#FFFFFF"
team.y = -10
w.add_objects([gold, team]); QTest.qWait(30)
w.scene.clearSelection(); w.items[team.id].setSelected(True)
w.puff_selected()
blocks = w.doc.machine_blocks()
check("Stopp am Ende des goldenen Blocks", blocks[0][1][-1][2] == engine.STOP)
for ext, want_stop, want_cc in (("pes", 1, 1), ("dst", 0, 2)):
    path = os.path.join(OUT, f"puff.{ext}")
    from stichwizard.fileio import export_file
    export_file(w.doc, path)
    pat = pe.read(path)
    cmds = [s[2] & pe.COMMAND_MASK for s in pat.stitches]
    check(f"{ext.upper()}: Stopp in der Datei (STOP {cmds.count(pe.STOP)}, Farbwechsel "
          f"{cmds.count(pe.COLOR_CHANGE)})",
          cmds.count(pe.STOP) == want_stop and cmds.count(pe.COLOR_CHANGE) == want_cc)

# ---- Nadelplan
stops = {i for i, (_, sts) in enumerate(blocks) if any(s[2] == engine.STOP for s in sts)}
steps, needles, too_many = machines.needle_plan(blocks, w.machine(), stops)
check("Nadelplan: Gold Nadel 1 mit Stopp, Weiß Nadel 2",
      steps[0][1] == 1 and steps[0][3] and steps[1][1] == 2 and not too_many)
many = [(c, []) for c in ["#%06X" % (i * 99991) for i in range(12)]]
check("Mehr Farben als Nadeln wird erkannt", machines.needle_plan(many, w.machine())[2])
pdf = w.export_worksheet(os.path.join(OUT, "blatt.pdf"))
check("Arbeitsblatt mit Nadelplan geschrieben", os.path.getsize(os.path.join(OUT, "blatt.pdf")) > 5000)

# ---- Rahmen größer als Stickfeld → Warnung
w.set_hoop(threads.hoop_for_size(360, 200))
check("Warnung: Rahmen größer als das Stickfeld", "größer als das Stickfeld" in w.lbl_tip.text())

# ---- Info-Fenster
w.show_machine_info()
check("Maschinen-Info zeigt Nadel und Stickfeld", shown and "DBxK5" in shown[-1] and "310 × 210" in shown[-1])

# ---- Einnadel-Maschine: Stopp über den Farbwechsel, kein zusätzlicher
w.set_machine("brother_800e")
check("Einnadel: keine ausdrücklichen Stopps", not engine.EXPLICIT_STOPS)
check("Einnadel: Format PES", w.prefs.get("export_format") == "pes")
b2 = w.doc.machine_blocks()
check("Einnadel: kein Extra-Stopp vor dem Farbwechsel", all(s[2] != engine.STOP for _, sts in b2 for s in sts))

# ---- eigene Maschine
controls.ask_values.auto = {"name": "Meine Happy", "needles": 12, "w": 400.0, "h": 300.0,
                            "format": "dst", "speed": 750, "system": "DBxK5", "auto": True}
w.add_custom_machine()
controls.ask_values.auto = None
mc = w.machine()
check("Eigene Maschine angelegt und gewählt", mc and mc["name"] == "Meine Happy" and mc["needles"] == 12)
check("Eigene Maschine gespeichert", any(m["name"] == "Meine Happy" for m in w.prefs.get("custom_machines")))
w2 = MainWindow()
check("Nach Neustart weiterhin gewählt", w2.machine() and w2.machine()["name"] == "Meine Happy"
      and engine.EXPLICIT_STOPS)
w2.close()
controls.ask_values.auto = {"id": mc["id"]}
w.delete_custom_machine()
controls.ask_values.auto = None
check("Eigene Maschine gelöscht → keine Maschine", w.machine() is None and not w.prefs.get("custom_machines"))
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
