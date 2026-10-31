"""Datenmodell: Stickobjekte und Dokument."""
import copy
import json
import math
import uuid
import zlib

from shapely import affinity, wkt
from shapely.geometry import LineString, Polygon

from . import DEFAULT_FONT, curves, engine
from .engine import JUMP, STITCH, TRIM
from .threads import HOOPS

DEFAULT_FILL = {"type": "tatami", "color": "#E53935", "angle": 45.0, "density": 0.4,
                "stitch_len": 3.5, "underlay": True, "pull": 0.15,
                "underlay_first": False,  # Unterlage aller Teile vor dem Deckstich
                "color2": "#1E88E5",      # zweite Farbe (Farbverlauf)
                "gradient_reverse": False,
                "satin_type": "satin",    # Säulen-Satin: satin | zigzag | estitch
                "pattern": "standard",   # Tatami-Einstichmuster
                "size": 5.0,             # Mustergröße (Welle, Kreuz, Motiv, Netz)
                "motif": "heart",
                "guide": None,           # geführte Füllung: Führungslinie [[x, y], …] (Objektkoord.)
                "start": None,           # Startpunkt [x, y] (Objektkoordinaten) oder None
                "end": None,             # Endpunkt [x, y]
                "short_inset": 15.0,     # Säulen-Satin: kurze Stiche in engen Kurven (% der Breite)
                "short_dist": 0.25,      # … wenn die Einstiche an einer Seite enger liegen (mm)
                "split_len": 8.0,        # Säulen-Satin: längere Stiche werden geteilt (mm)
                "split_random": False,   # Teilungspunkte zufällig versetzen (keine sichtbare Linie)
                # Feinheiten (wie Ink/Stitch)
                "ul_angle": 90.0,        # Flächen-Unterlage: Winkel zum Deckstich (°)
                "ul_spacing": 2.2,       # … Reihenabstand (mm)
                "ul_inset": 0.6,         # … Abstand zum Rand (mm)
                "ul_layers": 1,          # … Lagen (2 = gekreuzt)
                "ul_contour": True,      # … Randlinie vor den Reihen
                "expand": 0.0,           # Füllfläche erweitern (mm, negativ = schrumpfen)
                "len_random": 0.0,       # zufällige Stichlänge ± % (Deckstich)
                "satin_ul": "auto",      # Säulen-Satin-Unterlage (satin.SATIN_UNDERLAYS)
                "width_random": 0.0,     # Säulen-Satin: zufällige Breite ± %
                "spacing_random": 0.0,   # … zufälliger Stichabstand ± %
                "tie": "auto",           # Vernähstich-Art (engine.TIE_NAMES)
                "tie_force": False,      # auch vor kurzen Sprüngen vernähen
                "gradient_colors": [],   # Farbverlauf: weitere Farben nach color2
                "tartan": None,          # Schottenkaro: [[farbe, breite_mm], …] (None = Royal Stewart)
                "tartan_symmetric": True,    # Streifenfolge gespiegelt wiederholen
                "tartan_scale": 1.0,     # Streifenbreiten skalieren
                "auto_spacing": False,   # Satindichte nach Breite (neue Objekte: an)
                "underlay_auto": False,  # Unterlage nach Größe der Fläche (neue Objekte: an)
                "puff": False,           # 3D-Puff (Schaumstoff): Endkappen, keine Unterlage
                "knockout": True}        # automatisch aussparen (Document.knockout): von später
                                         # gestickten Objekten verdeckte Teile nicht sticken
DEFAULT_BORDER = {"type": "none", "color": "#1A1A1A", "width": 3.0, "stitch_len": 2.5,
                  "density": 0.4, "underlay": True,
                  "repeats": 1,             # Bohnenstich: Wiederholungen (1 = dreifach)
                  "corners": False,         # Steppstich: Ecken/Kreuzungen genau einstechen
                  "len_random": 0.0,        # zufällige Stichlänge ± %
                  "bean_pattern": "",       # Bohnenstich-Muster, z. B. "1 0" (leer = repeats)
                  "corner": "mitre",        # Satinlinie: spitze Ecken mit Gehrung | none
                  "auto_spacing": False}    # Satindichte nach Breite (neue Objekte: an)
DEFAULT_TEXT = {"text": "Text", "font": DEFAULT_FONT, "size": 20.0, "bold": True,
                "italic": False, "spacing": 0.0, "arc": 0.0,
                "embfont": "",        # Stickschrift-ID (leer = Computerschrift)
                "auto_satin": True,   # Computerschrift: schmale Striche als Satin (Profi-Lettering)
                "env": "none",        # Hüllform (textfx.ENVELOPES)
                "env_amount": 0.3,    # Stärke der Hüllform (Anteil der Schrifthöhe)
                "letters": {},        # einzelne Buchstaben: {"index": [dx, dy, drehung, größe%]}
                "emb_density": 0.0,   # 0 = Dichte der Stickschrift
                "emb_pull": 0.0,      # zusätzlicher Zugausgleich in mm
                "path": None,         # Schriftzug entlang Pfad: [[x, y], …] (Objektkoordinaten)
                "path_align": "center",   # start | center | end
                "path_flip": False}   # Pfad andersherum (Text auf der anderen Seite)

STITCHES_PER_MINUTE = 700   # wird aus den Einstellungen gesetzt

KIND_NAMES = {"shape": "Form", "text": "Text", "line": "Linie", "stitches": "Stickdatei",
              "satin": "Satinsäule", "stones": "Strass", "cross": "Kreuzstich",
              "print": "Druckbild"}


