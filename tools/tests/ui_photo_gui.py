"""Test: ein Fenster für Simulator/Optimierer, Oberfläche anpassen, Fotostich."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPalette, QRadialGradient
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QScrollArea, QTabWidget
OUT = sys.argv[1]
from testdata import hafnerei_project
app = QApplication(sys.argv); app.setStyle('Fusion')
from stichwizard.__main__ import apply_light_palette
apply_light_palette(app)
from stichwizard.mainwindow import MainWindow, RibbonButton
from stichwizard.model import Document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
w.open_document(hafnerei_project(OUT))
# --- Simulator und Optimierer: eine Funktion
seen = []
orig = QDialog.exec
QDialog.exec = lambda self: seen.append(self.windowTitle()) or 0
w.a_sim.trigger(); w.a_optimizer.trigger()
QDialog.exec = orig
check(f"F5 und F6 öffnen dasselbe Fenster: {seen}", len(seen) == 2 and seen[0] == seen[1])
btn_opt = [b for b in w.findChildren(RibbonButton) if b.defaultAction() is w.a_optimizer]
check("Kein zweiter Optimierer-Knopf im Menüband", not btn_opt)
from stichwizard.optimizer_dialog import OptimizerDialog
d = OptimizerDialog(w, "Stick-Simulator & Optimierer")
texts = [b.text() for b in d.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)]
check("Klare Beschriftung der Sammel-Schnitte", any("Schnitt setzen bei Sprüngen ab" in t for t in texts)
      and any("Schnitt entfernen bei Sprüngen unter" in t for t in texts))
d.resize(1360, 860); d.show(); QTest.qWait(30)
cb = d.auto_order
check("Haken-Text passt vollständig", cb.width() >= cb.sizeHint().width() - 2)
d.close()
# --- Menüband: kein Reiter läuft bei 1440 px über
r = w.findChild(QTabWidget, "ribbon")
over = []
for i in range(r.count()):
    r.setCurrentIndex(i); QTest.qWait(20)
    sa = r.currentWidget()
    if isinstance(sa, QScrollArea) and sa.horizontalScrollBar().maximum() > 0:
        over.append(r.tabText(i))
check(f"Alle Reiter passen in 1440 px Breite (zu breit: {over or 'keiner'})", not over)
r.setCurrentIndex(0)
# --- Werkzeugleiste vollständig sichtbar
tb = w.toolstrip
vis = [a for a in tb.actions() if not a.isSeparator()]
hidden = [a.text() for a in vis if not tb.widgetForAction(a) or not tb.widgetForAction(a).isVisible()
          or tb.widgetForAction(a).geometry().bottom() > tb.height()]
check(f"Werkzeugleiste: alle {len(vis)} Knöpfe sichtbar (fehlen: {hidden or 'keine'})", not hidden)
# --- Oberfläche anpassen
P = w.prefs
P.set("ui_theme", "dark"); P.set("ui_ribbon", "icons"); P.set("ui_toolbar", "right")
P.set("ui_side", "left"); P.set("ui_palette", False); P.set("ui_font", 12.5)
P.set("ui_favorites", "a_photo,a_sheet,tool:satin")
w.apply_ui(); QTest.qWait(30)
check("Dunkles Farbschema", app.palette().color(QPalette.Window).lightness() < 80)
check("Favoriten-Reiter mit 3 Knöpfen",
      r.tabText(0) == "★ Favoriten" and len(r.widget(0).findChildren(RibbonButton)) == 3)
order = [w.mid.widget(i) for i in range(w.mid.count())]
check("Seitenleiste links, Werkzeugleiste rechts",
      order.index(w.side) < order.index(w.canvas) < order.index(w.toolstrip))
check("Garnfarben-Leiste ausgeblendet", not w.palette_bar.isVisible())
check("Menüband nur Symbole", all(b.toolButtonStyle() == Qt.ToolButtonIconOnly for b in w.findChildren(RibbonButton)))
check("Größere Schrift", "13.8pt" in w.styleSheet() or "12.5pt" in w.styleSheet())
w.grab().save(os.path.join(OUT, "oberflaeche.png"))
from stichwizard.prefs import SettingsDialog
sd = SettingsDialog(P, w, w.action_catalog(), "Oberfläche")
check(f"Einstellungen › Oberfläche mit {sd.fav_list.count()} Funktionen zur Auswahl",
      sd.tabs.tabText(sd.tabs.currentIndex()) == "Oberfläche" and sd.fav_list.count() > 60)
sd.fav_list.item(0).setCheckState(Qt.Checked); sd.accept()
check("Favoriten werden gespeichert", sd.fav_list.item(0).data(Qt.UserRole) in P.get("ui_favorites"))
for k in ("ui_theme", "ui_ribbon", "ui_toolbar", "ui_side", "ui_palette", "ui_font", "ui_favorites"):
    P.qs.remove("prefs/" + k)
w.apply_ui(); QTest.qWait(20)
check("Zurück auf Standard (hell, Favoriten weg)", app.palette().color(QPalette.Window).lightness() > 200
      and not r.tabText(0).startswith("★"))
# --- Fotostich
img = QImage(600, 450, QImage.Format_ARGB32)
p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
img.fill(QColor("#9FD3E8"))
g = QRadialGradient(QPointF(300, 220), 170); g.setColorAt(0, QColor("#FFE0B2")); g.setColorAt(1, QColor("#7B4A1E"))
p.setBrush(QBrush(g)); p.setPen(Qt.NoPen); p.drawEllipse(QPointF(300, 220), 150, 180)
p.setBrush(QColor("#111111")); p.drawEllipse(QPointF(250, 190), 20, 14); p.drawEllipse(QPointF(350, 190), 20, 14)
p.end()
from stichwizard.photostitch import PhotoStitchDialog, color_photo, hatch_photo
objs = color_photo(img, 80, 6, 0.4)
dd = Document(); dd.objects = objs
st = dd.stats()
lum = [QColor(o.fill["color"]).lightness() for o in objs]
check(f"Farbiger Fotostich: {len(objs)} Lagen, {st['stitches']} Stiche, hell → dunkel",
      3 <= len(objs) <= 6 and st["stitches"] > 3000 and lum == sorted(lum, reverse=True))
h = hatch_photo(img, 80, 1.4)
dh = Document(); dh.objects = h
sh = dh.stats()
check(f"Linienschraffur: {sh['stitches']} Stiche, 1 Farbe", len(h) == 1 and sh["stitches"] > 1000 and sh["colors"] == 1)
dlg = PhotoStitchDialog(w, 130)
dlg.img = img; dlg.update_preview()
check("Fotostich-Dialog: Vorschau und Werte", dlg.preview.has_image() and "Stiche" in dlg.info.text())
dlg.mode.setCurrentIndex(1); dlg.update_preview()
from PySide6.QtWidgets import QFormLayout
form = dlg.findChild(QFormLayout)
check("Umschalten auf Schraffur zeigt passende Felder",
      form.isRowVisible(dlg.spacing) and form.isRowVisible(dlg.thread) and not form.isRowVisible(dlg.colors))
n0 = len(w.doc.objects)
QDialog.exec = lambda self: 1
w.photo_stitch.__func__  # vorhanden
import stichwizard.photostitch as ps
orig_init = ps.PhotoStitchDialog.__init__
def patched(self, *a, **k):
    orig_init(self, *a, **k)
    self.img = img
    self.update_preview()
ps.PhotoStitchDialog.__init__ = patched
w.a_photo.trigger()
QDialog.exec = orig
check(f"Fotostich ins Design übernommen ({n0} → {len(w.doc.objects)} Objekte)", len(w.doc.objects) > n0)
print("ERGEBNIS:", sum(ok), "/", len(ok))
