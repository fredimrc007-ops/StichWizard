"""Word Sculpt: Wörter füllen eine Form (Herz, Kreis, Stern … oder die ausgewählte Form).
Die Form wird in Zeilen geteilt; jede Zeile bekommt so viele Wörter, wie hineinpassen, und
wird auf die Breite der Form gedehnt bzw. gestaucht. Einträge im Format von
templates.TEMPLATES."""
from shapely import affinity
from shapely.geometry import LineString
from shapely.ops import unary_union

from . import shapes, templates
from .model import EmbObject

FONTS = templates.FONT_CHOICES + [("Klein & klar", "small")]
SHAPES = [(n, n) for n in ("Herz", "Kreis", "Stern", "Wolke", "Haus", "Tropfen", "Blatt",
                            "Sechseck", "Schmetterling", "Raute")]
MIN_SX, MAX_SX = 0.85, 1.12      # so weit darf eine Zeile gestaucht bzw. gedehnt werden
SPACING = 0.18                    # größter zusätzlicher Buchstabenabstand (Anteil der Zeilenhöhe)
MIN_H = 5.0                       # kleinste Schrifthöhe (mm), die noch sauber stickt


def _intervals(geom, y, x0, x1):
    """x-Bereiche, in denen die waagerechte Linie y in der Form liegt."""
    g = geom.intersection(LineString([(x0, y), (x1, y)]))
    out = []
    for part in getattr(g, "geoms", [g]):
        if part.is_empty or part.geom_type != "LineString":
            continue
        xs = [c[0] for c in part.coords]
        out.append((min(xs), max(xs)))
    return sorted(out)


