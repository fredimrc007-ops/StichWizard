"""Projekte im Stickrahmen (»in the hoop«): Untersetzer, Schlüsselanhänger, Gepäckanhänger,
Baumschmuck, Karte & Lesezeichen, Kartenetui, Handyhülle, Pass- & Buchhülle,
Reißverschluss-Etui und Kuschelfigur – komplett im Rahmen genäht.

Jedes Projekt besteht aus Arbeitsschritten (Platzierungslinie, Heftstich, Motiv, Rückseite,
Abschluss), zwischen denen die Maschine anhält (»Schnitt danach: Stopp«). Die Schrittanleitung
steht im ersten Objekt jedes Schritts (fill["ith_step"]), Material und Zuschnitt im ersten
Objekt des Projekts (fill["ith_project"]) – so bleibt beides im gespeicherten Projekt und die
PDF-Anleitung lässt sich jederzeit neu erzeugen."""
import math

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import substring

from . import shapes, templates
from .model import EmbObject
from .ornaments import ring_points

T = lambda *a: a
MOTIFS = [("Kein Motiv", "none"), ("Herz", "Herz"), ("Stern", "Stern"), ("Blume", "Blume"),
          ("Schmetterling", "Schmetterling"), ("Pfote", "Pfote"), ("Anker", "Anker"),
          ("Blatt", "Blatt"), ("Stern 8", "Stern 8"), ("Mond", "Mond")]


# ------------------------------------------------------------------ Geometrie
def rounded(w, h, r):
    return Polygon(ring_points("rect", w, h, r, 240))


def ring_of(g):
    """Außenkontur im Uhrzeigersinn (Bildschirm), Start oben in der Mitte."""
    if g.geom_type != "Polygon":
        g = max(g.geoms, key=lambda q: q.area)
    ring = list(g.exterior.coords)[:-1]
    if not g.exterior.is_ccw:
        ring = ring[::-1]
    cx = (g.bounds[0] + g.bounds[2]) / 2
    i = min(range(len(ring)), key=lambda k: (round(ring[k][1], 1), abs(ring[k][0] - cx)))
    return ring[i:] + ring[:i]


def inset(g, d):
    """Kontur nach innen (d > 0) bzw. außen (d < 0) versetzt, runde Ecken."""
    out = g.buffer(-d, join_style=1, resolution=24)
    if out.geom_type != "Polygon":
        out = max(out.geoms, key=lambda q: q.area)
    return out


def _sub(ln, a, b):
    """Stück eines geschlossenen Linienzugs von Länge a bis b im Umlaufsinn (b < a: über den
    Startpunkt hinweg)."""
    if b >= a:
        return list(substring(ln, a, b).coords)
    return list(substring(ln, a, ln.length).coords) + list(substring(ln, 0, b).coords)[1:]


def open_path(g, a, b):
    """Teil der Kontur von Bogenlänge-Anteil a bis b (0 ≈ oben, im Uhrzeigersinn)."""
    ring = ring_of(g)
    ln = LineString(ring + [ring[0]])
    return _sub(ln, a * ln.length, b * ln.length)


def without_top(g, w, r):
    """Kontur eines abgerundeten Rechtecks ohne die obere gerade Kante (»U«): von der rechten
    oberen Ecke im Uhrzeigersinn um die Form bis zur linken oberen Ecke."""
    ring = ring_of(g)
    ln = LineString(ring + [ring[0]])
    h0 = g.bounds[1]
    return _sub(ln, ln.project(Point(w / 2 - r, h0)), ln.project(Point(-w / 2 + r, h0)))


# ------------------------------------------------------------------- Bausteine
def line(pts, color, name, closed=True, stitch="run", width=4.0, length=2.5):
    o = EmbObject("line", name)
    o.set_points(list(pts), closed=closed)
    o.border.update(type=stitch, color=color, width=width, stitch_len=length)
    if stitch == "triple":
        o.border["repeats"] = 1
    return o


def ring_line(g, color, name, stitch="run", width=4.0, length=2.5):
    return line(ring_of(g), color, name, True, stitch, width, length)


def design(p, area, color_key="color"):
    """Motiv und/oder Text (bis zu zwei Zeilen, mit »/« getrennt) in die Fläche setzen."""
    x0, y0, x1, y1 = area.bounds
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lines = [t.strip() for t in p.get("text", "").split("/") if t.strip()][:3]
    mot = p.get("motif", "none")
    out = []
    if mot != "none" and lines:
        ms = min(w, h * 0.5) * 0.8
        out.append(templates.motif(mot, ms, p["accent"], cx, y0 + h * 0.27))
        ty, th = y0 + h * 0.55, h * 0.45
    elif mot != "none":
        out.append(templates.motif(mot, min(w, h) * 0.8, p["accent"], cx, cy))
        return out
    else:
        ty, th = y0, h
    if lines:
        lh = min(th / len(lines), p.get("text_h", 12.0) * 1.35)
        top = ty + (th - lh * len(lines)) / 2
        for i, t in enumerate(lines):
            out.append(templates.text(t, lh / 1.35, p[color_key], p.get("font", "block"), cx,
                                      top + lh * (i + 0.5), max_w=w, max_h=lh * 0.95))
    return out