class EmbObject:
    def __init__(self, kind, name=None):
        self.id = uuid.uuid4().hex[:10]
        self.kind = kind
        self.name = name or KIND_NAMES.get(kind, kind)
        self.x = self.y = 0.0
        self.rot = 0.0
        self.sx = self.sy = 1.0
        self.fill = dict(DEFAULT_FILL)
        self.border = dict(DEFAULT_BORDER)
        self.geom_wkt = None
        self.points = []
        self.closed = False
        self.text = dict(DEFAULT_TEXT)
        self.blocks = []          # nur kind == "stitches"
        self.cross = None         # nur kind == "cross": Kreuzstich-Raster (crossstitch.py)
        self.image = None         # nur kind == "print": Bild als PNG (base64, printapp.py)
        self.smooth = 0           # Kurvenglättung (Formen/Linien)
        self.curve = None         # Form als Pfade mit Eck-/Rundungspunkten [[[x, y, typ], …], …]
        self.ptypes = None        # Linie: Punkttyp je Punkt (0 Ecke, 1 Rundung)
        self.trim_after = "auto"  # nach dem Objekt: auto | always | never | stop (Maschine hält an)
        self._okey = self._oblocks = None
        self.visible = True
        self.group = None         # Gruppen-ID: gruppierte Objekte werden gemeinsam gewählt
        self.locked = False       # gesperrt: nicht anklickbar/verschiebbar (wie in Inkscape)
        self.layer = None         # Ebenen-ID (Document.layers); None = unterste Ebene
        self._gkey = self._geom = None
        self._skey = self._stitches = None
        self._knock = self._knock_key = None   # automatisches Aussparen (Document.update_knockouts)
        # Profi-Automatiken für neu erstellte Objekte (alte Projekte behalten ihre Werte)
        self.fill.update(auto_spacing=True, underlay_auto=True)
        self.border["auto_spacing"] = True
        if kind == "line":
            self.fill["type"] = "none"
            self.border.update(type="satin", width=2.5)

    # ----------------------------------------------------------- Persistenz
    FIELDS = ("id", "kind", "name", "x", "y", "rot", "sx", "sy", "fill", "border",
              "geom_wkt", "points", "closed", "text", "blocks", "smooth", "curve", "ptypes", "trim_after",
              "visible", "group", "locked", "layer", "cross", "image")

    def to_dict(self):
        return {k: copy.deepcopy(getattr(self, k)) for k in self.FIELDS}

    @classmethod
    def from_dict(cls, d):
        o = cls(d["kind"])
        for k in cls.FIELDS:
            if k in d:
                v = copy.deepcopy(d[k])
                if k == "fill":
                    v = {**DEFAULT_FILL, **v}
                elif k == "border":
                    v = {**DEFAULT_BORDER, **v}
                elif k == "text":
                    v = {**DEFAULT_TEXT, **v}
                setattr(o, k, v)
        return o

    def clone(self):
        d = self.to_dict()
        d["id"] = uuid.uuid4().hex[:10]
        return EmbObject.from_dict(d)

    # ------------------------------------------------------------ Geometrie
    def set_geometry(self, geom):
        """Setzt Formgeometrie (Weltkoordinaten) – zentriert und positioniert."""
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        self.geom_wkt = affinity.translate(geom, -cx, -cy).wkt
        self.x, self.y = cx, cy

    def set_points(self, pts, closed=False):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        self.points = [[p[0] - cx, p[1] - cy] for p in pts]
        self.closed = closed
        self.x, self.y = cx, cy

    def local_geometry(self):
        if self.kind == "print":           # Druckbild: Rechteck in Bildgröße
            key = ("print", self.fill.get("print_w"), self.fill.get("print_h"))
            if key != self._gkey:
                from .printapp import geometry
                self._gkey, self._geom = key, geometry(self)
            return self._geom
        if self.kind == "cross":           # Kreuzstich: belegte Kästchen und Rückstiche
            key = ("cross", id(self.cross), len(self.cross["cells"]), len(self.cross["back"]))
            if key != self._gkey:
                from .crossstitch import geometry
                self._gkey, self._geom = key, geometry(self.cross)
            return self._geom
        if self.kind == "stones":          # Strass: Kreisflächen, keine Stiche
            key = json.dumps([self.points, self.fill.get("stone")])
            if key != self._gkey:
                from .stones import geometry
                self._gkey, self._geom = key, geometry(self)
            return self._geom
        if self.kind in ("shape", "line", "satin"):
            key = json.dumps(self._gkey_source())
        elif self.kind == "text":
            key = json.dumps(self.text, sort_keys=True)
        else:
            return None
        if key != self._gkey:
            if self.kind == "text" and self.text.get("embfont"):
                g = self._emb_render(self.text["size"])[1]
            elif self.kind == "text":
                from .textgeom import text_geometry
                g = text_geometry(**self.text)
            else:
                g = self.raw_geometry()
            if self.kind != "text" and self.smooth:
                g = engine.smooth_geometry(g, self.smooth)
            self._gkey, self._geom = key, g
        return self._geom

    # ------------------------------------------------- Bearbeiten (Punkte)
    def to_world(self, x, y):
        """Objektkoordinate (vor Skalierung/Drehung) -> Arbeitsfläche."""
        x, y = x * self.sx, y * self.sy
        c, s = math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))
        return x * c - y * s + self.x, x * s + y * c + self.y

    def to_local(self, x, y):
        x, y = x - self.x, y - self.y
        c, s = math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))
        x, y = x * c + y * s, -x * s + y * c
        return x / (self.sx or 1e-9), y / (self.sy or 1e-9)

    def satin_rails(self):
        """Säulen-Satin: beide Schienen als Polygonzug (Objektkoordinaten) und die Stege."""
        a, b = self.curve
        ra, rb = curves.polyline(a, False), curves.polyline(b, False)
        rungs = [((p[0], p[1]), (q[0], q[1])) for p, q in list(zip(a, b))[1:-1]]
        return ra, rb, rungs

    def set_satin(self, a, b):
        self.curve = [[[float(p[0]), float(p[1]), int(p[2])] for p in a],
                      [[float(p[0]), float(p[1]), int(p[2])] for p in b]]

    def raw_geometry(self):
        """Form ohne Glättung – das, was beim Punkte-Bearbeiten verändert wird."""
        if self.kind == "satin":
            from . import satin
            ra, rb, _ = self.satin_rails()
            return satin.outline(ra, rb)
        if self.kind == "shape":
            if self.curve:
                return curves.rings_geometry(self.curve)
            return wkt.loads(self.geom_wkt) if self.geom_wkt else Polygon()
        if self.kind == "line":
            if self.ptypes and any(self.ptypes):
                return curves.line_geometry(self.line_nodes(), self.closed)
            pts = self.points + ([self.points[0]] if self.closed and self.points else [])
            return LineString(pts) if len(pts) >= 2 else LineString()
        return self.local_geometry()

    def set_raw_geometry(self, geom):
        """Setzt eine fertige Kontur (Eck-/Rundungsinformation geht dabei verloren)."""
        if self.kind == "line":
            pts = [list(p[:2]) for p in geom.coords]
            if self.closed and len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            self.points = pts
            self.ptypes = None
        else:
            self.geom_wkt = geom.wkt
            self.curve = None

    def line_nodes(self):
        t = self.ptypes if self.ptypes and len(self.ptypes) == len(self.points) else \
            [curves.CORNER] * len(self.points)
        return [[p[0], p[1], k] for p, k in zip(self.points, t)]

    def set_line_nodes(self, nodes):
        self.points = [[n[0], n[1]] for n in nodes]
        self.ptypes = [int(n[2]) for n in nodes] if any(n[2] for n in nodes) else None

    def set_curve(self, rings):
        """Form aus Eck-/Rundungspfaden setzen (Objektkoordinaten)."""
        self.curve = [[[float(p[0]), float(p[1]), int(p[2])] for p in r] for r in rings if len(r) >= 3]
        self.geom_wkt = curves.rings_geometry(self.curve).wkt

    def world_geometry(self):
        g = self.shaped_geometry()
        return None if g is None else affinity.translate(g, self.x, self.y)

    def _xform(self, geom):
        g = affinity.scale(geom, self.sx, self.sy, origin=(0, 0))
        return affinity.rotate(g, self.rot, origin=(0, 0))

    def shaped_geometry(self):
        g = self.local_geometry()
        return None if g is None else self._xform(g)

    def local_bounds(self):
        if self.kind == "stitches":
            pts = [s for b in self.blocks for s in b["stitches"]]
            return engine.bounds_of(pts)
        g = self.local_geometry()
        return g.bounds if g is not None and not g.is_empty else (0, 0, 0, 0)

    def local_size(self):
        b = self.local_bounds()
        return b[2] - b[0], b[3] - b[1]

    # --------------------------------------------------------------- Stiche
    def _stitch_key(self):
        base = [self.kind, self.sx, self.sy, self.rot]
        if self.kind == "stitches":
            return json.dumps(base + [id(self.blocks), len(self.blocks)])
        if self.kind == "cross":           # Daten werden beim Bearbeiten immer neu gesetzt
            return json.dumps(base + [id(self.cross), len(self.cross["cells"]),
                                      len(self.cross["back"]), self.cross.get("passes", 1),
                                      engine.TIE_MODE])
        return json.dumps(base + [self.fill, self.border, self._gkey_source(), engine.FABRIC,
                                  self._knock_key], sort_keys=True)

    def _gkey_source(self):
        if self.kind == "shape":
            return [self.curve or self.geom_wkt, self.smooth]
        if self.kind == "text":
            return self.text
        if self.kind == "satin":
            return [self.curve]
        return [self.points, self.ptypes, self.closed, self.smooth]

    def _emb_render(self, size, path_scale=(1.0, 1.0)):
        from . import embfont
        t = self.text
        if not embfont.exists(t["embfont"]):
            raise ValueError(f"Stickschrift {t['embfont']!r} nicht gefunden")
        path = t.get("path")
        if path and len(path) >= 2:
            fx, fy = path_scale
            path = tuple((float(p[0]) * fx, float(p[1]) * fy) for p in path)
        else:
            path = None
        return embfont.render(t["embfont"], t["text"] or " ", size, t.get("spacing", 0.0),
                              t.get("arc", 0.0), t.get("emb_density", 0.0), t.get("emb_pull", 0.0),
                              bool(self.fill.get("underlay", True)), None, path,
                              t.get("path_align", "center"), bool(t.get("path_flip", False)),
                              *self._text_fx())

    def _text_fx(self):
        """(hüllform, buchstaben) als hashbare Argumente für embfont.render/letter_centers."""
        from .textfx import letters_key
        t = self.text
        env = t.get("env", "none")
        envelope = (env, round(float(t.get("env_amount", 0.3)), 3)) if env and env != "none" else None
        return envelope, letters_key(t.get("letters"))

    def letter_centers(self):
        """[(index, zeichen, x, y)] der Buchstaben in Objektkoordinaten (für Anfasser)."""
        from . import embfont, textgeom
        t = self.text
        if t.get("embfont") and embfont.exists(t["embfont"]):
            path = t.get("path")
            path = tuple((float(p[0]), float(p[1])) for p in path) if path and len(path) >= 2 else None
            return embfont.letter_centers(t["embfont"], t["text"] or " ", t["size"],
                                          t.get("spacing", 0.0), t.get("arc", 0.0), path,
                                          t.get("path_align", "center"),
                                          bool(t.get("path_flip", False)), *self._text_fx())
        return textgeom.letter_centers(**t)

    def shaped_point(self, p):
        """Punkt in Objektkoordinaten -> Objektrahmen (skaliert und gedreht, nicht verschoben)."""
        x, y = self.to_world(p[0], p[1])
        return x - self.x, y - self.y

    def shaped_points(self, pts):
        return [self.shaped_point(p) for p in pts] if pts else None

    def _compute_stitches(self):
        """Liste von (farbschlüssel, stiche) im Objektrahmen – mit den Vernäh-Einstellungen
        des Objekts."""
        tie = self.fill.get("tie", "auto")
        old = engine.TIE_STYLE, engine.TIE_FORCE
        engine.TIE_STYLE = None if tie == "auto" else tie
        engine.TIE_FORCE = bool(self.fill.get("tie_force", False))
        own = self.fill, self.border
        if self.kind != "stitches":         # Stoffart: Dichte, Zugausgleich, Unterlage anpassen
            self.fill, self.border = engine.fabric_adjust(self.fill, self.border)
        try:
            return self._compute_stitches_raw()
        finally:
            engine.TIE_STYLE, engine.TIE_FORCE = old
            self.fill, self.border = own

    def _compute_stitches_raw(self):
        if self.kind in ("stones", "print"):   # aufgebügelt bzw. gedruckt, nicht gestickt
            return []
        if self.kind == "cross":           # Kreuzstich: Stiche aus dem Raster, dann skalieren/drehen
            from .crossstitch import stitches
            c, s = math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))
            out = []
            for col, sts in stitches(self.cross):
                pts = [((x * self.sx) * c - (y * self.sy) * s, (x * self.sx) * s + (y * self.sy) * c, f)
                       for x, y, f in sts]
                out.append((("const", col), pts))
            return out
        if self.kind == "text" and self.text.get("embfont"):
            # in echter Größe neu berechnen (Dichte bleibt richtig), Verzerrung/Drehung danach
            ay = abs(self.sy) or 1.0
            if self.text.get("path"):
                # Text am Pfad: Pfad mitskalieren, Buchstaben unverzerrt in echter Höhe
                blocks, _ = self._emb_render(self.text["size"] * ay, (self.sx, self.sy))
                fx = fy = 1.0
            else:
                blocks, _ = self._emb_render(self.text["size"] * ay)
                fx, fy = self.sx / ay, (1 if self.sy >= 0 else -1)
            c, s = math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))
            out = []
            for col, sts in blocks:
                pts = [((x * fx) * c - (y * fy) * s, (x * fx) * s + (y * fy) * c, f) for x, y, f in sts]
                out.append((("fill",) if col is None else ("const", col), pts))
            return out
        if self.kind == "stitches":
            c, s = math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))
            out = []
            for i, b in enumerate(self.blocks):
                pts = []
                for x, y, f in b["stitches"]:
                    x, y = x * self.sx, y * self.sy
                    pts.append((x * c - y * s, x * s + y * c, f))
                out.append((("block", i), pts))
            return out
        if self.kind == "satin":
            from . import satin
            ra, rb, rungs = self.satin_rails()
            X = lambda pts: list(self._xform(LineString(pts)).coords) if len(pts) > 1 else pts
            ra, rb = X(ra), X(rb)
            rungs = [tuple(X(list(r))) for r in rungs]
            width = sum(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(ra[::5], rb[::5])) / \
                max(1, len(ra[::5]))
            ul = bool(self.fill.get("underlay", True))
            st = self.fill.get("satin_type", "satin")
            if st != "satin":
                ul = ul and st == "zigzag"
            f = self.fill
            # Start-/Endpunkt: Säule passend herum bzw. mit Rückweg (Unterlage hin, Satin zurück)
            ra, rb, back = satin.orient_column(
                ra, rb, self.shaped_point(f["start"]) if f.get("start") else None,
                self.shaped_point(f["end"]) if f.get("end") else None)
            cw, co, zz = satin.underlay_flags(f.get("satin_ul", "auto"), width, st) if ul else \
                (False, False, False)
            pts = satin.satin_stitches(ra, rb, rungs,
                                       spacing=max(0.2, engine.satin_spacing(f, width)),
                                       caps=bool(f.get("puff")),
                                       pull=f.get("pull", 0.2), center_walk=cw,
                                       zigzag_underlay=zz, contour=co, kind=st,
                                       width_jitter=f.get("width_random", 0.0) / 100.0,
                                       spacing_jitter=f.get("spacing_random", 0.0) / 100.0,
                                       max_len=max(1.0, f.get("split_len", 8.0)),
                                       short_inset=f.get("short_inset", 0.0) / 100.0,
                                       short_dist=f.get("short_dist", 0.25),
                                       random_split=bool(f.get("split_random", False)),
                                       seed=zlib.crc32(self.id.encode()),
                                       back=back)
            if len(pts) < 2:
                return []
            out = []
            engine.connect(out, pts)
            return [(("fill",), engine.finish(out))]
        geom = self.shaped_geometry()
        if geom is None or geom.is_empty:
            return []
        res = []
        if self.kind in ("shape", "text") and self.fill["type"] == "applique":
            parts = engine.applique_stitches(geom, self.border.get("width", 3.0),
                                             self.fill.get("pattern", "zigzag")
                                             if self.fill.get("pattern") in ("zigzag", "run") else "zigzag",
                                             self.border.get("density", 0.4))
            for k, sts in enumerate(parts):
                if not sts:
                    continue
                if k > 0:      # Stopp vor Heftstich und Satinrand
                    sts = [(sts[0][0], sts[0][1], engine.STOP)] + sts
                res.append((("border",), sts))
            return res
        # automatisches Aussparen: die Füllung lässt Verdecktes weg, der Rand folgt der Kontur
        fgeom = self._knocked(geom)
        if self.kind in ("shape", "text") and self.fill["type"] == "gradient":
            f = dict(self.fill)
            f["angle"] = f["angle"] + self.rot
            parts = engine.gradient_fill(fgeom, f) if not fgeom.is_empty else []
            extra = engine.gradient_colors(self.fill)[2:]
            for i, sts in enumerate(parts):
                if sts:
                    key = ("fill",) if i == 0 else ("fill2",) if i == 1 else ("const", extra[i - 2])
                    res.append((key, engine.finish(sts)))
        elif self.kind in ("shape", "text") and self.fill["type"] == "tartan":
            f = dict(self.fill)
            f["angle"] = f["angle"] + self.rot
            for col, sts in (engine.tartan_fill(fgeom, f) if not fgeom.is_empty else []):
                res.append((("const", col), sts))
        elif self.kind in ("shape", "text") and self.fill["type"] != "none":
            f = dict(self.fill)
            f["angle"] = f["angle"] + self.rot
            f["guide"] = self.shaped_points(f.get("guide"))
            f["start"] = self.shaped_point(f["start"]) if f.get("start") else None
            f["end"] = self.shaped_point(f["end"]) if f.get("end") else None
            if self.border["type"] != "none" and \
                    self.border["color"].upper() == self.fill["color"].upper():
                # Rand in Füllfarbe: Element für Element (Teilfläche + ihr Rand, dann weiter)
                sts = engine.element_fill(geom, f, self.border,
                                          cut=self._knock if fgeom is not geom else None)
                if sts:
                    res.append((("fill",), engine.finish(sts)))
                return res
            if self.kind == "text" and f["type"] == "tatami" and self.text.get("auto_satin", True) \
                    and not self.text.get("embfont") and not fgeom.is_empty:
                # Computerschrift: schmale Striche als Satin, der der Buchstabenform folgt
                from .textsatin import lettering_stitches
                sts = lettering_stitches(fgeom, f, self.text.get("size", 20.0) * abs(self.sy))
            else:
                sts = engine.fill_with_underlay(fgeom, f) if not fgeom.is_empty else []
            if sts:
                res.append((("fill",), engine.finish(sts)))
        if self.border["type"] != "none":
            prev = next((s for _, b in reversed(res) for s in reversed(b) if s[2] == STITCH), None)
            if prev is None and self.kind in ("shape", "text") and self.fill.get("start"):
                prev = self.shaped_point(self.fill["start"])
            sts = engine.border_stitches(geom, self.border, start=prev[:2] if prev else None,
                                         exact=bool(self.fill.get("start") or self.fill.get("end")))
            if sts:
                res.append((("border",), engine.finish(sts)))
        return res

    def _knocked(self, geom):
        """Füllfläche ohne die von später gestickten Objekten verdeckten Bereiche
        (self._knock, Objektrahmen) – schmale Reststreifen und Krümel fallen weg."""
        if self._knock is None:
            return geom
        return engine.knock_out(geom, self._knock)

    def stitch_blocks(self):
        """[(farbe, stiche)] im Objektrahmen (ohne Verschiebung)."""
        key = self._stitch_key()
        if key != self._skey:
            self._stitches = self._compute_stitches()
            self._skey = key
        out = []
        for ck, sts in self._stitches:
            if ck[0] == "fill":
                col = self.fill["color"]
            elif ck[0] == "fill2":
                col = self.fill.get("color2", "#1E88E5")
            elif ck[0] == "border":
                col = self.border["color"]
            elif ck[0] == "const":
                col = ck[1]
            else:
                col = self.blocks[ck[1]]["color"]
            out.append((col, sts))
        return out

    def final_blocks(self, optimize=False):
        """Stiche, wie sie gestickt werden (Objektrahmen). optimize: Sprünge innerhalb des
        Objekts minimieren – nur für berechnete Objekte; Stickdateien bleiben, wie sie sind
        (dort entscheidet der Nutzer über »Sprungstiche optimieren« bzw. von Hand)."""
        blocks = self.stitch_blocks()
        if not optimize or self.kind == "stitches":
            return blocks
        if self._okey != self._skey:
            from .optimize import optimize_blocks
            res, _ = optimize_blocks([(i, s) for i, (_, s) in enumerate(blocks)], trials=4)
            self._oblocks = [s for _, s in res]
            self._okey = self._skey
        return [(c, s) for (c, _), s in zip(blocks, self._oblocks)]

    def world_blocks(self, optimize=False):
        return [(c, [(x + self.x, y + self.y, f) for x, y, f in s])
                for c, s in self.final_blocks(optimize)]

    def colors(self):
        return [c for c, _ in self.stitch_blocks()]


