"""Test (1.30): Sketch (Skizzenstich, Sketch-Werkzeug mit Stilen, echte Mausstriche) und
Stich-Editor (Navigieren, Verschieben, Löschen, Einfügen, Stichart, Farbwechsel, kurze/lange
Stiche, Rückgängig, Übernehmen, Umwandeln von Formen, Doppelklick)."""
import math
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
import pyembroidery as pe
from shapely.geometry import LineString, Point
from stichwizard import engine, fileio, templates
from stichwizard.engine import JUMP, STITCH, TRIM
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
from stichwizard.stitcheditor import StitchEditor
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(150)

# ---- Skizzenstich
path = [(0, 0), (40, 10), (80, 0)]
pts = engine.sketch_line(path, 2.0, 3, 0.4)
base = engine.resample(path, 2.0)
check(f"3 Durchgänge hin-zurück-hin ({len(pts)} ≈ 3 × {len(base)})", abs(len(pts) - (3 * len(base) - 2)) <= 1)
ln = LineString(path)
dev = max(ln.distance(Point(p)) for p in pts)
check(f"Seitlich höchstens um die Streuung versetzt ({dev:.2f} mm)", 0.1 < dev <= 0.41)
check("Enden exakt (keine Fransen)", pts[0] == base[0] and math.dist(pts[-1], base[-1]) < 1e-6)
check("Gleiche Linie → gleiches Ergebnis (kein Flackern beim Neuberechnen)",
      engine.sketch_line(path, 2.0, 3, 0.4) == pts)
o = EmbObject("line", "S"); o.set_points(path); o.border.update(type="sketch", width=1.2, repeats=2)
sts = [p for _, b in o.stitch_blocks() for p in b if p[2] == STITCH]
check("Linienart »Skizzenstich« stickt durchgehend ohne Sprung",
      len(sts) > 100 and not any(p[2] in (JUMP, TRIM) for _, b in o.stitch_blocks() for p in b[2:-2]))
w.doc.objects = [o]; w.sync_items(); w.commit()
w.scene.clearSelection(); w.items[o.id].setSelected(True); QTest.qWait(5); w.props.set_object(o)
lab = w.props.c_border.form.labelForField(w.props.b_repeats).text()
check(f"Eigenschaften: Streuung und Extra-Durchgänge ({lab})",
      lab == "Extra-Durchgänge" and w.props.b_width.isEnabled())

# ---- Sketch-Werkzeug (echte Mausstriche)
w.doc.objects = []; w.sync_items(); w.commit()
w.set_sketch_style(dict(w.SKETCH_STYLES[0][1]), "Bleistift")
check("Sketch-Werkzeug aktiv", w.canvas.tool == "sketch")
vp = w.canvas.viewport()
def ev(t, x, y, buttons):
    pos = QPointF(x, y)
    e = QMouseEvent(t, pos, vp.mapToGlobal(pos.toPoint()), Qt.LeftButton, buttons, Qt.NoModifier)
    QApplication.sendEvent(vp, e)
def stroke(y):
    ev(QEvent.MouseButtonPress, 300, y, Qt.LeftButton)
    for k in range(1, 40):
        ev(QEvent.MouseMove, 300 + k * 6, y + 25 * math.sin(k / 5), Qt.LeftButton)
    ev(QEvent.MouseButtonRelease, 534, y, Qt.NoButton)
    QTest.qWait(10)
stroke(400)
stroke(470)
objs = list(w.doc.objects)
check(f"Zwei Striche → zwei Sketch-Linien ({len(objs)})", len(objs) == 2 and
      all(x.kind == "line" and x.border["type"] == "sketch" for x in objs))
check("Werkzeug bleibt für weitere Striche aktiv", w.canvas.tool == "sketch")
w.set_sketch_style(dict(w.SKETCH_STYLES[4][1]), "Satin 2 mm")
stroke(540)
check("Stil »Satin 2 mm« für den nächsten Strich", w.doc.objects[-1].border["type"] == "satin"
      and w.doc.objects[-1].border["width"] == 2.0)
w.undo(); QTest.qWait(5)
check("Rückgängig nimmt den letzten Strich", len(w.doc.objects) == 2)
w.set_tool("select")

# ---- Stich-Editor
blocks = [{"color": "#E53935", "stitches": [[x * 2.0, 0.0, STITCH] for x in range(10)]},
          {"color": "#1E88E5", "stitches": [[0.0, 10.0, JUMP]] + [[x * 9.0, 10.0, STITCH] for x in range(1, 4)]}]
