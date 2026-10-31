"""Steuerschnittstelle für KI-Assistenten (über den MCP-Server).

Das laufende StichWizard lauscht auf einem lokalen Unix-Socket, der nur für den eigenen
Benutzer zugänglich ist. Jede Nachricht ist eine JSON-Zeile {"id", "method", "params"},
die Antwort {"id", "result"} bzw. {"id", "error"}. Alle Änderungen laufen über das normale
Dokument – sie erscheinen sofort im Fenster und lassen sich mit Strg+Z rückgängig machen.

Koordinaten: Millimeter, Ursprung = Mitte des Stickrahmens, x nach rechts, y nach unten.
"""
import json
import os

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter
from PySide6.QtNetwork import QLocalServer
from shapely import affinity
from shapely.geometry import Point, box

from . import engine, fileio
from .satin import SATIN_UNDERLAYS
from .autodigitize import digitize, load_image
from .engine import STITCH
from .ipc import socket_path
from .model import EmbObject
from .render import render_document
from .shapes import MOTIFS
from . import embfont, threads
from .threads import FABRICS, HOOPS, THREADS, thread_name

FILL_TYPES = ["tatami", "satin", "wave", "guided", "contour", "cross", "motif", "net", "circular",
              "meander", "ripple", "gradient", "tartan", "applique", "none"]
TATAMI_PATTERNS = list(engine.TATAMI_PATTERNS)
FILL_MOTIFS = ["heart", "star", "circle", "diamond", "flower"]
BORDER_TYPES = ["none", "run", "triple", "satin", "zigzag", "estitch", "manual", "motif"]
SATIN_TYPES = ["satin", "zigzag", "estitch"]
PATH_ALIGN = ["start", "center", "end"]
ROUTE_MODES = ["redwork", "autoroute"]
# Säulen-Satin: Wertebereiche wie im Eigenschaftenfeld
FINE_RANGES = {"ul_angle": (-180.0, 180.0), "ul_spacing": (0.8, 6.0), "ul_inset": (0.0, 3.0),
               "expand": (-3.0, 3.0), "len_random": (0.0, 50.0), "width_random": (0.0, 50.0),
               "spacing_random": (0.0, 80.0)}
SATIN_ULS = [k for _, k in SATIN_UNDERLAYS]
TIES = [k for _, k in engine.TIE_NAMES]
SATIN_RANGES = {"short_inset": (0.0, 50.0), "short_dist": (0.05, 2.0), "split_len": (2.0, 15.0)}
SHAPE_ALIASES = {"heart": "Herz", "star": "Stern", "circle": "Kreis", "square": "Quadrat",
                 "rounded": "Abgerundet", "triangle": "Dreieck", "hexagon": "Sechseck",
                 "diamond": "Raute", "flower": "Blume", "cloud": "Wolke", "moon": "Mond",
                 "bolt": "Blitz", "paw": "Pfote", "leaf": "Blatt", "ring": "Ring",
                 "drop": "Tropfen", "house": "Haus", "butterfly": "Schmetterling",
                 "anchor": "Anker", "star8": "Stern 8"}


class ApiError(Exception):
    pass


def parse_color(value):
    if not value:
        raise ApiError("Farbe fehlt")
    v = str(value).strip()
    from . import threads
    if threads.CURRENT_CHART:            # Nummer oder Name aus der gewählten Garnkarte
        for name, num, col in threads.charts()[threads.CURRENT_CHART]:
            if v.lower() in (num.lower(), name.lower(), f"{num} {name}".lower()):
                return col
    for name, col in THREADS:
        if name.lower() == v.lower():
            return col
    c = QColor(v)
    if not c.isValid():
        raise ApiError(f"Unbekannte Farbe: {value!r} (Hex wie #E53935, Garnname oder CSS-Farbname)")
    return c.name().upper()


def parse_point(value, what):
    """[x, y] oder {"x", "y"} -> (x, y)."""
    try:
        if isinstance(value, dict):
            return float(value["x"]), float(value["y"])
        return float(value[0]), float(value[1])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ApiError(f"{what}: Punkt als [x, y] in mm angeben") from None


def parse_points(value, what):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ApiError(f"{what}: mindestens zwei Punkte [[x, y], …] in mm angeben")
    return [parse_point(q, what) for q in value]


def hoop_index(value):
    if value is None:
        return None
    if isinstance(value, int):
        if 0 <= value < len(HOOPS):
            return value
        raise ApiError("Ungültiger Rahmenindex")
    v = str(value).lower().replace(" ", "").replace("×", "x").replace("mm", "")
    for i, (name, w, h) in enumerate(HOOPS):
        if v in (f"{w}x{h}", name.lower().replace(" ", "").replace("×", "x").replace("mm", "")):
            return i
    import re
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)", v)
    if m:                                   # beliebige Größe »BxH« = eigener Rahmen
        from .threads import hoop_for_size
        try:
            return hoop_for_size(float(m.group(1).replace(",", ".")),
                                 float(m.group(2).replace(",", ".")))
        except ValueError as e:
            raise ApiError(str(e))
    raise ApiError(f"Unbekannter Rahmen {value!r}. Verfügbar: " +
                   ", ".join(f"{w:g}x{h:g}" for _, w, h in HOOPS) + " oder eigene Größe »BxH«")