class Project:
    """Sammelt Arbeitsschritte: Objekte + Anleitungstext, Stopp nach jedem Schritt."""

    def __init__(self, title):
        self.title = title
        self.objs = []
        self.n = 0

    def step(self, text, objs, stop=True, label=None):
        objs = [o for o in objs if o is not None]
        if not objs:
            return
        self.n += 1
        for o in objs:
            o.name = f"{self.n}. {label or o.name}"
        objs[0].fill["ith_step"] = text
        objs[-1].trim_after = "stop" if stop else "auto"
        self.objs += objs

    def finish(self, materials, cut, notes):
        if self.objs:
            self.objs[0].fill["ith_project"] = {"title": self.title, "materials": materials,
                                                "cut": cut, "notes": notes}
            self.objs[-1].trim_after = "auto"
        return self.objs


def cm(v):
    return f"{v / 10:.1f}".replace(".", ",").replace(",0", "")


def piece(g, extra=20.0):
    b = g.bounds
    return f"{cm(b[2] - b[0] + extra)} × {cm(b[3] - b[1] + extra)} cm"


START = ("Stickvlies (Reißvlies, bei Filz/Volumenvlies auch Klebevlies) fest einspannen. "
         "Platzierungslinie sticken – sie zeigt, wohin der Stoff kommt.")
TACK = ("{what} mit der rechten Seite nach oben über die Linie legen (rundum mind. 1 cm "
        "überstehen lassen), mit Klebeband oder Sprühkleber fixieren. Heftstich sticken.")
BACK = ("Rahmen aus der Maschine nehmen, aber NICHT ausspannen. Umdrehen: {what} mit der rechten "
        "Seite nach außen (nach unten) unter die Form kleben – die Platzierungslinie ist von "
        "hinten zu sehen. Rahmen wieder einsetzen, Heftstich durch alle Lagen sticken.")
SATIN = "Satinrand sticken – er deckt alle Stoffkanten ab."
CUT = ("Ausspannen, Vlies vorsichtig abreißen. Überstehenden Stoff dicht am Satinrand "
       "abschneiden, ohne in die Stiche zu schneiden. Kanten bei Bedarf mit Nahtsicherung "
       "(Fray Check) betupfen.")


def _edge_steps(pr, g, p, back="Rückseitenstoff", eyelet=None):
    pr.step(BACK.format(what=back), [ring_line(inset(g, 2.2), p["line"], "Heftstich Rückseite")])
    pr.step(SATIN if eyelet is None else "Satinrand und Öse sticken (durch alle Lagen) – sie "
            "decken alle Stoffkanten ab.",
            [ring_line(inset(g, 1.6), p["edge"], "Satinrand", "satin", 3.8), eyelet], stop=False)


def _front(pr, g, p, fabric="Oberstoff"):
    pr.step(START, [ring_line(g, p["line"], "Platzierungslinie")])
    pr.step(TACK.format(what=fabric), [ring_line(inset(g, 1.2), p["line"], "Heftstich")])


def _eyelet(cx, cy, p, hole=3.5):
    o = line(ring_points("circle", 2 * (hole + 1.8), 0, res=72), p["edge"], "Öse", "satin", 3.4)
    o.x += cx
    o.y += cy
    return o


# ---------------------------------------------------------------- Projekte
def coaster(p):
    s = p["size"]
    g = {"round": lambda: Point(0, 0).buffer(s / 2, 64),
         "square": lambda: rounded(s, s, s * 0.12),
         "hex": lambda: affinity.scale(shapes.regular(6, 25), s / 50, s / 50, origin=(0, 0)),
         "heart": lambda: templates.motif("Herz", s, "#000").world_geometry()}[p["form"]]()
    pr = Project("Untersetzer")
    _front(pr, g, p, "Volumenvlies oder Filz und darauf der Oberstoff")
    pr.step("Motiv sticken.", design(p, inset(g, 9)))
    _edge_steps(pr, g, p)
    return pr.finish(
        ["Reißvlies", f"Oberstoff {piece(g)}", f"Rückseitenstoff {piece(g)}",
         f"Volumenvlies oder Filz {piece(g, 10)} (optional, für feste Untersetzer)",
         "Stickgarn, Unterfaden in Garnfarbe des Randes", "Klebeband"],
        [f"Oberstoff und Rückseite je {piece(g)}"], [CUT, "Bei 40 °C waschbar, wenn Stoffe "
                                                          "vorgewaschen wurden."])