ed = StitchEditor(w, blocks)
check("Editor kopiert die Stiche (Original bleibt)", ed.blocks is not blocks and
      ed.blocks[0]["stitches"] is not blocks[0]["stitches"])
check(f"Navigation: {len(ed.index)} Punkte, Start beim ersten", len(ed.index) == 14 and ed.current == (0, 0))
ed.step(1); ed.step(1)
check("Weiterblättern", ed.current == (0, 2))
ed.nudge(0.0, 1.0)
check("Pfeiltaste verschiebt um 1 mm", ed.stitch((0, 2))[1] == 1.0)
ed.undo()
check("Rückgängig", ed.stitch((0, 2))[1] == 0.0)
ed.redo(); ed.undo()
ed.insert_after()
check("Einfügen: neuer Stich in der Mitte", len(ed.blocks[0]["stitches"]) == 11 and
      ed.stitch((0, 3))[:2] == [5.0, 0.0])
ed.delete_selected()
check("Löschen", len(ed.blocks[0]["stitches"]) == 10)
ed.sel = {(0, 5), (0, 6), (0, 7)}
ed.delete_selected()
check("Mehrere löschen", len(ed.blocks[0]["stitches"]) == 7)
ed.set_current((0, 4))
ed.split_here()
check(f"Farbwechsel ab hier ({len(ed.blocks)} Blöcke)", len(ed.blocks) == 3 and
      len(ed.blocks[1]["stitches"]) == 3 and ed.blocks[1]["color"] != "#E53935")
ed.set_current((2, 2))
ed.flag.setCurrentIndex(ed.flag.findData(TRIM))
check("Stichart ändern (Fadenschnitt)", ed.stitch((2, 2))[2] == TRIM)
ed.flag.setCurrentIndex(ed.flag.findData(STITCH))
n = ed.split_long(4.0)
check(f"Lange Stiche teilen ({n} neu, alle ≤ 4 mm)", n >= 3 and
      max(math.dist(a[:2], b[:2]) for b_ in ed.blocks for a, b in zip(b_["stitches"], b_["stitches"][1:])
          if b[2] == STITCH) <= 4.0 + 1e-6)
ed.blocks[0]["stitches"].insert(2, [ed.stitch((0, 1))[0] + 0.1, 0.0, STITCH])
ed._rebuild_index()
n = ed.remove_short(0.4)
check(f"Kurze Stiche entfernen ({n})", n >= 1)
ed.block_color.set_color("#43A047"); ed.set_current((0, 0)); ed._color_edited("#43A047")
check("Blockfarbe ändern", ed.blocks[0]["color"] == "#43A047")
ed.show(); QTest.qWait(150); ed.view.fit(); QTest.qWait(50)
ed.grab().save(os.path.join(OUT, "stitcheditor.png")); ed.close()

# ---- im Programm
st = EmbObject("stitches", "Datei")
st.blocks = [{"color": "#E53935", "stitches": [[x * 2.0, 0.0, STITCH] for x in range(20)]}]
w.doc.objects = [st]; w.sync_items(); w.commit()
def accept_exec(self):
    self.set_current((0, 3)); self.delete_selected(); self.accept(); return 1
StitchEditor.exec = accept_exec
w.scene.clearSelection(); w.items[st.id].setSelected(True); QTest.qWait(5)
w.open_stitch_editor()
check("Übernehmen schreibt die Stiche zurück", len(st.blocks[0]["stitches"]) == 19)
w.undo(); QTest.qWait(5)
check("Rückgängig im Programm", len(w.doc.objects[0].blocks[0]["stitches"]) == 20)
heart = templates.motif("Herz", 30, "#C2185B")
w.doc.objects = [heart]; w.sync_items(); w.commit()
StitchEditor.exec = lambda self: 0
w.open_stitch_editor(heart)
check("Abbrechen lässt eine Form unverändert", heart.kind == "shape")
n0 = sum(1 for _, b in heart.world_blocks() for p in b if p[2] == STITCH)
StitchEditor.exec = accept_exec
w.open_stitch_editor(heart)
n1 = sum(1 for _, b in heart.world_blocks() for p in b if p[2] == STITCH)
check(f"Form umgewandelt und bearbeitet ({n0} → {n1} Stiche)", heart.kind == "stitches" and
      n1 == n0 - 1)
calls = []
w.open_stitch_editor = lambda o=None: calls.append(o)
w.canvas.crossRequested.emit(heart)
check("Doppelklick auf eine Stickdatei öffnet den Stich-Editor", calls == [heart])
pes = os.path.join(OUT, "edit.pes")
fileio.export_file(w.doc, pes)
check("Export nach dem Bearbeiten", len(pe.read(pes).stitches) > 100)
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
