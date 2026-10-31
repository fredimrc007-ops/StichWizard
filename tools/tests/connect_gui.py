"""Test: Werkzeug »Mit Linie verbinden« (K)."""
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion')
from stichwizard.mainwindow import MainWindow
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
c = w.canvas; vp = c.viewport(); v = lambda x, y: c.mapFromScene(QPointF(x, y))
def draw_line(pts):
    w.set_tool('line')
    for x, y in pts:
        QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(x, y))
    QTest.keyClick(c, Qt.Key_Return); QTest.qWait(30)
    return w.doc.objects[-1]
def rect(x0, y0, x1, y1):
    w.set_tool('rect'); QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(x0, y0))
    QTest.mouseMove(vp, v(x1, y1)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(x1, y1))
    return w.doc.objects[-1]
def connect(p, q, mods=Qt.NoModifier):
    w.set_tool('connect')
    QTest.mouseMove(vp, v(*p)); QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(*p))
    QTest.mouseMove(vp, v(*q)); QTest.mouseClick(vp, Qt.LeftButton, mods, v(*q)); QTest.qWait(30)
# 1) Ecken zweier Rechtecke verbinden (nahe daneben klicken -> einrasten)
r1 = rect(-50, -50, -30, -30); r2 = rect(20, 20, 40, 40)
n = len(w.doc.objects)
connect((-29.6, -29.7), (20.4, 19.6))
ln = w.doc.objects[-1]
pts = [ln.to_world(x, y) for x, y, _ in ln.line_nodes()]
check(f"Neue Linie zwischen zwei Formen ({n} → {len(w.doc.objects)})", len(w.doc.objects) == n + 1 and ln.kind == "line")
b1, b2 = r1.world_geometry().bounds, r2.world_geometry().bounds
check(f"Eingerastet auf den Eckpunkten {[(round(x,2), round(y,2)) for x, y in pts]}",
      abs(pts[0][0] - b1[2]) < 0.01 and abs(pts[0][1] - b1[3]) < 0.01 and
      abs(pts[1][0] - b2[0]) < 0.01 and abs(pts[1][1] - b2[1]) < 0.01)
check("Farbe von der Form übernommen", ln.border["color"].upper() == r1.fill["color"].upper())
check("Linie wird gestickt", sum(1 for _, s in ln.stitch_blocks() for p in s if p[2] == 0) > 10)
# 2) Linie verlängern: Linienende -> freier Punkt
a = draw_line([(-60, 50), (-40, 50)])
n = len(w.doc.objects)
connect((-40, 50), (-40, 70))
a2 = next(o for o in w.doc.objects if o.id == a.id)
check(f"Linienende verlängert (Objekte gleich: {len(w.doc.objects) == n}, Punkte {len(a2.line_nodes())})",
      len(w.doc.objects) == n and len(a2.line_nodes()) == 3)
# 3) Zwei Linien über ihre Enden zusammenführen
b = draw_line([(0, 60), (20, 60)])
c2 = draw_line([(30, 70), (50, 70)])
n = len(w.doc.objects)
connect((20, 60), (30, 70))
j = w.doc.objects[-1]
check(f"Zwei Linien zu einer zusammengeführt ({n} → {len(w.doc.objects)}, {len(j.line_nodes())} Punkte)",
      len(w.doc.objects) == n - 1 and len(j.line_nodes()) == 4)
# 4) Linie schließen über ihre beiden Enden
d = draw_line([(60, -60), (80, -60), (80, -40)])
connect((60, -60), (80, -40))
d2 = next(o for o in w.doc.objects if o.id == d.id)
check("Beide Enden einer Linie: geschlossen", d2.closed)
# 5) Umschalt: 15°-Winkel bei freiem Punkt
n = len(w.doc.objects)
connect((-80, 0), (-60, 1.5), Qt.ShiftModifier)
e = w.doc.objects[-1]; q = [e.to_world(x, y) for x, y, _ in e.line_nodes()]
check(f"Umschalt rastet Winkel ein ({q[1][1] - q[0][1]:.2f} mm Höhe)", abs(q[1][1] - q[0][1]) < 0.05)
# 6) Esc bricht ab
w.set_tool('connect'); QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(0, -80))
QTest.keyClick(c, Qt.Key_Escape)
check("Esc bricht ersten Punkt ab", c._conn_a is None)
# 7) Zwei gewählte Punkte im Punkte-Werkzeug + Knopf
r3 = rect(-20, -80, 0, -60)
w.scene.clearSelection(); w.items[r3.id].setSelected(True)
w.set_tool('nodes'); c._node_state()
c._node_sel = {(0, 0), (0, 2)}
n = len(w.doc.objects)
w.tool_actions["connect"].trigger(); QTest.qWait(30)
check(f"Knopf verbindet zwei gewählte Punkte sofort (Werkzeug bleibt: {c.tool})", len(w.doc.objects) == n + 1 and c.tool == "nodes")
w.undo(); QTest.qWait(30)
check("Rückgängig", len(w.doc.objects) == n)
print("ERGEBNIS:", sum(ok), "/", len(ok))