def keyfob(p):
    w, L = p["width"], p["length"]
    g = rounded(w, L, w * 0.45)
    pr = Project("Schlüsselanhänger")
    _front(pr, g, p)
    area = box(-w / 2 + 6, -L / 2 + w + 2, w / 2 - 6, L / 2 - 6)
    x0, y0, x1, y1 = area.bounds
    t = templates.text(p["text"] or " ", p["text_h"], p["color"], p["font"], 0, 0,
                       max_w=y1 - y0, max_h=x1 - x0)
    t.rot = -90.0                                # liest sich von unten nach oben
    t.x, t.y = (x0 + x1) / 2, (y0 + y1) / 2
    pr.step("Text sticken.", [t])
    _edge_steps(pr, g, p, eyelet=_eyelet(0, -L / 2 + w / 2, p))
    return pr.finish(
        ["Reißvlies", f"Oberstoff {piece(g)}", f"Rückseitenstoff {piece(g)}",
         "Schlüsselring 25 mm", "Lochzange oder Pfriem"],
        [f"Oberstoff und Rückseite je {piece(g)}"],
        [CUT, "Innerhalb der Öse ein Loch stanzen bzw. vorsichtig ausschneiden und den "
              "Schlüsselring einhängen."])


def luggage(p):
    w, h = p["width"], p["height"]
    k = w * 0.22
    g = Polygon([(-w / 2 + k, -h / 2), (w / 2 - k, -h / 2), (w / 2, -h / 2 + k), (w / 2, h / 2),
                 (-w / 2, h / 2), (-w / 2, -h / 2 + k)]).buffer(-3, join_style=1).buffer(3, 24)
    pr = Project("Gepäckanhänger")
    _front(pr, g, p)
    pr.step("Name/Text und Motiv sticken.", design(p, box(-w / 2 + 8, -h / 2 + k + 12,
                                                          w / 2 - 8, h / 2 - 8)))
    _edge_steps(pr, g, p, eyelet=_eyelet(0, -h / 2 + k * 0.75, p, 4.0))
    return pr.finish(
        ["Reißvlies", f"Oberstoff {piece(g)}", f"Rückseitenstoff {piece(g)}",
         "Volumenvlies (optional)", "Band oder Kordel 25 cm"],
        [f"Oberstoff und Rückseite je {piece(g)}"],
        [CUT, "Loch in der Öse ausschneiden, Band durchziehen und verknoten."])


def ornament(p):
    s = p["size"]
    form = p["form"]
    if form == "star":
        g = affinity.scale(shapes.star(5, 25, 12), s / 50, s / 50, origin=(0, 0))
        g = g.buffer(-2.5, join_style=1).buffer(2.5, 24)
    elif form == "heart":
        g = templates.motif("Herz", s, "#000").world_geometry()
    elif form == "tree":
        g = Polygon([(0, -s / 2), (s * 0.22, -s * 0.18), (s * 0.12, -s * 0.18), (s * 0.36, s * 0.18),
                     (s * 0.08, s * 0.18), (s * 0.08, s / 2), (-s * 0.08, s / 2), (-s * 0.08, s * 0.18),
                     (-s * 0.36, s * 0.18), (-s * 0.12, -s * 0.18), (-s * 0.22, -s * 0.18)])
        g = g.buffer(-2, join_style=1).buffer(2, 24)
    else:                                         # Kugel mit Kappe
        g = Point(0, s * 0.06).buffer(s * 0.44, 64).union(box(-s * 0.1, -s / 2, s * 0.1, -s * 0.34))
        g = g.buffer(1.5, join_style=1).buffer(-1.5, join_style=1)
    pr = Project("Baumschmuck")
    _front(pr, g, p)
    b = inset(g, 9)
    if form in ("star", "tree"):
        c = b.centroid
        r = math.sqrt(b.area / math.pi) * 0.9
        b = box(c.x - r, c.y - r * 0.7, c.x + r, c.y + r * 0.9).intersection(b)
    pr.step("Motiv bzw. Name und Jahr sticken.", design(p, b))
    top = g.bounds[1]
    tab = [line([(-3, top + 2), (-3, top + 9)], p["line"], "Band", False),
           line([(3, top + 9), (3, top + 2)], p["line"], "Band", False)]
    pr.step("Aufhängeband: ca. 15 cm Band zur Schlaufe legen und die beiden Enden oben in der "
            "Mitte etwa 1,5 cm in die Form hineinlegen, Schlaufe nach außen. Festkleben, "
            "Bandsicherung sticken.", tab)
    _edge_steps(pr, g, p)
    return pr.finish(
        ["Reißvlies oder Filz", f"Oberstoff/Filz {piece(g)}", f"Rückseitenstoff/Filz {piece(g)}",
         "Satinband 3–6 mm, ca. 15 cm"],
        [f"Vorder- und Rückseite je {piece(g)}"],
        [CUT, "Die Schlaufe beim Abschneiden des Stoffs aus dem Weg halten."])


