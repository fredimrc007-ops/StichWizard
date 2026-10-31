"""Test: Bitmap nachzeichnen (wie Inkscape) – Modi, Feinregler, Vorlage deckungsgleich, Menüband."""
import base64
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, help as shelp, trace
from stichwizard.mainwindow import MainWindow, RibbonButton
OUT = sys.argv[1]
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)

# Testbild 900 × 600 px: Kreis schwarz, Rechteck rot, Rechteck grau, Bogenlinie, Flecken
img = QImage(900, 600, QImage.Format_ARGB32); img.fill(QColor("white"))
p = QPainter(img); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen)
p.setBrush(QColor("#111111")); p.drawEllipse(QPointF(200, 250), 150, 150)
p.setBrush(QColor("#D32F2F")); p.drawRect(QRectF(450, 80, 300, 200))
p.setBrush(QColor("#888888")); p.drawRect(QRectF(450, 330, 300, 120))
for i in range(8):
    p.setBrush(QColor("#000000")); p.drawEllipse(QPointF(460 + i * 35, 520), 2.5, 2.5)
p.setPen(QPen(QColor("#111111"), 8, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
p.drawArc(QRectF(60, 440, 300, 300), 30 * 16, 120 * 16)
p.end()
W = 90.0
mm = W / 900                      # mm je Bildpunkt
def run(**o):
    return trace.trace(img, dict({"width": W}, **o))
def areas(r):
    return [round(l["geom"].area) for l in r["layers"] if l["rings"]]

# ---- Helligkeitsschwelle
r = run(mode="brightness", threshold=0.3)
circle = 3.1416 * (150 * mm) ** 2
check(f"Helligkeitsschwelle 30 %: nur Dunkles (Fläche {areas(r)}, Kreis ≈ {circle:.0f} mm²)",
      len(r["layers"]) == 1 and circle < r["layers"][0]["geom"].area < circle + 120)
r2 = run(mode="brightness", threshold=0.6)
check("Schwelle 60 % nimmt auch Rot und Grau dazu", r2["layers"][0]["geom"].area > r["layers"][0]["geom"].area + 500)
ri = run(mode="brightness", threshold=0.3, invert=True, speckles=0)
check("Invertieren zeichnet das Helle nach", ri["layers"][0]["geom"].area > 90 * 60 * 0.5)
# ---- Flecken
n_parts = lambda r: len(engine.polygons_of(r["layers"][0]["geom"]))
a, b = n_parts(run(mode="brightness", threshold=0.3, speckles=0)), n_parts(run(mode="brightness", threshold=0.3, speckles=1.0))
check(f"Flecken unterdrücken entfernt die Punkte ({a} → {b} Teile)", a >= b + 8)
# ---- Ecken glätten und Toleranz steuern die Knoten
nodes = lambda **o: run(mode="brightness", threshold=0.3, **o)["nodes"]
sharp, smooth = nodes(smooth=0), nodes(smooth=1.0)
r0 = run(mode="brightness", threshold=0.3, smooth=0)
curve_nodes = sum(1 for l in r0["layers"] for ring in l["rings"] for q in ring if q[2] == 1)
check(f"Ecken glätten 0: nur Eckpunkte ({curve_nodes} Rundungen)", curve_nodes == 0)
r1 = run(mode="brightness", threshold=0.3, smooth=1.0)
check("Ecken glätten 1: Kreis aus Rundungspunkten",
      sum(1 for l in r1["layers"] for ring in l["rings"] for q in ring if q[2] == 1) > 6)
fine, coarse = nodes(tolerance=0.05), nodes(tolerance=0.6)
check(f"Toleranz: genauer = mehr Knoten ({coarse} → {fine})", fine > coarse * 1.5)
dev = r1["layers"][0]["geom"].symmetric_difference(r0["layers"][0]["geom"]).area
check(f"Geglätteter Pfad bleibt nah am Pixelpfad (Abweichung {dev:.1f} mm²)", 0 < dev < 25)
# ---- Kanten und Mittellinie
re = run(mode="edges", edge=0.25)
check(f"Kantenerkennung: schmale Konturflächen ({areas(re)} mm²)",
      re["layers"] and re["layers"][0]["geom"].area < r2["layers"][0]["geom"].area * 0.5)
rc = run(mode="centerline", threshold=0.3)
lines = rc["layers"][0]["lines"]
check(f"Mittellinie: Bogen wird Linie ({len(lines)} Linien)", any(len(ln) >= 3 for ln in lines))
# ---- Mehrere Scans
rcol = run(mode="colors", scans=4)
cols = [l["color"] for l in rcol["layers"]]
check(f"Farben: Schwarz, Rot, Grau getrennt, Weiß als Hintergrund weg ({cols})",
      len(cols) == 3 and "#D32F2F" in cols and any(c.startswith("#88") or c.startswith("#89") for c in cols))
rmix = run(mode="colors", scans=4, drop_mix=True)
check("Kantenfarben zusammenfassen ist abschaltbar (sonst verschwindet Grau)", len(rmix["layers"]) <= len(rcol["layers"]))
rs = run(mode="steps", scans=3)
check(f"Helligkeitsstufen: {len(rs['layers'])} Ebenen", len(rs["layers"]) == 2)
rst = run(mode="steps", scans=3, stack=True)
check("Stapeln: hellere Stufe reicht unter die dunklere (wird zuerst gestickt)",
      rst["layers"][0]["geom"].area > rs["layers"][0]["geom"].area + 100
      and rst["layers"][0]["geom"].area > rst["layers"][-1]["geom"].area)
rg = run(mode="grays", scans=3)
check("Graustufen: graue Garnfarben", all(l["color"][1:3] == l["color"][3:5] == l["color"][5:7] for l in rg["layers"]))
rbg = run(mode="grays", scans=3, remove_bg=False)
check("Hintergrund behalten = eine Ebene mehr", len(rbg["layers"]) == len(rg["layers"]) + 1)
# ---- Objekte
objs = trace.make_objects(rcol, {"output": "fill"})
check(f"Flächen als Tatami in Bildfarbe ({len(objs)})",
      len(objs) == 3 and all(o.fill["type"] == "tatami" for o in objs)
      and all(sum(1 for _, b in o.stitch_blocks() for s in b if s[2] == 0) > 50 for o in objs))
outl = trace.make_objects(rcol, {"output": "satin", "line_width": 2})
check("Umriss als Satinrand ohne Füllung",
      all(o.fill["type"] == "none" and o.border["type"] == "satin" for o in outl))
ln = trace.make_objects(rc, {"output": "lines"})
check("Mittellinien als Steppstich-Linien", ln and all(o.kind == "line" and o.border["type"] == "run" for o in ln))

# ---- Oberfläche
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
check("Menüband: »Bitmap nachzeichnen«", w.a_trace in {b.defaultAction() for b in w.findChildren(RibbonButton)})
ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG")
w.doc.template = {"png": bytes(ba.toBase64()).decode("ascii"), "x": 10.0, "y": -5.0, "width": 80.0,
                  "opacity": 0.5, "visible": True, "locked": True}
w.apply_template()
seen = {}
def drive():
    from stichwizard.trace import TraceDialog
    d = next(x for x in app.topLevelWidgets() if isinstance(x, TraceDialog) and x.isVisible())
    seen["aligned"] = d.align.isChecked() and abs(d.width.value() - 80) < 0.01
    d.mode.setCurrentIndex(d.mode.findData("colors")); d.scans.setValue(4)
    d.view.setCurrentIndex(d.view.findData("outline")); d.update_preview()
    seen["rows"] = d.form.isRowVisible(d.scans) and not d.form.isRowVisible(d.threshold)
    seen["info"] = d.info.text()
    d.view.setCurrentIndex(d.view.findData("stitches")); QTest.qWait(10)
    seen["stitches"] = "Stiche" in d.info.text()
    d.accept()
QTimer.singleShot(300, drive)
w.trace_bitmap()
check("Vorlage wird übernommen, »Genau auf die Vorlage legen« an", seen.get("aligned"))
check("Regler passend zum Modus ein-/ausgeblendet", seen.get("rows"))
check(f"Info zeigt Ebenen und Knoten ({seen.get('info')})", "Knoten" in seen.get("info", ""))
check("Stich-Ansicht zählt Stiche", seen.get("stitches"))
objs = [o for o in w.doc.objects]
g = None
for o in objs:
    wg = o.world_geometry()
    g = wg if g is None else g.union(wg)
bx = g.bounds if g is not None else (0, 0, 0, 0)
# Kreis 50–350 px, Bild 900 px breit → x: 10 − 40 + 50·80/900 = −25,6
left = 10 - 40 + 50 * 80 / 900
check(f"{len(objs)} Objekte deckungsgleich auf der Vorlage (links {bx[0]:.1f} ≈ {left:.1f} mm)",
      len(objs) == 3 and abs(bx[0] - left) < 0.6)
w.undo()
check("Rückgängig entfernt das Nachgezeichnete", not w.doc.objects)
check("Hilfe erklärt »Bitmap nachzeichnen«", "Bitmap nachzeichnen" in shelp.GUIDE and "Ecken glätten" in shelp.GUIDE)
readme = open(__file__.rsplit("/tools/", 1)[0] + "/README.md", encoding="utf-8").read()
check("README erwähnt »Bitmap nachzeichnen«", "Bitmap nachzeichnen" in readme)
print("ERGEBNIS:", sum(ok), "/", len(ok))
