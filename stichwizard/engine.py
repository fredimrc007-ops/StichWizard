"""Stich-Engine: wandelt Geometrie (in mm) in Stichfolgen um.

Ein Stich ist ein Tupel (x, y, flag). flag:
  STITCH = normaler Stich (Nadel sticht ein)
  JUMP   = Sprung ohne Einstich (Maschine fährt nur)
  TRIM   = Faden schneiden an dieser Position
"""
import math

import shapely
import shapely.ops
import shapely.prepared
from shapely import affinity
from shapely.geometry import (GeometryCollection, LineString, MultiLineString,
                              MultiPolygon, Point, Polygon, box)
from shapely.ops import nearest_points, unary_union

STITCH, JUMP, TRIM, STOP = 0, 1, 2, 3   # STOP: Maschine hält an (z. B. Applikation)
EXPLICIT_STOPS = False   # True bei Mehrnadel-Maschinen (Maschinenprofil): Stopp auch vor Farbwechsel

TRIM_DISTANCE = 3.0     # mm – längere Sprünge werden geschnitten (Einstellungen › Sticken)
DIRECT_TRAVEL = 1.6     # mm – kürzere Wege werden direkt gestickt
TIE_MODE = "normal"     # Vernähen: none | normal | strong (Einstellungen)
CURVE_TOL = 0.2         # mm – Steppstich in Kurven teilen, wenn er weiter abweicht (0 = aus)
MIN_STITCH = 0.0        # mm – kürzere Stiche werden beim Export zusammengefasst (Einstellungen)
FABRIC = "standard"     # Stoffart des aktuellen Designs (FABRIC_PROFILES)

# Stoffarten wie in Hatch/Wilcom/PE-Design: passen Dichte, Zugausgleich und Unterlage beim
# Berechnen an, ohne die eingestellten Werte der Objekte zu ändern.
#   density: Faktor auf den Reihen-/Stichabstand (< 1 = dichter), pull: + mm Zugausgleich,
#   ul_layers / satin_ul: Unterlage mindestens so stark, ul_spacing: Faktor Unterlagenabstand,
#   len: + mm Stichlänge der Füllung
FABRIC_PROFILES = {
    "standard": dict(name="Webware / Baumwolle (Standard)", density=1.0, pull=0.0,
                     hint="Fester, nicht dehnbarer Stoff – die eingestellten Werte gelten so."),
    "jersey": dict(name="T-Shirt / Jersey (dehnbar)", density=1.05, pull=0.15, ul_layers=2,
                   satin_ul="contour_zigzag", hint="Mehr Unterlage und Zugausgleich gegen Verzug. "
                   "Mit Cut-away-Vlies (Schneidvlies) sticken."),
    "pique": dict(name="Polo / Piqué", density=1.0, pull=0.15, ul_layers=2,
                  satin_ul="contour_zigzag", hint="Kräftige Unterlage gegen die Struktur; "
                  "Cut-away-Vlies, bei feinen Details wasserlösliches Topping."),
    "towel": dict(name="Frottee / Handtuch", density=0.9, pull=0.2, ul_layers=2,
                  satin_ul="all", ul_spacing=0.8, hint="Dichter, damit die Schlingen nicht "
                  "durchschauen. Wasserlösliches Topping oder Knockdown-Stich verwenden."),
    "fleece": dict(name="Fleece / Plüsch", density=0.92, pull=0.2, ul_layers=2, satin_ul="all",
                   hint="Wie Frottee: dichter und mit Topping, damit der Flor nicht durchdrückt."),
    "denim": dict(name="Jeans / Canvas (fest)", density=1.08, pull=-0.05, hint="Fester Stoff – "
                  "etwas lockerer sticken, sonst wird die Stickerei bretthart."),
    "cap": dict(name="Kappe / Cap", density=1.0, pull=0.2, ul_layers=2, satin_ul="contour_zigzag",
                hint="Mehr Zugausgleich; von der Mitte nach außen und von unten nach oben sticken."),
    "leather": dict(name="Leder / Kunstleder", density=1.25, pull=0.0, ul_spacing=1.6, len=0.5,
                    hint="Wenige, längere Stiche – jeder Einstich ist ein Loch. Wenig Unterlage, "
                         "keine Mini-Details, Nadel für Leder."),
    "silk": dict(name="Seide / feiner Stoff", density=1.15, pull=-0.05, hint="Leichter sticken, "
                 "damit der Stoff nicht zieht; feine Nadel (65/9) und Abreißvlies."),
}


def fabric_adjust(fill, border, name=None):
    """Füll- und Randwerte für die Stoffart anpassen (Kopien)."""
    p = FABRIC_PROFILES.get(name or FABRIC, FABRIC_PROFILES["standard"])
    f, b = dict(fill), dict(border)
    if p is FABRIC_PROFILES["standard"]:
        return f, b
    k = p.get("density", 1.0)
    f["density"] = fill.get("density", 0.4) * k
    b["density"] = border.get("density", 0.4) * k
    f["pull"] = max(0.0, fill.get("pull", 0.15) + p.get("pull", 0.0))
    if p.get("ul_layers", 1) > int(fill.get("ul_layers", 1)):
        f["ul_layers"] = p["ul_layers"]
    if p.get("satin_ul") and fill.get("satin_ul", "auto") == "auto":
        f["satin_ul"] = p["satin_ul"]
    f["ul_spacing"] = fill.get("ul_spacing", 2.2) * p.get("ul_spacing", 1.0)
    f["stitch_len"] = fill.get("stitch_len", 3.5) + p.get("len", 0.0)
    return f, b


CHAIN_SHIFT = 2.0      # mm – so weit dürfen Reihenenden springen, ohne den Abschnitt zu teilen