def card(p):
    if p["form"] == "bookmark":
        w, h = 50.0, 170.0
        g = rounded(w, h, 6)
    else:
        w, h = p["width"], p["width"] * 1.4
        g = rounded(w, h, 4)
    pr = Project("Lesezeichen" if p["form"] == "bookmark" else "Stoffkarte")
    _front(pr, g, p, "Filz oder fester Stoff")
    pr.step("Motiv und Text sticken.", design(p, inset(g, 9)))
    _edge_steps(pr, g, p, "Filz oder Rückseitenstoff",
                _eyelet(0, -h / 2 + 12, p, 3.0) if p["form"] == "bookmark" else None)
    return pr.finish(
        ["Reißvlies oder wasserlösliches Vlies", f"Filz/Stoff vorn {piece(g)}",
         f"Filz/Stoff hinten {piece(g)}"] + (["Quaste oder Band"] if p["form"] == "bookmark"
                                             else []),
        [f"Vorder- und Rückseite je {piece(g)}"], [CUT])


def cardholder(p):
    w, h = p["width"], p["height"]
    g = rounded(w, h, 6)
    pocket_y = h / 2 - h * p["pocket"] / 100.0
    pr = Project("Kartenetui")
    pr.step(START + " Die zweite Linie zeigt, wo später hinten die Tasche beginnt.",
            [ring_line(g, p["line"], "Platzierungslinie"),
             line([(-w / 2 + 4, pocket_y), (w / 2 - 4, pocket_y)], p["line"], "Taschenlinie", False)])
    pr.step(TACK.format(what="Außenstoff"), [ring_line(inset(g, 1.2), p["line"], "Heftstich")])
    pr.step("Motiv sticken.", design(p, inset(g, 9)))
    pr.step(BACK.format(what="Futterstoff (ganze Größe) und darauf das Taschenteil (doppelt "
                             "gelegt, Bruchkante zur Taschenlinie, offene Kanten nach unten)"),
            [ring_line(inset(g, 2.2), p["line"], "Heftstich Rückseite")])
    pr.step(SATIN, [ring_line(inset(g, 1.6), p["edge"], "Satinrand", "satin", 3.8)], stop=False)
    ph = h - (pocket_y + h / 2) + 20
    return pr.finish(
        ["Reißvlies", f"Außenstoff {piece(g)}", f"Futterstoff {piece(g)}",
         f"Taschenteil {cm(w + 20)} × {cm(2 * ph)} cm (wird zur Hälfte gefaltet)",
         "Bügeleinlage für den Außenstoff (optional)"],
        [f"Außen- und Futterstoff je {piece(g)}", f"Tasche {cm(w + 20)} × {cm(2 * ph)} cm, "
         "längs zur Hälfte bügeln"],
        [CUT, "Die Tasche öffnet sich an der Bruchkante – dort nicht abschneiden."])


def phone(p):
    w = p["phone_w"] + p["thick"] + 5
    h = p["phone_h"] + p["thick"] + 5
    r = 6.0
    g = rounded(w, h, r)
    pr = Project("Handyhülle")
    pr.step(START, [ring_line(g, p["line"], "Platzierungslinie")])
    pr.step("Vorderteil: Stoff oben 1 cm nach links umbügeln (oder doppelt legen). Rechte Seite "
            "nach oben auflegen, Bruchkante genau auf die obere Linie. Festkleben, Heftstich "
            "sticken.", [line(without_top(inset(g, 1.2), w - 2.4, r), p["line"], "Heftstich",
                              False)])
    pr.step("Motiv sticken.", design(p, inset(g, 10)))
    pr.step(BACK.format(what="Rückteil (oben ebenfalls umgebügelt, Bruchkante an die obere "
                             "Linie)"),
            [line(without_top(inset(g, 2.2), w - 4.4, r), p["line"], "Heftstich Rückseite",
                  False)])
    pr.step("Satinrand an beiden Seiten und unten sticken – oben bleibt die Hülle offen.",
            [line(without_top(inset(g, 1.6), w - 3.2, r), p["edge"], "Satinrand", False,
                  "satin", 3.8)], stop=False)
    return pr.finish(
        ["Reißvlies (oben nach dem Sticken abreißen)", f"Vorderteil {cm(w + 20)} × {cm(h + 30)} cm",
         f"Rückteil {cm(w + 20)} × {cm(h + 30)} cm", "Volumenvlies (optional, polstert)"],
        [f"Hülle: Breite = Handybreite + Dicke + 5 mm = {cm(w)} cm, Höhe = Handyhöhe + Dicke + "
         f"5 mm = {cm(h)} cm", "Vorder- und Rückteil oben je 1 cm umbügeln"],
        [CUT, "Oben zwischen Vorder- und Rückteil das Vlies vorsichtig herauszupfen."])


