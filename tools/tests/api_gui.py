"""Test (1.4): KI-Schnittstelle (api.py / mcp_server.py) – Text an Pfad, geführte Füllung,
Start-/Endpunkt, Säulen-Satin-Optionen, Redwork/Auto-Route."""
import json
import math
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
app = QApplication(sys.argv); app.setStyle('Fusion')
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import engine, embfont, mcp_server
from stichwizard.api import ApiError, ApiServer, DesignAPI
from stichwizard.mainwindow import MainWindow
from stichwizard.model import EmbObject
from shapely.geometry import LineString, Point
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
api = DesignAPI(w)
def call(method, **p):
    return api.call(method, p)
def fails(method, **p):
    try:
        api.call(method, p)
    except ApiError as e:
        return str(e)
    return None
def clear():
    w.doc.objects = []; w.sync_items([])
def world_sts(o):
    return [s for _, b in o.world_blocks() for s in b if s[2] == engine.STITCH]
def line(pts):
    return call("add_path", points=pts, closed=False, border={"type": "run"})
def obj(d):
    return w.doc.find(d["id"])
near = lambda a, b, tol=0.05: all(abs(p - q) < tol for p, q in zip(a, b))

# ============ MCP-Schemas
tools = {t["name"]: t for t in mcp_server.tool_list()}
check("MCP-Werkzeuge = API-Funktionen", set(tools) == set(DesignAPI.METHODS))
check("MCP: route_lines mit mode redwork|autoroute",
      tools["route_lines"]["inputSchema"]["properties"]["mode"]["enum"] == ["redwork", "autoroute"])
check("MCP: fill_type kennt »guided«",
      "guided" in tools["add_shape"]["inputSchema"]["properties"]["fill_type"]["enum"])
check("MCP: add_text kennt path, path_line, path_align, path_flip",
      {"path", "path_line", "path_align", "path_flip"} <= set(tools["add_text"]["inputSchema"]["properties"]))
desc = tools["update_object"]["description"]
check("MCP: update_object beschreibt guide, start/end, Satin-Optionen",
      all(k in desc for k in ("guide_line", "start", "short_inset", "split_len", "split_random", "path_line")))
opts = call("get_options")
check("get_options: guided, satin_types, text_path_align, route_modes",
      "guided" in opts["fill_types"] and opts["satin_types"] and opts["text_path_align"] == ["start", "center", "end"]
      and opts["route_modes"] == ["redwork", "autoroute"])

# ============ Geführte Füllung
clear()
sh = call("add_shape", shape="rect", width=60, height=40, fill={"underlay": False, "density": 0.5})
gpts = [[-30, 0], [-10, -10], [10, 10], [30, 0]]
gl = line(gpts)
r = call("update_object", id=sh["id"], changes={"fill": {"guide_line": gl["id"]}})
check("guide_line: Füllart guided, Linie übernommen",
      r["fill"]["type"] == "guided" and w.doc.find(gl["id"]) is None and gl["id"] not in w.items)
check("get_design meldet die Führungslinie in mm", all(near(a, b) for a, b in zip(r["fill"]["guide"], gpts)))
o = obj(sh)
def mean_angle(o, x0, x1):
    sts = world_sts(o); angs = []
    for p, q in zip(sts, sts[1:]):
        if x0 < (p[0] + q[0]) / 2 < x1 and -15 < p[1] < 15 and math.dist(p[:2], q[:2]) > 1.5:
            angs.append((math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) + 90) % 180 - 90)
    return sum(angs) / max(1, len(angs))
mid = mean_angle(o, -6, 6)
check(f"Reihen folgen der Führungslinie (Mitte {mid:.0f}°)", 30 < mid < 60)
w.undo()
check("Rückgängig: Linie wieder da, Fläche wieder Tatami",
      w.doc.find(gl["id"]) is not None and w.doc.find(sh["id"]).fill["type"] == "tatami")
# Punkte direkt, bei gedrehter und verschobener Fläche
r = call("update_object", id=sh["id"], changes={"x": 10, "y": 5, "rotation": 30,
                                                 "fill": {"guide": [[-20, 5], [0, -5], [40, 5]]}})
o = obj(sh)
check("guide als Punkte: nach Verschieben/Drehen in Objektkoordinaten gespeichert",
      r["fill"]["type"] == "guided" and near(o.to_world(*o.fill["guide"][0]), (-20, 5))
      and near(r["fill"]["guide"][2], (40, 5)))
check("Ohne Führungslinie keine geführte Füllung",
      "Führungslinie" in (fails("add_shape", shape="rect", width=20, fill_type="guided") or ""))
