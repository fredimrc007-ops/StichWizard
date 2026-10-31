import sys, os
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from testdata import hafnerei_project, jumpy_dst
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion')
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
from stichwizard.mainwindow import MainWindow
from stichwizard.optimizer_dialog import OptimizerDialog
from stichwizard import fileio, jumps
SP = sys.argv[1]; ok = []
def check(name, cond): ok.append(bool(cond)); print(('✓' if cond else '✗'), name)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(80)
c = w.canvas; vp = c.viewport(); v = lambda x, y: c.mapFromScene(QPointF(x, y))
w.set_tool('rect'); QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(-20, -20)); QTest.mouseMove(vp, v(10, 5)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(10, 5))
o = w.doc.objects[-1]; check('Rechteck gezeichnet', o.kind == 'shape')
c.snap = False   # freies Verschieben (Einrasten hat einen eigenen Test)
x0 = o.x; QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(o.x, o.y))
for i in range(1, 6): QTest.mouseMove(vp, v(x0 + i * 2, o.y))
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(x0 + 10, o.y))
moved = c.mapToScene(v(x0 + 10, o.y)).x() - c.mapToScene(v(x0, o.y)).x()   # Strecke in ganzen Pixeln
check(f'Verschieben ({o.x - x0:.2f} mm, Maus {moved:.2f} mm)', abs(o.x - x0 - moved) < 0.05 and abs(moved - 10) < 0.6)
p = QPointF(700, 450); s0 = c.mapToScene(p.toPoint())
QApplication.sendEvent(vp, QWheelEvent(p, vp.mapToGlobal(p), QPoint(0, 0), QPoint(0, 240), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
s1 = c.mapToScene(p.toPoint()); check('Zoom bleibt unter der Maus', abs(s0.x() - s1.x()) < 0.5 and abs(s0.y() - s1.y()) < 0.5)
w.set_tool('polygon')
for (x, y), b in [((0, -40), Qt.LeftButton), ((15, -20), Qt.RightButton), ((0, -5), Qt.RightButton), ((-15, -20), Qt.RightButton)]:
    QTest.mouseClick(vp, b, Qt.NoModifier, v(x, y))
QTest.keyClick(c, Qt.Key_Return); check('Ecken/Rundungen', [p[2] for p in w.doc.objects[-1].curve[0]] == [0, 1, 1, 1])
w.set_tool('ellipse'); QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(-40, 30)); QTest.mouseMove(vp, v(-10, 50)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(-10, 50))
e = w.doc.objects[-1]; check('Ellipse mit Rundungspunkten', e.curve and len(e.curve[0]) in (8, 12) and abs(e.world_geometry().bounds[2] - e.world_geometry().bounds[0] - 30) < 1)
w.set_tool('select')
w.open_document(jumpy_dst(SP))   # eigene Datei mit vielen Sprüngen
d = OptimizerDialog(w); d.show(); QTest.qWait(50); n0 = len(d.records)
d.auto_optimize(); n1 = len(d.records); check(f'Optimierer {n0} → {n1} Sprünge', n1 < n0); d.accept()
recs = jumps.jump_list(w.doc); r = next(x for x in recs if x['trim']); w._edit_inside(r, 'trim_off')
check('Schnitt entfernen', sum(x['trim'] for x in jumps.jump_list(w.doc)) == sum(x['trim'] for x in recs) - 1)
w.undo(); check('Rückgängig', sum(x['trim'] for x in jumps.jump_list(w.doc)) == sum(x['trim'] for x in recs))
for e in ('pes', 'dst', 'jef', 'exp', 'vp3', 'xxx'):
    path = os.path.join(SP, 'r.' + e)
    fileio.export_file(w.doc, path)
    b = fileio.import_file(path)
    n = sum(1 for bl in b.blocks for s in bl['stitches'] if s[2] == 0)
    check(f'Export/Import {e}', n > 1000)
pp = os.path.join(SP, 'r.stickproj'); w.doc.objects = w.doc.objects
open(pp, 'w', encoding='utf-8').write(w.doc.to_json(True))
proj = hafnerei_project(SP)
w.open_document(proj)
# das Original-Projekt hat 3 Objekte; der Ersatz aus der DST-Datei eines
check('Projekt laden', len(w.doc.objects) == (3 if not proj.startswith(SP) else 1)
      and w.doc.stats()['stitches'] > 2000)
print('ERGEBNIS:', sum(ok), '/', len(ok))