def cover(p):
    bw, bh, t = p["book_w"], p["book_h"], p["thick"]
    w = 2 * bw + t + 12
    h = bh + 10
    flap = bw * p["flap"] / 100.0
    g = rounded(w, h, 5)
    title = "Passhülle" if p.get("passport") else "Buchhülle"
    pr = Project(title)
    pr.step(START + " Die senkrechten Linien zeigen, wo hinten die Einschubklappen enden.",
            [ring_line(g, p["line"], "Platzierungslinie"),
             line([(-w / 2 + flap, -h / 2 + 4), (-w / 2 + flap, h / 2 - 4)], p["line"], "Klappe",
                  False),
             line([(w / 2 - flap, h / 2 - 4), (w / 2 - flap, -h / 2 + 4)], p["line"], "Klappe",
                  False)])
    pr.step(TACK.format(what="Außenstoff"), [ring_line(inset(g, 1.2), p["line"], "Heftstich")])
    fx = t / 2 + 6 + bw / 2
    pr.step("Motiv auf der Vorderseite (rechte Hälfte) sticken.",
            design(p, box(fx - bw / 2 + 8, -h / 2 + 12, fx + bw / 2 - 8, h / 2 - 12)))
    pr.step(BACK.format(what="Futterstoff (ganze Größe) und darauf die beiden Klappen (je "
                             "doppelt gelegt, Bruchkante zur Mitte an die senkrechte Linie)"),
            [ring_line(inset(g, 2.2), p["line"], "Heftstich Rückseite")])
    pr.step(SATIN, [ring_line(inset(g, 1.6), p["edge"], "Satinrand", "satin", 3.8)], stop=False)
    return pr.finish(
        ["Reißvlies", f"Außenstoff {piece(g)}", f"Futterstoff {piece(g)}",
         f"2 Klappen je {cm(flap + 20)} × {cm(2 * (h + 20))} cm (werden gefaltet)",
         "Bügeleinlage für den Außenstoff (empfohlen)"],
        [f"Hülle offen {cm(w)} × {cm(h)} cm (Buch {cm(bw)} × {cm(bh)} cm, Rücken {cm(t)} cm)",
         f"Klappen je {cm(flap + 20)} × {cm(2 * (h + 20))} cm, quer zur Hälfte bügeln"],
        [CUT, "Die Klappen öffnen sich zur Mitte hin – dort nicht abschneiden. Buchdeckel in "
              "die Klappen schieben."])


def zipper(p):
    w, h = p["width"], p["height"]
    g = rounded(w, h, 6)
    zy = -h / 2 + p["top"]
    pr = Project("Reißverschluss-Etui")
    pr.step(START + " Die waagerechte Linie zeigt, wo der Reißverschluss hinkommt.",
            [ring_line(g, p["line"], "Platzierungslinie"),
             line([(-w / 2 - 8, zy), (w / 2 + 8, zy)], p["line"], "Reißverschluss-Linie", False)])
    pr.step("Reißverschluss (Kunststoff-Spirale, 3–5 mm, mind. 4 cm länger als das Etui) mit der "
            "rechten Seite nach oben auflegen, Zähnchen genau auf der Linie. Den Zipper außerhalb "
            "der Form parken. Festkleben, Heftstich sticken.",
            [line([(-w / 2 - 8, zy - 6), (w / 2 + 8, zy - 6)], p["line"], "Heftstich RV oben", False),
             line([(w / 2 + 8, zy + 6), (-w / 2 - 8, zy + 6)], p["line"], "Heftstich RV unten", False)])
    pr.step("Unteres Vorderteil: obere Kante 1 cm nach links umbügeln, rechte Seite nach oben "
            "auflegen, Bruchkante ca. 3 mm unter den Zähnchen. Festkleben, Heftstich sticken.",
            [line([(-w / 2 - 4, zy + 4.5), (w / 2 + 4, zy + 4.5)], p["line"], "Heftstich unten",
                  False)])
    pr.step("Oberes Vorderteil (Streifen): untere Kante umbügeln, Bruchkante ca. 3 mm über den "
            "Zähnchen auflegen. Festkleben, Heftstich sticken.",
            [line([(w / 2 + 4, zy - 4.5), (-w / 2 - 4, zy - 4.5)], p["line"], "Heftstich oben",
                  False)])
    pr.step("Motiv auf dem unteren Vorderteil sticken.",
            design(p, box(-w / 2 + 12, zy + 12, w / 2 - 12, h / 2 - 12)))
    pr.step("Reißverschluss zur Hälfte öffnen (sonst lässt sich das Etui nicht wenden)! "
            "Rückseitenstoff mit der rechten Seite nach UNTEN auf die Vorderteile legen, "
            "festkleben. Abschlussnaht sticken.",
            [ring_line(g, p["edge"], "Abschlussnaht", "triple", length=2.2)], stop=False)
    return pr.finish(
        ["Reißvlies", f"Reißverschluss Kunststoff-Spirale, mind. {cm(w + 40)} cm",
         f"unteres Vorderteil {cm(w + 30)} × {cm(h - p['top'] + 30)} cm",
         f"oberes Vorderteil {cm(w + 30)} × {cm(p['top'] + 30)} cm",
         f"Rückseitenstoff {piece(g, 30)}", "Bügeleinlage (empfohlen)"],
        [f"Etui fertig ca. {cm(w)} × {cm(h)} cm"],
        ["Ausspannen, Vlies entfernen. Stoff rundum 5 mm neben der Naht abschneiden, Ecken "
         "schräg kürzen, Reißverschlussenden bündig abschneiden (nicht über den Zipper!).",
         "Durch den offenen Reißverschluss wenden, Ecken ausformen, bügeln.",
         "Nur Kunststoff-Reißverschlüsse verwenden – Metall bricht die Nadel."])


