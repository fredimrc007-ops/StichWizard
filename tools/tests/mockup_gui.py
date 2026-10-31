"""Test (1.16): Kappenrahmen und Produktvorschau (T-Shirt, Kappe, Tasche, Handtuch, Kissen …)."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import mockup, threads
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)

# ---- Kappenrahmen
caps = [i for i in range(threads.N_BUILTIN_HOOPS) if threads.is_cap_hoop(i)]
check(f"Zwei Kappenrahmen in der Liste {[threads.HOOPS[i][0] for i in caps]}", len(caps) == 2)
check("Flache Rahmen sind keine Kappenrahmen", not threads.is_cap_hoop(1))
w.set_hoop(caps[0])
check("Kappenrahmen 130 × 60 mm aktiv", w.doc.hoop_size == (130, 60))
check("Stoffart wird automatisch »Kappe«", w.doc.fabric_type == "cap")
check("Rahmen wird als Kappenrahmen gezeichnet (mit Schirm)",
      w.hoop_item.cap and w.hoop_item.boundingRect().height() > 60 + 44 + 40)
check("Hinweis zum Sticken auf Kappen", "Kappe" in w.lbl_tip.text())
w.set_hoop(1)
check("Zurück auf flachen Rahmen: normaler Rahmen", not w.hoop_item.cap)
check("… und die vorige Stoffart kommt zurück", w.doc.fabric_type == "standard")
check("Import wählt nie einen Kappenrahmen als »größten« Rahmen",
      all(not threads.is_cap_hoop(i) for i in range(threads.N_BUILTIN_HOOPS)
          if threads.HOOPS[i][1] * threads.HOOPS[i][2] ==
          max(h[1] * h[2] for k, h in enumerate(threads.HOOPS[:threads.N_BUILTIN_HOOPS])
              if not threads.is_cap_hoop(k))))

# ---- Produktvorschau
t = EmbObject("text", "Anna"); t.text.update(text="Anna", size=20); t.fill["color"] = "#D50000"
w.add_objects([t]); QTest.qWait(30)
w.a_mockup.trigger(); QTest.qWait(300)
d = w._mockup
check("Vorschau-Fenster offen und nicht modal", d.isVisible() and not d.isModal())
check("Zehn Produkte", d.prod_cb.count() == 10 and set(mockup.PRODUCTS) ==
      {"shirt", "shirt_back", "hoodie", "polo", "apron", "cap", "bag", "towel", "pillow", "bib"})
check("Start mit T-Shirt bei flachem Rahmen", d.product == "shirt")
check("Größe des Entwurfs wird angezeigt", d.info.text().startswith("Motiv "))


def red_pixels(img):
    n = 0
    for y in range(0, img.height(), 3):
        for x in range(0, img.width(), 3):
            c = img.pixelColor(x, y)
            if c.red() > 150 and c.green() < 80 and c.blue() < 80:
                n += 1
    return n


d.zoom_cb.setCurrentIndex(2)                         # nah heran
img = d.render_image(QSize(500, 500))
check("Der Entwurf ist auf dem T-Shirt zu sehen", red_pixels(img) > 20)
before = red_pixels(img)
t.text["size"] = 40
w.rebuild([t]); w.commit(); QTest.qWait(500)
img2 = d.render_image(QSize(500, 500))
check("Live: größere Schrift → größer in der Vorschau", red_pixels(img2) > before * 1.5)

for k in mockup.PRODUCTS:
    d.prod_cb.setCurrentIndex(d.prod_cb.findData(k)); QTest.qWait(10)
    im = d.render_image(QSize(400, 400))
    check(f"{mockup.PRODUCTS[k]['name']}: Vorschau mit Entwurf", red_pixels(im) > 5)
d.prod_cb.setCurrentIndex(d.prod_cb.findData("shirt"))
d.place_cb.setCurrentIndex(0)                        # Brust links: bis 100 mm
QTest.qWait(50); d.view.repaint(); QTest.qWait(20)
check("Warnung, wenn der Entwurf für die Stelle zu groß ist", "größer als üblich" in d.info.text())

# Rahmen auf Kappe → Vorschau wechselt mit, Stofffarbe auch
w.set_hoop(caps[0]); QTest.qWait(500)
check("Vorschau folgt dem Kappenrahmen", d.product == "cap" and d.prod_cb.currentData() == "cap")
w.set_fabric("#22304A"); QTest.qWait(500)
check("Vorschau folgt der Stofffarbe", d.color == "#22304A")

# ---- Zoom, Ansicht verschieben, Motiv anordnen (1.20)
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
w.set_hoop(1); QTest.qWait(400)
d.prod_cb.setCurrentIndex(d.prod_cb.findData("shirt")); QTest.qWait(20)
d.place_cb.setCurrentIndex(0); d.fit_view(); QTest.qWait(20)
v = d.view; v.repaint(); QTest.qWait(20)
check("Abstand zum Kragen wird angezeigt", "unter dem Kragen" in d.info.text())
pos = QPointF(v.width() * 0.6, v.height() * 0.4)
before = v.to_world(pos)
QApplication.sendEvent(v, QWheelEvent(pos, v.mapToGlobal(pos), QPoint(0, 0), QPoint(0, 360),
                                      Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
after = v.to_world(pos)
check(f"Mausrad zoomt ({d.zoom:.2f}×) und der Punkt unter der Maus bleibt stehen",
      d.zoom > 1.5 and abs(before.x() - after.x()) < 0.5 and abs(before.y() - after.y()) < 0.5)
d.zoom_to_design(); QTest.qWait(20); v.repaint()
bb = d.cache["bb"]
c, rot, k, dw, dh = mockup.design_frame(mockup.PRODUCTS["shirt"], d.state(), bb)
_, sc, o = v._xf()
start = (o + c * sc).toPoint()
check("Klick auf das Motiv wird erkannt", v.on_design(QPointF(start)))
end = start + QPoint(int(20 * sc), int(10 * sc))
QTest.mousePress(v, Qt.LeftButton, Qt.NoModifier, start)
QTest.mouseMove(v, end); QTest.mouseRelease(v, Qt.LeftButton, Qt.NoModifier, end); QTest.qWait(20)
check(f"Motiv ziehen verschiebt es (→ {d.dx:.0f} mm, ↓ {d.dy:.0f} mm)",
      abs(d.dx - 20) < 1.5 and abs(d.dy - 10) < 1.5)
pan0 = d.pan
empty = QPoint(5, 5)
QTest.mousePress(v, Qt.LeftButton, Qt.NoModifier, empty)
QTest.mouseMove(v, empty + QPoint(40, 0)); QTest.mouseRelease(v, Qt.LeftButton, Qt.NoModifier, empty + QPoint(40, 0))
check("Daneben ziehen verschiebt die Ansicht", d.pan != pan0)
v.setFocus(); QTest.keyClick(v, Qt.Key_Left); QTest.qWait(10)
check("Pfeiltaste schiebt das Motiv 1 mm", abs(d.dx - 19) < 1.5)
d.rot_s.setValue(30); d.scale_s.setValue(150); QTest.qWait(20)
check("Größe in der Vorschau 150 %", "150 %" in d.info.text() or "Vorschau 150" in d.info.text())
size0 = w.doc.stats()["width"]
d.apply_to_design(); QTest.qWait(50)
check(f"Ins Design übernommen: breiter ({size0:.0f} → {w.doc.stats()['width']:.0f} mm)",
      w.doc.stats()["width"] > size0 * 1.2)
check("Nach dem Übernehmen steht die Vorschau wieder auf 100 %", d.scale == 100 and d.rot == 0)
w.undo(); QTest.qWait(50)
check("Rückgängig stellt die alte Größe her", abs(w.doc.stats()["width"] - size0) < 0.5)
d.reset_layout()
check("Zurücksetzen: Motiv wieder auf der Position", d.dx == 0 and d.dy == 0)
for prod in ("hoodie", "polo", "apron", "shirt_back"):
    d.prod_cb.setCurrentIndex(d.prod_cb.findData(prod)); QTest.qWait(10)
    for i in range(d.place_cb.count()):
        d.place_cb.setCurrentIndex(i)
        im = d.render_image(QSize(700, 700))
        check(f"{mockup.PRODUCTS[prod]['name']} › {d.place_cb.itemText(i)}: Motiv sichtbar", red_pixels(im) > 3)
d.prod_cb.setCurrentIndex(d.prod_cb.findData("cap")); QTest.qWait(10)

path = os.path.join(OUT, "vorschau.png")
d.save_image(path)
check("Als Bild speichern", os.path.getsize(path) > 5000)

# leeres Design
w.doc.objects = []; w.sync_items([]); w.commit(); QTest.qWait(500)
d.view.repaint()
check("Leeres Design: Hinweis statt Fehler", "Noch kein Entwurf" in d.info.text())

# Menüband passt weiterhin
over = []
for i in range(w.ribbon.count()):
    w.ribbon.setCurrentIndex(i); QTest.qWait(10)
    sa = w.ribbon.currentWidget(); sa = sa if isinstance(sa, QScrollArea) else sa.findChild(QScrollArea)
    if sa.widget().sizeHint().width() > 1440:
        over.append((w.ribbon.tabText(i), sa.widget().sizeHint().width()))
check(f"Alle Reiter passen in 1440 Pixel {over}", not over)
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
