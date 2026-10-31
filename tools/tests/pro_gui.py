"""Test (1.11): Satin-Ecken (Gehrung), Satindichte nach Breite, Unterlage nach Größe, 3D-Puff,
Maschinenstopp als Sperre bei »Farben zusammenfassen«."""
import math
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, satin, shapes
from stichwizard.api import ApiError, DesignAPI
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document, EmbObject
from shapely.geometry import Polygon
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
api = DesignAPI(w)
def sts(o):
    return [p for _, b in o.world_blocks() for p in b if p[2] == engine.STITCH]
def n_st(o):
    return len(sts(o))
def column(width, length=20):
    o = EmbObject("satin"); h = width / 2
    o.set_satin([[-length / 2, h, 0], [length / 2, h, 0]], [[-length / 2, -h, 0], [length / 2, -h, 0]])
    return o

# ============ Satin-Ecken
ln = EmbObject("line"); ln.set_points([(0, 0), (25, 0), (25, 20)])
ln.border.update(type="satin", width=4)
mitre = sts(ln)
ln.border["corner"] = "none"
plain = sts(ln)
check("Satinlinie mit Ecke: Gehrung aktiv (anderer Stichverlauf)", mitre != plain)
outer = max(p[0] for p in mitre)
check("Gehrung reicht außen bis an die Ecke (kein Loch)", outer > 26.8)
# Stiche an der Innenseite der Ecke verkürzt (kein Garnstau): Stiche im Eckbereich kürzer
corner_lens = [math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(mitre, mitre[1:])
               if 21 < (a[0] + b[0]) / 2 < 29 and -4 < (a[1] + b[1]) / 2 < 4]
check("Im Eckbereich werden Innenstiche verkürzt", min(corner_lens) < 3.0)
rails = satin.corner_rails([(0, 0), (25, 0), (25, 20)], 4)
check("Fächer-Stege an der Ecke (vor, Gehrung, nach)", rails and len(rails[2]) == 3)
check("Gerade Linie: keine Gehrung nötig", satin.corner_rails([(0, 0), (10, 0), (20, 0.5)], 4) is None)
sq = EmbObject("shape"); sq.set_geometry(shapes.rounded_rect(30, 20, 0.01)); sq.fill["type"] = "none"
sq.border.update(type="satin", width=4)
check("Rand eines Rechtecks: Ecken werden erkannt", satin.corner_rails(
    list(sq.shaped_geometry().exterior.coords), 4, True) is not None and n_st(sq) > 100)
check("Satinlinie mit Unterlage endet am Anfang (wie bisher)",
      math.hypot(*[a - b for a, b in zip(mitre[-1], (0, 0))]) < 3.0)

# ============ Satindichte nach Breite
narrow, wide = column(1.2), column(8)
nn, nw = n_st(narrow), n_st(wide)
narrow.fill["auto_spacing"] = False; wide.fill["auto_spacing"] = False
check("Schmale Säule: lockerer (weniger Stiche)", nn < n_st(narrow))
check("Breite Säule: dichter (mehr Stiche)", nw > n_st(wide))
check("Neue Objekte haben die Automatik an, alte Projekte nicht",
      EmbObject("satin").fill["auto_spacing"] and
      not EmbObject.from_dict({"kind": "satin", "fill": {}}).fill["auto_spacing"])
check("Abstandsfaktoren", abs(engine.satin_spacing({"density": 0.4, "auto_spacing": True}, 1.0) - 0.56) < 1e-6
      and engine.satin_spacing({"density": 0.4, "auto_spacing": True}, 5.0) == 0.4)

# ============ Unterlage nach Größe
thin = EmbObject("shape"); thin.set_geometry(shapes.rounded_rect(40, 3, 0.5))
a = n_st(thin); thin.fill["underlay_auto"] = False
check("Schmaler Streifen (3 mm): weniger Unterlage", a < n_st(thin))
check("Stufen: <2 mm keine, <5 mm Rand, sonst voll",
      [engine.auto_underlay(shapes.rounded_rect(40, h, 0.1), {"underlay_auto": True})
       for h in (1.5, 4, 10)] == [0, 1, 2])