before = len(w.doc.objects)
check("Fehler ändert nichts (falsche guide_line)",
      fails("update_object", id=sh["id"], changes={"x": 0, "fill": {"guide_line": sh["id"]}})
      and len(w.doc.objects) == before and obj(sh).x == 10)
r = call("update_object", id=sh["id"], changes={"fill": {"guide": None}})
check("guide: null entfernt die Führungslinie", r["fill"]["type"] == "tatami" and "guide" not in r["fill"])

# ============ Text an Pfad
clear()
path = [[-45, 10], [-15, -12], [15, -12], [45, 10]]
t = call("add_text", text="Sticken", height=9, path=path, path_align="center")
o = obj(t); g = o.world_geometry(); guide = LineString(path)
check(f"add_text mit path: Text liegt auf dem Pfad (Abstand {g.distance(guide):.2f} mm)",
      o.text.get("path") and g.distance(guide) < 1.5 and guide.buffer(9 * 1.6).contains(g))
check("get_design meldet den Pfad in mm", all(near(a, b) for a, b in zip(t["text"]["path"], path)))
xc = g.centroid.x
r = call("update_object", id=t["id"], changes={"text": {"path_align": "start"}})
check(f"path_align start schiebt nach links ({xc:.1f} → {obj(t).world_geometry().centroid.x:.1f})",
      obj(t).world_geometry().centroid.x < xc - 5 and r["text"]["path_align"] == "start")
call("update_object", id=t["id"], changes={"text": {"path_flip": True, "path_align": "center"}})
g2 = obj(t).world_geometry()
check("path_flip: Text unter der Linie", g2.centroid.y > guide.interpolate(guide.project(g2.centroid)).y)
check("Falsches path_align wird abgelehnt, nichts geändert",
      fails("update_object", id=t["id"], changes={"text": {"text": "X", "path_align": "links"}})
      and obj(t).text["text"] == "Sticken")
r = call("update_object", id=t["id"], changes={"text": {"path": None}})
check("path: null macht den Text wieder gerade", not obj(t).text.get("path") and not r["text"]["path"])
ln = line([[-30, 30], [0, 20], [30, 30]])
call("update_object", id=t["id"], changes={"text": {"path_line": ln["id"], "path_flip": False}})
g3 = obj(t).world_geometry()
check("path_line übernimmt eine Linie", w.doc.find(ln["id"]) is None and obj(t).text.get("path")
      and g3.distance(LineString([[-30, 30], [0, 20], [30, 30]])) < 1.5)
fid = next(f["id"] for f in embfont.font_index() if not embfont.missing_chars(f, "Sticken")
           and f["min"] <= 12 <= f["max"] + 10)
et = call("add_text", text="Sticken", embroidery_font=fid, height=12, path=path)
sts = world_sts(obj(et))
check(f"Stickschrift am Pfad ({len(sts)} Stiche)", len(sts) > 300 and
      max(guide.distance(Point(s[:2])) for s in sts) < 12 * 1.8)
check("Stickschrift: keine geführte Füllung / kein Startpunkt",
      fails("update_object", id=et["id"], changes={"fill": {"start": [0, 0]}})
      and fails("update_object", id=et["id"], changes={"fill_type": "guided"}))

# ============ Start-/Endpunkt
clear()
sq = call("add_shape", shape="rect", width=50, height=30, x=10, y=5, rotation=20)
r = call("update_object", id=sq["id"], changes={"fill": {"start": [30, 15], "end": [-12, -5]}})
o = obj(sq); first, last = world_sts(o)[0], world_sts(o)[-1]
check(f"Fläche beginnt am Startpunkt ({first[0]:.1f}, {first[1]:.1f})", math.dist(first[:2], (30, 15)) < 3.5)
check(f"… und endet am Endpunkt ({last[0]:.1f}, {last[1]:.1f})", math.dist(last[:2], (-12, -5)) < 1.5)
check("get_design meldet Start/Ende in mm", near(r["fill"]["start"], (30, 15), 0.01)
      and near(r["fill"]["end"], (-12, -5), 0.01))
call("update_object", id=sq["id"], changes={"x": 20})
check("Punkte wandern mit dem Objekt", near(call("get_design")["objects"][0]["fill"]["start"], (40, 15), 0.01))
r = call("update_object", id=sq["id"], changes={"fill": {"start": None, "end": None}})
check("start/end: null = automatisch", "start" not in r["fill"] and not obj(sq).fill.get("end"))
check("Linien haben keinen Startpunkt", fails("update_object", id=line([[0, 0], [10, 0]])["id"],
                                                changes={"fill": {"start": [0, 0]}}))

