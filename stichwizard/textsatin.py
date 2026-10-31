"""Schrift-Satin für Computerschriften (wie »TrueType-Lettering« in Profi-Programmen).

Schmale Striche eines Buchstabens werden als Satinsäule gestickt, die genau der Buchstabenform
folgt: entlang der Mittellinie wird alle paar Zehntelmillimeter quer zum Strich bis an den Rand
gemessen – so dreht sich der Satin mit jeder Kurve, wird an dünnen Stellen schmaler und läuft an
Strichenden spitz aus. Was übrig bleibt (Knotenpunkte, breite Bäuche), wird als Tatami gefüllt.
"""
import math

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from . import engine, satin
from .centerline import centerlines
from .engine import polygons_of

MAX_SATIN = 7.0          # mm – breitere Striche werden gefüllt (zu lange Satinstiche)


def _hit(boundary, o, d, maxlen):
    """Erster Schnittpunkt eines Strahls von o in Richtung d mit dem Rand (oder None)."""
    end = (o[0] + d[0] * maxlen, o[1] + d[1] * maxlen)
    inter = boundary.intersection(LineString([o, end]))
    if inter.is_empty:
        return None
    pts = []
    for g in getattr(inter, "geoms", [inter]):
        if g.geom_type == "Point":
            pts.append((g.x, g.y))
        elif hasattr(g, "coords"):
            pts.extend(g.coords)
    pts = [p for p in pts if math.hypot(p[0] - o[0], p[1] - o[1]) > 1e-6]
    return min(pts, key=lambda p: math.hypot(p[0] - o[0], p[1] - o[1])) if pts else None


def _resample(pts, step):
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        while acc + seg >= step and seg > 0:
            t = (step - acc) / seg
            a = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            out.append(a)
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
            acc = 0.0
        acc += seg
    if math.hypot(out[-1][0] - pts[-1][0], out[-1][1] - pts[-1][1]) > step * 0.3:
        out.append(pts[-1])
    return out


def _extend(line, poly, boundary, width):
    """Mittellinie an beiden Enden bis kurz vor den Rand verlängern (die Mittellinie endet
    sonst eine halbe Strichbreite vor dem Strichende – dort bliebe eine Lücke)."""
    pts = list(line)
    for end in (0, -1):
        p = pts[end]
        q = pts[1] if end == 0 else pts[-2]
        dx, dy = p[0] - q[0], p[1] - q[1]
        n = math.hypot(dx, dy)
        if n < 1e-9:
            continue
        hit = _hit(boundary, p, (dx / n, dy / n), width * 1.5 + 1.0)
        if hit is None:
            continue
        dist = math.hypot(hit[0] - p[0], hit[1] - p[1]) - 0.15
        if dist > 0.1:
            tip = (p[0] + dx / n * dist, p[1] + dy / n * dist)
            if end == 0:
                pts.insert(0, tip)
            else:
                pts.append(tip)
    return pts