def plush(p):
    s = p["size"]
    form = p["form"]
    if form == "cloud":
        g = templates.motif("Wolke", s, "#000").world_geometry()
    elif form == "star":
        g = affinity.scale(shapes.star(5, 25, 13), s / 50, s / 50, origin=(0, 0))
        g = g.buffer(-4, join_style=1).buffer(4, 24)
    elif form == "circle":
        g = Point(0, 0).buffer(s / 2, 64)
    else:
        g = templates.motif("Herz", s, "#000").world_geometry()
    pr = Project("Kuschelfigur")
    _front(pr, g, p)
    pr.step("Motiv bzw. Gesicht/Name sticken.", design(p, inset(g, 12)))
    pr.step(BACK.format(what="Rückseitenstoff"),
            [ring_line(inset(g, 2.2), p["line"], "Heftstich Rückseite")])
    gap = p["gap"] / LineString(ring_of(g) + [ring_of(g)[0]]).length
    pr.step("Satinrand mit Füllöffnung sticken.",
            [line(open_path(inset(g, 1.6), 0.75 + gap / 2, 0.75 - gap / 2), p["edge"],
                  "Satinrand", False, "satin", 3.8)])
    pr.step("Rahmen herausnehmen (nicht ausspannen), durch die Öffnung zwischen Vorder- und "
            "Rückseite mit Füllwatte locker füllen. Rahmen wieder einsetzen, Öffnung schließen.",
            [line(open_path(inset(g, 1.6), 0.75 - gap, 0.75 + gap), p["edge"], "Öffnung schließen",
                  False, "satin", 3.8)], stop=False)
    return pr.finish(
        ["Reißvlies", f"Vorderseite (Minky, Fleece, Baumwolle) {piece(g)}",
         f"Rückseite {piece(g)}", "Füllwatte"],
        [f"Vorder- und Rückseite je {piece(g)}"],
        [CUT, "Kleine Figuren nicht zu prall füllen, sonst wellt sich der Rand."])


# ------------------------------------------------------------------ Einträge
COLORS = [T("line", "Farbe Heftstiche", "color", "#8D6E63"),
          T("edge", "Farbe Rand", "color", "#5D4037"),
          T("color", "Schriftfarbe", "color", "#AD1457"),
          T("accent", "Motivfarbe", "color", "#E91E63")]
FONT = T("font", "Schrift", "choice", templates.FONT_CHOICES, "block")


def _deco(text="", motif="none"):
    return [T("text", "Text (Zeilen mit /)", "text", text), FONT,
            T("motif", "Motiv", "choice", MOTIFS, motif)]