def _drop_short(sts, minimum):
    """Zu kurze Stiche zusammenfassen (Einstich weglassen, außer am Ende eines Laufs)."""
    out, last = [], None
    for k, s in enumerate(sts):
        if s[2] == STITCH and last is not None and engine.dist(last, s) < minimum:
            nxt = sts[k + 1] if k + 1 < len(sts) else None
            if nxt is not None and nxt[2] == STITCH:
                continue
        out.append(s)
        last = s if s[2] == STITCH else (None if s[2] in (JUMP, TRIM) else last)
    return out


def _column_area(o):
    """Fläche einer Satinsäule bzw. Satinlinie (Welt) – darunter darf Auto-Satin laufen."""
    g = o.world_geometry()
    if g is None or g.is_empty:
        return None
    if o.kind == "line":
        g = g.buffer(max(0.4, o.border.get("width", 3.0) / 2 - 0.3), cap_style=2)
    else:
        g = g.buffer(-0.25)
    return None if g.is_empty else g


def autosatin_groups(items):
    """Auto-Satin-Gruppen: {gruppe: [objekte in Stickreihenfolge]} samt Flächen."""
    groups = {}
    for o, *_ in items:
        g = o.fill.get("autosatin") if o.kind in ("satin", "line") else None
        if g and o not in groups.setdefault(g, {"objs": [], "areas": {}})["objs"]:
            groups[g]["objs"].append(o)
            groups[g]["areas"][o.id] = _column_area(o)
    return groups


