"""Test (1.29): Mal-Atelier (Pinsel, Formen, Füllen, Radierer, Rückgängig, Bild laden) und
Druck-Applikation (Druckbild-Objekt, Umriss Rechteck/Oval/Motiv, Applikationsstiche mit Stopps,
Druckvorlage-PDF, Speichern/Laden, Bearbeiten per Doppelklick, Vorlage, Bild-Assistent)."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
import numpy as np
import pyembroidery as pe
from shapely.geometry import Point
from stichwizard import engine, fileio, printapp
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document
from stichwizard.paintdialog import PPM, PaintDialog
from stichwizard.render import render_document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)


def px(img, x_mm, y_mm):
    return img.pixelColor(int(x_mm * PPM), int(y_mm * PPM)).name().upper()


# ---- Mal-Atelier
d = PaintDialog(w, None, (80, 60))
check("Neues Bild 80 × 60 mm, weiß", d.img.width() == 640 and d.img.height() == 480 and
      px(d.img, 40, 30) == "#FFFFFF")
d.set_color("#1E88E5"); d.set_tool("rect"); d.filled.setChecked(True)
d.snapshot()
pa = QPainter(d.img); d.draw_shape(pa, QPointF(80, 80), QPointF(240, 240)); pa.end()
check("Rechteck gefüllt", px(d.img, 20, 20) == "#1E88E5")
d.set_color("#E53935")
d.snapshot(); d.fill(500, 400)
check("Füllen färbt den weißen Bereich, nicht das Rechteck",
      px(d.img, 70, 50) == "#E53935" and px(d.img, 20, 20) == "#1E88E5")
d.set_color("#000000"); d.set_tool("brush"); d.snapshot(); d.stroke(QPointF(300, 50), QPointF(600, 50))
check("Pinselstrich", d.img.pixelColor(450, 50).name().upper() == "#000000")
d.undo()
check("Rückgängig nimmt den Pinselstrich zurück", d.img.pixelColor(450, 50).name().upper() == "#E53935")
d.undo()
check("Rückgängig: Füllen zurück", px(d.img, 70, 50) == "#FFFFFF")
d.redo()
check("Wiederholen: Füllen wieder da", px(d.img, 70, 50) == "#E53935")
d.set_tool("erase"); d.snapshot(); d.stroke(QPointF(600, 400), QPointF(600, 400))
check("Radierer macht durchsichtig", d.img.pixelColor(600, 400).alpha() == 0)
src = QImage(200, 100, QImage.Format_ARGB32); src.fill(QColor("#43A047"))
sp = os.path.join(OUT, "gruen.png"); src.save(sp)
d.load_image(sp)
check("Bild laden: Seitenverhältnis übernommen (80 × 40 mm)", d.h_mm == 40 and
      px(d.img, 40, 20) == "#43A047")
d.w_spin.setValue(120); d.h_spin.setValue(60); d.resize_image()
check("Größe ändern skaliert das Bild", d.img.width() == 960 and px(d.img, 100, 50) == "#43A047")

# ---- Umriss
circ = QImage(400, 400, QImage.Format_ARGB32); circ.fill(Qt.transparent)
pp = QPainter(circ); pp.setRenderHint(QPainter.Antialiasing); pp.setBrush(QColor("#E53935"))
pp.setPen(Qt.NoPen); pp.drawEllipse(QRectF(100, 100, 200, 200)); pp.end()
g = printapp.outline(circ, 50, 50, "motif")
check(f"Motiv-Umriss folgt dem Kreis (Fläche {g.area:.0f} ≈ {3.1416 * 13.7 ** 2:.0f} mm²)",
      abs(g.area - 3.1416 * 13.7 ** 2) < 90 and g.contains(Point(0, 0)))
r = printapp.outline(circ, 50, 50, "rect")
o = printapp.outline(circ, 50, 50, "oval")
check("Rechteck/Oval 1 mm innerhalb des Bildrands",
      abs(r.bounds[2] - 24) < 0.01 and abs(o.bounds[3] - 24) < 0.1)

# ---- Druck-Applikation
po = printapp.make(circ, 50, 50)
po.x, po.y = 10, -5
ap = printapp.applique(po, "motif", "#3E2723", 3.0)
check("Applikation in derselben Gruppe, an der Bildstelle",
      ap.group == po.group and ap.fill["type"] == "applique" and ap.fill["print"] and
      abs(ap.x - 10) < 1 and abs(ap.y + 5) < 1)
parts = ap.stitch_blocks()
check(f"Applikationsstiche: Platzierung, Heftstich, Satin ({len(parts)} Teile)", len(parts) == 3)
check("Druckbild selbst wird nicht gestickt", not po.stitch_blocks())
doc = Document(); doc.objects = [po, ap]
pes = os.path.join(OUT, "druck.pes")
fileio.export_file(doc, pes)
pat = pe.read(pes)
stops = sum(1 for s in pat.stitches if s[2] & pe.COMMAND_MASK in (pe.STOP, pe.COLOR_CHANGE))
check(f"PES: Maschine hält zum Auflegen und Zurückschneiden an ({stops})", stops >= 2)
img = render_document(doc, 4)
c = img.pixelColor(int(img.width() / 2), int(img.height() / 2)).name().upper()
check(f"PNG-Bild zeigt das Druckbild unter den Stichen ({c})", c == "#E53935")
d2 = Document(); d2.load_json(doc.to_json())
p2 = next(o for o in d2.objects if o.kind == "print")
check("Speichern/Laden behält das Bild", p2.image == po.image and
      printapp.image_of(p2).width() == 400)
pdf = os.path.join(OUT, "druck.pdf")
check("Druckvorlage PDF", printapp.export_sheet(doc, pdf) == 1 and
      open(pdf, "rb").read(5) == b"%PDF-" and os.path.getsize(pdf) > 3000)
check("Druckvorlage gespiegelt", printapp.export_sheet(doc, os.path.join(OUT, "sp.pdf"), True) == 1)

# ---- im Programm
def fake_exec(self):
    self.set_color("#8E24AA"); self.set_tool("ellipse"); self.filled.setChecked(True)
    pa = QPainter(self.img); self.draw_shape(pa, QPointF(100, 100), QPointF(500, 400)); pa.end()
    self.outline.setCurrentIndex(self.outline.findData("motif"))
    self.accept()
    return 1
PaintDialog.exec = fake_exec
w.doc.objects = []; w.sync_items(); w.commit()
w.open_paint()
objs = list(w.doc.objects)
pr = next((o for o in objs if o.kind == "print"), None)
apl = next((o for o in objs if o.kind == "shape"), None)
check("Mal-Atelier fügt Druckbild + Applikation ein", pr and apl and len(objs) == 2 and
      pr.group == apl.group)
area0 = apl.world_geometry().area
w.scene.clearSelection(); w.items[pr.id].setSelected(True); QTest.qWait(5)
w.props.set_object(pr)
check("Eigenschaften zeigen die Karte »Druckbild«", w.props.c_print.isVisibleTo(w.props))
def edit_exec(self):
    self.clear(False)
    self.set_color("#8E24AA"); self.set_tool("rect"); self.filled.setChecked(True)
    pa = QPainter(self.img); self.draw_shape(pa, QPointF(50, 50), QPointF(150, 150)); pa.end()
    self.accept(); return 1
PaintDialog.exec = edit_exec
w.canvas.crossRequested.emit(pr)
check(f"Doppelklick: Bild bearbeitet, Applikation folgt ({apl.world_geometry().area:.0f} < {area0:.0f})",
      apl.world_geometry().area < area0 * 0.5)
w.undo(); QTest.qWait(5)
check("Rückgängig nach dem Bearbeiten",
      abs(next(o for o in w.doc.objects if o.kind == "shape").world_geometry().area - area0) < 1)
pdf2 = os.path.join(OUT, "vorlage.pdf")
w.export_print_sheet(pdf2, False)
check("Druckvorlage aus dem Programm", os.path.exists(pdf2))
def tpl_exec(self):
    self.use_combo.setCurrentIndex(self.use_combo.findData("template")); self.accept(); return 1
PaintDialog.exec = tpl_exec
w.doc.objects = []; w.sync_items(); w.commit()
w.open_paint()
check("Als Vorlage zum Nachzeichnen", w.doc.template and w.doc.template["width"] > 0 and
      not w.doc.objects)
calls = []
w.digitize_image = lambda path=None: calls.append(os.path.exists(path) and QImage(path).width() > 0)
def dig_exec(self):
    self.use_combo.setCurrentIndex(self.use_combo.findData("digitize")); self.accept(); return 1
PaintDialog.exec = dig_exec
w.open_paint()
check("Mit dem Bild-Assistenten: Bild wird übergeben", calls == [True])
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