PROJECTS = [
    ("coaster", "Untersetzer", "Untersetzer mit Motiv – rund, eckig, sechseckig oder als Herz. "
     "Zwei Stofflagen, auf Wunsch mit Filz oder Volumenvlies, Satinrand rundum.",
     [T("form", "Form", "choice", [("Rund", "round"), ("Eckig", "square"), ("Sechseck", "hex"),
                                   ("Herz", "heart")], "round"),
      T("size", "Größe", "num", 70.0, 140.0, 1.0, 0, " mm", 100.0), *_deco("", "Blume"), *COLORS],
     coaster),
    ("keyfob", "Schlüsselanhänger", "Länglicher Anhänger mit Namen und gestickter Öse für den "
     "Schlüsselring.",
     [T("text", "Text", "text", "Lena"), FONT,
      T("text_h", "Schrifthöhe", "num", 6.0, 20.0, 0.5, 1, " mm", 12.0),
      T("width", "Breite", "num", 25.0, 45.0, 1.0, 0, " mm", 32.0),
      T("length", "Länge", "num", 70.0, 160.0, 1.0, 0, " mm", 120.0), *COLORS], keyfob),
    ("luggage", "Gepäckanhänger", "Anhänger mit abgeschrägten Ecken, Namen und Öse für Band "
     "oder Kordel.",
     [T("width", "Breite", "num", 50.0, 100.0, 1.0, 0, " mm", 70.0),
      T("height", "Höhe", "num", 80.0, 160.0, 1.0, 0, " mm", 115.0),
      *_deco("Familie / Müller", "Anker"), *COLORS], luggage),
    ("ornament", "Baumschmuck", "Anhänger für den Weihnachtsbaum mit eingenähter Bandschlaufe: "
     "Stern, Herz, Tannenbaum oder Kugel.",
     [T("form", "Form", "choice", [("Kugel", "ball"), ("Stern", "star"), ("Herz", "heart"),
                                   ("Tannenbaum", "tree")], "ball"),
      T("size", "Größe", "num", 60.0, 140.0, 1.0, 0, " mm", 90.0),
      *_deco("2026", "Stern 8"), *COLORS], ornament),
    ("card", "Karte & Lesezeichen", "Gestickte Stoff-/Filzkarte oder Lesezeichen mit Öse für "
     "eine Quaste.",
     [T("form", "Art", "choice", [("Karte", "card"), ("Lesezeichen", "bookmark")], "card"),
      T("width", "Breite (Karte)", "num", 70.0, 140.0, 1.0, 0, " mm", 95.0),
      *_deco("Alles Liebe / zum Geburtstag", "Herz"), *COLORS], card),
    ("cardholder", "Kartenetui", "Etui für Bank- oder Visitenkarten: Motiv vorne, Einstecktasche "
     "hinten.",
     [T("width", "Breite", "num", 90.0, 130.0, 1.0, 0, " mm", 100.0),
      T("height", "Höhe", "num", 60.0, 100.0, 1.0, 0, " mm", 70.0),
      T("pocket", "Taschenhöhe", "num", 40.0, 90.0, 1.0, 0, " %", 75.0),
      *_deco("", "Blume"), *COLORS], cardholder),
    ("phone", "Handyhülle", "Einsteckhülle passend zum Handy: Breite und Höhe werden aus den "
     "Handymaßen berechnet (+ Dicke + 5 mm). Oben offen.",
     [T("phone_w", "Handy Breite", "num", 50.0, 90.0, 0.5, 1, " mm", 72.0),
      T("phone_h", "Handy Höhe", "num", 100.0, 180.0, 0.5, 1, " mm", 147.0),
      T("thick", "Handy Dicke", "num", 5.0, 15.0, 0.5, 1, " mm", 8.0),
      *_deco("", "Schmetterling"), *COLORS], phone),
    ("cover", "Pass- & Buchhülle", "Hülle mit Einschubklappen innen – für Reisepass, Notizbuch "
     "oder Taschenbuch. Motiv auf der Vorderseite.",
     [T("book_w", "Buch Breite", "num", 80.0, 160.0, 1.0, 0, " mm", 88.0),
      T("book_h", "Buch Höhe", "num", 100.0, 220.0, 1.0, 0, " mm", 125.0),
      T("thick", "Buchrücken", "num", 3.0, 40.0, 0.5, 1, " mm", 6.0),
      T("flap", "Klappenbreite", "num", 30.0, 70.0, 1.0, 0, " %", 50.0),
      *_deco("PASS", "Anker"), *COLORS], cover),
    ("zipper", "Reißverschluss-Etui", "Kleines Etui mit Reißverschluss oben – im Rahmen genäht, "
     "danach gewendet.",
     [T("width", "Breite", "num", 90.0, 200.0, 1.0, 0, " mm", 140.0),
      T("height", "Höhe", "num", 70.0, 160.0, 1.0, 0, " mm", 100.0),
      T("top", "Abstand Reißverschluss oben", "num", 12.0, 40.0, 1.0, 0, " mm", 20.0),
      *_deco("", "Herz"), *COLORS], zipper),
    ("plush", "Kuschelfigur", "Gefüllte Figur (Herz, Stern, Wolke, Kreis) – mit Öffnung zum "
     "Füllen, die danach im Rahmen geschlossen wird.",
     [T("form", "Form", "choice", [("Herz", "heart"), ("Stern", "star"), ("Wolke", "cloud"),
                                   ("Kreis", "circle")], "heart"),
      T("size", "Größe", "num", 70.0, 180.0, 1.0, 0, " mm", 110.0),
      T("gap", "Füllöffnung", "num", 25.0, 60.0, 1.0, 0, " mm", 35.0),
      *_deco("", "none"), *COLORS], plush),
]


# ---------------------------------------------------------------- Anleitung
def project_info(objs):
    """(projektdaten, [(nr, text, farbe)]) aus den Objekten (Reihenfolge = Stickfolge)."""
    info = next((o.fill["ith_project"] for o in objs if o.fill.get("ith_project")), None)
    steps = []
    for o in objs:
        if o.fill.get("ith_step"):
            nr = o.name.split(".", 1)[0]
            col = o.border["color"] if o.kind == "line" else o.fill["color"]
            steps.append((nr, o.fill["ith_step"], col))
    return info, steps


