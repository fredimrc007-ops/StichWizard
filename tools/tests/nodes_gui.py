import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion')
from stichwizard.__main__ import apply_light_palette
apply_light_palette(app)
from stichwizard.mainwindow import MainWindow
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
c = w.canvas; vp = c.viewport(); v = lambda x, y: c.mapFromScene(QPointF(x, y))
def select(o):
    w.scene.clearSelection(); w.item_for(o).setSelected(True) if hasattr(w, "item_for") else None
# Rechteck zeichnen
w.set_tool('rect'); QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(-20, -20)); QTest.mouseMove(vp, v(20, 10)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(20, 10))
o = w.doc.objects[-1]
w.set_tool('nodes'); QTest.qWait(50)
st = c._node_state(); n0 = sum(len(r["pts"]) for r in st["rings"])
# Hover über Kante zeigt +
QTest.mouseMove(vp, v(0, -20)); QTest.qWait(30)
check("Vorschau-Plus auf der Kante", c._edge_hover is not None and abs(c._edge_hover[1] + 20) < 0.5)
# Klick auf Kante + ziehen
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(0, -20))
for k in range(1, 5): QTest.mouseMove(vp, v(0, -20 - k * 2))
QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(0, -28)); QTest.qWait(30)
st = c._node_state(); pts = st["rings"][0]["world"]
check(f"Klick fügt Punkt ein ({n0} → {len(pts)})", len(pts) == n0 + 1)
check("Neuer Punkt gleich gezogen", any(abs(x) < 0.6 and abs(y + 28) < 0.6 for x, y in pts))
check("Form folgt dem Punkt", o.world_geometry().bounds[1] < -27)
# Rückgängig
w.undo(); QTest.qWait(30)
check("Rückgängig entfernt ihn", sum(len(r["pts"]) for r in c._node_state()["rings"]) == n0)
o = w.doc.objects[-1]
w.scene.clearSelection()
for it in w.scene.items():
    if getattr(it, "obj", None) is o: it.setSelected(True)
QTest.qWait(30)
print("  ausgewählt:", c._node_state() is not None)
# Einfg-Taste: zwei benachbarte Punkte wählen
st = c._node_state(); c._node_sel = {(0, 0), (0, 1)}
c.setFocus(); QTest.keyClick(c, Qt.Key_Insert); QTest.qWait(30)
check("Einfg zwischen zwei gewählten Punkten", sum(len(r["pts"]) for r in c._node_state()["rings"]) == n0 + 1 and c._node_sel == {(0, 1)})
# Ribbon-Knopf ohne Auswahl -> Hinweis
c._node_sel = set(); w.a_addnode.trigger()
check("Knopf ohne Auswahl zeigt Hinweis", "Kante" in w.lbl_tip.text())
# Rechtsklick auf Kante: Menüeintrag
acts = []
def grab_menu():
    m = QApplication.activePopupWidget()
    if isinstance(m, QMenu):
        acts.extend(a.text() for a in m.actions() if a.text())
        m.close()
QTimer.singleShot(150, grab_menu)
QTest.mouseClick(vp, Qt.RightButton, Qt.NoModifier, v(20, 0)); QTest.qWait(250)
check(f"Rechtsklick-Menü auf Kante {acts}", "Punkt hier einfügen" in acts)
# Linie: Strg+Klick verlängert
w.set_tool('line')
for x, y in ((-40, 40), (-20, 50)):
    QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(x, y))
QTest.keyClick(c, Qt.Key_Return); QTest.qWait(30)
ln = w.doc.objects[-1]
w.set_tool('nodes'); QTest.qWait(30)
QTest.mouseClick(vp, Qt.LeftButton, Qt.ControlModifier, v(0, 45)); QTest.qWait(30)
check(f"Strg+Klick verlängert Linie ({ln.kind})", len(c._node_state()["rings"][0]["pts"]) == 3)
# Säulen-Satin: paarweise
w.set_tool('satin')
for x, y in ((30, 30), (36, 30), (30, 60), (36, 60)):
    QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(x, y))
QTest.keyClick(c, Qt.Key_Return); QTest.qWait(30)
sa = w.doc.objects[-1]
w.set_tool('nodes'); QTest.qWait(30)
st = c._node_state(); before = [len(r["pts"]) for r in st["rings"]]
r0 = st["rings"][0]["world"]; mid = ((r0[0][0] + r0[1][0]) / 2, (r0[0][1] + r0[1][1]) / 2)
QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(*mid)); QTest.qWait(30)
after = [len(r["pts"]) for r in c._node_state()["rings"]]
check(f"Satin: Punktepaar ({sa.kind} {before} → {after})", after == [b + 1 for b in before])
check("Satin stickt weiter", sum(1 for _, s in sa.stitch_blocks() for p in s if p[2] == 0) > 50)
w.grab().save(sys.argv[1] + "/nodes_ui.png")
print("ERGEBNIS:", sum(ok), "/", len(ok))
