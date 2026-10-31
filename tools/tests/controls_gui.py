"""Test (1.12): Schieberegler-Felder, zoombare Vorschau im Bild-Assistenten und Fotostich."""
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
from stichwizard.controls import SliderSpin
from stichwizard.mainwindow import MainWindow
from stichwizard.model import EmbObject
from stichwizard import shapes
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)

# ---- SliderSpin
s = SliderSpin(0.1, 2.0, 0.05, 2, " mm", value=0.4)
got = []
s.valueChanged.connect(got.append)
s.slider.setValue(s.slider.maximum())
check("Regler ganz rechts = Höchstwert", abs(s.value() - 2.0) < 1e-9 and got and abs(got[-1] - 2.0) < 1e-9)
s.setValue(1.0)
check("Zahlenfeld stellt den Regler nach", abs(s.slider.value() / s.slider.maximum() - (0.9 / 1.9)) < 0.01)
inv = SliderSpin(0.1, 2.0, 0.05, 2, value=0.4, invert=True)
inv.slider.setValue(inv.slider.maximum())
check("Umgekehrter Regler: rechts = kleinster Wert (fein)", abs(inv.value() - 0.1) < 1e-9)
iv = SliderSpin(1, 16, 1, integer=True, value=5)
iv.slider.setValue(iv.slider.maximum())
check("Ganzzahl-Regler", iv.value() == 16 and isinstance(iv.value(), int))

# ---- Eigenschaften
o = EmbObject("shape"); o.set_geometry(shapes.rounded_rect(30, 20, 2))
w.doc.objects = [o]; w.sync_items([o.id]); w.props.set_object(o)
p = w.props
check("Winkel, Dichte, Stichlänge mit Regler", all(isinstance(x, SliderSpin) for x in
                                                   (p.f_angle, p.f_density, p.f_len, p.f_pull)))
check("Position und Größe ohne Regler", not isinstance(p.x, SliderSpin) and not isinstance(p.w, SliderSpin))
p.f_angle.slider.setValue(p.f_angle.slider.minimum())
QTest.qWait(500)
check("Regler ändert das Objekt", o.fill["angle"] == -180)
check("Leiste nicht zu breit", p.widget().minimumSizeHint().width() <= p.viewport().width())

# ---- Bild-Assistent
img = QImage(300, 200, QImage.Format_RGB32); img.fill(QColor("white"))
pa = QPainter(img); pa.setBrush(QColor("#C62828")); pa.drawEllipse(40, 30, 120, 120)
pa.setBrush(QColor("#1565C0")); pa.drawRect(170, 60, 100, 90); pa.end()
path = OUT + "/bild.png"; img.save(path)
from stichwizard.autodigitize import DigitizeDialog
d = DigitizeDialog(w); d.show(); d.load(path); QTest.qWait(200)
check("Original und Ergebnis werden angezeigt", d.orig.has_image() and d.prev.has_image() and d.objects)
d.prev.zoom_by(3); QTest.qWait(50)
check("Zoom gekoppelt", abs(d.prev.zoom_factor() - 3) < 0.01 and abs(d.orig.zoom_factor() - 3) < 0.01)
d.linked.setChecked(False); d.prev.zoom_by(2); QTest.qWait(50)
check("Entkoppelt zoomt nur eine Ansicht", abs(d.prev.zoom_factor() - 6) < 0.05 and abs(d.orig.zoom_factor() - 3) < 0.05)
d.prev.fit(); QTest.qWait(20)
check("Einpassen", abs(d.prev.zoom_factor() - 1) < 0.01)
d.show_mode.setCurrentIndex(1); QTest.qWait(200)
check("Stich-Vorschau in hoher Auflösung", d.prev.item.pixmap().width() >= 1000)
n0 = sum(len(b) for x in d.objects for _, b in x.stitch_blocks())
d.detail.slider.setValue(d.detail.slider.maximum()); d.update_preview()
n1 = sum(len(b) for x in d.objects for _, b in x.stitch_blocks())
check(f"Feinere Detailgenauigkeit = mehr Details ({n0} → {n1} Stiche)", abs(d.detail.value() - 0.1) < 1e-9 and n1 > n0)
d.reject()

# ---- Fotostich
from stichwizard.photostitch import PhotoStitchDialog
ph = PhotoStitchDialog(w); ph.show(); ph.load(path); QTest.qWait(300)
check("Fotostich: Foto und Stickerei zoombar", ph.orig_panel.view.has_image() and ph.preview.has_image())
ph.preview.zoom_by(2); QTest.qWait(30)
check("Fotostich: Ansichten gekoppelt", abs(ph.orig_panel.view.zoom_factor() - 2) < 0.05)
check("Fotostich: Regler", isinstance(ph.detail, SliderSpin) and isinstance(ph.colors, SliderSpin))
ph.reject()

# ---- Einstellungen
from stichwizard.prefs import SettingsDialog
sd = SettingsDialog(w.prefs, w, w.action_catalog())
check("Einstellungen: Regler für Sprunglänge und Kurvenanpassung",
      isinstance(sd.trim_dist, SliderSpin) and isinstance(sd.curve_tol, SliderSpin))
sd.reject()
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