def autosatin_link(groups, a_obj, b_obj, a, b):
    """Weg von Säule a_obj (Ende a) zur nächsten Säule b_obj (Anfang b) derselben Auto-Satin-
    Gruppe – als Steppstich unter den Säulen, bevorzugt unter noch kommenden. None = Sprung."""
    g = a_obj.fill.get("autosatin")
    if not g or g != b_obj.fill.get("autosatin") or g not in groups or a_obj is b_obj:
        return None
    from shapely.ops import unary_union
    from .optimize import _route, _travel_points
    objs = groups[g]["objs"]
    areas = groups[g]["areas"]
    if "cover" not in groups[g]:
        groups[g]["cover"] = unary_union([x for x in areas.values() if x is not None])
    cover = groups[g]["cover"]
    if cover.is_empty:
        return None
    k = objs.index(b_obj) if b_obj in objs else 0
    later = unary_union([areas[x.id] for x in objs[k:] if areas.get(x.id) is not None])
    path = _route(tuple(a[:2]), tuple(b[:2]), cover.buffer(0.3), detour=(3.0, 20.0),
                  within=cover.bounds, prefer=later if not later.is_empty else None, penalty=4.0)
    return _travel_points(path) if path else None


def scan_gaps(sts):
    """Sprünge innerhalb einer Stichliste: (gap_start, gap_ende, a, b, mit_schnitt).
    gap_start = erster Nicht-Stich nach einem Stich, gap_ende = Index des nächsten Stichs."""
    gaps = []
    last = None
    k, n = 0, len(sts)
    while k < n:
        if sts[k][2] == STITCH:
            last = k
            k += 1
            continue
        gs = k
        while k < n and sts[k][2] != STITCH:
            k += 1
        if last is not None and k < n and not any(sts[i][2] == engine.STOP for i in range(gs, k)):
            has_trim = any(sts[i][2] == TRIM for i in range(gs, k))
            gaps.append((gs, k, tuple(sts[last][:2]), tuple(sts[k][:2]), has_trim))
    return gaps