# ============ Säulen-Satin
clear()
A = [[12 * math.cos(k * math.pi / 8), 12 * math.sin(k * math.pi / 8), 1] for k in range(9)]
B = [[5 * math.cos(k * math.pi / 8), 5 * math.sin(k * math.pi / 8), 1] for k in range(9)]
cs = EmbObject("satin"); cs.set_satin(B, A); cs.fill["underlay"] = False; w.add_objects([cs])
def inner(o):
    return sum(1 for s in world_sts(o) if 5.3 < math.hypot(s[0], s[1]) < 7.5)
call("update_object", id=cs.id, changes={"fill": {"short_inset": 0}}); a0 = inner(cs)
r = call("update_object", id=cs.id, changes={"fill": {"short_inset": 25, "short_dist": 0.3}})
a1 = inner(cs)
check(f"short_inset: kurze Stiche an der Innenkurve ({a0} → {a1})", a0 <= 4 and a1 > a0 + 20)
check("get_design zeigt Satin-Optionen", r["fill"]["short_inset"] == 25 and r["fill"]["short_dist"] == 0.3
      and "split_len" in r["fill"] and r["fill"]["satin_type"] == "satin")
ws = EmbObject("satin"); ws.set_satin([[-20, -10, 0], [20, -10, 0]], [[-20, 10, 0], [20, 10, 0]])
ws.fill["underlay"] = False; w.add_objects([ws])
call("update_object", id=ws.id, changes={"fill": {"split_len": 7}})
sts = world_sts(ws)
longest = max(math.dist(p[:2], q[:2]) for p, q in zip(sts, sts[1:]))
regular = {round(s[1], 1) for s in sts if -8.5 < s[1] < 8.5}
r = call("update_object", id=ws.id, changes={"fill": {"split_random": True, "short_inset": 99}})
rand = {round(s[1], 1) for s in world_sts(ws) if -8.5 < s[1] < 8.5}
check(f"split_len: längster Stich {longest:.1f} mm ≤ 7 mm", longest <= 7.2)
check(f"split_random streut die Teilung ({len(regular)} → {len(rand)} Höhen)",
      r["fill"]["split_random"] is True and len(rand) > len(regular) * 3)
check("Werte außerhalb des Bereichs werden begrenzt (short_inset 99 → 50)", ws.fill["short_inset"] == 50)
r = call("update_object", id=ws.id, changes={"fill": {"start": [20, 0]}})
check(f"Satinsäule beginnt am Startpunkt (x={world_sts(ws)[0][0]:.0f})", world_sts(ws)[0][0] > 0
      and near(r["fill"]["start"], (20, 0), 0.01))

# ============ Redwork / Auto-Route
def grid():
    clear()
    return [line(p) for p in ([[-30, -10], [30, -10]], [[-30, 10], [30, 10]], [[-20, -20], [-20, 20]],
                              [[0, -20], [0, 20]], [[20, -20], [20, 9.7]])]
src = grid(); total = sum(obj(d).world_geometry().length for d in src)
r = call("route_lines", mode="redwork")
lines = [o for o in w.doc.objects if o.kind == "line"]
check(f"route_lines redwork: 5 Linien → {len(lines)} Weg ohne Sprung",
      len(lines) == 1 and r["jumps"] == 0 and sorted(r["replaced"]) == sorted(d["id"] for d in src))
check(f"Redwork: doppelte Länge ({lines[0].world_geometry().length:.0f} ≈ 2 × {total:.0f} mm), Ecken genau",
      abs(lines[0].world_geometry().length - 2 * total) < 3 and r["lines"][0]["line"]["corners"] is True)
w.undo()
check("Rückgängig stellt die Linien wieder her", sum(o.kind == "line" for o in w.doc.objects) == 5)
r = call("route_lines", ids=[d["id"] for d in src], mode="autoroute")
check(f"route_lines autoroute: {r['doubled']} von {r['edges']} Strecken doppelt",
      len(r["lines"]) == 1 and 0 < r["doubled"] < r["edges"]
      and total - 1 < obj(r["lines"][0]).world_geometry().length < 2 * total)
clear(); a = line([[-30, 0], [-10, 0]]); b = line([[10, 0], [30, 0]])
sq = call("add_shape", shape="rect", width=10)
check("Nur Linien zulässig", fails("route_lines", ids=[a["id"], sq["id"]]))
check("Falscher mode wird abgelehnt", fails("route_lines", mode="zickzack"))
r = call("route_lines", ids=[a["id"], b["id"]], mode="autoroute")
check("Getrennte Linien → getrennte Wege", len(r["lines"]) == 2 and r["jumps"] == 1)

# ============ JSON über den Socket-Handler
srv = ApiServer(w)
resp = json.loads(srv._handle(json.dumps({"id": 7, "method": "get_design", "params": {}}).encode()))
check("get_design ist JSON-serialisierbar", resp.get("id") == 7 and "result" in resp)
print("ERGEBNIS:", sum(ok), "/", len(ok))
