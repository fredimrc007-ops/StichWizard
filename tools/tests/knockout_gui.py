"""Test (1.19): Automatisch aussparen – verdeckte Bereiche live und ohne die Form zu ändern
auslassen (Motiv darüberschieben, wegschieben, je Objekt aus, Rand, Schrift, Speichern/Laden,
Rückgängig, Geschwindigkeit)."""
import os
import sys
import time
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, shapes
from stichwizard.mainwindow import MainWindow, RibbonButton
from stichwizard.model import EmbObject
from shapely.geometry import Point, box
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)

def rect(wd, ht, x=0.0, y=0.0, color="#43A047"):
    o = EmbObject("shape"); o.set_geometry(shapes.rounded_rect(wd, ht, 1)); o.x, o.y = x, y
    o.fill["color"] = color
    return o
def n_st(o, block=None):
    return sum(1 for i, (_, s) in enumerate(o.stitch_blocks()) if block is None or i == block
               for p in s if p[2] == engine.STITCH)
def drawn(o):
    """Stiche, die das Objekt auf der Arbeitsfläche zeichnet (ObjectItem)."""
    return sum(len(lines) + 1 for _, lines, _ in w.items[o.id].blocks if lines)
def machine():
    return sum(1 for _, s in w.doc.machine_blocks() for p in s if p[2] == engine.STITCH)
def under(o, x, y, r):
    """Stiche der Fläche o im Quadrat ±r um (x, y)."""
    return sum(1 for _, s in o.world_blocks() for p in s
               if p[2] == engine.STITCH and abs(p[0] - x) < r and abs(p[1] - y) < r)
def drag(o, x, y):
    """Objekt mit der Maus an (x, y) ziehen (Auswahlwerkzeug)."""
    w.set_tool("select"); w.scene.clearSelection()
    vp = w.canvas.viewport()
    a = w.canvas.mapFromScene(QPointF(o.x, o.y))
    b = w.canvas.mapFromScene(QPointF(x, y))
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, a); QTest.qWait(10)
    for k in range(1, 6):
        QTest.mouseMove(vp, a + (b - a) * k / 5); QTest.qWait(5)
    t = time.perf_counter()
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, b); QTest.qWait(10)
    return time.perf_counter() - t

# ---- Menüband
r = w.ribbon
tab = [r.tabText(i) for i in range(r.count())
       if any(b.defaultAction() is w.a_knockout for b in r.widget(i).findChildren(RibbonButton))]
check(f"»Automatisch aussparen« im Reiter Optimieren {tab}", tab == ["Optimieren"])
check("Schalter zum Ein-/Ausschalten", w.a_knockout.isCheckable() and not w.a_knockout.isChecked())

low = rect(60, 40); top = rect(30, 30, 80, 0, color="#FDD835")
w.doc.objects = [low, top]; w.sync_items([]); w.commit()
full, area = n_st(low), low.world_geometry().area
w.a_knockout.trigger(); QTest.qWait(10)
check("Eingeschaltet: Dokument-Schalter gesetzt", w.doc.knockout and w.a_knockout.isChecked())
check("Nichts verdeckt: Fläche vollständig", n_st(low) == full)

# ---- Motiv über die Fläche schieben
dt = drag(top, 0, 0)
check(f"Motiv mit der Maus verschoben ({top.x:.1f}, {top.y:.1f})", abs(top.x) < 0.6 and abs(top.y) < 0.6)
cut = n_st(low)
check(f"Darunter weniger Stiche ({full} → {cut})", cut < full * 0.85)
check("Unter dem Motiv keine Stiche (1 mm Überlappung bleibt)",
      under(low, top.x, top.y, 13.5) == 0 and under(low, top.x, top.y, 15.5) > 0)
check("Form selbst unverändert (nicht destruktiv)", abs(low.world_geometry().area - area) < 1e-6
      and low.world_geometry().geom_type == "Polygon" and not low.world_geometry().interiors)
check(f"Arbeitsfläche zeigt die Aussparung ({drawn(low)} Stiche gezeichnet)",
      abs(drawn(low) - cut) <= 2)
mb = machine()
check(f"Simulator/Export: dieselben Stiche ({mb} = {cut} + {n_st(top)})", mb <= cut + n_st(top)
      and mb > (cut + n_st(top)) * 0.97)
check(f"Loslassen geht flott ({dt * 1000:.0f} ms)", dt < 1.5)

