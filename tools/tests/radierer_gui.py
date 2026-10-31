"""Test: Radierer wie im Malprogramm – runder Pinsel, der beim Ziehen entlang des Strichs radiert,
einstellbare Größe ([ / ] und Menü), Kreis am Mauszeiger, Klick radiert einen Punkt, Linien bleiben
in allen Stücken erhalten, Umschalt+Ziehen umfährt weiter einen Bereich (Lasso), Rückgängig."""
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv); app.setStyle('Fusion')
from shapely.geometry import Point
from stichwizard.mainwindow import MainWindow
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
c = w.canvas; vp = c.viewport(); v = lambda x, y: c.mapFromScene(QPointF(x, y))


def rect(x0, y0, x1, y1):
    w.set_tool('rect'); QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(x0, y0))
    QTest.mouseMove(vp, v(x1, y1)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(x1, y1))
    QTest.qWait(20)
    return w.doc.objects[-1]


def stroke(pts, mods=Qt.NoModifier):
    QTest.mouseMove(vp, v(*pts[0]))
    QTest.mousePress(vp, Qt.LeftButton, mods, v(*pts[0]))
    for p in pts[1:]:
        QTest.mouseMove(vp, v(*p))
    QTest.mouseRelease(vp, Qt.LeftButton, mods, v(*pts[-1])); QTest.qWait(20)


def shapes():
    return [o for o in w.doc.objects if o.kind in ("shape", "line")]


# ---- Pinsel: Ziehen radiert einen Streifen in Pinselbreite quer durch das Rechteck
o = rect(-30, -20, 30, 20)
a0 = o.world_geometry().area
w.scene.clearSelection()
w.set_eraser(4, False)
check("Werkzeug Radierer, Pinsel 4 mm", c.tool == "eraser" and c.eraser_size == 4 and not c.eraser_lasso)
check("Hinweis nennt Größe und Tasten", "4 mm" in w.lbl_tip.text() and "[ / ]" in w.lbl_tip.text())
QTest.mouseMove(vp, v(0, 0)); QTest.qWait(20)
check("Kreis am Mauszeiger", c._erase_hover and abs(c._mouse.x()) < 0.5)
QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, v(0, -30))
QTest.mouseMove(vp, v(0, -5)); QTest.mouseMove(vp, v(0, 10))
check("Vorschau zeigt den überstrichenen Streifen schon beim Ziehen",
      abs(c.preview.path().boundingRect().width() - 4) < 0.3)
QTest.mouseMove(vp, v(0, 30)); QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, v(0, 30)); QTest.qWait(20)
g = o.world_geometry()
check(f"Streifen von ~4 mm Breite entfernt ({a0:.0f} → {g.area:.0f} mm²)",
      abs((a0 - g.area) - 4 * 40) < 6)
check("Rechteck in zwei Hälften geteilt", g.geom_type == "MultiPolygon" and len(g.geoms) == 2)
check("Mitte ist weg, Ränder bleiben", not g.contains(Point(0, 0)) and g.contains(Point(-10, 0))
      and g.contains(Point(10, 0)))
check("Kein Lasso-Verhalten: Fläche links vom Strich bleibt", g.contains(Point(-25, 15)))
w.undo(); QTest.qWait(20)
o = shapes()[-1]
check("Rückgängig stellt das Rechteck wieder her", abs(o.world_geometry().area - a0) < 0.5)

# ---- Klick ohne Ziehen radiert einen runden Punkt (Loch)
w.scene.clearSelection(); w.set_tool("eraser")
QTest.mouseMove(vp, v(10, 0)); QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(10, 0)); QTest.qWait(20)
o = shapes()[-1]; g = o.world_geometry()
hole = a0 - g.area
check(f"Klick stanzt ein rundes Loch ({hole:.1f} mm² ≈ π·2²)", abs(hole - 3.1416 * 4) < 1.0)
check("Loch liegt unter dem Mauszeiger", not g.contains(Point(10, 0)) and g.contains(Point(14, 0)))
w.undo(); QTest.qWait(20)

# ---- Größe mit [ und ] ändern und merken
c.setFocus(); w.set_eraser(4, False)
QTest.keyClick(c, Qt.Key_BracketRight); QTest.qWait(10)
check(f"] vergrößert ({c.eraser_size} mm)", c.eraser_size == 5)
QTest.keyClick(c, Qt.Key_BracketLeft); QTest.keyClick(c, Qt.Key_BracketLeft); QTest.qWait(10)
check(f"[ verkleinert ({c.eraser_size} mm)", abs(c.eraser_size - 3.2) < 1e-6)
check("Hinweis folgt der Größe", "3.2 mm" in w.lbl_tip.text())
check("Größe wird gespeichert", abs(float(w.settings.value("eraserSize")) - 3.2) < 1e-6)
for _ in range(40):
    QTest.keyClick(c, Qt.Key_BracketLeft)
