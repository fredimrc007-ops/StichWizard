"""Test: Punkte verbinden / Linien verbinden / Auftrennen."""
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
def select(*objs):
    w.scene.clearSelection()
    for o in objs:
        w.items[o.id].setSelected(True)
    QTest.qWait(20)
# 1) Linie schließen: beide Endpunkte wählen
ln = draw_line([(-40, -40), (-10, -40), (-10, -10)])
select(ln); w.set_tool('nodes'); c._node_state()
n = len(ln.line_nodes()); c._node_sel = {(0, 0), (0, n - 1)}
w.a_joinnode.trigger(); QTest.qWait(30)
ln = w.doc.objects[-1]
check(f"Endpunkte verbinden schließt Linie (closed={ln.closed})", ln.closed and len(ln.line_nodes()) == 3)
check("Geschlossene Linie stickt", sum(1 for _, s in ln.stitch_blocks() for p in s if p[2] == 0) > 20)
# 2) Auftrennen der geschlossenen Linie
select(ln); w.set_tool('nodes'); c._node_state(); c._node_sel = {(0, 1)}
w.a_breaknode.trigger(); QTest.qWait(30)
ln = w.doc.objects[-1]
check(f"Auftrennen öffnet Linie (closed={ln.closed}, Punkte {len(ln.line_nodes())})", not ln.closed and len(ln.line_nodes()) == 4)
# 3) Offene Linie in zwei teilen
select(ln); w.set_tool('nodes'); c._node_state(); c._node_sel = {(0, 2)}
count = len(w.doc.objects)
w.a_breaknode.trigger(); QTest.qWait(30)
check(f"Offene Linie in zwei geteilt ({count} → {len(w.doc.objects)})", len(w.doc.objects) == count + 1)
# 4) Zwei Linien verbinden (Auswahlwerkzeug)
a = draw_line([(10, 10), (30, 10)])
b = draw_line([(60, 20), (35, 12)])
w.set_tool('select'); select(a, b)
count = len(w.doc.objects)
w.a_joinnode.trigger(); QTest.qWait(30)
j = w.doc.objects[-1]
pts = [j.to_world(x, y) for x, y, _ in j.line_nodes()]
check(f"Zwei Linien zu einer ({count} → {len(w.doc.objects)}, {len(pts)} Punkte)", len(w.doc.objects) == count - 1 and len(pts) == 4)
check("Nächstgelegene Enden verknüpft", abs(pts[1][0] - 30) < 0.5 and abs(pts[2][0] - 35) < 0.5)
w.undo(); QTest.qWait(30)
check("Rückgängig stellt beide Linien wieder her", len(w.doc.objects) == count)
# 5) Nachbarpunkte einer Form zusammenfassen
w.set_tool('rect'); QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(-30, 20)); QTest.mouseMove(vp, v(0, 50)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(0, 50))
r = w.doc.objects[-1]; select(r); w.set_tool('nodes'); c._node_state()
c._node_sel = {(0, 0), (0, 1)}
w.a_joinnode.trigger(); QTest.qWait(30)
st = c._node_state()
check(f"Rechteck: 2 Nachbarpunkte → 1 (jetzt {len(st['rings'][0]['pts'])} Punkte = Dreieck)", len(st["rings"][0]["pts"]) == 3)
# 6) Nicht benachbarte Punkte -> Hinweis, keine Änderung
c._node_sel = {(0, 0), (0, 1)} if len(st["rings"][0]["pts"]) > 3 else set()
w.set_tool('ellipse'); QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(20, 30)); QTest.mouseMove(vp, v(50, 60)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(50, 60))
e = w.doc.objects[-1]; select(e); w.set_tool('nodes'); c._node_state(); c._node_sel = {(0, 0), (0, 4)}
w.a_joinnode.trigger(); QTest.qWait(30)
check("Nicht benachbart: Hinweis statt Änderung", len(c._node_state()["rings"][0]["pts"]) == 8 and "benachbarte" in w.lbl_tip.text())
# 7) Echter Ablauf mit Maus und Tastatur: Endpunkt klicken, Umschalt+Klick, Strg+J
ln = draw_line([(-60, 60), (-40, 70), (-20, 60)])
select(ln); w.set_tool('nodes'); c._node_state()
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(-60, 60))
QTest.mouseClick(vp, Qt.LeftButton, Qt.ShiftModifier, v(-20, 60)); QTest.qWait(20)
check(f"Maus: zwei Endpunkte gewählt {sorted(c._node_sel)}", len(c._node_sel) == 2)
QTest.keyClick(w, Qt.Key_J, Qt.ControlModifier); QTest.qWait(30)
check("Strg+J schließt die Linie", w.doc.objects[-1].closed)
print("ERGEBNIS:", sum(ok), "/", len(ok))