def knock_target(o):
    """Kann das Objekt verdeckte Bereiche aussparen? Flächen und Schriftzüge in Computerschrift
    mit Füllstich (nicht Applikation), sofern beim Objekt nicht abgeschaltet."""
    return o.kind in ("shape", "text") and not (o.kind == "text" and o.text.get("embfont")) \
        and o.fill.get("type", "none") not in ("none", "applique") and o.fill.get("knockout", True)


def cover_area(o):
    """Fläche (Welt), die ein Objekt mit Stichen bzw. Applikationsstoff deckt, oder None."""
    g = o.world_geometry()
    if g is None or g.is_empty:
        return None
    satin_border = o.border.get("type") == "satin"
    w = o.border.get("width", 3.0) / 2
    if o.kind in ("shape", "text"):
        filled = o.fill.get("type", "none") != "none" or \
            (o.kind == "text" and o.text.get("embfont"))
        if satin_border and o.kind == "shape":
            band = g.boundary.buffer(w, cap_style=2, join_style=2)
            return g.union(band) if filled else band
        return g if filled else None
    if o.kind == "satin":
        return g
    if o.kind == "line" and satin_border:
        return g.buffer(w, cap_style=2, join_style=2)
    return None


def _cover_info(o, margin):
    """Deckfläche eines Objekts samt Signatur (zwischengespeichert, solange sich Lage, Form
    und Stichart nicht ändern) – None, wenn es nichts deckt oder die Form nicht lesbar ist."""
    try:
        return _cover_info_raw(o, margin)
    except Exception:       # z. B. Stickschrift fehlt, ungültige Form
        o._cov = None
        return None


