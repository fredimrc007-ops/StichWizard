"""Test: Illustrator-/PDF-Vektorgrafiken öffnen (AI/PDF -> Formen und Linien)."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from pypdf import PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject,
                           NameObject, NumberObject)
from stichwizard import engine, help as shelp
from stichwizard import vectorimport as vi
from stichwizard.autodigitize import IMAGE_EXTS, load_image
from stichwizard.mainwindow import MainWindow, RibbonButton
from testdata import STICK_DIR
OUT = sys.argv[1]
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)

# ---- Testdatei wie aus Illustrator: 2 Seiten, Kurven, Loch, CMYK, Schmuckfarbe, Kontur,
#      Weiß auf Schwarz, maskiertes Bild, Text
PAGE1 = b"""
q 1 0 0 1 0 0 cm
0 0.5 1 0 k
72 72 m 216 72 l 216 216 l 72 216 l h
108 108 m 108 180 l 180 180 l 180 108 l h f*
0 0 0 1 k
288 72 144 144 re f
1 1 1 rg
324 108 72 72 re f
/CS0 cs 1 scn
72 288 m 72 340 120 360 144 360 c 168 360 216 340 216 288 c h f
0 0 1 RG 5.67 w
288 288 m 432 360 l S
q 72 400 m 144 400 l 108 460 l h W n
q 72 0 0 60 72 400 cm /Im0 Do Q Q
BT /F1 12 Tf 300 500 Td (Hallo) Tj ET
Q
"""
PAGE2 = b"0 0 0 1 k 0 0 144 72 re f"
w = PdfWriter()
def add_page(content, resources):
    pg = w.add_blank_page(612, 792)
    st = DecodedStreamObject(); st.set_data(content)
    pg[NameObject("/Contents")] = w._add_object(st)
    pg[NameObject("/Resources")] = resources
    return pg
img = DecodedStreamObject(); img.set_data(bytes([255] * 64))     # volle Tinte (Separation)
fn = DictionaryObject({NameObject("/FunctionType"): NumberObject(2),
                       NameObject("/Domain"): ArrayObject([NumberObject(0), NumberObject(1)]),
                       NameObject("/C0"): ArrayObject([FloatObject(0)] * 4),
                       NameObject("/C1"): ArrayObject([FloatObject(0), FloatObject(0.8),
                                                       FloatObject(0.8), FloatObject(0)]),
                       NameObject("/N"): NumberObject(1)})
sep = ArrayObject([NameObject("/Separation"), NameObject("/Rot"), NameObject("/DeviceCMYK"), fn])
img.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(8), NameObject("/Height"): NumberObject(8),
            NameObject("/BitsPerComponent"): NumberObject(8), NameObject("/ColorSpace"): sep})
res = DictionaryObject({NameObject("/ColorSpace"): DictionaryObject({NameObject("/CS0"): sep}),
                        NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): w._add_object(img)})})
add_page(PAGE1, res)
add_page(PAGE2, DictionaryObject())
AI = os.path.join(OUT, "logo.ai")
with open(AI, "wb") as f:
    w.write(f)

d = vi.read(AI)
check(f"Seiten erkannt ({d['pages']})", d["pages"] == 2)
fills = [i for i in d["items"] if i["kind"] == "fill"]
cols = [i["color"] for i in fills]
check(f"CMYK 0/50/100/0 → Orange ({cols[0]})", cols[0] == "#FF8000")
check(f"Schmuckfarbe über Ersatzfarbe ({cols[3]})", cols[3] == "#FF3333")
check(f"Maskiertes Bild als Fläche in Bildfarbe ({cols[-1]})", cols[-1] == "#FF3333" and len(fills) == 5)
check(f"Text gemeldet ({d['info']})", d["info"]["text"] == 1 and d["info"]["images"] == 0)
lays = vi.layers(d, merge=False)
orange = next(l for l in lays if l["color"] == "#FF8000")
mm = 25.4 / 72
check(f"Loch bleibt Loch (gerade/ungerade): {orange['geom'].area:.0f} mm²",
      abs(orange["geom"].area - (144 ** 2 - 72 ** 2) * mm * mm) < 5)
black = next(l for l in lays if l["color"] == "#000000")
check(f"Weißes Rechteck darüber: Schwarz ausgespart ({black['geom'].area:.0f} mm²), Weiß weggelassen",
      abs(black["geom"].area - (144 ** 2 - 72 ** 2) * mm * mm) < 5 and
      not any(l["color"] == "#FFFFFF" for l in lays))
keep = vi.layers(d, merge=False, hide=False, drop_white=False)
check("Optionen abschaltbar: ohne Aussparen bleibt Weiß und Schwarz ganz",
      any(l["color"] == "#FFFFFF" for l in keep) and
      next(l for l in keep if l["color"] == "#000000")["geom"].area > black["geom"].area + 100)
st = [l for l in lays if l["kind"] == "stroke"]
check(f"Kontur übernommen (Breite {st[0]['width']:.1f} mm)" if st else "Kontur übernommen",
      st and abs(st[0]["width"] - 2.0) < 0.05 and st[0]["color"] == "#0000FF")
check(f"Größe des Inhalts {d['w']:.1f} × {d['h']:.1f} mm", abs(d["w"] - 144 * 2 * mm - 72 * mm) < 1)
half = vi.layers(d, scale=0.5, merge=False)
check("Skalieren halbiert die Maße", abs(next(l for l in half if l["color"] == "#FF8000")["geom"].area
                                         - orange["geom"].area / 4) < 2)
objs = vi.make_objects(lays)
shapes = [o for o in objs if o.kind == "shape"]
lines = [o for o in objs if o.kind == "line"]
check(f"{len(shapes)} Formen, {len(lines)} Linie(n), alle stickbar",
      len(shapes) == 4 and len(lines) == 1 and lines[0].border["type"] == "satin" and
      all(sum(1 for _, b in o.stitch_blocks() for p in b if p[2] == engine.STITCH) > 20 for o in objs))
d2 = vi.read(AI, page=1)
check(f"Zweite Seite lesbar ({d2['w']:.1f} mm breit)", abs(d2["w"] - 144 * mm) < 0.1)
im = load_image(AI, 800)
check("Als Bild ladbar (Vorlage, Bild-Assistent, Nachzeichnen)", im is not None and max(im.width(), im.height()) == 800
      and "ai" in IMAGE_EXTS and "pdf" in IMAGE_EXTS)
bad = os.path.join(OUT, "alt.ai")
open(bad, "w").write("%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator 8\n")
try:
    vi.read(bad); msg = ""
except vi.VectorError as e:
    msg = str(e)
check("Nicht PDF-kompatible AI-Datei: verständliche Meldung", "PDF-kompatibel" in msg)

# ---- Oberfläche
win = MainWindow(); win.resize(1440, 900); win.show(); QTest.qWait(100)
check("Menüband: »AI / PDF öffnen«", win.a_vector in {b.defaultAction() for b in win.findChildren(RibbonButton)})
seen = {}
def drive():
    dlg = next(x for x in app.topLevelWidgets() if isinstance(x, vi.VectorImportDialog) and x.isVisible())
    seen["pages"] = dlg.page.maximum()
    seen["warn"] = "Text" in dlg.info.text()
    dlg.width.setValue(80); dlg.update_preview()
    seen["fill"] = dlg.fill.findData("auto") >= 0
    dlg.accept()
QTimer.singleShot(300, drive)
win.load_path(AI)                    # wie »Öffnen« mit einer .ai-Datei
check("Öffnen einer .ai-Datei startet den Vektor-Dialog mit 2 Seiten und Text-Hinweis",
      seen.get("pages") == 2 and seen.get("warn"))
g = None
for o in win.doc.objects:
    wg = o.world_geometry()
    g = wg if g is None else g.union(wg)
b = g.bounds if g is not None else (0, 0, 0, 0)
# 4 Flächenfarben (Bildmaske und Schmuckfarbe sind gleich rot -> zusammengefasst) + 1 Kontur
check(f"{len(win.doc.objects)} Objekte übernommen, 80 mm breit, mittig ({b[0]:.1f} … {b[2]:.1f})",
      len(win.doc.objects) == 4 and abs((b[2] - b[0]) - 80) < 1.5 and abs(b[0] + b[2]) < 1.5)
win.undo()
check("Rückgängig entfernt die Grafik", not win.doc.objects)
check("Hilfe und README erklären »AI / PDF öffnen«", "AI / PDF öffnen" in shelp.GUIDE and "AI / PDF öffnen" in
      open(__file__.rsplit("/tools/", 1)[0] + "/README.md", encoding="utf-8").read())

# ---- echte Illustrator-Datei (nur lesend), falls vorhanden
real = os.path.join(STICK_DIR, "Bilddateien", "Vektordateien zu manchen Logos 20260914",
                    "dieHafnerei_mit_flame.ai")
if os.path.exists(real):
    rd = vi.read(real)
    rl = vi.layers(rd)
    check(f"Hafnerei-Logo: Flamme orange + Schrift schwarz ({sorted(l['color'] for l in rl)})",
          sorted(l["color"] for l in rl) == ["#000000", "#FC7C00"] and 140 < rd["w"] < 150)
print("ERGEBNIS:", sum(ok), "/", len(ok))