big = EmbObject("shape"); big.set_geometry(shapes.rounded_rect(40, 30, 1))
b0 = n_st(big); big.fill["underlay_auto"] = False
check("Große Fläche: Unterlage unverändert", b0 == n_st(big))

# ============ 3D-Puff
flat = EmbObject("shape"); flat.set_geometry(shapes.rounded_rect(40, 30, 1)); flat.name = "Fläche"
pc = column(5); pc.name = "Puff"
txt = EmbObject("line"); txt.set_points([(0, 10), (20, 10)]); txt.border.update(type="satin", width=4)
w.doc.objects = [pc, flat, txt]; w.sync_items([pc.id, txt.id])
before = n_st(pc)
w.puff_selected()
check("Puff-Objekte zuletzt, Stopp davor", w.doc.objects[0] is flat and flat.trim_after == "stop"
      and w.doc.objects[1:] == [pc, txt])
check("Puff-Säule: dicht, Mittellinie, Endkappen", pc.fill["puff"] and pc.fill["density"] == 0.25
      and pc.fill["satin_ul"] == "center" and n_st(pc) > before)
pts = sts(pc)
check("Endkappen liegen an beiden Enden", sum(1 for p in pts if p[0] < -9.5) > 10 and
      sum(1 for p in pts if p[0] > 9.5) > 10)
check("Puff-Satinlinie ohne Unterlage", txt.border["underlay"] is False and txt.border["density"] == 0.25)
blocks = w.doc.machine_blocks()
stops = [i for i, (c, b) in enumerate(blocks) for p in b if p[2] == engine.STOP]
check("Maschinenstopp im Stickablauf", len(stops) == 1)
check("Hinweis zum Schaumstoff", "Schaumstoff" in w.lbl_tip.text())

# ============ Stopp als Sperre bei »Farben zusammenfassen«
a1 = EmbObject("shape"); a1.set_geometry(shapes.rounded_rect(10, 10, 1)); a1.x = -30
a1.fill["color"] = "#E53935"; a1.trim_after = "stop"
b1 = EmbObject("shape"); b1.set_geometry(shapes.rounded_rect(10, 10, 1)); b1.x = 0; b1.fill["color"] = "#1E88E5"
c1 = EmbObject("shape"); c1.set_geometry(shapes.rounded_rect(10, 10, 1)); c1.x = 30; c1.fill["color"] = "#E53935"
d = Document(); d.objects = [a1, b1, c1]; d.color_sort = True
d.machine_blocks()
order = [oid for oid, _, _ in d.last_order]
check("Nach einem Stopp wird nichts vorgezogen", order.index(a1.id) < order.index(b1.id) and
      order.index(a1.id) < order.index(c1.id))
a1.trim_after = "auto"; d.machine_blocks()
order = [oid for oid, _, _ in d.last_order]
check("Ohne Stopp werden gleiche Farben zusammengefasst", abs(order.index(a1.id) - order.index(c1.id)) == 1)

# ============ Oberfläche & API
w.doc.objects = [column(4)]; w.sync_items([w.doc.objects[0].id]); w.props.set_object(w.doc.objects[0])
fm = w.props.c_fine.form
check("Feinheiten (Säule): Dichte nach Breite und Puff sichtbar",
      fm.isRowVisible(w.props.x_autosp) and fm.isRowVisible(w.props.x_puff)
      and not fm.isRowVisible(w.props.x_corner))
l2 = EmbObject("line"); l2.set_points([(0, 0), (10, 0)]); w.doc.objects.append(l2); w.sync_items([l2.id])
w.props.set_object(l2)
check("Feinheiten (Satinlinie): Satin-Ecken sichtbar", fm.isRowVisible(w.props.x_corner))
w.props.x_corner.setCurrentIndex(1); w.props._apply()
check("Satin-Ecken umschaltbar", l2.border["corner"] == "none")
r = api.call("update_object", {"id": l2.id, "changes": {"border": {"corner": "mitre"},
                                                         "fill": {"puff": True}}})
check("API: corner und puff", l2.border["corner"] == "mitre" and l2.fill["puff"] is True)
try:
    api.call("update_object", {"id": l2.id, "changes": {"border": {"corner": "rund"}}}); bad = False
except ApiError:
    bad = True
check("API: ungültige Ecke abgelehnt", bad)

print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