def export_instructions(doc, path, image=None):
    """Anleitung als PDF: Titel, Vorschau, Material, Zuschnitt, Arbeitsschritte, Abschluss."""
    from PySide6.QtCore import QMarginsF, QRectF, Qt
    from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter,
                               QPdfWriter, QPen)
    from .threads import thread_name
    info, steps = project_info(doc.objects)
    if not info:
        raise ValueError("Im Design ist kein Projekt aus dem Projekt-Assistenten.")
    w = QPdfWriter(path)
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageMargins(QMarginsF(16, 14, 16, 14), QPageLayout.Millimeter)
    w.setResolution(300)
    w.setTitle(f"StichWizard – {info['title']}")
    p = QPainter(w)
    page = w.pageLayout().paintRectPixels(w.resolution())
    W, H = page.width(), page.height()
    dpmm = w.resolution() / 25.4
    y = 0.0

    def need(hh):
        nonlocal y
        if y + hh > H:
            w.newPage()
            y = 0.0

    def para(text, size=10, bold=False, indent=0.0, color="#222222", gap=2.0):
        nonlocal y
        f = QFont("DejaVu Sans", size, QFont.Bold if bold else QFont.Normal)
        p.setFont(f)
        r = QFontMetricsF(f, w).boundingRect(QRectF(0, 0, W - indent, 10 * H),
                                              Qt.TextWordWrap, text)
        need(r.height())
        p.setPen(QColor(color))
        p.drawText(QRectF(indent, y, W - indent, r.height() + 2), Qt.TextWordWrap, text)
        y += r.height() + gap * dpmm

    para(f"{info['title']} – im Stickrahmen genäht", 18, True, gap=1)
    st = doc.stats()
    para(f"Größe {st['width']:.0f} × {st['height']:.0f} mm · {st['stitches']:,} Stiche · "
         f"{len(steps)} Arbeitsschritte · ca. {st['minutes']:.0f} min Stickzeit".replace(",", "."),
         9, color="#666666", gap=4)
    if image is not None and not image.isNull():
        ih = min(70 * dpmm, H * 0.3)
        iw = ih * image.width() / max(1, image.height())
        if iw > W * 0.6:
            iw = W * 0.6
            ih = iw * image.height() / max(1, image.width())
        p.drawImage(QRectF((W - iw) / 2, y, iw, ih), image)
        y += ih + 5 * dpmm
    para("Material", 12, True, gap=1)
    for m in info["materials"]:
        para("• " + m, 10, indent=4 * dpmm, gap=0.6)
    y += 2 * dpmm
    para("Zuschnitt", 12, True, gap=1)
    for m in info["cut"]:
        para("• " + m, 10, indent=4 * dpmm, gap=0.6)
    y += 2 * dpmm
    para("Arbeitsschritte", 12, True, gap=1.5)
    for nr, text, col in steps:
        f = QFont("DejaVu Sans", 10)
        r = QFontMetricsF(f, w).boundingRect(QRectF(0, 0, W - 22 * dpmm, 10 * H), Qt.TextWordWrap,
                                              text)
        need(r.height() + 6 * dpmm)
        p.setPen(QPen(QColor("#555555"), 1))
        p.setBrush(QColor(col))
        p.drawEllipse(QRectF(0, y + 0.5 * dpmm, 5 * dpmm, 5 * dpmm))
        p.setFont(QFont("DejaVu Sans", 10, QFont.Bold))
        p.setPen(QColor("#222222"))
        p.drawText(QRectF(7 * dpmm, y, 14 * dpmm, 6 * dpmm), Qt.AlignLeft | Qt.AlignVCenter, nr)
        p.setFont(QFont("DejaVu Sans", 7))
        p.setPen(QColor("#777777"))
        p.drawText(QRectF(0, y + 6 * dpmm, 20 * dpmm, 4 * dpmm), Qt.AlignLeft,
                   thread_name(col)[:18] if thread_name(col) else col)
        p.setFont(f)
        p.setPen(QColor("#222222"))
        p.drawText(QRectF(22 * dpmm, y, W - 22 * dpmm, r.height() + 2), Qt.TextWordWrap, text)
        y += max(r.height(), 10 * dpmm) + 3 * dpmm
    y += 2 * dpmm
    para("Fertigstellen", 12, True, gap=1)
    for m in info["notes"]:
        para("• " + m, 10, indent=4 * dpmm, gap=0.8)
    y += 3 * dpmm
    para("Tipp: Die Maschine hält nach jedem Schritt an. Farbe der Heftstiche und des Randes "
         "dürfen gleich sein – dann einfach mit derselben Farbe weitersticken.", 8,
         color="#777777")
    p.end()
    return len(steps)