check("Mindestgröße 0,3 mm", c.eraser_size == 0.3)
m = w._eraser_btn().menu(); w._fill_eraser_menu(m)
texts = [a.text() for a in m.actions() if a.text()]
check(f"Menü am Knopf: Größen und Lasso ({len(texts)})", "Pinsel 8 mm" in texts and
      "Lasso: Bereich umfahren" in texts)

# ---- Linie quer durchradieren: beide Stücke bleiben erhalten
for o in shapes():
    w.doc.objects.remove(o)
w.sync_items(); w.commit()
w.set_tool('line')
for p in ((-40, 40), (40, 40)):
    QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, v(*p))
QTest.keyClick(c, Qt.Key_Return); QTest.qWait(20)
line = shapes()[-1]
check("Linie gezeichnet", line.kind == "line" and abs(line.world_geometry().length - 80) < 0.5)
w.scene.clearSelection(); w.set_eraser(2, False)
stroke([(0, 30), (0, 40), (0, 50)])
lines = [o for o in shapes() if o.kind == "line"]
lens = sorted(round(o.world_geometry().length) for o in lines)
check(f"Linie in zwei Stücke geteilt, keins geht verloren ({lens})", lens == [39, 39])
w.undo(); QTest.qWait(20)
check("Rückgängig: wieder eine Linie", len([o for o in shapes() if o.kind == "line"]) == 1)

# ---- Nur die ausgewählte Form wird radiert
for o in shapes():
    w.doc.objects.remove(o)
w.sync_items(); w.commit()
a = rect(-30, -20, 0, 20); b = rect(0, -20, 30, 20)
w.scene.clearSelection(); w.items[a.id].setSelected(True)
aa, ab = a.world_geometry().area, b.world_geometry().area
w.set_eraser(6, False)
stroke([(-20, 0), (20, 0)])
a, b = [next(o for o in w.doc.objects if o.id == x.id) for x in (a, b)]
check("Ausgewählte Form radiert", a.world_geometry().area < aa - 50)
check("Nicht ausgewählte Form bleibt", abs(b.world_geometry().area - ab) < 0.5)

# ---- Umschalt+Ziehen: Bereich umfahren wie bisher (Lasso)
w.scene.clearSelection(); w.set_eraser(1, False)
ab = b.world_geometry().area
stroke([(5, -10), (25, -10), (25, 10), (5, 10), (5, -9)], Qt.ShiftModifier)
b = next(o for o in w.doc.objects if o.id == b.id)
check(f"Umschalt: umfahrener Bereich weg ({ab:.0f} → {b.world_geometry().area:.0f})",
      abs((ab - b.world_geometry().area) - 400) < 25 and not b.world_geometry().contains(Point(15, 0)))
w.set_eraser(None, True)
check("Lasso-Modus im Menü", c.eraser_lasso and "Lasso" in w.lbl_tip.text())
check("Lasso-Häkchen unten folgt", w.eraser_lasso_box.isChecked())
w.eraser_lasso_box.setChecked(False)
check("Häkchen weg = wieder Pinsel", not c.eraser_lasso)
w.set_eraser(3, False)

# ---- Einstellungen sichtbar: Leiste unten links und Pfeil am Knopf der Werkzeugleiste links
from PySide6.QtWidgets import QToolButton
check("Radierer-Leiste unten sichtbar", w.eraser_bar.isVisible() and w.eraser_spin.value() == 3)
w.eraser_spin.setValue(7)
check("Größenfeld stellt den Radierer ein", c.eraser_size == 7 and "7 mm" in w.lbl_tip.text())
QTest.keyClick(c, Qt.Key_BracketRight)
check("Größenfeld folgt der ]-Taste", abs(w.eraser_spin.value() - 8.8) < 0.06)
eb = w.toolstrip.widgetForAction(w.tool_actions["eraser"])
check("Pfeil am Radierer der linken Werkzeugleiste", isinstance(eb, QToolButton) and eb.menu() is not None
      and eb.popupMode() == QToolButton.MenuButtonPopup)
w.set_tool("select")
check("Leiste verschwindet bei anderem Werkzeug", not w.eraser_bar.isVisible())
w.set_tool("eraser")

w.grab().save(sys.argv[1] + "/radierer_ui.png")
print("ERGEBNIS:", sum(ok), "/", len(ok))