class DesignAPI:
    def __init__(self, window):
        self.w = window

    # ------------------------------------------------------------- Helfer
    @property
    def doc(self):
        return self.w.doc

    def _obj(self, oid):
        o = self.doc.find(str(oid))
        if o is None:
            raise ApiError(f"Kein Objekt mit id {oid!r}. Mit get_design die ids abfragen.")
        return o

    def summary(self, o):
        lw, lh = o.local_size()
        n = sum(1 for _, s in o.stitch_blocks() for p in s if p[2] == STITCH)
        d = {"id": o.id, "name": o.name, "kind": o.kind, "x": round(o.x, 2), "y": round(o.y, 2),
             "width": round(lw * abs(o.sx), 2), "height": round(lh * abs(o.sy), 2),
             "rotation": round(o.rot, 1), "visible": o.visible, "stitches": n}
        world = lambda q: [round(v, 2) for v in o.to_world(q[0], q[1])]
        f = o.fill
        if o.kind in ("shape", "text"):
            d["fill"] = {k: f[k] for k in ("type", "color", "angle", "density", "pattern",
                                           "motif", "size", "underlay", "underlay_first")}
            d["fill"]["knockout"] = bool(f.get("knockout", True))
            if f.get("guide"):
                d["fill"]["guide"] = [world(q) for q in f["guide"]]
        elif o.kind == "satin":
            d["fill"] = {k: f.get(k) for k in ("color", "density", "pull", "underlay", "satin_type",
                                               "short_inset", "short_dist", "split_len",
                                               "split_random")}
        if "fill" in d:
            d["fill"]["thread"] = thread_name(f["color"])
            for k in ("start", "end"):
                if f.get(k):
                    d["fill"][k] = world(f[k])
        if o.kind != "stitches":
            b = o.border
            d["border" if o.kind != "line" else "line"] = {
                "type": b["type"], "color": b["color"], "thread": thread_name(b["color"]),
                "width": b["width"]}
            if b["type"] in ("run", "triple"):
                d["border" if o.kind != "line" else "line"]["corners"] = bool(b.get("corners"))
        if o.kind == "text":
            d["text"] = dict(o.text)
            if o.text.get("path"):
                d["text"]["path"] = [world(q) for q in o.text["path"]]
        if o.kind == "stitches":
            d["colors"] = [b["color"] for b in o.blocks]
        if o.kind in ("shape", "line") and (o.curve or o.ptypes):
            d["has_curves"] = True
        return d

    def _done(self, changed=None, select=None):
        """Nach Änderungen: neu zeichnen, Rückgängig-Schritt anlegen, Auswahl zeigen."""
        if changed:
            self.w.rebuild(changed)
        self.w.commit()
        if select is not None:
            self.w._syncing = True
            self.w.scene.clearSelection()
            for oid in select:
                if oid in self.w.items:
                    self.w.items[oid].setSelected(True)
            self.w._syncing = False
            self.w.on_scene_selection()
        self.w.props.refresh()

    def _apply_style(self, o, p, text=None):
        """Gemeinsame Gestaltungsparameter (fill, border, color …) übernehmen. `text`: Angaben
        zum Textpfad (path, path_line), die erst nach Position/Drehung umgerechnet werden."""
        if "color" in p and p["color"]:
            if o.kind == "line":
                o.border["color"] = parse_color(p["color"])
            else:
                o.fill["color"] = parse_color(p["color"])
        fill, refs = self._fill_changes(p)
        self._check_refs(o, fill, refs)
        if fill:
            if "color" in fill:
                fill["color"] = parse_color(fill["color"])
            if "color2" in fill:
                fill["color2"] = parse_color(fill["color2"])
            if "satin_type" in fill and fill["satin_type"] not in SATIN_TYPES:
                raise ApiError(f"satin_type muss eines von {SATIN_TYPES} sein")
            if "type" in fill and fill["type"] not in FILL_TYPES:
                raise ApiError(f"fill type muss eines von {FILL_TYPES} sein")
            if "pattern" in fill and fill["pattern"] not in TATAMI_PATTERNS:
                raise ApiError(f"pattern muss eines von {TATAMI_PATTERNS} sein")
            if "motif" in fill and fill["motif"] not in FILL_MOTIFS:
                raise ApiError(f"motif muss eines von {FILL_MOTIFS} sein")
            for k in ("angle", "density", "size", "stitch_len", "pull"):
                if k in fill:
                    fill[k] = float(fill[k])
            for k, (lo, hi) in SATIN_RANGES.items():
                if k in fill:
                    fill[k] = min(max(float(fill[k]), lo), hi)
            for k, (lo, hi) in FINE_RANGES.items():
                if k in fill:
                    fill[k] = min(max(float(fill[k]), lo), hi)
            if "gradient_colors" in fill:
                fill["gradient_colors"] = [parse_color(c) for c in (fill["gradient_colors"] or [])][:3]
            if "tartan" in fill and fill["tartan"] is not None:
                if isinstance(fill["tartan"], str):
                    if fill["tartan"] not in engine.TARTAN_PRESETS:
                        raise ApiError(f"tartan-Vorlage muss eine von {list(engine.TARTAN_PRESETS)} "
                                       "sein oder eine Liste [[farbe, breite_mm], …]")
                    fill["tartan"] = [list(x) for x in engine.TARTAN_PRESETS[fill["tartan"]]]
                else:
                    try:
                        fill["tartan"] = [[parse_color(c), min(30.0, max(0.5, float(w)))]
                                          for c, w in fill["tartan"]]
                    except (TypeError, ValueError):
                        raise ApiError("tartan: Liste [[farbe, breite_mm], …] erwartet")
                    if len(fill["tartan"]) < 2:
                        raise ApiError("tartan: mindestens zwei Streifen")
            if "tartan_scale" in fill:
                fill["tartan_scale"] = min(4.0, max(0.25, float(fill["tartan_scale"])))
            if "tartan_symmetric" in fill:
                fill["tartan_symmetric"] = bool(fill["tartan_symmetric"])
            if "ul_layers" in fill:
                fill["ul_layers"] = 2 if int(fill["ul_layers"]) >= 2 else 1
            if "satin_ul" in fill and fill["satin_ul"] not in SATIN_ULS:
                raise ApiError(f"satin_ul muss eines von {SATIN_ULS} sein")
            if "tie" in fill and fill["tie"] not in TIES:
                raise ApiError(f"tie muss eines von {TIES} sein")
            for k in ("underlay", "underlay_first", "split_random", "gradient_reverse",
                      "ul_contour", "tie_force", "auto_spacing", "underlay_auto", "puff",
                      "knockout"):
                if k in fill:
                    fill[k] = bool(fill[k])
            o.fill.update({k: v for k, v in fill.items() if k in o.fill})
        border = dict(p.get("border") or p.get("line") or {})
        if border:
            if "color" in border:
                border["color"] = parse_color(border["color"])
            if "type" in border and border["type"] not in BORDER_TYPES:
                raise ApiError(f"border type muss eines von {BORDER_TYPES} sein")
            for k in ("width", "stitch_len", "density"):
                if k in border:
                    border[k] = float(border[k])
            if "corners" in border:
                border["corners"] = bool(border["corners"])
            if "corner" in border and border["corner"] not in ("mitre", "none"):
                raise ApiError("corner muss mitre oder none sein")
            if "auto_spacing" in border:
                border["auto_spacing"] = bool(border["auto_spacing"])
            if "bean_pattern" in border:
                vals = engine.bean_pattern(border["bean_pattern"] if not isinstance(
                    border["bean_pattern"], list) else " ".join(map(str, border["bean_pattern"])))
                border["bean_pattern"] = " ".join(map(str, vals or []))
            if "len_random" in border:
                border["len_random"] = min(max(float(border["len_random"]), 0.0), 50.0)
            o.border.update({k: v for k, v in border.items() if k in o.border})
        if "name" in p and p["name"]:
            o.name = str(p["name"])
        if "rotation" in p and p["rotation"] is not None:
            o.rot = float(p["rotation"]) % 360
        # Punkte in mm (Arbeitsfläche) erst jetzt umrechnen – nach Position, Größe und Drehung
        if text:
            self._apply_text_path(o, text)
        self._apply_refs(o, refs)

    @staticmethod
    def _fill_changes(p):
        """Füllangaben -> (einfache Werte, Punktangaben guide/guide_line/start/end)."""
        fill = dict(p.get("fill") or {})
        for key in ("fill_type", "pattern", "motif", "pattern_size", "angle", "density"):
            if key in p and p[key] is not None:
                fill[{"fill_type": "type", "pattern_size": "size"}.get(key, key)] = p[key]
        refs = {k: fill.pop(k) for k in ("guide", "guide_line", "start", "end") if k in fill}
        return fill, refs

    @staticmethod
    def _text_path_changes(t):
        return {k: t[k] for k in ("path", "path_line", "path_align", "path_flip") if k in t}

    def _line(self, oid, what):
        ln = self._obj(oid)
        if ln.kind != "line":
            raise ApiError(f"{what}: {oid!r} ist keine Linie")
        pts = self.w._world_polyline(ln)
        if len(pts) < 2:
            raise ApiError(f"{what}: Linie {oid!r} ist leer")
        return ln, pts

    def _consume(self, ln, keep):
        """Übernommene Linie (Pfad, Führungslinie) aus dem Design entfernen."""
        if ln in self.doc.objects:
            self.doc.objects.remove(ln)
            self.w.sync_items(keep)

    def _check_refs(self, o, fill, refs):
        """Vorab prüfen, damit ein Fehler nichts halb ändert."""
        plain = o.kind in ("shape", "text") and not (o.kind == "text" and o.text.get("embfont"))
        if ("guide" in refs or "guide_line" in refs or fill.get("type") == "guided") and not plain:
            raise ApiError("Geführte Füllung gibt es nur für Flächen und Schriftzüge in "
                           "Computerschrift")
        if ("start" in refs or "end" in refs) and not (plain or o.kind == "satin"):
            raise ApiError("Start-/Endpunkt gibt es nur für Flächen, Schriftzüge in Computerschrift "
                           "und Satinsäulen")
        if refs.get("guide_line") is not None:
            self._line(refs["guide_line"], "guide_line")
        elif refs.get("guide") is not None:
            parse_points(refs["guide"], "guide")
        elif fill.get("type") == "guided" and not o.fill.get("guide") and "guide" not in refs:
            raise ApiError("Geführte Füllung braucht eine Führungslinie: fill.guide [[x, y], …] "
                           "in mm oder fill.guide_line = id einer Linie")
        for k in ("start", "end"):
            if refs.get(k) is not None:
                parse_point(refs[k], k)

    def _apply_refs(self, o, refs):
        if refs.get("guide_line") is not None:
            ln, pts = self._line(refs["guide_line"], "guide_line")
            self.w.set_guide(o, pts)
            self._consume(ln, [o.id])
        elif refs.get("guide") is not None:
            self.w.set_guide(o, parse_points(refs["guide"], "guide"))
        elif "guide" in refs:          # null = Führungslinie entfernen
            o.fill.update(guide=None, type="tatami" if o.fill["type"] == "guided" else o.fill["type"])
        for k in ("start", "end"):
            if k in refs:
                o.fill[k] = None if refs[k] is None else \
                    [round(v, 3) for v in o.to_local(*parse_point(refs[k], k))]

    def _check_text_path(self, t):
        if t.get("path_align") is not None and t["path_align"] not in PATH_ALIGN:
            raise ApiError(f"path_align muss eines von {PATH_ALIGN} sein")
        if t.get("path_line") is not None:
            self._line(t["path_line"], "path_line")
        elif t.get("path") is not None:
            parse_points(t["path"], "path")

    def _apply_text_path(self, o, t):
        if o.kind != "text":
            return
        if t.get("path_align") is not None:
            o.text["path_align"] = t["path_align"]
        if t.get("path_flip") is not None:
            o.text["path_flip"] = bool(t["path_flip"])
        if t.get("path_line") is not None:
            ln, pts = self._line(t["path_line"], "path_line")
            self.w.set_text_path(o, pts)
            self._consume(ln, [o.id])
        elif t.get("path") is not None:
            self.w.set_text_path(o, parse_points(t["path"], "path"))
        elif "path" in t:               # null = Text wieder gerade
            o.text = dict(o.text, path=None)

    def _add(self, objs):
        self.w.add_objects(objs)
        self.w.props.refresh()
        return [self.summary(o) for o in objs]

    # ----------------------------------------------------------- Befehle
    def get_design(self, p):
        st = self.doc.stats()
        w, h = self.doc.hoop_size
        b = st["bounds"]
        outside = bool(st["stitches"]) and (b[0] < -w / 2 or b[2] > w / 2 or
                                            b[1] < -h / 2 or b[3] > h / 2)
        return {"file": self.w.path, "unsaved_changes": self.w.dirty,
                "hoop": {"name": HOOPS[self.doc.hoop][0], "width": w, "height": h},
                "fabric": self.doc.fabric, "fabric_type": self.doc.fabric_type,
                "knockout": self.doc.knockout, "knockout_margin": self.doc.knockout_margin,
                "stats": {"stitches": st["stitches"], "colors": st["colors"],
                          "trims": st["trims"], "width_mm": round(st["width"], 1),
                          "height_mm": round(st["height"], 1),
                          "minutes": round(st["minutes"], 1), "outside_hoop": outside},
                "color_sequence": [{"color": c, "thread": thread_name(c)}
                                   for c, _ in self.doc.machine_blocks()],
                "selected": [o.id for o in self.w.selected_objects()],
                "objects": [self.summary(o) for o in self.doc.objects]}

    def get_options(self, p):
        return {"hoops": [f"{w:g}x{h:g}" for _, w, h in HOOPS],
                "fabrics": [{"name": n, "color": c} for n, c in FABRICS],
                "threads": [{"name": n, "color": c} for n, c in THREADS],
                "fill_types": FILL_TYPES, "tatami_patterns": TATAMI_PATTERNS,
                "fill_motifs": FILL_MOTIFS, "border_types": BORDER_TYPES,
                "satin_types": SATIN_TYPES, "text_path_align": PATH_ALIGN,
                "route_modes": ROUTE_MODES,
                "shapes": ["rect", "ellipse"] + sorted(SHAPE_ALIASES),
                "fonts": sorted(set(QFontDatabase.families())),
                "embroidery_fonts": [{"id": f["id"], "name": f["name"],
                                      "height_mm": [round(f["min"]), round(f["max"])],
                                      "license": f["license"]} for f in embfont.font_index()],
                "thread_charts": threads.chart_names(), "thread_chart": threads.CURRENT_CHART}

    def new_design(self, p):
        if self.w.dirty and self.doc.objects and not p.get("discard_changes"):
            raise ApiError("Das aktuelle Design hat ungespeicherte Änderungen. Erst save_project "
                           "aufrufen oder discard_changes=true setzen.")
        self.w.doc = self.w._new_document()
        self.w.path = None
        self.w.undo_stack, self.w.redo_stack = [], []
        if p.get("hoop") is not None:
            self.w.doc.hoop = hoop_index(p["hoop"])
        if p.get("fabric"):
            self.w.doc.fabric = parse_color(p["fabric"])
        if p.get("fabric_type"):
            self._check_fabric_type(p["fabric_type"])
            self.w.doc.fabric_type = p["fabric_type"]
        self.w.apply_hoop()
        self.w.sync_items()
        self.w.commit(initial=True)
        self.w.dirty = False
        self.w.update_title()
        return self.get_design({})

    def set_hoop(self, p):
        if p.get("hoop") is not None:
            self.w.set_hoop(hoop_index(p["hoop"]))
        if p.get("fabric"):
            self.w.set_fabric(parse_color(p["fabric"]))
        if p.get("fabric_type"):
            self._check_fabric_type(p["fabric_type"])
            self.w.set_fabric_type(p["fabric_type"])
        if p.get("thread_chart") is not None:
            self.w.palette_bar.set_chart(p["thread_chart"])
            self.w.set_thread_chart(p["thread_chart"])
        if p.get("color_sort") is not None:
            self.w.a_colorsort.setChecked(bool(p["color_sort"]))
            self.w.toggle_colorsort()
        if p.get("knockout_margin") is not None:
            try:
                margin = float(p["knockout_margin"])
            except (TypeError, ValueError):
                raise ApiError("knockout_margin: Zahl in mm erwartet")
            self.doc.knockout_margin = min(5.0, max(0.0, margin))
            if p.get("knockout") is None:
                self.w.commit()
        if p.get("knockout") is not None:
            self.w.a_knockout.setChecked(bool(p["knockout"]))
            self.w.toggle_knockout()
        return {"hoop": HOOPS[self.doc.hoop][0], "fabric": self.doc.fabric,
                "fabric_type": self.doc.fabric_type, "knockout": self.doc.knockout,
                "knockout_margin": self.doc.knockout_margin,
                "color_sort": self.doc.color_sort, "thread_chart": threads.CURRENT_CHART}

    @staticmethod
    def _check_fabric_type(key):
        if key not in engine.FABRIC_PROFILES:
            raise ApiError(f"fabric_type muss eines von {list(engine.FABRIC_PROFILES)} sein")

    def add_text(self, p):
        text = str(p.get("text") or "").strip("\n")
        if not text:
            raise ApiError("text fehlt")
        o = EmbObject("text", text.split("\n")[0][:24])
        o.text["text"] = text
        if p.get("embroidery_font"):
            if not embfont.exists(p["embroidery_font"]):
                raise ApiError("Unbekannte Stickschrift – siehe get_options › embroidery_fonts")
            o.text["embfont"] = p["embroidery_font"]
        for k_api, k in (("font", "font"), ("height", "size"), ("bold", "bold"),
                         ("italic", "italic"), ("arc_radius", "arc"), ("letter_spacing", "spacing")):
            if p.get(k_api) is not None:
                o.text[k] = p[k_api] if k in ("font", "bold", "italic") else float(p[k_api])
        o.fill.update(type="satin", angle=0, color="#1565C0")
        o.x, o.y = float(p.get("x", 0)), float(p.get("y", 0))
        tpath = self._text_path_changes(p)
        self._check_text_path(tpath)
        self._apply_style(o, p, text=tpath)
        return self._add([o])[0]

    def add_shape(self, p):
        shape = str(p.get("shape", "rect")).strip()
        w, h = p.get("width"), p.get("height")
        if shape.lower() in ("rect", "rectangle", "rechteck"):
            g = box(-0.5, -0.5, 0.5, 0.5)
            w, h = float(w or 40), float(h or w or 30)
        elif shape.lower() in ("ellipse", "oval"):
            g = Point(0, 0).buffer(0.5, resolution=64)
            w, h = float(w or 40), float(h or w or 30)
        else:
            name = SHAPE_ALIASES.get(shape.lower(), shape)
            lib = {n.lower(): fn for n, fn in MOTIFS}
            if name.lower() not in lib:
                raise ApiError(f"Unbekannte Form {shape!r}. Verfügbar: rect, ellipse, " +
                               ", ".join(sorted(SHAPE_ALIASES)))
            g = lib[name.lower()]()
            minx, miny, maxx, maxy = g.bounds
            g = affinity.translate(g, -(minx + maxx) / 2, -(miny + maxy) / 2)
            gw, gh = maxx - minx, maxy - miny
            if w and not h:
                h = float(w) * gh / gw
            elif h and not w:
                w = float(h) * gw / gh
            w, h = float(w or gw), float(h or gh)
            g = affinity.scale(g, 1 / gw, 1 / gh, origin=(0, 0))
        o = EmbObject("shape", p.get("name") or shape.capitalize())
        o.set_geometry(affinity.scale(g, w, h, origin=(0, 0)))
        o.x, o.y = float(p.get("x", 0)), float(p.get("y", 0))
        self._apply_style(o, p)
        return self._add([o])[0]

    def add_path(self, p):
        pts = p.get("points") or []
        nodes = []
        for q in pts:
            if isinstance(q, dict):
                x, y, t = q.get("x"), q.get("y"), q.get("type", "corner")
            else:
                x, y = q[0], q[1]
                t = q[2] if len(q) > 2 else "corner"
            nodes.append([float(x), float(y), 1 if str(t).lower() in ("curve", "1", "rundung") else 0])
        closed = bool(p.get("closed", True))
        if len(nodes) < (3 if closed else 2):
            raise ApiError("Zu wenige Punkte (Fläche: mind. 3, Linie: mind. 2)")
        if closed:
            o = EmbObject("shape", p.get("name") or "Form")
            self.w._set_world_curve(o, [nodes])
        else:
            o = EmbObject("line", p.get("name") or "Linie")
            xs, ys = [n[0] for n in nodes], [n[1] for n in nodes]
            o.x, o.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            o.set_line_nodes([[x - o.x, y - o.y, t] for x, y, t in nodes])
        self._apply_style(o, p)
        return self._add([o])[0]

    def update_object(self, p):
        o = self._obj(p.get("id"))
        ch = dict(p.get("changes") or {})
        t = ch.get("text") if o.kind == "text" else None
        if isinstance(t, str):
            t = {"text": t}
        tpath = self._text_path_changes(t) if t else None
        if tpath:                       # erst prüfen, damit ein Fehler nichts halb ändert
            self._check_text_path(tpath)
        self._check_refs(o, *self._fill_changes(ch))
        if "x" in ch:
            o.x = float(ch["x"])
        if "y" in ch:
            o.y = float(ch["y"])
        if "visible" in ch:
            o.visible = bool(ch["visible"])
        if ch.get("trim_after") in ("auto", "always", "never"):
            o.trim_after = ch["trim_after"]
        if "smooth" in ch and o.kind in ("shape", "line"):
            o.smooth = int(ch["smooth"])
        if t:
            mapping = {"height": "size", "arc_radius": "arc", "letter_spacing": "spacing",
                       "embroidery_font": "embfont"}
            for k, v in t.items():
                k = mapping.get(k, k)
                if k in o.text and k not in tpath:
                    o.text[k] = v if k in ("text", "font", "bold", "italic", "embfont") else float(v)
            if set(t) - set(tpath):
                o.sx, o.sy = (1 if o.sx >= 0 else -1), (1 if o.sy >= 0 else -1)
        lw, lh = o.local_size()
        if ("width" in ch or "height" in ch) and lw > 0 and lh > 0:
            sx_new = float(ch["width"]) / lw if "width" in ch else None
            sy_new = float(ch["height"]) / lh if "height" in ch else None
            if sx_new is None:
                sx_new = sy_new
            if sy_new is None:
                sy_new = sx_new
            o.sx = (1 if o.sx >= 0 else -1) * sx_new
            o.sy = (1 if o.sy >= 0 else -1) * sy_new
        if ch.get("mirror") in ("horizontal", "vertical"):
            if ch["mirror"] == "horizontal":
                o.sx = -o.sx
            else:
                o.sy = -o.sy
        self._apply_style(o, ch, text=tpath)
        self.w.items[o.id].setVisible(o.visible)
        self._done([o])
        return self.summary(o)

    def route_lines(self, p):
        mode = p.get("mode") or "redwork"
        if mode not in ROUTE_MODES:
            raise ApiError(f"mode muss eines von {ROUTE_MODES} sein")
        ids = p.get("ids")
        lines = [self._obj(i) for i in ids] if ids else [o for o in self.doc.objects
                                                         if o.kind == "line"]
        bad = [o.id for o in lines if o.kind != "line"]
        if bad:
            raise ApiError(f"Nur Linien lassen sich verbinden – keine Linie: {', '.join(bad)}")
        if not lines:
            raise ApiError("Keine Linien im Design")
        lines = sorted(set(lines), key=self.doc.objects.index)
        new, info = self.w.route_objects(lines, mode)
        self.w.props.refresh()
        return {"mode": mode, "replaced": [o.id for o in lines], "edges": info["edges"],
                "doubled": info["doubled"], "jumps": max(0, len(new) - 1),
                "lines": [self.summary(o) for o in new]}

    def delete_objects(self, p):
        ids = {str(i) for i in (p.get("ids") or [])}
        for i in ids:
            self._obj(i)
        self.doc.objects = [o for o in self.doc.objects if o.id not in ids]
        self.w.sync_items()
        self._done()
        return {"deleted": sorted(ids), "remaining": len(self.doc.objects)}

    def duplicate_object(self, p):
        o = self._obj(p.get("id"))
        c = o.clone()
        c.name = o.name + " Kopie"
        c.x += float(p.get("dx", 5))
        c.y += float(p.get("dy", 5))
        return self._add([c])[0]

    def set_order(self, p):
        ids = [str(i) for i in (p.get("ids") or [])]
        if sorted(ids) != sorted(o.id for o in self.doc.objects):
            raise ApiError("ids muss alle Objekt-ids genau einmal enthalten (neue Stickreihenfolge)")
        order = {oid: i for i, oid in enumerate(ids)}
        self.doc.objects.sort(key=lambda o: order[o.id])
        self.w.restack()
        self._done()
        return {"order": ids}

    def select_objects(self, p):
        ids = [str(i) for i in (p.get("ids") or [])]
        self._done(select=ids)
        return {"selected": [o.id for o in self.w.selected_objects()]}

    def center_design(self, p):
        objs = list(self.doc.objects)
        self.w.center_group(objs)
        self.w.sync_items()
        self._done()
        return {"centered": len(objs)}

    def digitize_image(self, p):
        path = os.path.expanduser(str(p.get("path", "")))
        img = load_image(path)
        if img is None:
            raise ApiError(f"Bild konnte nicht geladen werden: {path}")
        objs, _ = digitize(img, int(p.get("colors", 5)), float(p.get("width", 100)),
                           bool(p.get("remove_background", True)), float(p.get("smoothing", 0.4)))
        if not objs:
            raise ApiError("Im Bild wurden keine Flächen gefunden")
        self.w.center_group(objs, float(p.get("x", 0)), float(p.get("y", 0)))
        return {"added": self._add(objs)}

    def import_embroidery(self, p):
        path = os.path.expanduser(str(p.get("path", "")))
        obj = fileio.import_file(path)
        obj.x, obj.y = float(p.get("x", 0)), float(p.get("y", 0))
        return self._add([obj])[0]

    def open_file(self, p):
        if self.w.dirty and self.doc.objects and not p.get("discard_changes"):
            raise ApiError("Ungespeicherte Änderungen. Erst save_project oder discard_changes=true.")
        self.w.open_document(os.path.expanduser(str(p.get("path", ""))))
        return self.get_design({})

    def save_project(self, p):
        path = p.get("path") or self.w.path
        if not path:
            raise ApiError("Noch kein Dateiname – path angeben (Endung .stickproj).")
        path = os.path.expanduser(str(path))
        if not path.lower().endswith(".stickproj"):
            path += ".stickproj"
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.doc.to_json(with_template=True))
        self.w.path = path
        self.w.dirty = False
        self.w.update_title()
        return {"saved": path}

    def export_design(self, p):
        path = os.path.expanduser(str(p.get("path", "")))
        fmt = (p.get("format") or os.path.splitext(path)[1].lstrip(".") or "pes").lower()
        allowed = [e for _, e in fileio.EXPORT_FORMATS]
        if fmt not in allowed:
            raise ApiError(f"format muss eines von {allowed} sein")
        if not path.lower().endswith("." + fmt):
            path += "." + fmt
        if not self.doc.objects:
            raise ApiError("Das Design ist leer")
        opt = p.get("optimize")
        if opt is None:
            opt = self.w.prefs.get("optimize_export")
        res = fileio.export_file(self.doc, path, bool(opt))
        st = self.doc.stats()
        out = {"exported": path, "format": fmt, "stitches": st["stitches"], "colors": st["colors"]}
        if res:
            out["jump_optimization"] = res
        return out

    def render_preview(self, p):
        view = p.get("view", "design")
        if view == "hoop":
            img = self._render_hoop(int(p.get("pixels", 900)))
        else:
            if not self.doc.objects:
                raise ApiError("Das Design ist leer – nichts zu zeigen")
            img = render_document(self.doc, float(p.get("scale", 6)))
            if max(img.width(), img.height()) > 1600:
                img = img.scaled(1600, 1600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        return {"image_png_base64": bytes(ba.toBase64()).decode("ascii"),
                "width": img.width(), "height": img.height()}

    def _render_hoop(self, pixels):
        rect = self.w.hoop_item.boundingRect()
        f = pixels / max(rect.width(), rect.height())
        img = QImage(int(rect.width() * f), int(rect.height() * f), QImage.Format_ARGB32)
        img.fill(QColor("#E6E9EF"))
        sel = [it for it in self.w.scene.selectedItems()]
        self.w._syncing = True
        for it in sel:
            it.setSelected(False)
        self.w.canvas.preview.hide()
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        self.w.scene.render(painter, QRectF(img.rect()), rect)
        painter.end()
        self.w.canvas.preview.show()
        for it in sel:
            it.setSelected(True)
        self.w._syncing = False
        return img

    def optimize_jumps(self, p):
        ids = p.get("ids")
        objs = [self._obj(i) for i in ids] if ids else None
        return self.w.optimize_jumps(objs)

    def get_jumps(self, p):
        from . import jumps
        out = []
        for r in jumps.jump_list(self.doc):
            o = self.doc.find(r["obj"])
            e = {"index": r["index"], "kind": r["kind"], "from": [round(v, 2) for v in r["a"]],
                 "to": [round(v, 2) for v in r["b"]], "length": round(r["length"], 2),
                 "trim": r["trim"], "object": r["obj"], "object_name": o.name if o else None,
                 "object_kind": o.kind if o else None}
            if r["kind"] == "between":
                e["next_object"] = r["obj_b"]
                e["trim_mode"] = r["mode"]
            else:
                e["connect_would_be_hidden"] = jumps.is_covered(self.doc, r)
            out.append(e)
        return {"jumps": out, "count": len(out), "trims": sum(e["trim"] for e in out)}

    def edit_jump(self, p):
        from . import jumps
        recs = jumps.jump_list(self.doc)
        i = int(p.get("index", -1))
        if not 0 <= i < len(recs):
            raise ApiError("Ungültiger Sprung-Index – erst get_jumps aufrufen")
        rec, action = recs[i], p.get("action")
        o = self.doc.find(rec["obj"])
        if rec["kind"] == "between" and not rec["same"]:
            mode = {"trim_on": "always", "trim_off": "never", "trim_auto": "auto"}.get(action)
            if not mode:
                raise ApiError("Zwischen zwei Objekten sind nur trim_on, trim_off, trim_auto möglich")
            jumps.set_trim_mode(self.doc, rec, mode)
            self._done([o])
            return {"index": i, "trim_mode": mode}
        if action not in ("trim_on", "trim_off", "connect"):
            raise ApiError("action muss trim_on, trim_off oder connect sein")
        if o.kind != "stitches":
            if not p.get("convert"):
                raise ApiError(f"Der Sprung liegt in der berechneten Form »{o.name}«. Zum Bearbeiten "
                               "wird sie in feste Stiche umgewandelt – mit convert=true bestätigen.")
            jumps.to_stitches(o, self.doc.optimize)
            rec = self.w._refind_jump(rec) or rec
        if action == "connect":
            hidden = jumps.is_covered(self.doc, rec)
            jumps.connect(self.doc, rec)
        else:
            hidden = None
            jumps.set_trim(self.doc, rec, action == "trim_on")
        self.w.sync_items([o.id])
        self._done()
        out = {"index": i, "action": action, "object": o.id}
        if hidden is not None:
            out["connection_hidden"] = hidden
        return out

    def convert_to_stitches(self, p):
        objs = [self._obj(i) for i in (p.get("ids") or [])]
        if not objs:
            raise ApiError("ids angeben")
        self.w.convert_to_stitches(objs)
        return {"converted": [o.id for o in objs]}

    def export_worksheet(self, p):
        path = os.path.expanduser(str(p.get("path", "")))
        if not path:
            raise ApiError("path angeben (Endung .pdf)")
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.w.export_worksheet(path)
        return {"worksheet": path}

    def undo(self, p):
        for _ in range(int(p.get("steps", 1))):
            self.w.undo()
        return {"objects": len(self.doc.objects)}

    def redo(self, p):
        for _ in range(int(p.get("steps", 1))):
            self.w.redo()
        return {"objects": len(self.doc.objects)}

    METHODS = ("get_design", "get_options", "new_design", "set_hoop", "add_text", "add_shape",
               "add_path", "update_object", "route_lines", "delete_objects", "duplicate_object", "set_order",
               "select_objects", "center_design", "digitize_image", "import_embroidery",
               "open_file", "save_project", "export_design", "render_preview", "undo", "redo",
               "optimize_jumps", "get_jumps", "edit_jump", "convert_to_stitches",
               "export_worksheet")

    def call(self, method, params):
        if method not in self.METHODS:
            raise ApiError(f"Unbekannte Funktion {method!r}")
        return getattr(self, method)(params or {})


class ApiServer:
    """Lokaler Socket-Server im Qt-Hauptthread."""

    def __init__(self, window, on_activity=None):
        self.api = DesignAPI(window)
        self.on_activity = on_activity
        self.server = None
        self.buffers = {}

    def start(self):
        path = socket_path()
        QLocalServer.removeServer(path)
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        if not self.server.listen(path):
            self.server = None
            return False
        self.server.newConnection.connect(self._new_conn)
        return True

    def stop(self):
        if self.server:
            self.server.close()
            QLocalServer.removeServer(self.server.fullServerName())
            self.server = None

    def running(self):
        return self.server is not None

    def _new_conn(self):
        while self.server and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            self.buffers[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(lambda s=sock: (self.buffers.pop(s, None), s.deleteLater()))

    def _read(self, sock):
        self.buffers[sock] = self.buffers.get(sock, b"") + bytes(sock.readAll())
        while b"\n" in self.buffers[sock]:
            line, rest = self.buffers[sock].split(b"\n", 1)
            self.buffers[sock] = rest
            if line.strip():
                sock.write(self._handle(line) + b"\n")
                sock.flush()

    def _handle(self, line):
        try:
            msg = json.loads(line)
        except ValueError:
            return json.dumps({"id": None, "error": "Ungültiges JSON"}).encode()
        mid, method = msg.get("id"), msg.get("method")
        if self.on_activity:
            self.on_activity(method)
        try:
            result = self.api.call(method, msg.get("params"))
            return json.dumps({"id": mid, "result": result}).encode()
        except ApiError as e:
            return json.dumps({"id": mid, "error": str(e)}).encode()
        except Exception as e:      # unerwartete Fehler an die KI melden statt abzustürzen
            return json.dumps({"id": mid, "error": f"{type(e).__name__}: {e}"}).encode()