def _columns(poly, spacing, width):
    """Satinsäulen eines Strichs: Listen von Stichpaaren (A, B) entlang der Mittellinien."""
    boundary = poly.boundary
    maxw = min(MAX_SATIN + 1.0, max(width * 2.2, 1.5))
    cols = []
    for line in centerlines(poly, step=max(0.2, min(0.4, width / 3)), prune=1.3, rounds=1):
        if len(line) < 2:
            continue
        samples = _resample(_extend(line, poly, boundary, width), spacing)
        cur = []
        for i, c in enumerate(samples):
            a = samples[max(0, i - 2)]
            b = samples[min(len(samples) - 1, i + 2)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            n = math.hypot(tx, ty)
            if n < 1e-9:
                continue
            nx, ny = -ty / n, tx / n
            pa = _hit(boundary, c, (nx, ny), maxw)
            pb = _hit(boundary, c, (-nx, -ny), maxw)
            ok = pa is not None and pb is not None and \
                math.hypot(pa[0] - pb[0], pa[1] - pb[1]) <= maxw
            if ok:
                cur.append((pa, pb))
                last = (math.hypot(pa[0] - c[0], pa[1] - c[1]), math.hypot(pb[0] - c[0], pb[1] - c[1]))
            elif cur:
                # Knotenpunkt (z. B. Querbalken trifft Stamm): mit der bisherigen Breite
                # weiterlaufen statt abzubrechen – die Säulen überlappen sich dort
                ha = min(last[0], pa and math.hypot(pa[0] - c[0], pa[1] - c[1]) or last[0])
                hb = min(last[1], pb and math.hypot(pb[0] - c[0], pb[1] - c[1]) or last[1])
                A = (c[0] + nx * ha, c[1] + ny * ha)
                B = (c[0] - nx * hb, c[1] - ny * hb)
                if poly.buffer(0.2).contains(LineString([A, B])):
                    cur.append((A, B))
                else:
                    if len(cur) >= 2:
                        cols.append(cur)
                    cur = []
        if len(cur) >= 2:
            cols.append(cur)
    return cols


def _column_stitches(pairs, fill, width):
    """Unterlage hin, Satin zurück – endet wieder am Anfang der Säule."""
    pull = fill.get("pull", 0.2)
    top = []
    for a, b in pairs:
        w = math.hypot(b[0] - a[0], b[1] - a[1])
        if w < 1e-6:
            continue
        ux, uy = (b[0] - a[0]) / w, (b[1] - a[1]) / w
        e = pull / 2 if w + pull >= 0.6 else (0.6 - w) / 2      # mindestens 0,6 mm breit
        top.append(((a[0] - ux * e, a[1] - uy * e), (b[0] + ux * e, b[1] + uy * e)))
    if len(top) < 2:
        return []
    top = satin.short_stitches(top, 0.15, 0.25)
    pts = []
    back = True                               # Deckstich zurück zum Säulenanfang
    if fill.get("underlay", True):
        mid = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in pairs]
        pts += engine.resample(mid, 2.0)
        if width > 3.0:                       # breite Säule: Zickzack-Unterlage dazu
            step = max(1, int(round(2.0 / max(0.2, fill.get("density", 0.4)))))
            zz = []
            for k, (a, b) in enumerate(pairs[::-1][::step]):
                ins = 0.35 / max(math.hypot(b[0] - a[0], b[1] - a[1]), 1e-6)
                a2 = (a[0] + (b[0] - a[0]) * ins, a[1] + (b[1] - a[1]) * ins)
                b2 = (b[0] + (a[0] - b[0]) * ins, b[1] + (a[1] - b[1]) * ins)
                zz.append(a2 if k % 2 == 0 else b2)
            pts += zz
            back = False                      # Zickzack lief schon zurück: Deckstich wieder vor
    for k, (a, b) in enumerate(reversed(top) if back else top):
        pts.extend((a, b) if k % 2 == 0 else (b, a))
    return pts


def lettering_stitches(geom, fill, cap=None):
    """Stiche für einen Schriftzug aus einer Computerschrift: schmale Striche als Satin, breite
    Teile und Knotenpunkte als Tatami. Liefert eine Stichliste (wie fill_with_underlay)."""
    spacing = max(0.25, fill.get("density", 0.4))
    polys = sorted((p for p in polygons_of(geom) if p.area > 0.05), key=lambda p: p.bounds[0])
    out = []
    tat = dict(fill, type="tatami")
    for poly in polys:
        width = 2 * poly.area / max(poly.length, 1e-6)
        if width > MAX_SATIN * 0.9 or (cap and width > cap * 0.45):
            _append(out, engine.fill_with_underlay(poly, tat))
            continue
        cols = _columns(poly, spacing, width)
        inner = poly.buffer(0.1)
        covered = unary_union([Polygon([a, b, d, c]).buffer(0.01)
                               for col in cols for (a, b), (c, d) in zip(col, col[1:])
                               if Polygon([a, b, d, c]).is_valid]) if cols else None
        # Säulen in sinnvoller Reihenfolge (nächster Anfang/Ende zuerst, auch rückwärts)
        pos = (out[-1][0], out[-1][1]) if out else None
        left = list(cols)
        while left:
            if pos is None:
                k, rev = 0, False
            else:
                k, rev = min(((i, r) for i in range(len(left)) for r in (False, True)),
                             key=lambda ir: engine.dist(pos, _mid(left[ir[0]][-1 if ir[1] else 0])))
            col = left.pop(k)
            if rev:
                col = col[::-1]
            pts = _column_stitches(col, fill, width)
            if pts:
                # Weg innerhalb des Buchstabens: sticken statt springen (kein Fadenschnitt)
                seg = LineString([out[-1][:2], pts[0]]) if out else None
                inside = seg is not None and seg.length <= 2.5 and inner.contains(seg)
                engine.connect(out, pts, 1e9 if inside else engine.DIRECT_TRAVEL)
                pos = (out[-1][0], out[-1][1])
        # Rest (Knotenpunkte, zu breite Stellen) füllen
        rest = poly if covered is None else poly.difference(covered.buffer(0.15))
        for piece in polygons_of(rest):
            if piece.area >= 1.2 and 2 * piece.area / max(piece.length, 1e-6) > 0.5:
                _append(out, engine.fill_with_underlay(piece, dict(tat, underlay=False)))
    return out


def _append(out, sts):
    """Füllstiche anhängen – Lauf für Lauf, damit interne Sprünge Sprünge bleiben."""
    run = []
    for x, y, f in sts or []:
        if f == engine.STITCH:
            run.append((x, y))
        elif run:
            engine.connect(out, run)
            run = []
    if run:
        engine.connect(out, run)


def _mid(pair):
    a, b = pair
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