# ---- ein Stück weiter: die Aussparung wandert mit
drag(top, 12, 5)
check(f"Aussparung wandert mit ({top.x:.1f}, {top.y:.1f})", under(low, top.x, top.y, 13.5) == 0
      and under(low, -10, 0, 2) > 0)

# ---- Rückgängig / Wiederholen
w.undo(); QTest.qWait(10)
low, top = w.doc.objects
check(f"Rückgängig: Motiv zurück, Aussparung zurück ({n_st(low)})",
      abs(top.x) < 0.6 and n_st(low) == cut and abs(drawn(low) - cut) <= 2)
w.undo(); QTest.qWait(10)
low, top = w.doc.objects
check(f"Rückgängig bis vor das Verschieben: wieder vollständig ({n_st(low)})",
      top.x > 70 and w.doc.knockout and n_st(low) == full and abs(drawn(low) - full) <= 2)
w.redo(); QTest.qWait(10)
low, top = w.doc.objects
check("Wiederholen: wieder ausgespart", abs(top.x) < 0.6 and n_st(low) == cut
      and abs(drawn(low) - cut) <= 2)

# ---- wegschieben
drag(top, 0, 60)
check(f"Weggeschoben: wieder vollständig ({n_st(low)})", n_st(low) == full and
      abs(drawn(low) - full) <= 2)
drag(top, 0, 0)

# ---- je Objekt abschaltbar (Eigenschaften › Füllstich)
w.scene.clearSelection(); w.items[low.id].setSelected(True); QTest.qWait(10)
p = w.props
check("Häkchen in den Eigenschaften sichtbar und gesetzt",
      p.c_fill.form.isRowVisible(p.f_knock) and p.f_knock.isChecked())
p.f_knock.setChecked(False); p._timer.stop(); p._apply(); QTest.qWait(10)
check(f"Für das Objekt abgeschaltet: vollständig ({n_st(low)})",
      low.fill["knockout"] is False and n_st(low) == full and abs(drawn(low) - full) <= 2)
p.f_knock.setChecked(True); p._timer.stop(); p._apply(); QTest.qWait(10)
check("Wieder eingeschaltet: ausgespart", n_st(low) == cut)
w.items[low.id].setSelected(False); w.items[top.id].setSelected(True); QTest.qWait(10)
check("Häkchen auch beim oberen Objekt (Fläche)", p.c_fill.form.isRowVisible(p.f_knock))

# ---- Überlappung einstellen
QInputDialog.getDouble = staticmethod(lambda *a, **k: (2.5, True))
w.set_knockout_margin()
check(f"Überlappung 2,5 mm: weniger ausgespart ({n_st(low)} > {cut})",
      w.doc.knockout_margin == 2.5 and n_st(low) > cut and under(low, 0, 0, 11.5) == 0
      and under(low, 0, 0, 13.5) > 0)
QInputDialog.getDouble = staticmethod(lambda *a, **k: (1.0, True))
w.set_knockout_margin()
check("Zurück auf 1 mm", n_st(low) == cut)

# ---- Speichern / Laden
path = os.path.join(OUT, "aussparen.stickproj")
w.path = path; w.save_doc()
w.new_doc(); QTest.qWait(10)
check("Neues Design: aus", not w.doc.knockout and not w.a_knockout.isChecked())
w.open_document(path); QTest.qWait(10)
low, top = w.doc.objects
check("Geladen: Schalter und Überlappung erhalten", w.doc.knockout and w.a_knockout.isChecked()
      and w.doc.knockout_margin == 1.0)
check(f"Geladen: Fläche wieder ausgespart ({n_st(low)})", n_st(low) == cut
      and abs(drawn(low) - cut) <= 2)
import json
d = json.load(open(path, encoding="utf-8"))
check("Im Projekt gespeichert: Originalform ohne Loch", "knockout" in d and
      d["objects"][0]["fill"]["knockout"] is True and low.world_geometry().area == area)

# ---- Fläche mit Rand: Rand folgt weiter der Originalkontur
w.a_knockout.trigger(); QTest.qWait(10)
check("Ausgeschaltet: vollständig", not w.doc.knockout and n_st(low) == full)
low.border.update(type="satin", width=3.0, color="#1A1A1A"); w.rebuild([low]); w.commit()
b_full, f_full = n_st(low, 1), n_st(low, 0)
w.a_knockout.trigger(); QTest.qWait(10)
edge = low.world_geometry().boundary
far = max(edge.distance(Point(p[0], p[1])) for _, s in low.world_blocks()[1:] for p in s)
check(f"Mit Rand: Füllung ausgespart ({f_full} → {n_st(low, 0)}), Rand folgt der Kontur "
      f"({b_full} → {n_st(low, 1)} Stiche, max. {far:.1f} mm daneben)",
      n_st(low, 0) < f_full * 0.85 and abs(n_st(low, 1) - b_full) < b_full * 0.03 and far < 2.0)
