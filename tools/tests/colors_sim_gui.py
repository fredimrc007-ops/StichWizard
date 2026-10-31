"""Test: Farbwahl bei großen Garnkarten (alles sichtbar, passt auf den Bildschirm) und
stufenloser Tempo-Regler in Simulator und Stick-Optimierer."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
OUT = sys.argv[1]
app = QApplication(sys.argv); app.setStyle('Fusion')
from stichwizard.__main__ import apply_light_palette
apply_light_palette(app)
from stichwizard import threads
from stichwizard.mainwindow import MainWindow
from stichwizard.model import EmbObject
from stichwizard.simulator import SimulatorDialog
from stichwizard.optimizer_dialog import OptimizerDialog
from shapely.geometry import box
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1300, 800); w.show(); QTest.qWait(100)
screen = app.primaryScreen().availableGeometry()
big = max(threads.chart_names(), key=lambda n: len(threads.charts()[n]))
for chart in ("", big):
    threads.set_chart(chart)
    btn = w.props.f_color
    o = EmbObject("shape"); o.set_geometry(box(-10, -10, 10, 10)); w.add_objects([o]); QTest.qWait(20)
    btn._open(); QTest.qWait(50)
    pop = btn.popup
    g = pop.geometry()
    grid = pop.grid
    n = len(grid.colors)
    inside = screen.contains(g)
    # letzte Spalte vollständig sichtbar (nicht unter der Bildlaufleiste)?
    vp = grid.area.viewport().width()
    need = grid._cols * (grid.CELL + grid.GAP) - grid.GAP
    check(f"{chart or 'Standard'} ({n} Farben): Fenster {g.width()}×{g.height()} passt auf Bildschirm "
          f"{screen.width()}×{screen.height()}", inside)
    check(f"   alle {grid._cols} Spalten sichtbar (Platz {vp} px ≥ {need} px)", vp >= need)
    last = grid.buttons[-1][1]
    grid.area.ensureWidgetVisible(last); QTest.qWait(10)
    pos = last.mapTo(grid.area.viewport(), QPoint(0, 0))
    check("   letzte Farbe per Bildlauf erreichbar", 0 <= pos.y() <= grid.area.viewport().height() - grid.CELL + 1)
    picked = []
    grid.picked.connect(picked.append)
    QTest.mouseClick(last, Qt.LeftButton); QTest.qWait(10)
    check("   Klick übernimmt die Farbe", picked and o.fill["color"] == picked[-1] or btn.color == picked[-1])
    if n > 60:
        btn._open(); QTest.qWait(30)
        grid = btn.popup.grid
        grid.as_list.setChecked(True)
        grid.search.setText(grid.colors[5][0].split()[0])
        vis = [grid.list.item(i) for i in range(grid.list.count()) if not grid.list.item(i).isHidden()]
        check(f"   Liste + Suche: {len(vis)} Treffer", 1 <= len(vis) < n and grid.list.isVisible())
        btn.popup.grab().save(os.path.join(OUT, "farbliste.png"))
        btn.popup.close()
    pop.grab().save(os.path.join(OUT, f"farben_{'gross' if chart else 'standard'}.png"))
    if pop.isVisible():
        pop.close()
# Leiste unten: Mausrad blättert, »Alle …« öffnet großes Fenster
bar = w.palette_bar
hb = bar.area.horizontalScrollBar()
check(f"Garnfarben-Leiste blätterbar (max {hb.maximum()})", hb.maximum() > 0)
from PySide6.QtGui import QWheelEvent
ev = QWheelEvent(QPointF(20, 10), QPointF(20, 10), QPoint(0, 0), QPoint(0, -240), Qt.NoButton,
                 Qt.NoModifier, Qt.NoScrollPhase, False)
v0 = hb.value(); QApplication.sendEvent(bar.area.viewport(), ev); QTest.qWait(10)
check(f"Mausrad blättert seitlich ({v0} → {hb.value()})", hb.value() > v0)
got = []
bar.picked.connect(lambda c, border: got.append((c, border)))
bar._open_all(); QTest.qWait(30)
QTest.mouseClick(bar.popup.grid.buttons[3][1], Qt.LeftButton); QTest.qWait(10)
check("»Alle …« wählt Füllfarbe", got and got[-1][1] is False)
threads.set_chart("")
# Tempo-Regler
o = EmbObject("shape"); o.set_geometry(box(-30, -30, 30, 30)); w.doc.objects = [o]; w.sync_items([])
sim = SimulatorDialog(w.doc, w.opts, w); sim.show(); QTest.qWait(30)
sp = sim.speed
sp.set_speed(2.0); slow = sp.speed()
sp.set_speed(3000); fast = sp.speed()
check(f"Regler stufenlos: {slow:.1f} … {fast:.0f} Stiche/s", 1.8 < slow < 2.2 and 2700 < fast < 3300)
sp.set_speed(sp.machine_sps())
check(f"Markierung »wie Maschine«: {sp.label.text()}", "wie Maschine" in sp.label.text())
for target, ms in ((10.0, 1000), (500.0, 600)):
    sp.set_speed(target)
    sim.slider.setValue(0); sim.toggle(); QTest.qWait(ms); sim.toggle()
    rate = sim.slider.value() / (ms / 1000)
    check(f"Simulation bei {target:.0f} Stichen/s: gemessen ≈ {rate:.0f}/s", 0.5 * target < rate < 1.6 * target)
sim.close()
from PySide6.QtCore import QSettings
check("Tempo wird gemerkt", abs(float(QSettings("StickStudio", "StickStudio").value("sim/speed")) - 500) < 30)
opt = OptimizerDialog(w); opt.show(); QTest.qWait(30)
check("Stick-Optimierer hat denselben Regler", hasattr(opt.speed, "slider") and abs(opt.speed.speed() - 500) < 30)
opt.slider.setValue(0); opt.toggle(); QTest.qWait(500); opt.toggle()
check(f"Optimierer-Simulation läuft ({opt.slider.value()} Stiche)", opt.slider.value() > 100)
opt.grab().save(os.path.join(OUT, "optimierer.png"))
opt.accept()
print("ERGEBNIS:", sum(ok), "/", len(ok))