# ---------------------------------------------------------------- Helfer
def polygons_of(geom):
    """Liefert alle Polygone einer beliebigen Geometrie."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        out = []
        for g in geom.geoms:
            out.extend(polygons_of(g))
        return out
    return []


def lines_of(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, (MultiLineString, GeometryCollection)):
        out = []
        for g in geom.geoms:
            out.extend(lines_of(g))
        return out
    return []


def resample(coords, step, closed=False, tol=0.0):
    """Punkte entlang eines Polygonzugs im Abstand ~step (Endpunkte inklusive).
    tol > 0: Kurvenanpassung – weicht ein Stich weiter als tol (mm) von der Linie ab, wird er
    geteilt (wie »curve stitch length« in Profi-Programmen): Rundungen bleiben rund, gerade
    Strecken behalten die volle Stichlänge."""
    pts = [tuple(p[:2]) for p in coords]
    if closed and pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 2:
        return pts
    line = LineString(pts)
    length = line.length
    if length < 1e-6:
        return [pts[0]]
    n = max(1, int(math.ceil(length / step)))
    ds = [length * i / n for i in range(n + 1)]
    if tol > 0 and len(pts) > 2:
        at = lambda d: line.interpolate(d).coords[0]

        def err(d0, d1):
            a, b = at(d0), at(d1)
            vx, vy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(vx, vy) or 1e-9
            return max(abs((p[0] - a[0]) * vy - (p[1] - a[1]) * vx) / L
                       for p in (at(d0 + (d1 - d0) * f) for f in (0.25, 0.5, 0.75)))

        def split(d0, d1, depth=0):
            if depth < 4 and d1 - d0 > 1.0 and err(d0, d1) > tol:
                m = (d0 + d1) / 2
                return split(d0, m, depth + 1) + split(m, d1, depth + 1)
            return [d1]
        refined = [ds[0]]
        for d0, d1 in zip(ds, ds[1:]):
            refined.extend(split(d0, d1))
        ds = refined
    return [line.interpolate(d).coords[0] for d in ds]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


TIE_STYLE = None        # Vernähstich-Art des gerade berechneten Objekts (None = TIE_MODE)
TIE_FORCE = False       # auch vor kurzen Sprüngen ohne Schnitt vernähen (pro Objekt)

# Vernähstich-Formen wie in Ink/Stitch: Punkte (entlang, quer) in Einheiten der Größe,
# die Folge endet immer am Ansatzpunkt (0, 0)
TIE_SHAPES = {
    "half": ([(0.5, 0), (0, 0)] * 2, 1.2),
    "strong": ([(0.5, 0), (0, 0)] * 3, 1.2),
    "backforth": ([(1, 0), (0, 0)] * 2, 0.9),
    "arrow": ([(1, 0.45), (0, 0), (1, -0.45), (0, 0)], 0.9),
    "star": ([(0.7, 0), (0, 0), (0, 0.7), (0, 0), (-0.5, 0), (0, 0), (0, -0.7), (0, 0)], 0.8),
    "triangle": ([(1, 0.45), (1, -0.45), (0, 0)] * 2, 0.9),
    "zigzag": ([(0.3, 0.3), (0.6, -0.3), (0.9, 0.3), (0.6, -0.3), (0.3, 0.3), (0, 0)], 1.0),
}
TIE_NAMES = [("Wie in den Einstellungen", "auto"), ("Halbstich", "half"),
             ("Halbstich, kräftig", "strong"), ("Vor und zurück", "backforth"),
             ("Pfeil", "arrow"), ("Stern", "star"), ("Dreieck", "triangle"),
             ("Zickzack", "zigzag"), ("Nicht vernähen", "none")]


def tie(points, out, at_start=True):
    """Vernähstiche am Anfang bzw. Ende eines Stichzugs (Form siehe TIE_SHAPES)."""
    if len(points) < 2:
        return
    if at_start:
        a, b = points[0], points[1]
    else:
        a, b = points[-1], points[-2]
    d = dist(a, b)
    mode = TIE_STYLE or TIE_MODE
    mode = {"normal": "half"}.get(mode, mode)
    if d < 1e-6 or mode == "none" or mode not in TIE_SHAPES:
        return
    shape, size = TIE_SHAPES[mode]
    along = min(size, d) if mode not in ("half", "strong") else min(0.6, d * 0.5) / 0.5
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    for t, q in shape:
        out.append((a[0] + ux * t * along - uy * q * along, a[1] + uy * t * along + ux * q * along,
                    STITCH))


def random_resample(pts, length, pct, seed=1):
    """Stichlänge zufällig variieren (±pct, Anteil 0…0.5) – Ecken bleiben genau erhalten.
    Unterbricht das gleichmäßige Einstichbild (keine sichtbaren Reihenmuster)."""
    import random
    if pct <= 0 or len(pts) < 3:
        return pts
    rnd = random.Random(seed)
    fixed = [0]
    for i in range(1, len(pts) - 1):
        ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        if la < 1e-6 or lb < 1e-6 or (ax * bx + ay * by) / (la * lb) < 0.94:   # > ~20°
            fixed.append(i)
    fixed.append(len(pts) - 1)
    out = [tuple(pts[0][:2])]
    for i0, i1 in zip(fixed, fixed[1:]):
        seg = [tuple(p[:2]) for p in pts[i0:i1 + 1]]
        line = LineString(seg) if len(seg) > 1 else None
        if line is None or line.length < 1e-6:
            continue
        L, pos = line.length, 0.0
        while True:
            step = length * (1 + rnd.uniform(-pct, pct))
            if L - pos - step < length * 0.4:
                break
            pos += step
            out.append(line.interpolate(pos).coords[0])
        out.append(seg[-1])
    return out


def _seed(pts):
    """Fester Zufallsstartwert aus den Koordinaten (gleiches Objekt = gleiche Stiche)."""
    p = pts[0] if pts else (0, 0)
    return int(abs(p[0] * 7919 + p[1] * 104729) * 1000) % 2147483647


def connect(out, pts, direct=DIRECT_TRAVEL):
    """Hängt einen Stichzug an `out` an und erzeugt passende Verbindung
    (kurze Wege direkt gestickt, längere als Sprung, sehr lange mit Fadenschnitt)."""
    if not pts:
        return
    if not out:
        out.append((pts[0][0], pts[0][1], JUMP))
        tie(pts, out, True)
        out.extend((p[0], p[1], STITCH) for p in pts[1:])
        return
    last = out[-1]
    d = dist(last, pts[0])
    if d <= max(direct, DIRECT_TRAVEL):
        if d > 3.0:                           # langer Verbindungsweg: in kurze Stiche teilen
            n = int(math.ceil(d / 2.5))
            out.extend((last[0] + (pts[0][0] - last[0]) * k / n,
                        last[1] + (pts[0][1] - last[1]) * k / n, STITCH) for k in range(1, n))
        out.extend((p[0], p[1], STITCH) for p in (pts[1:] if d < 1e-6 else pts))
        return
    if d > TRIM_DISTANCE or TIE_FORCE:
        tail = [(s[0], s[1]) for s in out[-3:]]
        tie(tail, out, False)
    if d > TRIM_DISTANCE:
        out.append((last[0], last[1], TRIM))
    out.append((pts[0][0], pts[0][1], JUMP))
    tie(pts, out, True)
    out.extend((p[0], p[1], STITCH) for p in pts[1:])


def finish(out):
    """Vernähen am Ende eines Blocks."""
    if len(out) >= 2:
        tail = [(s[0], s[1]) for s in out[-3:]]
        tie(tail, out, False)
    return out


# ---------------------------------------------------------- Linienstiche
def resample_corners(coords, step, closed=False, angle=25.0, tol=0.0):
    """Wie resample, aber Ecken (Knick > angle°) und mehrfach besuchte Punkte (Kreuzungen eines
    Redwork-Wegs) werden genau eingestochen. Dazwischen gleichmäßig – so treffen Hin- und
    Rückweg über dieselbe Strecke dieselben Einstiche."""
    pts = [tuple(p[:2]) for p in coords]
    if closed and pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 3:
        return resample(pts, step, tol=tol)
    key = lambda p: (round(p[0], 2), round(p[1], 2))
    seen = {}
    for p in pts:
        seen[key(p)] = seen.get(key(p), 0) + 1
    cut = [0]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        t1 = math.atan2(b[1] - a[1], b[0] - a[0])
        t2 = math.atan2(c[1] - b[1], c[0] - b[0])
        turn = abs((t2 - t1 + math.pi) % (2 * math.pi) - math.pi)
        if math.degrees(turn) > angle or seen[key(b)] > 1:
            cut.append(i)
    cut.append(len(pts) - 1)
    out = []
    for i, j in zip(cut, cut[1:]):
        part = resample(pts[i:j + 1], step, tol=tol)
        out.extend(part if not out else part[1:])
    return out


def running_stitch(coords, length=2.5, triple=False, closed=False, repeats=1, corners=False,
                   jitter=0.0):
    """Steppstich; triple=True: Bohnenstich (jeder Stich hin-zurück-hin, `repeats`-mal).
    corners: Ecken und Kreuzungspunkte genau einstechen (siehe resample_corners).
    jitter: Stichlänge zufällig um diesen Anteil variieren."""
    tol = CURVE_TOL if length > 1.2 else 0.0
    pts = resample_corners(coords, length, closed, tol=tol) if corners else \
        resample(coords, length, closed, tol=tol)
    if jitter > 0:
        pts = random_resample(pts, length, jitter, _seed(pts))
    if not triple or len(pts) < 2:
        return pts
    # repeats: Zahl oder Muster [1, 0, …] (wie Ink/Stitch »bean stitch repeats« mit mehreren
    # Werten: Stich für Stich der Reihe nach, 0 = einfacher Stich)
    pattern = [max(0, min(4, int(r))) for r in repeats] if isinstance(repeats, (list, tuple)) \
        else [max(1, int(repeats))]
    pattern = pattern or [1]
    out = [pts[0]]
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        out.append(b)
        for _ in range(pattern[k % len(pattern)]):
            out.extend([a, b])
    return out


def bean_pattern(text):
    """»1 0 2« -> [1, 0, 2] (ungültige Angaben werden übergangen); leer -> None."""
    vals = []
    for t in str(text or "").replace(",", " ").split():
        if t.isdigit():
            vals.append(min(4, int(t)))
    return vals or None


def zigzag_line(coords, width=2.0, spacing=1.5, closed=False):
    """Zickzackstich: abwechselnd links und rechts der Linie (schräge Stiche)."""
    center = resample(coords, max(0.3, spacing / 2), closed)
    if len(center) < 2:
        return center
    nrm = _normals(center, closed)
    h = width / 2.0
    return [(p[0] + n[0] * h * (1 if i % 2 == 0 else -1), p[1] + n[1] * h * (1 if i % 2 == 0 else -1))
            for i, (p, n) in enumerate(zip(center, nrm))]


def estitch_line(coords, width=2.5, spacing=2.5, closed=False):
    """E-Stich (Deckenstich): Grundlinie mit Zacken zur linken Seite – ideal für Applikationen
    (Zacken zeigen bei geschlossenen, gegen den Uhrzeigersinn laufenden Ringen nach innen)."""
    base = resample(coords, max(0.5, spacing), closed)
    if len(base) < 2:
        return base
    nrm = _normals(base, closed)
    out = []
    for p, n in zip(base, nrm):
        tip = (p[0] + n[0] * width, p[1] + n[1] * width)
        out.extend([p, tip, p])
    return out


def manual_stitch(coords):
    """Manueller Stich: jeder Punkt ist ein Einstich (doppelte Punkte entfallen)."""
    out = []
    for p in coords:
        if not out or dist(out[-1], p) > 0.05:
            out.append((p[0], p[1]))
    return out


def _normals(pts, closed):
    n = len(pts)
    normals = []
    for i in range(n):
        if closed and n > 2:
            a = pts[i - 1] if i > 0 else pts[-2]
            b = pts[i + 1] if i < n - 1 else pts[1]
        else:
            a = pts[max(0, i - 1)]
            b = pts[min(n - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        l = math.hypot(tx, ty) or 1.0
        normals.append((-ty / l, tx / l))
    return normals


def satin_spacing(style, width):
    """Satinabstand – mit »auto_spacing« nach Breite angepasst (wie »Auto Spacing« in Wilcom):
    schmale Säulen lockerer (sonst steif und wulstig), breite etwas dichter (deckt besser)."""
    sp = style.get("density", 0.4)
    if not style.get("auto_spacing"):
        return sp
    table = ((1.0, 1.4), (2.0, 1.25), (3.0, 1.1), (5.0, 1.0), (8.0, 0.92), (12.0, 0.88))
    if width <= table[0][0]:
        f = table[0][1]
    elif width >= table[-1][0]:
        f = table[-1][1]
    else:
        f = next(f0 + (f1 - f0) * (width - w0) / (w1 - w0)
                 for (w0, f0), (w1, f1) in zip(table, table[1:]) if w0 <= width <= w1)
    return sp * f


def satin_line(coords, width=3.0, density=0.4, closed=False, underlay=True, corners=True):
    """Satinstich (Zickzack) entlang einer Mittellinie. corners: spitze Ecken mit Gehrung und
    verkürzten Innenstichen (satin.satin_corner_line) statt Garnhäufung."""
    if corners and width >= 1.2:
        from .satin import satin_corner_line
        pts = satin_corner_line(coords, width, density, closed, underlay)
        if pts is not None and len(pts) > 1:
            return pts
    center = resample(coords, density, closed)
    if len(center) < 2:
        return center
    nrm = _normals(center, closed)
    h = width / 2.0
    zig = []
    for i, (p, n) in enumerate(zip(center, nrm)):
        left = (p[0] + n[0] * h, p[1] + n[1] * h)
        right = (p[0] - n[0] * h, p[1] - n[1] * h)
        zig.extend([left, right] if i % 2 == 0 else [right, left])
    if not underlay or width < 1.2:
        return zig
    walk = resample(coords, 2.0, closed)
    if closed:
        return walk + zig
    # Unterlage vorwärts laufen, Satin rückwärts zurück
    return walk + list(reversed(zig))


# ------------------------------------------------------------ Flächenstich
def _scan_rows(geom, spacing):
    minx, miny, maxx, maxy = geom.bounds
    rows = []
    y = miny + spacing / 2.0
    while y < maxy:
        line = LineString([(minx - 1, y), (maxx + 1, y)])
        inter = geom.intersection(line)
        segs = []
        for seg in lines_of(inter):
            xs = [c[0] for c in seg.coords]
            a, b = min(xs), max(xs)
            if b - a > 0.3:
                segs.append((a, b))
        segs.sort()
        rows.append((y, segs))
        y += spacing
    return rows


def _chains(rows):
    used = [[False] * len(segs) for _, segs in rows]
    chains = []
    for i, (_, segs) in enumerate(rows):
        for j in range(len(segs)):
            if used[i][j]:
                continue
            used[i][j] = True
            chain = [(i, j)]
            ci, cj = i, j
            while ci + 1 < len(rows):
                x0, x1 = rows[ci][1][cj]
                nxt = None
                for k, (a, b) in enumerate(rows[ci + 1][1]):
                    if (not used[ci + 1][k] and a < x1 - 0.2 and b > x0 + 0.2
                            and abs(a - x0) < CHAIN_SHIFT and abs(b - x1) < CHAIN_SHIFT):
                        nxt = k
                        break
                if nxt is None:
                    break
                used[ci + 1][nxt] = True
                chain.append((ci + 1, nxt))
                ci, cj = ci + 1, nxt
            chains.append(chain)
    return chains


# Einstichmuster für Tatami: Versatz der Einstiche je Reihe (Anteil der Stichlänge).
# Die versetzten Einstichpunkte bilden auf der Fläche sichtbare Linien und Muster.
def _arc_rows():
    """Schuppen: Halbkreise aus Einstichpunkten, versetzt wie Dachziegel (Raster 2 Stichlängen)."""
    rows = []
    for r in range(16):
        c = 1.0 if r < 8 else 0.0
        t = (r % 8) / 8
        w = math.sqrt(max(0.0, 1 - t * t))
        rows.append([(c - w) % 2, (c + w) % 2])
    return rows


# Einstichmuster der Tatami-Füllung. Einfache Muster: Versatz je Reihe (Anteil der Stichlänge).
# Erweiterte Muster: {"tile": Breite in Stichlängen, "rows": [[Einstichpunkte je Reihe], …]} –
# zu enge Punkte fallen weg, zu weite Lücken werden aufgefüllt (siehe _row_points).
TATAMI_PATTERNS = {
    "standard": [0, 0.25, 0.5, 0.75],                        # feine Diagonale
    "brick": [0, 0.5],                                       # Ziegel / Mauerwerk
    "herringbone": [0, 0.2, 0.4, 0.6, 0.8, 0.6, 0.4, 0.2],   # Fischgrät / Zickzack
    "waves": [0.5 + 0.45 * math.sin(2 * math.pi * i / 16) for i in range(16)],
    "straight": [0],                                         # gerade Einstichlinien
    "steps": [0, 0.333, 0.667],                              # steile Diagonale
    "shallow": [i / 10 for i in range(10)],                  # flache Diagonale
    "twill": [0, 0, 0.25, 0.25, 0.5, 0.5, 0.75, 0.75],       # Köper (Doppelschritte)
    "scatter": [(i * 0.6180339887) % 1 for i in range(13)],  # gestreut – kein sichtbares Muster
    "bigbrick": {"tile": 2, "rows": [[0, 1]] * 4 + [[0.5, 1.5]] * 4},
    "bigwaves": {"tile": 1, "rows": [[0.5 + 0.48 * math.sin(2 * math.pi * i / 32)]
                                     for i in range(32)]},
    "zigzag": {"tile": 2, "rows": [[abs(8 - i) / 8 * 1.6] for i in range(16)]},
    "diamond": {"tile": 2, "rows": [[(0.125 * i) % 2, (-0.125 * i) % 2] for i in range(16)]},
    "check": {"tile": 2, "rows": [[0, 0.5, 1, 1.5]] + [[0, 1]] * 7},
    "scales": {"tile": 2, "rows": _arc_rows()},
}
_PATTERN_ROWS = {}


def _pattern(offsets):
    """Muster -> (rasterbreite, [einstichpunkte je reihe]) in Stichlängen."""
    key = id(offsets)
    if key not in _PATTERN_ROWS:
        if isinstance(offsets, dict):
            _PATTERN_ROWS[key] = (float(offsets["tile"]), [sorted(r) for r in offsets["rows"]],
                                  offsets)
        else:
            _PATTERN_ROWS[key] = (1.0, [[o] for o in (offsets or [0.0])], offsets)
    return _PATTERN_ROWS[key][:2]


def _row_points(a, b, y, row_idx, length, offsets):
    """Stiche einer Reihe von a nach b (a kann > b sein). Bei erweiterten Mustern (Raster über
    mehrere Stichlängen) werden zu enge Einstiche ausgelassen und zu lange Stiche geteilt –
    so bleibt jede Stichlänge zwischen ~0,35 und ~1,35 × der eingestellten Länge."""
    pts = [(a, y)]
    lo, hi = min(a, b), max(a, b)
    if length < 50:
        tile, rows = _pattern(offsets)
        base = rows[row_idx % len(rows)]
        span = tile * length
        k0, k1 = math.floor(lo / span) - 1, math.ceil(hi / span) + 1
        xs = sorted(k * span + p * length for k in range(k0, k1) for p in base)
        grid, prev = [], lo
        for x in xs:
            if x - lo <= 0.5 or hi - x <= 0.5:
                continue
            if tile > 1:
                gap = x - prev
                if gap < length * 0.35:               # zu eng: Einstich auslassen
                    continue
                if gap > length * 1.35:               # zu weit: gleichmäßig teilen
                    n = math.ceil(gap / length)
                    grid.extend(prev + gap * j / n for j in range(1, n))
            grid.append(x)
            prev = x
        if tile > 1 and hi - prev > length * 1.35:
            n = math.ceil((hi - prev) / length)
            grid.extend(q for q in (prev + (hi - prev) * j / n for j in range(1, n)) if hi - q > 0.5)
        if a > b:
            grid.reverse()
        pts.extend((x, y) for x in grid)
    pts.append((b, y))
    return pts


def _to_frame(pt, angle):
    a = math.radians(-angle)
    return (pt[0] * math.cos(a) - pt[1] * math.sin(a), pt[0] * math.sin(a) + pt[1] * math.cos(a))


def _from_frame(run, angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c) for x, y in run]


def _unwarp(run, warp):
    """Stiche aus dem verformten Reihenrahmen zurückrechnen. warp[2] (falls vorhanden):
    größte Stichlänge – längere Stiche werden im Rahmen geteilt und folgen so der Reihe.
    warp[3]: x-Stellen, an denen die Reihen knicken (Ecken der Führungslinie) – dort wird
    zusätzlich eingestochen, sonst schnitte der Stich die Ecke ab."""
    back = warp[1]
    lim = warp[2] if len(warp) > 2 else None
    if not lim:
        return [back(x, y) for x, y in run]
    breaks = warp[3] if len(warp) > 3 else []
    out = [back(*run[0])] if run else []

    def piece(p, q, depth=0):
        P, Q = out[-1], back(*q)
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        M = back(*m)
        d = dist(P, Q)
        bow = dist(M, ((P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2))
        if depth < 5 and (d > lim or (bow > 0.2 and d > 2.0)):
            piece(p, m, depth + 1)
            piece(m, q, depth + 1)
        else:
            out.append(Q)
    for p, q in zip(run, run[1:]):
        lo, hi = min(p[0], q[0]) + 0.6, max(p[0], q[0]) - 0.6
        ks = [b for b in breaks if lo < b < hi]
        if q[0] < p[0]:
            ks.reverse()
        cur = p
        for b in ks:
            t = (b - p[0]) / (q[0] - p[0])
            nxt = (b, p[1] + (q[1] - p[1]) * t)
            piece(cur, nxt)
            cur = nxt
        piece(cur, q)
    return out


def fill_stitches(geom, angle=45.0, spacing=0.4, length=3.5, offsets=None,
                  start=None, warp=None, travel=True, any_node=False, keep=None, end=None):
    """Reihenfüllung (Tatami/Satin). warp=(hin, zurück[, max. Stichlänge]) verformt die Reihen
    (z. B. Wellen, geführte Füllung). end: Füllung soll möglichst nah an diesem Punkt enden.
    travel: Abschnitte über Verbindungsstiche unter späteren Reihen bzw. am Rand verbinden
    (nur bei dichten Füllungen sinnvoll). any_node: Verbindungen dürfen auch über schon
    gestickte Reihen laufen (Unterlage). Liefert Liste von Stichzügen (Listen von Punkten);
    setzt der erste Zug direkt an `start` an, ist `start` sein erster Punkt."""
    from . import autofill
    if geom.is_empty:
        return []
    offsets = TATAMI_PATTERNS["standard"] if offsets is None else offsets
    rot = affinity.rotate(geom, -angle, origin=(0, 0))
    if warp:
        rot = shapely.ops.transform(lambda x, y, z=None: warp[0](x, y),
                                    shapely.segmentize(rot, 0.5))
        rot = rot.buffer(0)
    pos = None
    if start is not None:
        pos = _to_frame(start, angle)
        if warp:
            pos = warp[0](*pos)
    goal = None
    if end is not None:
        goal = _to_frame(end, angle)
        if warp:
            goal = warp[0](*goal)
    islands = [p for p in polygons_of(rot) if p.area > 0.01]
    last = None
    if goal is not None and len(islands) > 1:     # Insel am Endpunkt zuletzt
        G = Point(goal)
        last = islands.pop(min(range(len(islands)), key=lambda k: islands[k].distance(G)))
    runs = []
    while islands or last is not None:
        if not islands:
            islands, last = [last], None
        if pos is None:
            i = min(range(len(islands)), key=lambda k: islands[k].bounds[0])
        else:
            P = Point(pos)
            i = min(range(len(islands)), key=lambda k: islands[k].distance(P))
        final = len(islands) == 1 and last is None
        part, pos = autofill.island_runs(islands.pop(i), spacing, length, offsets, pos,
                                         _row_points, _scan_rows, _chains, travel, any_node,
                                         keep=keep, end=goal if final else None)
        runs.extend(part)
    out = []
    for run in runs:
        if len(run) < 2:
            continue
        if warp:
            run = _unwarp(run, warp)
        out.append(_from_frame(run, angle))
    if out and start is not None and dist(out[0][0], start) < 1e-6:
        out[0][0] = tuple(start[:2])
    return out


def wave_warp(wavelength, amplitude):
    k = 2 * math.pi / max(wavelength, 1.0)
    return (lambda x, y: (x, y - amplitude * math.sin(k * x)),
            lambda x, y: (x, y + amplitude * math.sin(k * x)))


def guided_warp(guide, max_len=None):
    """Geführte Füllung (wie Ink/Stitch »Guided Fill«, Strategie Kopie): Die Reihen sind
    Kopien der Führungslinie, quer zu ihrer Hauptrichtung versetzt. Liefert (winkel, warp) –
    warp bildet die Fläche so ab, dass die Führungslinie waagerecht liegt; dann füllen ganz
    normale Reihen. None, wenn die Linie unbrauchbar ist."""
    import numpy as np
    pts = [(float(p[0]), float(p[1])) for p in guide or []]
    if len(pts) < 2:
        return 0.0, None
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    if math.hypot(x1 - x0, y1 - y0) < 1.0:            # geschlossene Linie: erste Richtung
        x1, y1 = max(pts[1:], key=lambda p: math.hypot(p[0] - x0, p[1] - y0))
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    xs, ys = [], []
    for x, y in (_to_frame(p, ang) for p in pts):
        if xs and x <= xs[-1] + 1e-3:                 # rückläufige Stücke überspringen
            continue
        xs.append(x)
        ys.append(y)
    if len(xs) < 2:
        return ang, None
    X, Y = np.array(xs), np.array(ys) - ys[0]
    # Knicke der Führungslinie (dort wird in jeder Reihe eingestochen)
    breaks = []
    for i in range(1, len(xs) - 1):
        t1 = math.atan2(ys[i] - ys[i - 1], xs[i] - xs[i - 1])
        t2 = math.atan2(ys[i + 1] - ys[i], xs[i + 1] - xs[i])
        if abs(math.degrees(t2 - t1)) > 6 and (not breaks or xs[i] - breaks[-1] > 1.0):
            breaks.append(xs[i])

    def fwd(x, y):
        if isinstance(x, (tuple, list, np.ndarray)):
            x = np.asarray(x, dtype=float)
            return x, np.asarray(y, dtype=float) - np.interp(x, X, Y)
        return float(x), float(y - np.interp(x, X, Y))

    def back(x, y):
        return float(x), float(y + np.interp(x, X, Y))
    return ang, (fwd, back, max_len, breaks)


def contour_fill(geom, spacing=0.6, length=2.5, start=None):
    """Konturfüllung: Linien laufen in gleichem Abstand parallel zum Umriss nach innen."""
    rings = []
    k = 0
    while k < 400:
        g = geom.buffer(-spacing * (k + 0.5), join_style=1)
        if g.is_empty or g.area < spacing * spacing:
            break
        for poly in polygons_of(g):
            if poly.area < spacing * spacing:
                continue
            rings.append((k, list(poly.exterior.coords)))
            rings.extend((k, list(r.coords)) for r in poly.interiors)
        k += 1
    runs = []
    pos = tuple(start[:2]) if start is not None else None
    remaining = rings
    while remaining:
        depth = min(r[0] for r in remaining)
        cand = [i for i, r in enumerate(remaining) if r[0] == depth]
        # nächstgelegenen Ring derselben Tiefe wählen und dort beginnen, wo wir gerade sind
        best, bi, bd = None, 0, 1e18
        for i in cand:
            pts = remaining[i][1][:-1]
            if pos is None:
                best, bi, bd = i, 0, 0
                break
            for j, p in enumerate(pts):
                d = dist(pos, p)
                if d < bd:
                    best, bi, bd = i, j, d
        pts = remaining.pop(best)[1][:-1]
        ring = pts[bi:] + pts[:bi] + [pts[bi]]
        run = resample(ring, length)
        runs.append(run)
        pos = run[-1]
    return runs


def cross_fill(geom, size=2.5, angle=0.0, origin=None):
    """Kreuzstich: kleine X auf einem Raster. Jede Reihe wird hin (erste Diagonalen) und
    zurück (zweite Diagonalen) gestickt – ohne sichtbare Verbindungsstiche.
    origin: Rasterursprung (z. B. die Ecke einer Pixel-Schrift), damit die Kreuze genau auf
    den Kästchen sitzen statt halb darüber."""
    rot = affinity.rotate(geom, -angle, origin=(0, 0))
    minx, miny, maxx, maxy = rot.bounds
    if origin is not None:
        gx, gy = _to_frame(origin, angle) if angle else origin
        ox = gx + math.floor((minx - gx) / size + 1e-6) * size
        oy = gy + math.floor((miny - gy) / size + 1e-6) * size
    else:
        ox = math.floor(minx / size) * size
        oy = math.floor(miny / size) * size
    nx = int(math.ceil((maxx - ox) / size))
    ny = int(math.ceil((maxy - oy) / size))
    prepared = shapely.prepared.prep(rot)
    groups = []                                # (reihe, erste spalte, letzte spalte)
    for row in range(ny - 1, -1, -1):
        yt = oy + row * size
        cells = [c for c in range(nx)
                 if prepared.contains(Point(ox + (c + 0.5) * size, yt + size / 2))]
        cur = []
        for c in cells:
            if cur and c != cur[-1] + 1:
                groups.append((row, cur[0], cur[-1]))
                cur = []
            cur.append(c)
        if cur:
            groups.append((row, cur[0], cur[-1]))

    def run_of(g):
        row, c0, c1 = g
        yt = oy + row * size
        yb = yt + size
        x0, n = ox + c0 * size, c1 - c0 + 1
        pts = [(x0, yb)]
        pts += [(x0 + (i + 1) * size, yt if i % 2 == 0 else yb) for i in range(n)]
        pts.append((x0 + n * size, yb if (n - 1) % 2 == 0 else yt))
        pts += [(x0 + i * size, yt if i % 2 == 0 else yb) for i in reversed(range(n))]
        return pts

    # Reihenfolge: Streifen für Streifen von unten nach oben (z. B. erst das linke Bein eines
    # »A«, dann das rechte) – so liegen die Wege in der Fläche statt quer über Löcher
    left = set(groups)
    runs = []
    while left:
        g = max(left, key=lambda q: (q[0], -q[1]))          # unterste, dann linkeste Gruppe
        while g is not None:
            left.discard(g)
            runs.append(_from_frame(run_of(g), angle))
            above = [q for q in left if q[0] == g[0] - 1 and q[1] <= g[2] and q[2] >= g[1]]
            g = min(above, key=lambda q: abs(q[1] - g[1])) if above else None
    return runs


def _motif_outline(name, size):
    if name == "circle":
        g = Point(0, 0).buffer(size / 2, resolution=12)
    elif name == "diamond":
        g = Polygon([(0, -size / 2), (size * 0.36, 0), (0, size / 2), (-size * 0.36, 0)])
    else:
        from . import shapes
        fn = {"heart": shapes.heart, "star": shapes.star, "flower": shapes.flower}.get(name, shapes.heart)
        g = fn()
        if name == "flower":
            g = Polygon(g.exterior) if isinstance(g, Polygon) else g
        minx, miny, maxx, maxy = g.bounds
        f = size / max(maxx - minx, maxy - miny)
        g = affinity.scale(g, f, f, origin=(0, 0))
        g = affinity.translate(g, -(minx + maxx) / 2 * f, -(miny + maxy) / 2 * f)
    return list(polygons_of(g)[0].exterior.coords)


def motif_fill(geom, motif="heart", size=6.0, angle=0.0, length=2.0):
    """Motivfüllung: kleine Motive im versetzten Raster, als Steppstich-Umriss."""
    rot = affinity.rotate(geom, -angle, origin=(0, 0))
    inner = shapely.prepared.prep(rot.buffer(-0.3))
    base = _motif_outline(motif, size)
    gap = size * 1.25
    minx, miny, maxx, maxy = rot.bounds
    runs = []
    pos = None
    row = 0
    y = miny + gap / 2
    while y < maxy:
        xs = []
        x = minx + gap / 2 + (gap / 2 if row % 2 else 0)
        while x < maxx:
            xs.append(x)
            x += gap
        if row % 2:
            xs.reverse()
        for x in xs:
            pts = [(px + x, py + y) for px, py in base]
            if not inner.contains(Polygon(pts)):
                continue
            ring = pts[:-1]
            if pos is not None:
                j = min(range(len(ring)), key=lambda k: dist(pos, ring[k]))
                ring = ring[j:] + ring[:j]
            run = resample(ring + [ring[0]], min(length, size / 5))
            runs.append(run)
            pos = run[-1]
        y += gap * 0.87
        row += 1
    return [_from_frame(r, angle) for r in runs]


def _nearest_first(items, pos, key):
    """Reihenfolge: immer das nächstgelegene Teil zuerst (key(item) -> Geometrie)."""
    items, out = list(items), []
    while items:
        if pos is None:
            i = min(range(len(items)), key=lambda k: key(items[k]).bounds[0])
        else:
            P = Point(pos)
            i = min(range(len(items)), key=lambda k: key(items[k]).distance(P))
        out.append(items.pop(i))
        if pos is None:
            pos = key(out[-1]).centroid.coords[0]
    return out


def _planned(parts, pos, last=None):
    """Reihenfolge der Teilflächen mit den kürzesten Wegen insgesamt (siehe tour.py) – nicht nur
    jeweils zum nächstgelegenen Teil, das sonst einzelne Teile für einen langen Rücksprung
    liegen lässt. Mit Startpunkt beginnt es im Teil dort, sonst am linken Ende.
    last: Teil, das zuletzt kommt."""
    from . import tour
    parts = list(parts) + ([last] if last is not None else [])
    n = len(parts)
    if n > tour.HEURISTIC:
        rest = _nearest_first(parts[:n - 1] if last is not None else parts, pos, lambda p: p)
        return rest + ([last] if last is not None else [])
    gap = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            gap[i][j] = gap[j][i] = parts[i].distance(parts[j])
    pred = None
    if pos is not None:
        P = Point(pos)
        cand = range(n - 1) if last is not None else range(n)
        f = min(cand, key=lambda k: parts[k].distance(P))
        pred = [set() if k == f else {f} for k in range(n)]
        start = [0.0] * n
    else:
        x0 = min(p.bounds[0] for p in parts)
        start = [0.01 * (p.bounds[0] - x0) for p in parts]
    seq = tour.order(n, lambda i, j: gap[i][j], lambda i: start[i], pred,
                     end=n - 1 if last is not None else None)
    return [parts[i] for i in seq]


def _rotate_ring(coords, pos, exact=False):
    """Geschlossenen Ring so drehen, dass er an der Stelle nächst `pos` beginnt.
    exact: dort einen Punkt einfügen (sonst beginnt er am nächsten vorhandenen Punkt)."""
    pts = list(coords)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if exact and pos is not None and len(pts) >= 3:
        ring = LineString(pts + pts[:1])
        s = ring.project(Point(pos))
        if 1e-6 < s < ring.length - 1e-6:
            q = ring.interpolate(s).coords[0]
            acc, k = 0.0, 0
            for k in range(len(pts)):
                seg = dist(pts[k], pts[(k + 1) % len(pts)])
                if acc + seg >= s:
                    break
                acc += seg
            pts = pts[:k + 1] + [q] + pts[k + 1:]
            pts = pts[k + 1:] + pts[:k + 1]
            return pts + pts[:1]
    if pos is not None and pts:
        j = min(range(len(pts)), key=lambda k: dist(pos, pts[k]))
        pts = pts[j:] + pts[:j]
    return pts + pts[:1]


def _bridge(runs, cover):
    """Aufeinanderfolgende Züge über Verbindungsstiche innerhalb `cover` verbinden
    (z. B. Unterlage, die später vom Deckstich überdeckt wird)."""
    from .optimize import _route, _travel_points
    out = []
    for run in runs:
        if out and dist(out[-1][-1], run[0]) > DIRECT_TRAVEL:
            path = _route(out[-1][-1], run[0], cover, detour=(8.0, 60.0), within=cover.bounds)
            if path is not None:
                out[-1] = out[-1] + _travel_points(path)[:-1] + list(run)
                continue
        out.append(list(run))
    return out


def auto_underlay(geom, fill):
    """Unterlage nach Größe (wie »Auto Underlay« in Hatch/Wilcom): 0 = keine (sehr schmale
    Teile, < 2 mm), 1 = nur Randlinie (schmal, < 5 mm), 2 = Randlinie + Reihen.
    Breite = Durchmesser des größten Kreises, der in die Fläche passt."""
    if not fill.get("underlay_auto"):
        return 2
    from shapely.ops import polylabel
    w = 0.0
    for p in polygons_of(geom):
        if p.area < 0.05:
            continue
        c = polylabel(p, tolerance=0.1)
        w = max(w, 2 * p.exterior.distance(c) if not p.interiors else
                2 * min([p.exterior.distance(c)] + [r.distance(c) for r in p.interiors]))
    return 0 if w < 2.0 else 1 if w < 5.0 else 2


def underlay_params(fill):
    """Einstellungen der Flächen-Unterlage (wie Ink/Stitch »fill underlay«)."""
    return dict(angle=fill.get("ul_angle", 90.0), spacing=max(0.8, fill.get("ul_spacing", 2.2)),
                inset=fill.get("ul_inset", 0.6), layers=int(fill.get("ul_layers", 1)),
                contour=bool(fill.get("ul_contour", True)), length=fill.get("ul_len", 4.0))


def _underlay_runs(isl, base, angle, pos, fill=None):
    """Unterlage einer Insel: Kontur-Steppstich, dann Reihen quer zum Deckstich (eine oder zwei
    gekreuzte Lagen) – alles über verdeckte Verbindungsstiche zusammenhängend.
    Liefert (läufe, endposition)."""
    u = underlay_params(fill or {})
    runs = []
    level = auto_underlay(isl, fill or {})
    if level == 0:
        return [], pos
    inner = base.buffer(-u["inset"], join_style=2)
    parts = [p for p in polygons_of(inner) if p.area > 3.0]
    for part in _nearest_first(parts, pos, lambda p: p):
        if u["contour"]:
            ring = running_stitch(_rotate_ring(part.exterior.coords, pos, exact=True), 2.5)
            runs.append(ring)
            pos = ring[-1]
        for k in range(max(1, min(2, u["layers"])) if level == 2 else 0):
            a = angle + u["angle"] + 90.0 * k        # zweite Lage gekreuzt
            rows = fill_stitches(part, a, u["spacing"], u["length"], [0], start=pos, any_node=True)
            runs.extend(rows)
            if rows:
                pos = rows[-1][-1]
    return _bridge(runs, isl.buffer(-0.15)), pos


def _jitter_runs(runs, fill):
    """Zufällige Stichlänge auf Deckstich-Züge anwenden (fill["len_random"] in %)."""
    pct = fill.get("len_random", 0.0) / 100.0
    if pct <= 0:
        return runs
    length = fill.get("stitch_len", 3.5)
    return [random_resample(r, length, pct, _seed(r) + k) for k, r in enumerate(runs)]


def pull_expand(geom, pull, angle):
    """Zugausgleich wie in Wilcom/Ink/Stitch: Der Stoff zieht sich in Stichrichtung zusammen,
    also wird die Fläche nur in Stichrichtung (angle) um »pull« mm je Seite verlängert – nicht
    quer dazu, wo die Reihen ohnehin eher auseinanderdrücken. Exakt die Minkowski-Summe mit der
    Strecke ±pull: Fläche nach links und rechts verschoben plus jede Kante überstrichen."""
    if not pull or geom.is_empty:
        return geom
    if pull < 0:
        return geom.buffer(pull, join_style=2)
    rot = affinity.rotate(geom, -angle, origin=(0, 0))
    import numpy as np
    parts = [rot, affinity.translate(rot, -pull, 0), affinity.translate(rot, pull, 0)]
    v = np.array([pull, 0.0])
    for poly in polygons_of(rot):
        for ring in (poly.exterior, *poly.interiors):
            c = np.asarray(ring.coords)[:, :2]
            a, b = c[:-1], c[1:]
            k = np.abs(b[:, 1] - a[:, 1]) > 1e-9   # waagrechte Kanten deckt die Verschiebung ab
            quads = np.stack([a[k] - v, b[k] - v, b[k] + v, a[k] + v, a[k] - v], axis=1)
            parts.extend(shapely.polygons(quads))
    return affinity.rotate(shapely.union_all(parts), angle, origin=(0, 0))


def _auto_fill(geom, fill, kind, angle, spacing, length, size, pull, keep=None, underlay=None):
    """Dichte Reihenfüllung Insel für Insel: Unterlage, dann Deckstich, dann die nächste Insel.
    Innerhalb einer Insel wird über Verbindungsstiche statt mit Sprüngen weitergestickt.
    fill["underlay_first"]: erst die Unterlage *aller* Teile, dann der Deckstich – stabilisiert
    große bzw. mehrteilige Flächen besser, kostet aber mehr Sprünge."""
    out = []
    if kind == "guided":        # Reihen folgen der Führungslinie: keine feste Stichrichtung
        top = geom.buffer(pull, join_style=2) if pull else geom
    else:
        top = pull_expand(geom, pull, angle)
    islands = [p for p in polygons_of(top) if p.area > 0.02]
    if kind == "satin":
        args = dict(length=7.0, offsets=[0, 0.33, 0.67])
    elif kind == "wave":
        args = dict(length=min(length, 2.2), offsets=[0, 0.5], warp=wave_warp(size * 4, size * 0.5))
    elif kind == "guided" and guided_warp(fill.get("guide"))[1] is not None:
        angle, warp = guided_warp(fill.get("guide"), length * 1.25)
        args = dict(length=length, offsets=TATAMI_PATTERNS.get(fill.get("pattern", "standard"),
                                                               TATAMI_PATTERNS["standard"]), warp=warp)
    else:
        args = dict(length=length, offsets=TATAMI_PATTERNS.get(fill.get("pattern", "standard"),
                                                               TATAMI_PATTERNS["standard"]))
    if underlay is None:
        underlay = fill.get("underlay", True)
    first = underlay and fill.get("underlay_first", False) and len(islands) > 1
    pos = tuple(fill["start"][:2]) if fill.get("start") else None
    end = tuple(fill["end"][:2]) if fill.get("end") else None
    last = None
    if end is not None and len(islands) > 1:      # Teil am Endpunkt zuletzt sticken
        E = Point(end)
        last = islands.pop(min(range(len(islands)), key=lambda k: islands[k].distance(E)))
    if first:
        # Durchgang 1: Unterlage aller Teile
        rest = list(islands) + ([last] if last is not None else [])
        while rest:
            isl = _nearest_first(rest, pos, lambda p: p)[0]
            rest.remove(isl)
            runs, _ = _underlay_runs(isl, geom.intersection(isl) if pull else isl, angle, pos, fill)
            for run in runs:
                connect(out, run)
            if out:
                pos = out[-1][:2]
    plan = _planned(islands, pos, last)
    for k, isl in enumerate(plan):
        final = k == len(plan) - 1
        goal = end if final else None
        if goal is None:
            # in Richtung des nächsten Elements enden (kurzer Sprung)
            if not final:
                goal = nearest_points(isl, plan[k + 1])[1].coords[0]
            elif fill.get("_target") is not None:
                goal = tuple(fill["_target"][:2])
        runs = []
        if underlay and not first:
            runs, pos = _underlay_runs(isl, geom.intersection(isl) if pull else isl, angle, pos, fill)
        runs += _jitter_runs(fill_stitches(isl, angle, spacing, start=pos, keep=keep, end=goal,
                                           **args), fill)
        for run in runs:
            connect(out, run)
        if out:
            pos = out[-1][:2]
        if final and end is not None and out and dist(pos, end) > DIRECT_TRAVEL:
            _travel_to(out, end, isl)
    return out


def _travel_to(out, end, area):
    """Endpunkt: vom Ende der Füllung zum Endpunkt laufen – am Rand entlang (dort deckt ein Rand
    den Weg ab) und erst zuletzt nach innen; geht das nicht, auf kürzestem Weg in der Fläche."""
    from .autofill import EDGE_LEN, _Edge, _resample
    from .optimize import _route, _travel_points
    a, target = tuple(out[-1][:2]), tuple(end[:2])
    edge = _Edge(area)
    pts = None
    if edge.rings:
        T = Point(target)
        ring = min(edge.rings, key=lambda r: r.distance(T))
        q = ring.interpolate(ring.project(T)).coords[0]
        if edge.length(a, q) is not None:
            pts = _resample(edge.path(a, q), EDGE_LEN)
            if dist(q, target) > 0.3:
                if not area.covers(LineString([q, target])):
                    pts = None
                else:
                    pts += _resample([q, target], EDGE_LEN)
    if pts is None:
        path = _route(a, target, area.buffer(0.05))
        if path is None:
            return
        pts = _travel_points(path)
    out.extend((p[0], p[1], STITCH) for p in pts)


def gradient_colors(fill):
    """Farben eines Farbverlaufs: Farbe 1, Farbe 2 und weitere Zwischenstufen."""
    extra = [c for c in (fill.get("gradient_colors") or []) if c]
    return [fill.get("color", "#000000"), fill.get("color2", "#1E88E5")] + extra


def gradient_fill(geom, fill):
    """Farbverlauf über 2–5 Garnfarben: Die Reihen gehen quer zur Stichrichtung von Farbe zu
    Farbe über (fein gestreut gemischt), zusammen ergeben sie die volle Dichte.
    Liefert eine Stichliste je Farbe (Reihenfolge wie gradient_colors)."""
    geom = expand_geometry(geom, fill)
    angle = fill.get("angle", 45.0)
    spacing = max(0.15, fill.get("density", 0.4))
    length = fill.get("stitch_len", 3.5)
    pull = fill.get("pull", 0.15)
    n = len(gradient_colors(fill))
    top = pull_expand(geom, pull, angle)
    rot = affinity.rotate(top, -angle, origin=(0, 0))
    y0, y1 = rot.bounds[1], rot.bounds[3]
    span = max(1e-6, y1 - y0)
    rev = bool(fill.get("gradient_reverse", False))

    def which(y):
        t = min(1.0, max(0.0, (y - y0) / span))
        if rev:
            t = 1 - t
        pos = t * (n - 1)
        i = min(n - 2, int(pos))
        local = pos - i
        k = round((y - y0) / spacing)
        return i + 1 if (k * 0.6180339887) % 1.0 < local else i   # gleichmäßig gestreut
    out = []
    for c in range(n):
        out.append(_auto_fill(geom, fill, "tatami", angle, spacing, length, 5.0, pull,
                              keep=lambda y, c=c: which(y) == c, underlay=None if c == 0 else False))
    return out


TARTAN_PRESETS = {
    "Royal Stewart": [["#C8102E", 8], ["#002F6C", 2], ["#000000", 2], ["#FFFFFF", 1],
                      ["#000000", 1], ["#FFD100", 1], ["#000000", 2], ["#C8102E", 6]],
    "Black Watch": [["#0B3D2E", 8], ["#000000", 6], ["#002F6C", 6], ["#000000", 2],
                    ["#002F6C", 2]],
    "MacLeod (gelb)": [["#FFD100", 8], ["#000000", 4], ["#C8102E", 1], ["#000000", 4]],
    "Buchanan": [["#FFD100", 4], ["#0B6E3A", 6], ["#C8102E", 6], ["#000000", 1],
                 ["#FFFFFF", 1]],
    "Holzfäller (rot/schwarz)": [["#C8102E", 8], ["#000000", 8]],
    "Vichy (blau/weiß)": [["#1E5AA8", 4], ["#FFFFFF", 4]],
}


def tartan_sett(fill):
    sett = [s for s in (fill.get("tartan") or TARTAN_PRESETS["Royal Stewart"])
            if s and float(s[1]) > 0]
    if fill.get("tartan_symmetric", True) and len(sett) > 2:
        sett = sett + sett[-2:0:-1]                 # gespiegelt: A B C D C B
    return [(str(c), float(w) * fill.get("tartan_scale", 1.0)) for c, w in sett]


def tartan_colors(fill):
    """Farben des Tartans in Stickreihenfolge: erst Kette (längs), dann Schuss (quer)."""
    cols = list(dict.fromkeys(c.upper() for c, _ in tartan_sett(fill)))
    return [("warp", c) for c in cols] + [("weft", c) for c in cols]


def tartan_fill(geom, fill):
    """Schottenkaro (wie Ink/Stitch »Tartan«): Streifenfolge (Sett) in Längs- und Querrichtung.
    Jede Farbe der Kette wird als Reihen längs ihrer Streifen gestickt, danach der Schuss quer
    darüber – an den Kreuzungen mischen sich die Farben wie bei gewebtem Stoff.
    Liefert [(farbe, stiche)] in Stickreihenfolge."""
    geom = expand_geometry(geom, fill)
    angle = fill.get("angle", 45.0)
    spacing = max(0.3, fill.get("density", 0.4) * 1.4)   # zwei Lagen: lockerer je Lage
    length = fill.get("stitch_len", 3.5)
    sett = tartan_sett(fill)
    total = sum(w for _, w in sett)
    if total <= 0 or geom.is_empty:
        return []
    rot = affinity.rotate(geom, -angle, origin=(0, 0))
    minx, miny, maxx, maxy = rot.bounds
    out = []
    for layer in ("warp", "weft"):
        lo, hi = (minx, maxx) if layer == "warp" else (miny, maxy)
        bands = {}
        u = math.floor(lo / total) * total
        while u < hi:
            for c, w in sett:
                if u + w > lo and u < hi:
                    b = box(u, miny - 1, u + w, maxy + 1) if layer == "warp" else \
                        box(minx - 1, u, maxx + 1, u + w)
                    bands.setdefault(c.upper(), []).append(b)
                u += w
        for c in dict.fromkeys(c.upper() for c, _ in sett):
            region = unary_union(bands.get(c, [])).intersection(rot)
            region = affinity.rotate(region, angle, origin=(0, 0))
            sts = []
            a = angle + 90 if layer == "warp" else angle
            for run in _jitter_runs(fill_stitches(region, a, spacing, length, start=None), fill):
                connect(sts, run)
            if sts:
                out.append((c, finish(sts)))
    return out


def spiral_fill(geom, spacing=0.4, length=3.0):
    """Spiralfüllung: eine Spirale von der Mitte nach außen (wie »Circular Fill«)."""
    c = geom.centroid
    if not geom.contains(c):
        c = geom.representative_point()
    cx, cy = c.x, c.y
    minx, miny, maxx, maxy = geom.bounds
    rmax = max(math.hypot(x - cx, y - cy) for x in (minx, maxx) for y in (miny, maxy)) + spacing
    b = spacing / (2 * math.pi)
    pts, th, r = [], 0.0, 0.0
    while r < rmax:
        pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
        th += length / max(r, length)
        r = b * th
    if len(pts) < 2:
        return []
    spiral = LineString(pts)
    pieces = [p for p in lines_of(spiral.intersection(geom)) if p.length > 0.6]
    pieces.sort(key=lambda p: spiral.project(Point(p.coords[0])))
    runs = [list(p.coords) for p in pieces]
    if not runs:
        return []
    # Bogenstücke wie Abschnitte behandeln: immer das nächstgelegene Bogenende anschließen
    # (notfalls rückwärts) – so wird jede »Ausbuchtung« ohne Sprung durchgestickt
    out = [runs.pop(0)]
    while runs:
        e = out[-1][-1]
        best = min(range(len(runs)), key=lambda k: min(dist(e, runs[k][0]), dist(e, runs[k][-1])))
        run = runs.pop(best)
        if dist(e, run[-1]) < dist(e, run[0]):
            run = run[::-1]
        out.append(run)
    return out


def meander_fill(geom, size=5.0, length=2.0, seed=7, start=None):
    """Mäanderfüllung (Quilt-Stil): eine verschlungene, sich nie kreuzende Linie über die
    ganze Fläche. Entsteht als Umriss eines zufälligen Labyrinth-Baums auf einem Raster."""
    import random
    import numpy as np
    s = max(1.2, size * 0.6)            # Rasterweite; die Linien liegen s/2 auseinander
    inner = geom.buffer(-0.4 * s)
    if inner.is_empty:
        return []
    minx, miny, maxx, maxy = inner.bounds
    nx, ny = int((maxx - minx) / s) + 2, int((maxy - miny) / s) + 2
    xs = minx + (np.arange(nx) + 0.25) * s
    ys = miny + (np.arange(ny) + 0.25) * s
    gx, gy = np.meshgrid(xs, ys)
    ok = shapely.contains_xy(inner, gx, gy)
    cells = {(i, j) for j in range(ny) for i in range(nx) if ok[j, i]}
    rnd = random.Random(seed)
    h = s * 0.25
    seen, runs, pos = set(), [], (tuple(start[:2]) if start is not None else None)
    while cells - seen:
        rest = cells - seen
        start = min(rest) if pos is None else \
            min(rest, key=lambda c: math.hypot(xs[c[0]] - pos[0], ys[c[1]] - pos[1]))
        seen.add(start)
        parts = [box(xs[start[0]] - h, ys[start[1]] - h, xs[start[0]] + h, ys[start[1]] + h)]
        stack = [start]
        while stack:                    # Labyrinth: Tiefensuche mit zufälliger Richtung
            c = stack[-1]
            nbs = [(c[0] + dx, c[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            nbs = [n for n in nbs if n in cells and n not in seen]
            if not nbs:
                stack.pop()
                continue
            n = rnd.choice(nbs)
            seen.add(n)
            stack.append(n)
            x0, y0, x1, y1 = xs[c[0]], ys[c[1]], xs[n[0]], ys[n[1]]
            parts.append(box(min(x0, x1) - h, min(y0, y1) - h, max(x0, x1) + h, max(y0, y1) + h))
        poly = unary_union(parts)
        for p in polygons_of(poly):
            ring = chaikin(_rotate_ring(p.exterior.coords, pos)[:-1], 3, True)
            run = resample(list(ring) + [ring[0]], length)
            runs.append(run)
            pos = run[-1]
    return runs


def _append(out, sts):
    """Fertige Stichliste eines Elements anhängen – kurze Wege direkt, sonst Sprung (mit Schnitt
    und Vernähen, wenn weit)."""
    first = next((k for k, s in enumerate(sts) if s[2] == STITCH), None)
    if first is None:
        return
    if not out:
        out.extend(sts)
        return
    last = next(s for s in reversed(out) if s[2] == STITCH)
    b = sts[first]
    d = dist(last, b)
    if d <= DIRECT_TRAVEL:
        out.extend(sts[first:])
        return
    if d > TRIM_DISTANCE or TIE_FORCE:
        tie([(s[0], s[1]) for s in out[-3:]], out, False)
    if d > TRIM_DISTANCE:
        out.append((last[0], last[1], TRIM))
    if sts[0][2] != JUMP:
        out.append((b[0], b[1], JUMP))
    out.extend(sts)


def knock_out(geom, cut):
    """Fläche ohne den Bereich cut (automatisches Aussparen verdeckter Teile). Schmale
    Reststreifen (unter 0,8 mm) und Krümel (unter 0,5 mm²) fallen weg – sie ergäben nur
    Sprünge; Ecken bleiben spitz."""
    try:
        rest = geom.difference(cut)
    except shapely.errors.GEOSException:     # ungültige Form: lieber nichts aussparen
        return geom
    if rest.is_empty:
        return rest
    opened = rest.buffer(-0.4, join_style=2).buffer(0.4, join_style=2).intersection(rest)
    parts = [p for p in polygons_of(opened) if p.area > 0.5]
    return unary_union(parts) if parts else Polygon()


def element_fill(geom, fill, border, cut=None):
    """Element für Element sticken: für jede Teilfläche Unterlage, Füllung und ihr eigener Rand,
    erst dann geht es zum nächsten Element (Rand in derselben Farbe wie die Füllung).
    Jedes Element endet möglichst nah am nächsten – Sprünge nur zwischen fertigen Elementen.
    cut: verdeckter Bereich, den die Füllung ausspart (der Rand folgt weiter der Kontur)."""
    parts = [p for p in polygons_of(geom) if p.area > 0.05]
    out = []
    pos = tuple(fill["start"][:2]) if fill.get("start") else None
    plan = _planned(parts, pos)
    for k, isl in enumerate(plan):
        f = dict(fill)
        f.pop("end", None)
        if pos is not None:
            f["start"] = pos
        if k < len(plan) - 1:
            f["_target"] = nearest_points(isl, plan[k + 1])[1].coords[0]
        elif fill.get("end"):
            f["_target"] = tuple(fill["end"][:2])
        area = isl if cut is None else knock_out(isl, cut)
        sts = fill_with_underlay(area, f) if not area.is_empty else []
        _append(out, sts)
        if out:
            pos = (out[-1][0], out[-1][1])
        # Rand direkt an die Füllung anschließen (Wege über die gleichfarbige Fläche)
        border_stitches(isl, border, out=out, area=isl, end=f.get("_target"))
        if out:
            pos = (out[-1][0], out[-1][1])
    return out


def expand_geometry(geom, fill):
    """Füllfläche vergrößern/verkleinern (fill["expand"] in mm, wie Ink/Stitch »Erweitern«) –
    z. B. damit die Füllung unter einen Satinrand reicht."""
    e = fill.get("expand", 0.0)
    if not e or geom.is_empty:
        return geom
    g = geom.buffer(e, join_style=2)
    return g if not g.is_empty else geom


def fill_with_underlay(geom, fill):
    """Komplette Füllung inkl. Unterlage und Zugausgleich -> Stichliste."""
    out = []
    geom = expand_geometry(geom, fill)
    angle = fill.get("angle", 45.0)
    spacing = max(0.15, fill.get("density", 0.4))
    kind = fill.get("type", "tatami")
    length = fill.get("stitch_len", 3.5)
    size = max(1.0, fill.get("size", 5.0))
    pull = fill.get("pull", 0.15)
    if kind not in ("contour", "cross", "motif", "net", "circular", "meander", "ripple"):
        return _auto_fill(geom, fill, kind, angle, spacing, length, size, pull)
    dense = kind in ("contour", "circular")
    level = auto_underlay(geom, fill) if dense else 2
    if dense and fill.get("underlay", True) and level:
        u = underlay_params(fill)
        inner = geom.buffer(-u["inset"], join_style=2)
        if not inner.is_empty and inner.area > 4:
            first = tuple(fill["start"][:2]) if fill.get("start") else None
            if u["contour"]:
                for poly in _nearest_first(polygons_of(inner), first, lambda p: p):
                    pos = (out[-1][0], out[-1][1]) if out else first
                    connect(out, running_stitch(_rotate_ring(poly.exterior.coords, pos,
                                                             pos is not None), 2.5))
            for k in range(max(1, min(2, u["layers"])) if level == 2 else 0):
                for run in fill_stitches(inner, angle + u["angle"] + 90.0 * k, u["spacing"],
                                         u["length"], [0], any_node=True,
                                         start=(out[-1][0], out[-1][1]) if out else first):
                    connect(out, run)
    top = geom.buffer(pull, join_style=2) if pull and dense else geom
    start = (out[-1][0], out[-1][1]) if out else (tuple(fill["start"][:2]) if fill.get("start")
                                                  else None)
    if kind == "contour":
        runs = contour_fill(top, spacing, min(length, 2.5), start)
    elif kind == "circular":
        runs = spiral_fill(top, spacing, min(length, 3.0))
    elif kind == "meander":
        runs = meander_fill(geom, size, min(length, 2.5), start=start)
    elif kind == "ripple":
        runs = contour_fill(geom, size * 0.5, min(length, 2.5), start)
    elif kind == "cross":
        runs = cross_fill(geom, size * 0.5, angle - 45,   # 45° = aufrechte Kreuze
                          fill.get("grid_origin"))
    elif kind == "motif":
        runs = motif_fill(geom, fill.get("motif", "heart"), size, angle - 45, min(length, 2.0))
    else:   # Netz: offene Reihen – Verbindungen wären sichtbar, daher springen
        runs = fill_stitches(geom, angle, size * 0.6, length, [0], start, travel=False)
        runs += fill_stitches(geom, angle + 90, size * 0.6, length, [0],
                              runs[-1][-1] if runs else start, travel=False)
    if kind in ("contour", "circular", "meander", "ripple"):
        runs = _jitter_runs(runs, fill)
    direct = {"cross": size * 0.6, "motif": size * 0.4, "contour": spacing * 2.5,
              "net": size * 0.7, "circular": spacing * 3, "meander": size * 0.6,
              "ripple": size * 0.9}.get(kind, DIRECT_TRAVEL)
    inside = shapely.prepared.prep(geom.buffer(0.3)) if kind == "cross" else None
    cell, cang = size * 0.5, angle - 45
    for run in runs:
        # Kreuzstich: der Weg zur nächsten Reihe darüber läuft als Stich auf der Reihengrenze –
        # die folgende Kreuzreihe deckt ihn zu (statt bei jeder Reihe zu springen)
        if inside is not None and out and run:
            a_, b_ = _to_frame(out[-1][:2], cang), _to_frame(run[0][:2], cang)
            near = abs(a_[1] - b_[1]) < 0.05 and b_[1] <= a_[1] + 1e-6 or \
                abs(abs(a_[1] - b_[1]) - cell) < 0.05 and abs(a_[0] - b_[0]) < 0.05
            if near and inside.contains(LineString([out[-1][:2], run[0][:2]])):
                connect(out, run, 1e9)
                continue
            connect(out, run, direct)
        else:
            connect(out, run, direct)
    return out


def applique_stitches(geom, cover_width=3.0, tack="zigzag", density=0.4):
    """Applikation: Platzierungslinie – Stopp – Heftstich – Stopp – Satinrand.
    Liefert drei Stichlisten; zwischen ihnen hält die Maschine an."""
    rings = []
    for poly in polygons_of(geom):
        rings.append(list(poly.exterior.coords))
        rings.extend(list(r.coords) for r in poly.interiors)
    place, tackdown, cover = [], [], []
    for ring in rings:
        connect(place, running_stitch(ring, 2.5, closed=True))
    inner = geom.buffer(-0.4, join_style=2)
    for poly in polygons_of(inner if not inner.is_empty else geom):
        for ring in [poly.exterior] + list(poly.interiors):
            pts = list(ring.coords)
            if tack == "zigzag":
                connect(tackdown, satin_line(pts, 1.2, 1.6, closed=True, underlay=False))
            else:
                connect(tackdown, running_stitch(pts, 2.0, closed=True))
    for ring in rings:
        connect(cover, satin_line(ring, cover_width, density, closed=True, underlay=True))
    return [finish(place), finish(tackdown), finish(cover)]


# ------------------------------------------------------------- Objekte
def _travel_over(out, pos, ring_pt, pts, area, later=None):
    """Steppstich-Weg über die schon gestickte, gleichfarbige Fläche bis zum Ringpunkt (der Rand
    selbst kann leicht außerhalb beginnen, z. B. Satin). later: Bereich, den der noch folgende
    Rand überdeckt – dort läuft der Weg bevorzugt (unsichtbar). True, wenn ein Weg gelegt wurde."""
    if not out or not pts or dist(pos, pts[0]) <= DIRECT_TRAVEL:
        return False
    from .optimize import _route
    path = _route(pos, ring_pt, area.buffer(-0.1), detour=(6.0, 40.0), within=area.bounds,
                  prefer=later)
    if path is None:
        return False
    out.extend((x, y, STITCH) for x, y in resample(path, 2.5)[1:])
    return True


def _ring_band(rings, border):
    """Bereich, den die noch zu stickenden Ringe der Umrandung überdecken."""
    w = border.get("width", 3.0) / 2 if border.get("type") in ("satin", "zigzag", "estitch") else 0.35
    parts = [LineString(c).buffer(max(0.35, w * 0.9)) for c, _ in rings if len(c) > 1]
    return unary_union(parts) if parts else None


def border_stitches(geom, border, out=None, start=None, exact=False, area=None, end=None):
    """Umrandung. Die Ringe werden in kürzester Reihenfolge gestickt und beginnen jeweils
    an der Stelle, die der Nadel am nächsten ist (exact: genau dort, nicht am nächsten Punkt).
    area: gleichfarbige, schon gestickte Fläche – Wege zwischen den Ringen (z. B. zum Rand eines
    Lochs) laufen dann als Steppstich darüber statt als Sprung.
    end: hier soll die Umrandung enden (z. B. Richtung nächstes Element) – der nächstgelegene
    Ring kommt zuletzt und beginnt/endet an diesem Punkt."""
    out = [] if out is None else out
    kind = border.get("type", "none")
    if kind == "none":
        return out
    rings = []
    from shapely.geometry.polygon import orient
    for poly in polygons_of(geom):
        poly = orient(poly, 1.0)        # außen gegen, Löcher mit dem Uhrzeigersinn: links = innen
        rings.append((list(poly.exterior.coords), True))
        rings.extend((list(r.coords), True) for r in poly.interiors)
    for line in lines_of(geom):
        rings.append((list(line.coords), False))
    pos = (out[-1][0], out[-1][1]) if out else start
    last_ring = None
    if end is not None and len(rings) > 1 and area is not None:
        E_ = Point(end)
        k = min(range(len(rings)), key=lambda i: LineString(rings[i][0]).distance(E_))
        if rings[k][1]:
            last_ring = rings.pop(k)
    while rings or last_ring is not None:
        if not rings:
            rings, last_ring = [last_ring], None
            coords, closed = rings.pop()
            coords = _rotate_ring(coords, end, True)
            pts = line_stitches(coords, border, closed)
            _travel_over(out, pos, coords[0], pts, area, _ring_band([(coords, closed)], border))
            connect(out, pts, 3.0)
            pos = (out[-1][0], out[-1][1])
            continue
        best = None
        for i, (coords, closed) in enumerate(rings):
            if pos is None:
                key = (min(c[0] for c in coords), 0)
                cand = (key, i, None)
            elif closed:
                d = min(dist(pos, c) for c in coords)
                cand = (d, i, None)
            else:
                d0, d1 = dist(pos, coords[0]), dist(pos, coords[-1])
                cand = (min(d0, d1), i, d1 < d0)
            if best is None or cand[0] < best[0]:
                best = cand
        _, i, rev = best
        coords, closed = rings.pop(i)
        if closed:
            coords = _rotate_ring(coords, pos, exact)
        elif rev:
            coords = coords[::-1]
        pts = line_stitches(coords, border, closed)
        later = _ring_band(rings + [(coords, closed)] + ([last_ring] if last_ring else []), border) \
            if area is not None else None
        moved = area is not None and _travel_over(out, pos, coords[0], pts, area, later)
        connect(out, pts, 3.0 if moved else DIRECT_TRAVEL)
        pos = (out[-1][0], out[-1][1])
    return out


# ---------------------------------------------------------------- Motivstich-Linie
# (Schlüssel, Name, durchgehend) – durchgehende Muster laufen ohne Verbindungslinie weiter
LINE_MOTIFS = [("heart", "Herzen", False), ("star", "Sterne", False), ("circle", "Kreise", False),
               ("diamond", "Rauten", False), ("leaf", "Blätter", False),
               ("flower", "Blüten", False), ("scallop", "Bögen (Muschelkante)", True),
               ("wave", "Welle", True), ("zigzag", "Zacken", True), ("loop", "Schlaufen", True)]


def _line_motif_outline(kind):
    """Motiv in Einheitskoordinaten: u 0 … 1 entlang der Linie, v nach oben (0 = Linie).
    Geschlossene Motive beginnen und enden am Ankerpunkt auf der Linie, durchgehende laufen
    von (0, 0) nach (1, 0)."""
    def ring(pts_fn, n, cy=0.5, anchor=0.5):
        pts = [pts_fn(2 * math.pi * k / n) for k in range(n + 1)]
        # Stiel vom Anker zum untersten Punkt, Umriss, zurück
        low = min(range(len(pts)), key=lambda i: (pts[i][1], abs(pts[i][0] - anchor)))
        loop = pts[low:-1] + pts[:low + 1]
        return [(anchor, 0.0)] + loop + [(anchor, 0.0)]
    if kind == "heart":
        def f(t):
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            return 0.5 + x / 34.0, (y + 17) / 30.0
        return ring(f, 48)
    if kind == "star":
        pts = []
        for k in range(11):
            r = 0.5 if k % 2 == 0 else 0.21
            a = math.pi / 2 + k * math.pi / 5
            pts.append((0.5 + r * math.cos(a), 0.55 + r * math.sin(a)))
        low = min(range(10), key=lambda i: pts[i][1])
        loop = pts[low:10] + pts[:low + 1]
        return [(0.5, 0.0)] + loop + [(0.5, 0.0)]
    if kind == "circle":
        return ring(lambda t: (0.5 + 0.4 * math.cos(t), 0.5 + 0.4 * math.sin(t)), 32)
    if kind == "diamond":
        return [(0.5, 0.0), (0.15, 0.5), (0.5, 1.0), (0.85, 0.5), (0.5, 0.0)]
    if kind == "leaf":                           # aufrechtes, leicht geneigtes Blatt mit Stiel
        a = math.radians(-25)
        ca, sa = math.cos(a), math.sin(a)
        side = []
        for k in range(17):
            t = k / 16
            side.append((0.24 * math.sin(math.pi * t), 0.12 + 0.88 * t))
        outline = [(x, y) for x, y in side] + [(-x, y) for x, y in reversed(side)]
        rot = [(0.5 + x * ca - y * sa, x * sa + y * ca) for x, y in outline]
        return [(0.5, 0.0)] + rot + [(0.5, 0.0)]
    if kind == "flower":
        pts = []
        for k in range(61):
            a = 2 * math.pi * k / 60
            r = 0.26 + 0.17 * abs(math.cos(2.5 * a))
            pts.append((0.5 + r * math.cos(a), 0.5 + r * math.sin(a)))
        low = min(range(60), key=lambda i: pts[i][1])
        loop = pts[low:60] + pts[:low + 1]
        return [(0.5, 0.0)] + loop + [(0.5, 0.0)]
    if kind == "scallop":
        return [(0.5 - 0.5 * math.cos(math.pi * k / 16), 0.5 * math.sin(math.pi * k / 16))
                for k in range(17)]
    if kind == "wave":
        return [(k / 24, 0.35 * math.sin(2 * math.pi * k / 24)) for k in range(25)]
    if kind == "zigzag":
        return [(0.0, 0.0), (0.25, 0.4), (0.75, -0.4), (1.0, 0.0)]
    if kind == "loop":                           # Schreibschrift-Schlaufe (verschlungene Zykloide)
        out = []
        for k in range(41):
            t = 2 * math.pi * k / 40
            out.append(((t - 1.7 * math.sin(t)) / (2 * math.pi), 0.42 * (1 - math.cos(t))))
        return out
    return [(0.0, 0.0), (1.0, 0.0)]


class _PathParam:
    """Punkt und Richtung bei Bogenlänge s auf einem Polygonzug."""

    def __init__(self, pts):
        self.pts = [tuple(p[:2]) for p in pts]
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + dist(a, b))
        self.length = self.cum[-1]

    def at(self, s):
        import bisect
        s = min(max(s, 0.0), self.length)
        i = min(max(bisect.bisect_right(self.cum, s) - 1, 0), len(self.pts) - 2)
        a, b = self.pts[i], self.pts[i + 1]
        seg = (self.cum[i + 1] - self.cum[i]) or 1e-9
        t = (s - self.cum[i]) / seg
        tx, ty = (b[0] - a[0]) / seg, (b[1] - a[1]) / seg
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), (tx, ty)


def motif_line(coords, style, closed=False):
    """Motive (Herzen, Sterne, Bögen …) entlang einer Linie – wie »Motif Run« in Profi-Programmen.
    style: motif, width (Motivgröße), gap (Abstand), stitch_len, motif_alt (abwechselnd oben/unten),
    type triple → Bohnenstich für kräftige Motive."""
    pts = [tuple(p[:2]) for p in coords]
    if closed and pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 2:
        return []
    pp = _PathParam(pts)
    kind = style.get("motif", "heart")
    w = max(1.0, float(style.get("width", 6.0)))
    gap = max(0.0, float(style.get("gap", 1.0)))
    cont = next((c for k, _, c in LINE_MOTIFS if k == kind), False)
    if cont:
        gap = 0.0
    n = max(1, int((pp.length + gap) // (w + gap)))
    if cont:                                      # durchgehend: Motive auf die Länge strecken
        w = pp.length / n
    start = (pp.length - (n * w + (n - 1) * gap)) / 2
    unit = _line_motif_outline(kind)
    if cont:                                      # durchgehend: fein unterteilen, biegt mit
        dense = [unit[0]]
        for a, b in zip(unit, unit[1:]):
            for j in range(1, 7):
                dense.append((a[0] + (b[0] - a[0]) * j / 6, a[1] + (b[1] - a[1]) * j / 6))
        unit = dense
    alt = bool(style.get("motif_alt", False))
    path = []
    pos = 0.0
    for k in range(n):
        s0 = start + k * (w + gap)
        flip = -1.0 if alt and k % 2 else 1.0
        if s0 > pos:                              # Verbindung auf der Linie bis zum Motiv
            steps = max(1, int((s0 - pos) / 1.0))
            for j in range(steps + 1):
                path.append(pp.at(pos + (s0 - pos) * j / steps)[0])
        if cont:
            for u, v in unit:
                (x, y), (tx, ty) = pp.at(s0 + u * w)
                nx, ny = ty, -tx                  # links der Laufrichtung = »oben«
                path.append((x + nx * v * w * flip, y + ny * v * w * flip))
        else:                                     # geschlossene Motive: starr, am Anker ausgerichtet
            (ax, ay), (tx, ty) = pp.at(s0 + 0.5 * w)
            nx, ny = ty, -tx
            path.append(pp.at(s0 + unit[0][0] * w)[0])
            for u, v in unit:
                du, dv = (u - 0.5) * w, v * w * flip
                path.append((ax + tx * du + nx * dv, ay + ty * du + ny * dv))
        pos = s0 + w
    if pos < pp.length:
        path.append(pp.at(pp.length)[0])
    dedup = [path[0]]
    for q in path[1:]:
        if dist(q, dedup[-1]) > 0.05:
            dedup.append(q)
    sl = min(float(style.get("stitch_len", 2.0)), max(0.8, w / 5.0))
    return running_stitch(dedup, sl, style.get("motif_triple", False))


def line_stitches(coords, style, closed=False):
    kind = style.get("type", "run")
    if kind == "motif":
        return motif_line(coords, style, closed)
    if kind == "satin":
        return satin_line(coords, style.get("width", 3.0), satin_spacing(style, style.get("width", 3.0)),
                          closed, style.get("underlay", True), style.get("corner", "mitre") != "none")
    if kind == "zigzag":
        return zigzag_line(coords, style.get("width", 2.0), style.get("stitch_len", 1.5), closed)
    if kind == "estitch":
        return estitch_line(coords, style.get("width", 2.5), style.get("stitch_len", 2.5), closed)
    if kind == "manual":
        pts = list(coords) + ([coords[0]] if closed and coords and coords[0] != coords[-1] else [])
        return manual_stitch(pts)
    if kind == "sketch":
        return sketch_line(coords, style.get("stitch_len", 2.0), int(style.get("repeats", 2)) + 1,
                           style.get("width", 1.0) * 0.35, closed)
    return running_stitch(coords, style.get("stitch_len", 2.5), kind == "triple", closed,
                          bean_pattern(style.get("bean_pattern")) or style.get("repeats", 1),
                          bool(style.get("corners", False)),
                          style.get("len_random", 0.0) / 100.0)


def sketch_line(coords, length=2.0, passes=3, spread=0.35, closed=False):
    """Skizzenstich (wie mit dem Bleistift skizziert): die Linie mehrmals hin und zurück, jeder
    Durchgang seitlich leicht und gleichmäßig versetzt (geglättetes Rauschen). Die Durchgänge
    gehen ineinander über – ein durchgehender Stichzug ohne Sprung."""
    import random
    base = resample(coords, length, closed)
    if len(base) < 2:
        return base
    rnd = random.Random(_seed(base))
    n = len(base)
    normals = []
    for i in range(n):
        a, b = base[max(0, i - 1)], base[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        normals.append((-dy / L, dx / L))
    out = []
    for k in range(max(1, passes)):
        # geglättetes Rauschen: Zufallsweg, mehrfach gemittelt, Enden laufen auf 0 aus
        walk, v = [], 0.0
        for _ in range(n):
            v = 0.7 * v + rnd.uniform(-1, 1)
            walk.append(v)
        for _ in range(2):
            walk = [(walk[max(0, i - 1)] + walk[i] + walk[min(n - 1, i + 1)]) / 3 for i in range(n)]
        m = max(1e-6, max(abs(w) for w in walk))
        idx = range(n) if k % 2 == 0 else range(n - 1, -1, -1)
        for j, i in enumerate(idx):
            if out and j == 0:
                continue                      # Wendepunkt nicht doppelt
            off = 0.0 if k == 0 else spread * walk[i] / m
            if not closed:
                off *= min(1.0, i / 3, (n - 1 - i) / 3)
            out.append((base[i][0] + normals[i][0] * off, base[i][1] + normals[i][1] * off))
    return out


def chaikin(coords, n, closed):
    """Rundet Ecken eines Polygonzugs ab (Chaikin-Verfahren, n Durchläufe)."""
    pts = [tuple(p[:2]) for p in coords]
    if closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    for _ in range(n):
        if len(pts) < 3:
            break
        out = [] if closed else [pts[0]]
        segs = list(zip(pts, pts[1:] + pts[:1])) if closed else list(zip(pts, pts[1:]))
        for a, b in segs:
            out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        if not closed:
            out[1:2] = []          # Startpunkt bleibt exakt erhalten
            out[-1:] = [pts[-1]]   # Endpunkt ebenso
        pts = out
    return pts


def smooth_geometry(geom, n):
    if not n or geom is None or geom.is_empty:
        return geom
    if isinstance(geom, LineString):
        return LineString(chaikin(geom.coords, n, geom.is_closed))
    polys = []
    for p in polygons_of(geom):
        ext = chaikin(p.exterior.coords, n, True)
        holes = [chaikin(r.coords, n, True) for r in p.interiors]
        if len(ext) >= 3:
            polys.append(Polygon(ext, [h for h in holes if len(h) >= 3]).buffer(0))
    return unary_union(polys) if polys else geom


def bounds_of(stitches):
    xs = [s[0] for s in stitches]
    ys = [s[1] for s in stitches]
    if not xs:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


def merge_union(geoms):
    return unary_union([g for g in geoms if g is not None and not g.is_empty])