low.border.update(color=low.fill["color"]); w.rebuild([low]); w.commit()
check("Rand in Füllfarbe (Element für Element): ebenfalls ausgespart",
      under(low, 0, 0, 13.5) == 0 and under(low, 0, 0, 15.5) > 0)
low.border["type"] = "none"; w.rebuild([low]); w.commit()

# ---- Schriftzug (Computerschrift) unter einer Fläche, Satinlinie als Deckel
t = EmbObject("text"); t.text.update(text="HH", size=30.0); t.x, t.y = 0, 80
w.add_objects([t]); QTest.qWait(10)
t_full = n_st(t)
lid = rect(50, 10, 0, 80, color="#1E88E5"); w.add_objects([lid]); QTest.qWait(10)
check(f"Schriftzug unter einer Fläche ausgespart ({t_full} → {n_st(t)})", n_st(t) < t_full * 0.9
      and under(t, 0, 80, 3.5) == 0)
check("… und auf der Arbeitsfläche gezeigt", abs(drawn(t) - n_st(t)) <= 3)
ln = EmbObject("line"); ln.set_points([(-40, 0), (40, 0)]); ln.border.update(type="satin", width=4.0)
before = n_st(low)
w.add_objects([ln]); QTest.qWait(10)
check(f"Satinlinie spart die Fläche darunter aus ({before} → {n_st(low)})", n_st(low) != before
      and under(low, 22.5, 0, 0.6) == 0)
w.doc.objects.remove(ln); w.sync_items([]); w.commit()
check("Linie gelöscht: Lücke wieder gefüllt", n_st(low) == before)

# ---- Ebene ausblenden: was nicht gestickt wird, verdeckt nichts
lid.visible = False; w.sync_items([]); w.commit()
check("Ausgeblendetes Objekt verdeckt nichts", n_st(t) == t_full)
lid.visible = True; w.sync_items([]); w.commit()

# ---- Geschwindigkeit: viele Objekte, nichts geändert
many = [rect(5, 5, -45 + (k % 15) * 6, -30 + (k // 15) * 6) for k in range(150)]
w.doc.objects = list(many); w.sync_items([]); w.commit(); QTest.qWait(10)
t0 = time.perf_counter()
for _ in range(10):
    w.doc.update_knockouts()
dt = (time.perf_counter() - t0) / 10
check(f"Prüfen ohne Änderung bei {len(w.doc.objects)} Objekten: {dt * 1000:.1f} ms", dt < 0.05)
dt = drag(many[0], -42, -30)
check(f"Verschieben zwischen 150 Flächen ({dt * 1000:.0f} ms)", dt < 1.0
      and abs(many[0].x + 42) < 0.6 and many[0]._knock is not None)

# ---- KI-Schnittstelle (api.py / mcp_server.py)
from stichwizard.api import DesignAPI
from stichwizard import mcp_server
api = DesignAPI(w)
low = rect(60, 40); top = rect(30, 30, 0, 0, color="#FDD835")
w.doc.knockout = False; w.apply_hoop(fit=False)
w.doc.objects = [low, top]; w.sync_items([]); w.commit()
res = api.call("set_hoop", {"knockout": True, "knockout_margin": 1.5})
check("KI: set_hoop schaltet ein und setzt die Überlappung", res["knockout"] is True and
      res["knockout_margin"] == 1.5 and w.a_knockout.isChecked() and n_st(low) < full * 0.85)
d = api.call("get_design", {})
check("KI: get_design meldet Schalter und je Objekt", d["knockout"] is True and
      d["objects"][0]["fill"]["knockout"] is True)
api.call("update_object", {"id": low.id, "changes": {"fill": {"knockout": False}}})
check("KI: je Objekt abschaltbar", low.fill["knockout"] is False and n_st(low) == full)
props = next(t for t in mcp_server.TOOLS if t[0] == "set_hoop")[2]
check("MCP-Werkzeug set_hoop kennt knockout", "knockout" in props and "knockout_margin" in props)
api.call("set_hoop", {"knockout": False})
check("KI: wieder aus", not w.doc.knockout and not w.a_knockout.isChecked())

print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