def _cover_info_raw(o, margin):
    o.local_geometry()                          # hält o._gkey aktuell
    target = knock_target(o)
    sig = hash((o.kind, o._gkey, o.x, o.y, o.sx, o.sy, o.rot, o.fill.get("type"), target,
                o.border.get("type"), o.border.get("width"), margin))
    cov = getattr(o, "_cov", None)
    if cov is None or cov["sig"] != sig:
        world = cover_area(o)
        cov = o._cov = {"sig": sig, "world": None, "shrunk": None, "bounds": None}
        if world is not None:
            shrunk = world.buffer(-margin, join_style=2) if margin > 0 else world
            cov.update(world=o.world_geometry() if target else world, bounds=world.bounds,
                       shrunk=None if shrunk.is_empty else shrunk)
    return cov if cov["world"] is not None else None


def new_layer(name):
    return {"id": uuid.uuid4().hex[:8], "name": name, "visible": True, "locked": False}


class Document:
    def __init__(self):
        self.hoop = 1
        self.fabric = "#FFFFFF"
        self.fabric_type = "standard"   # Stoffart (engine.FABRIC_PROFILES)
        self.objects = []
        self.optimize = False     # Sprünge in Formen beim Sticken/Export optimieren
        self.color_sort = True    # Farbblöcke zusammenfassen (weniger Farbwechsel)
        self.order_mode = "auto"  # Reihenfolge gleicher Farben: auto (kürzeste Wege) | manual
        # Automatisch aussparen: was später gestickte Objekte verdecken, wird darunter nicht
        # gestickt – nur beim Berechnen der Stiche, die Formen selbst bleiben unverändert
        self.knockout = False
        self.knockout_margin = 1.0    # so viel bleibt unter dem oberen Objekt überlappend (mm)
        self._kpairs = {}             # Zwischenspeicher: (unten, oben) -> verdeckt merklich?
        # Vorlage zum Nachzeichnen: {"png": base64, "x", "y", "width", "opacity",
        # "visible", "locked"} – wird gespeichert, aber nie gestickt
        self.template = None
        # Ebenen von unten nach oben (untere zuerst gestickt) – wie in Inkscape
        self.layers = [new_layer("Ebene 1")]
        self.active_layer = self.layers[0]["id"]

    # ----------------------------------------------------------------- Ebenen
    def layer_of(self, o):
        for L in self.layers:
            if L["id"] == o.layer:
                return L
        return self.layers[0]

    def layer_index(self, o):
        L = self.layer_of(o)
        return self.layers.index(L)

    def layer_shown(self, o):
        return bool(self.layer_of(o)["visible"])

    def sort_by_layers(self):
        """Stickreihenfolge: Ebene für Ebene von unten nach oben (innerhalb einer Ebene
        bleibt die Reihenfolge erhalten)."""
        order = {L["id"]: k for k, L in enumerate(self.layers)}
        first = self.layers[0]["id"]
        self.objects.sort(key=lambda o: order.get(o.layer, order[first]))

    def apply_layer_flags(self):
        """Ebenen-Zustand an die Objekte geben (für Darstellung und Auswahl)."""
        ids = {L["id"] for L in self.layers}
        for o in self.objects:
            if o.layer not in ids:                 # neue/alte Objekte: aktive Ebene
                o.layer = self.active_layer if self.active_layer in ids else self.layers[0]["id"]
            L = self.layer_of(o)
            o._lhidden = not L["visible"]
            o._llocked = bool(L["locked"])

    @property
    def hoop_size(self):
        _, w, h = HOOPS[min(max(0, self.hoop), len(HOOPS) - 1)]
        return w, h

    def to_json(self, with_template=False):
        """with_template=False für Rückgängig-Schritte (spart das Mitkopieren des Bildes)."""
        d = {"app": "StickStudio", "version": 1, "hoop": self.hoop,
             "hoop_size": list(self.hoop_size), "fabric": self.fabric,
             "fabric_type": self.fabric_type,
             "color_sort": self.color_sort, "order_mode": self.order_mode,
             "knockout": self.knockout, "knockout_margin": self.knockout_margin,
             "layers": self.layers, "active_layer": self.active_layer,
             "objects": [o.to_dict() for o in self.objects]}
        if with_template and self.template:
            d["template"] = self.template
        return json.dumps(d)

    def load_json(self, text):
        d = json.loads(text)
        self.hoop = d.get("hoop", 1)
        size = d.get("hoop_size")
        if isinstance(size, list) and len(size) == 2:
            # Größe zählt (auch eigene Rahmen von anderen Rechnern), der Index nur als Rückfall
            from .threads import hoop_for_size
            try:
                self.hoop = hoop_for_size(*size)
            except (TypeError, ValueError):
                pass
        self.fabric = d.get("fabric", "#FFFFFF")
        self.fabric_type = d.get("fabric_type", "standard") \
            if d.get("fabric_type") in engine.FABRIC_PROFILES else "standard"
        self.color_sort = bool(d.get("color_sort", True))
        self.order_mode = d.get("order_mode", "auto") if d.get("order_mode") in ("auto", "manual") else "auto"
        self.knockout = bool(d.get("knockout", False))
        try:
            self.knockout_margin = min(5.0, max(0.0, float(d.get("knockout_margin", 1.0))))
        except (TypeError, ValueError):
            self.knockout_margin = 1.0
        if "template" in d:
            self.template = d["template"]
        layers = d.get("layers") or []
        self.layers = [dict(new_layer(L.get("name", "Ebene")), **L) for L in layers
                       if isinstance(L, dict) and L.get("id")] or [new_layer("Ebene 1")]
        ids = [L["id"] for L in self.layers]
        self.active_layer = d.get("active_layer") if d.get("active_layer") in ids else ids[-1]
        old = {o.id: o for o in self.objects}
        objs = []
        for od in d.get("objects", []):
            o = EmbObject.from_dict(od)
            prev = old.get(o.id)
            if prev is not None:   # Caches wiederverwenden (schnelles Rückgängig)
                o._gkey, o._geom = prev._gkey, prev._geom
                if prev.kind != "stitches":
                    o._skey, o._stitches = prev._skey, prev._stitches
                    o._knock, o._knock_key = prev._knock, prev._knock_key
                o._cov = getattr(prev, "_cov", None)
            objs.append(o)
        self.objects = objs
        self.apply_layer_flags()

    def find(self, oid):
        for o in self.objects:
            if o.id == oid:
                return o
        return None

    # ------------------------------------------------ Automatisch aussparen
    def update_knockouts(self):
        """Verdeckte Bereiche aller Flächen neu bestimmen (Document.knockout). Ändert nur die
        vorübergehenden Aussparungen der Objekte (o._knock, Objektrahmen) – die Stiche rechnet
        stitch_blocks() bei Bedarf neu. Liefert die Objekte, deren Aussparung sich geändert hat."""
        margin = round(float(self.knockout_margin), 3)
        shown = [o for o in self.objects if o.visible and self.layer_shown(o)]
        covers = [_cover_info(o, margin) for o in shown] if self.knockout else []
        if len(self._kpairs) > 20000:
            self._kpairs.clear()
        changed = []
        for i, o in enumerate(shown if self.knockout else []):
            key = knock = None
            if knock_target(o):
                own = covers[i]
                hits = [c for c in covers[i + 1:] if c is not None and own is not None
                        and self._covers(own, c)]
                if hits:
                    key = [margin, round(o.x, 4), round(o.y, 4)] + [c["sig"] for c in hits]
                    if key != o._knock_key:
                        from shapely.ops import unary_union
                        try:
                            knock = affinity.translate(unary_union([c["shrunk"] for c in hits]),
                                                       -o.x, -o.y)
                        except Exception:    # ungültige Form: dann eben ohne Aussparung
                            knock = None
            if key != o._knock_key:
                o._knock, o._knock_key = knock, key
                changed.append(o)
        rest = set(map(id, shown)) if self.knockout else set()
        for o in self.objects:
            if id(o) not in rest and o._knock_key is not None:
                o._knock = o._knock_key = None
                changed.append(o)
        return changed

    def _covers(self, low, top):
        """Verdeckt top (merklich, über 1 mm²) einen Teil der Fläche low?"""
        lb, tb = low["bounds"], top["bounds"]
        if top["shrunk"] is None or tb[0] > lb[2] or tb[2] < lb[0] or tb[1] > lb[3] or tb[3] < lb[1]:
            return False
        k = (low["sig"], top["sig"])
        hit = self._kpairs.get(k)
        if hit is None:
            try:
                hit = low["world"].intersection(top["shrunk"]).area > 1.0
            except Exception:       # ungültige Form
                hit = False
            self._kpairs[k] = hit
        return hit

    # ---------------------------------------------------- Export-Stichfolge
    def machine_blocks(self, optimize=None, records=None):
        """Zusammengeführte Farbblöcke für Maschine/Simulation: [(farbe, stiche)].
        records (Liste) wird mit allen Sprüngen samt Herkunft gefüllt (für den Sprung-Editor)."""
        if optimize is None:
            optimize = self.optimize
        self.update_knockouts()
        items = [(o, bi, color, sts) for o in self.objects if o.visible and self.layer_shown(o)
                 for bi, (color, sts) in enumerate(o.world_blocks(optimize))
                 if any(s[2] == STITCH for s in sts)]
        if self.color_sort:
            from .colororder import sort_blocks
            items = sort_blocks(items, shortest=self.order_mode == "auto")
        self.last_order = [(o.id, bi, color) for o, bi, color, _ in items]   # für den Reihenfolge-Editor
        merged = []
        prev_obj = None
        groups = autosatin_groups(items)
        for o, bi, color, sts in items:
            first = next(k for k, s in enumerate(sts) if s[2] == STITCH)
            if merged and merged[-1][0].upper() == color.upper():
                cur = merged[-1][1]
                last = next(s for s in reversed(cur) if s[2] == STITCH)
                b = sts[first]
                d = engine.dist(last, b)
                mode = prev_obj.trim_after if prev_obj is not o else "auto"
                trim = mode in ("always", "stop") or (mode == "auto" and d > engine.TRIM_DISTANCE)
                link = autosatin_link(groups, prev_obj, o, last, b) if mode == "auto" and \
                    d > engine.DIRECT_TRAVEL else None
                if link:                    # Auto-Satin: verdeckter Steppstich statt Sprung
                    cur.extend((x, y, STITCH) for x, y in link)
                    trim = False
                    sts = sts[first:]
                elif records is not None:
                    records.append({"kind": "between", "obj": prev_obj.id, "obj_b": o.id,
                                    "same": prev_obj is o, "a": last[:2], "b": b[:2],
                                    "trim": trim, "mblock": len(merged) - 1,
                                    "mpos": len(cur), "mode": mode})
                if trim:
                    cur.append((last[0], last[1], TRIM))
                if mode == "stop":          # Maschine hält an (z. B. Applikation, Puffschaum)
                    cur.append((last[0], last[1], engine.STOP))
                cur.extend(sts)
                base = len(cur) - len(sts)
            else:
                # Mehrnadel-Maschinen wechseln die Farbe ohne anzuhalten: ein gewünschter Stopp
                # (Applikation, Puffschaum) muss dann ausdrücklich in der Datei stehen
                if merged and prev_obj is not None and prev_obj is not o and \
                        getattr(prev_obj, "trim_after", "auto") == "stop" and engine.EXPLICIT_STOPS:
                    prev = merged[-1][1]
                    end = next((s for s in reversed(prev) if s[2] == STITCH), None)
                    if end is not None and prev[-1][2] != engine.STOP:
                        prev.append((end[0], end[1], engine.STOP))
                merged.append((color, list(sts)))
                base = 0
            if records is not None:
                for g in scan_gaps(sts):
                    records.append({"kind": "inside", "obj": o.id, "block": bi,
                                    "gs": g[0], "ge": g[1], "a": g[2], "b": g[3],
                                    "trim": g[4], "mblock": len(merged) - 1,
                                    "mpos": base + g[0]})
            prev_obj = o
        if records is None and engine.MIN_STITCH > 0:
            merged = [(c, _drop_short(sts, engine.MIN_STITCH)) for c, sts in merged]
        return merged

    def stats(self):
        blocks = self.machine_blocks()
        n = jumps = trims = stops = 0
        allpts = []
        for _, sts in blocks:
            for s in sts:
                if s[2] == STITCH:
                    n += 1
                    allpts.append(s)
                elif s[2] == JUMP:
                    jumps += 1
                elif s[2] == TRIM:
                    trims += 1
                elif s[2] == engine.STOP:
                    stops += 1
        b = engine.bounds_of(allpts)
        minutes = n / float(STITCHES_PER_MINUTE) + max(0, len(blocks) - 1) * 0.5 + trims * 0.05
        return {"stitches": n, "colors": len(blocks), "jumps": jumps, "trims": trims, "stops": stops,
                "width": b[2] - b[0], "height": b[3] - b[1], "minutes": minutes,
                "bounds": b}