def rows(geom, row_h, gap, pad=1.0):
    """Zeilen der Form: [(y_mitte, [(x_links, x_rechts), …])] – ein Bereich nur dort, wo die
    ganze Zeilenhöhe in der Form liegt (oben, Mitte und unten geprüft)."""
    minx, miny, maxx, maxy = geom.bounds
    n = int((maxy - miny + gap) // (row_h + gap))
    if n < 1:
        return []
    y0 = miny + (maxy - miny - (n * row_h + (n - 1) * gap)) / 2
    out = []
    for i in range(n):
        top = y0 + i * (row_h + gap)
        lines = [_intervals(geom, top + row_h * f, minx - 1, maxx + 1) for f in (0.12, 0.5, 0.88)]
        segs = []
        for a, b in lines[1]:
            lo, hi = a, b
            for other in (lines[0], lines[2]):
                ov = [(max(a, c), min(b, d)) for c, d in other if min(b, d) > max(a, c)]
                if not ov:
                    lo, hi = 0, -1
                    break
                c, d = max(ov, key=lambda t: t[1] - t[0])
                lo, hi = max(lo, c), min(hi, d)
            if hi - lo - 2 * pad >= row_h * 1.2:
                segs.append((lo + pad, hi - pad))
        if segs:
            out.append((top + row_h / 2, segs))
    return out


class _Measure:
    """Wortbreiten einer Stickschrift (einmal gemessen, dann aus dem Speicher)."""

    def __init__(self, font, size):
        self.font, self.size = font, size
        self.cache = {}

    def width(self, text):
        if text not in self.cache:
            o = templates.text(text, self.size, "#000000", self.font)
            self.cache[text] = o.local_size()[0]
        return self.cache[text]

    def line(self, words):
        return self.width(" ".join(words)) if len(words) <= 1 else \
            sum(self.width(w) for w in words) + self.space() * (len(words) - 1)

    def space(self):
        if "␣" not in self.cache:
            self.cache["␣"] = max(self.size * 0.25, self.width("a a") - 2 * self.width("a"))
        return self.cache["␣"]


def _place(txt, seg, p, color):
    """Schriftzug für eine Zeile der Breite seg. Fertig digitalisierte Stickschriften vertragen
    kaum Verzerrung (Satinstiche reißen auf): darum nur leicht stauchen/dehnen, den Rest über
    den Buchstabenabstand füllen und zu Breites kleiner setzen. None: würde kleiner als MIN_H."""
    o = templates.text(txt, p["row"], color, p["font"])
    w, h = o.local_size()
    if w <= 0 or h <= 0:
        return None
    if h > p["row"] * 1.02:                     # Unterlängen: ganze Zeile auf Zeilenhöhe
        o.text["size"] *= p["row"] / h
        w, h = o.local_size()
    f = seg / w
    if f < MIN_SX:                              # zu breit: kleiner setzen
        if h * f / MIN_SX < MIN_H:
            return None
        o.text["size"] *= f / MIN_SX * 0.99     # Rundung: danach sicher ≥ MIN_SX
        w, h = o.local_size()
        o.sx = max(MIN_SX, min(1.0, seg / w))
        return o
    if f <= 1.0:
        o.sx = f
        return o
    n = len(txt)
    if n > 1 and seg / MAX_SX > w:              # zu schmal: Buchstaben etwas auseinander
        sp = min(p["row"] * SPACING, (seg / MAX_SX - w) / (n - 1))
        if " " in txt and sp > 0.3:             # Wortlücken mitwachsen lassen
            o.text["text"] = txt.replace(" ", "  ")
            sp = min(sp, (seg / MAX_SX - w) / (n - 1 + txt.count(" ") * 2))
        o.text["spacing"] = sp
        w, h = o.local_size()
    o.sx = max(MIN_SX, min(MAX_SX, seg / w))
    return o


def sculpt(geom, words, p):
    """Schriftzüge, die die Form (Weltkoordinaten) füllen."""
    if not words:
        return []
    if p.get("upper"):
        words = [w.upper() for w in words]
    m = _Measure(p["font"], p["row"])
    by_width = sorted(set(words), key=m.width, reverse=True)
    out = []
    k = 0
    colors = [p["color"], p["color2"]] if p.get("two") else [p["color"]]
    for ri, (yc, segs) in enumerate(rows(geom, p["row"], p["gap"])):
        col = colors[ri % len(colors)]
        for x0, x1 in segs:
            if k >= len(words) and not p.get("repeat"):
                break
            seg = x1 - x0
            line = [words[k % len(words)]]
            # weitere Wörter, solange die Zeile höchstens bis MIN_SX gestaucht werden muss
            while (k + len(line) < len(words) or p.get("repeat")) and \
                    m.line(line + [words[(k + len(line)) % len(words)]]) * MIN_SX <= seg * 0.97:
                line.append(words[(k + len(line)) % len(words)])
            o = _place(" ".join(line), seg, p, col)
            if o is not None:
                k += len(line)
            elif p.get("repeat"):
                # schmale Stelle (z. B. Sternzacke): ein kürzeres Wort einspringen lassen
                for alt in by_width:
                    if m.width(alt) < m.width(line[0]):
                        o = _place(alt, seg, p, col)
                        if o is not None:
                            break
            if o is None:
                continue
            o.x, o.y = (x0 + x1) / 2, yc
            out.append(o)
    if p.get("outline"):
        ln = EmbObject("line", "Umriss")
        ring = geom.exterior if geom.geom_type == "Polygon" else \
            max(geom.geoms, key=lambda g: g.area).exterior
        ln.set_points(list(ring.coords)[:-1], closed=True)
        ln.border.update(type=p["outline_st"], color=p["outline_c"], width=2.0)
        if p["outline_st"] == "triple":
            ln.border["repeats"] = 1
        out.append(ln)
    return out


def shape_geometry(name, size):
    g = dict(shapes.MOTIFS)[name]()
    b = g.bounds
    f = size / max(b[2] - b[0], 1e-6)
    g = affinity.scale(g, f, f, origin=(0, 0))
    b = g.bounds
    return affinity.translate(g, -(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2)


def _words(text):
    return [w for w in text.replace("\n", " ").split(" ") if w.strip()]


def sculpt_templates(sel=None):
    """Einträge für templates.TemplateDialog. sel: ausgewählte Objekte – ihre Flächen werden
    als eigene Form angeboten und bleiben auf Wunsch als Hintergrund stehen (_context)."""
    src = None
    if sel:
        polys = [o.world_geometry() for o in sel
                 if o.kind in ("shape", "satin") and o.world_geometry() is not None]
        polys = [g for g in polys if g.geom_type in ("Polygon", "MultiPolygon") and g.area > 50]
        if polys:
            src = unary_union(polys)

    T = lambda *a: a
    common = [T("text", "Text", "text", "Liebe Glück Familie Zuhause Freude Lachen Herz"),
              T("font", "Schrift", "choice", FONTS, "block"),
              T("upper", "GROSSBUCHSTABEN", "check", True),
              T("row", "Zeilenhöhe", "num", 5.0, 40.0, 0.5, 1, " mm", 9.0),
              T("gap", "Zeilenabstand", "num", 0.0, 15.0, 0.5, 1, " mm", 2.0),
              T("repeat", "Wörter wiederholen, bis die Form voll ist", "check", True),
              T("two", "Zeilen in zwei Farben", "check", True),
              T("color", "Farbe 1", "color", "#AD1457"), T("color2", "Farbe 2", "color", "#6A1B9A"),
              T("outline", "Umriss sticken", "check", False),
              T("outline_st", "Umriss-Stichart", "choice", [("Satin", "satin"),
                                                             ("Bohnenstich", "triple"),
                                                             ("Steppstich", "run")], "triple"),
              T("outline_c", "Umrissfarbe", "color", "#4A148C")]

    def build_shape(p):
        return sculpt(shape_geometry(p["shape"], p["size"]), _words(p["text"]), p)

    def build_sel(p):
        out = sculpt(src, _words(p["text"]), p)
        if p["keep"]:
            for o in sel:
                c = o.clone()
                c._context = True
                out.insert(0, c)
        return out

    out = [("shape", "Text in Form", "Wörter füllen eine Form – jede Zeile wird auf die Breite "
            "der Form gedehnt. Schön für Geschenke, Kissen, Wandbilder.",
            [T("shape", "Form", "choice", SHAPES, "Herz"),
             T("size", "Breite", "num", 40.0, 300.0, 1.0, 0, " mm", 110.0), *common], build_shape)]
    if src is not None:
        out.insert(0, ("selection", "Ausgewählte Form", "Wörter füllen die ausgewählte Form. "
                       "Die Form selbst bleibt erhalten (Haken entfernen = nur der Text).",
                       [T("keep", "Form in der Vorschau zeigen", "check", False), *common],
                       build_sel))
    return out
