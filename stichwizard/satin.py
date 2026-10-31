"""Säulen-Satin: Satinstich zwischen zwei Führungslinien (Schienen) mit Richtungsstegen.

Wie in Profi-Programmen bzw. Ink/Stitch: Die Stiche laufen quer von Schiene A nach Schiene B.
Stege (kurze Querlinien) legen fest, welche Stellen der beiden Schienen zusammengehören –
so dreht sich die Stichrichtung in Kurven sauber mit.
"""
import math
import random

from shapely.geometry import LineString, Point, Polygon

from .engine import resample


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _align_rails(a, b):
    """Schiene B in dieselbe Richtung wie A drehen."""
    if _d(a[0], b[0]) + _d(a[-1], b[-1]) > _d(a[0], b[-1]) + _d(a[-1], b[0]):
        b = b[::-1]
    return a, b


def _sections(ra, rb, rungs):
    """Positionen (Länge entlang A, Länge entlang B) aller Stege, sortiert."""
    la, lb = LineString(ra), LineString(rb)
    cuts = [(0.0, 0.0), (la.length, lb.length)]
    for p, q in rungs:
        rung = LineString([p, q])
        # Schnittpunkt mit der Schiene, sonst nächster Punkt
        ia = rung.intersection(la)
        ib = rung.intersection(lb)
        pa = ia if not ia.is_empty and ia.geom_type == "Point" else None
        pb = ib if not ib.is_empty and ib.geom_type == "Point" else None
        if pa is None:
            pa = Point(p) if Point(p).distance(la) < Point(q).distance(la) else Point(q)
        if pb is None:
            pb = Point(q) if Point(q).distance(lb) < Point(p).distance(lb) else Point(p)
        cuts.append((la.project(pa), lb.project(pb)))
    cuts.sort()
    out = []
    for c in cuts:            # nur monoton steigende Paare behalten
        if not out or (c[0] > out[-1][0] + 1e-6 and c[1] > out[-1][1] + 1e-6):
            out.append(c)
    if out[-1] != (la.length, lb.length):
        out[-1] = (la.length, lb.length)
    return la, lb, out


def pairs(ra, rb, rungs, spacing, inset=0.0, pull=0.0, pull_pct=0.0, align=True):
    """Stichpaare (Punkt auf A, Punkt auf B) im Abstand `spacing` entlang der längeren Schiene.
    pull_pct: zusätzlicher Zugausgleich in Prozent der Säulenbreite (wie Ink/Stitch).
    align=False: Schienen so nehmen, wie sie kommen (Richtung wurde schon festgelegt)."""
    if align:
        ra, rb = _align_rails(list(ra), list(rb))
    la, lb, cuts = _sections(ra, rb, rungs or [])
    out = []
    for (a0, b0), (a1, b1) in zip(cuts, cuts[1:]):
        n = max(1, int(math.ceil(max(a1 - a0, b1 - b0) / max(spacing, 0.05))))
        for k in range(n + (1 if (a1, b1) == cuts[-1] else 0)):
            t = k / n
            pa = la.interpolate(a0 + (a1 - a0) * t)
            pb = lb.interpolate(b0 + (b1 - b0) * t)
            A, B = (pa.x, pa.y), (pb.x, pb.y)
            w = _d(A, B)
            if w > 1e-6 and (inset or pull or pull_pct):
                ux, uy = (B[0] - A[0]) / w, (B[1] - A[1]) / w
                e = (pull + w * pull_pct / 100.0) / 2 - inset
                if w + 2 * e < 0.2:
                    e = (0.2 - w) / 2
                A = (A[0] - ux * e, A[1] - uy * e)
                B = (B[0] + ux * e, B[1] + uy * e)
            out.append((A, B))
    return out


def orient_column(ra, rb, start=None, end=None):
    """Säule für Start-/Endpunkt ausrichten (wie die Ink/Stitch-Befehle).
    Liefert (schiene_a, schiene_b, zurück): Die Säule beginnt an dem Ende, das dem Startpunkt
    näher liegt, und endet am anderen. Liegen Start und Ende am selben Ende, ist zurück=True:
    die Unterlage läuft hin, der Satinstich zurück."""
    ra, rb = _align_rails(list(ra), list(rb))
    if start is None and end is None:
        return ra, rb, False
    head = ((ra[0][0] + rb[0][0]) / 2, (ra[0][1] + rb[0][1]) / 2)
    tail = ((ra[-1][0] + rb[-1][0]) / 2, (ra[-1][1] + rb[-1][1]) / 2)
    back = False
    if start is not None:
        rev = _d(start, tail) < _d(start, head)
        if end is not None:
            first = tail if rev else head
            other = head if rev else tail
            back = _d(end, first) < _d(end, other)
    else:
        rev = _d(end, head) < _d(end, tail)
    if rev:
        ra, rb = ra[::-1], rb[::-1]
    return ra, rb, back


def short_stitches(top, inset=0.15, min_dist=0.25):
    """Kurze Stiche in engen Kurven (wie Ink/Stitch »short stitch inset«): Liegen die Einstiche
    an einer Schiene enger als `min_dist`, wird dort jeder zweite Stich um `inset` (Anteil der
    Säulenbreite) eingerückt – so häuft sich an der Innenseite kein Garn."""
    if inset <= 0 or min_dist <= 0 or len(top) < 3:
        return top
    out = [list(t) for t in top]
    for side in (0, 1):
        last = False
        for k in range(1, len(top) - 1):
            if not last and _d(top[k][side], top[k - 1][side]) < min_dist:
                a, b = top[k]
                p, q = (a, b) if side == 0 else (b, a)
                f = min(inset, 0.45)
                out[k][side] = (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)
                last = True
            else:
                last = False
    return [tuple(t) for t in out]


def end_cap(a, b, inward, depth=1.2, step=0.3):
    """Endkappe: kurze, dichte Stiche entlang der Endkante a–b, jeweils ein Stück (`depth`)
    in die Säule hinein (Richtung `inward`, ein Paar am anderen Ende)."""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ix = (inward[0][0] + inward[1][0]) / 2 - mx
    iy = (inward[0][1] + inward[1][1]) / 2 - my
    L = math.hypot(ix, iy) or 1e-9
    ix, iy = ix / L * depth, iy / L * depth
    w = _d(a, b)
    n = max(2, int(w / step))
    out = []
    for k in range(n + 1):
        t = k / n
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        out.extend([p, (p[0] + ix, p[1] + iy)] if k % 2 == 0 else [(p[0] + ix, p[1] + iy), p])
    return out


def _jitter_pairs(top, wj, sj, rng):
    """Satinpaare zufällig verbreitern/verschmälern (wj) und entlang der Säule verschieben (sj)."""
    out = []
    n = len(top)
    for k, (a, b) in enumerate(top):
        if sj > 0 and 0 < k < n - 1:
            t = rng.uniform(-sj, sj) / 2
            o = top[k + 1] if t > 0 else top[k - 1]
            t = abs(t)
            a = (a[0] + (o[0][0] - a[0]) * t, a[1] + (o[0][1] - a[1]) * t)
            b = (b[0] + (o[1][0] - b[0]) * t, b[1] + (o[1][1] - b[1]) * t)
        if wj > 0:
            ea, eb = rng.uniform(-wj, wj) / 2, rng.uniform(-wj, wj) / 2
            dx, dy = b[0] - a[0], b[1] - a[1]
            a = (a[0] - dx * ea, a[1] - dy * ea)
            b = (b[0] + dx * eb, b[1] + dy * eb)
        out.append((a, b))
    return out


SATIN_UNDERLAYS = [("Automatisch (nach Breite)", "auto"), ("Keine", "none"),
                   ("Mittellinie", "center"), ("Kontur", "contour"), ("Zickzack", "zigzag"),
                   ("Mittellinie + Zickzack", "center_zigzag"), ("Kontur + Zickzack", "contour_zigzag"),
                   ("Alle drei", "all")]


def underlay_flags(mode, width, kind="satin"):
    """(mittellinie, kontur, zickzack) für eine Unterlagen-Einstellung."""
    if mode == "auto":
        return True, width > 5, width > 2.5 and kind == "satin"
    if mode == "none":
        return False, False, False
    return ("center" in mode or mode == "all", "contour" in mode or mode == "all",
            "zigzag" in mode or mode == "all")


def satin_stitches(ra, rb, rungs=None, spacing=0.4, pull=0.2, center_walk=False,
                   contour=False, zigzag_underlay=True, underlay_inset=0.3,
                   underlay_spacing=3.0, max_len=8.0, min_len=0.3, kind="satin",
                   short_inset=0.0, short_dist=0.25, random_split=False, seed=1, back=False,
                   width_jitter=0.0, spacing_jitter=0.0, caps=False, pull_pct=0.0, align=True):
    """Komplette Satinsäule: Unterlage(n) und Deckstich von Anfang bis Ende.
    Endet am Ende der Säule (wichtig, damit Schriften sauber weiterlaufen).
    kind: "satin" (Standard), "zigzag" (schräge Zickzackstiche) oder "estitch"
    (E-/Deckenstich: Grundlinie an Schiene A mit Zacken zu Schiene B, z. B. für Applikationen).
    short_inset/short_dist: kurze Stiche in engen Kurven (siehe short_stitches).
    max_len: breitere Stiche werden geteilt – random_split versetzt die Teilungspunkte zufällig
    (seed), damit keine sichtbare Linie entsteht.
    back: Unterlage läuft zum Ende der Säule, der Deckstich zurück zum Anfang.
    width_jitter / spacing_jitter: Breite bzw. Stichabstand zufällig variieren (Anteil, wie
    Ink/Stitch »random width« und »random zigzag spacing«) – wirkt natürlicher, z. B. bei Fell."""
    if align:
        ra, rb = _align_rails(list(ra), list(rb))
    pts = []
    walk = None
    if center_walk or contour or zigzag_underlay or back:
        under = pairs(ra, rb, rungs, 1.5, inset=underlay_inset, align=align)
    if center_walk or back:
        mid = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in under]
        walk = resample(mid, 2.0)
        if not back:
            pts += walk + walk[::-1][1:]
    if contour:
        ca = resample([a for a, _ in under], 2.0)
        cb = resample([b for _, b in under], 2.0)
        pts += ca + cb[::-1]
    if zigzag_underlay:
        z = pairs(ra, rb, rungs, underlay_spacing / 2, inset=underlay_inset, align=align)
        fwd = [p for k, (a, b) in enumerate(z) for p in ((a,) if k % 2 == 0 else (b,))]
        bwd = [p for k, (a, b) in enumerate(z[::-1]) for p in ((a,) if k % 2 == 0 else (b,))]
        pts += fwd + bwd
    if back:                                 # zuletzt die Mittellinie hin – Deckstich zurück
        pts += walk
    top = short_stitches(pairs(ra, rb, rungs, spacing, pull=pull, pull_pct=pull_pct, align=align),
                         short_inset, short_dist)
    rng = random.Random(seed)
    if width_jitter > 0 or spacing_jitter > 0:
        top = _jitter_pairs(top, width_jitter, spacing_jitter, random.Random(seed + 7))
    if back:
        top = top[::-1]
    if kind == "zigzag":
        pts += [a if k % 2 == 0 else b for k, (a, b) in enumerate(top)]
        top = []
    elif kind == "estitch":
        for a, b in top:
            pts += [a, b, a]
        top = []
    zig = []
    for k, (a, b) in enumerate(top):
        seq = (a, b) if k % 2 == 0 else (b, a)
        w = _d(a, b)
        if w > max_len:                      # sehr breite Satinstiche aufteilen
            n = int(math.ceil(w / max_len))
            # versetzte Teilungspunkte dürfen kein Stück länger als max_len machen
            need = 1.3 if random_split else 1.2
            while n * max_len < w * need:
                n += 1
            jit = min(0.35, (n * max_len / w - 1) / 2)
            s, e = seq
            zig.append(s)
            for i in range(1, n):
                if random_split:
                    f = (i + rng.uniform(-jit, jit)) / n
                else:
                    off = 0.5 if (k + i) % 2 else 0.0
                    f = (i - off * 0.4) / n
                zig.append((s[0] + (e[0] - s[0]) * f, s[1] + (e[1] - s[1]) * f))
            zig.append(e)
        else:
            zig.extend(seq)
    if caps and zig:
        # 3D-Puff: Endkappen – dichte Stiche quer über beide Enden schneiden den Schaumstoff
        # sauber ab, damit er nicht seitlich herausschaut
        head, tail = (top[0], top[-1]) if top else ((zig[0], zig[1]), (zig[-2], zig[-1]))
        zig = end_cap(*head, inward=tail) + zig + end_cap(*tail, inward=head)
    pts += zig
    out = []
    lim = max(max_len, 1.0) + 0.5
    for p in pts:                            # zu kurze Stiche weglassen, zu lange teilen
        if out and _d(out[-1], p) > lim:     # (z. B. Zickzack-Unterlage sehr breiter Säulen)
            q = out[-1]
            n = int(math.ceil(_d(q, p) / max(max_len, 1.0)))
            out.extend((q[0] + (p[0] - q[0]) * k / n, q[1] + (p[1] - q[1]) * k / n)
                       for k in range(1, n))
        if not out or _d(out[-1], p) >= min_len:
            out.append(p)
    return out


def outline(ra, rb):
    """Fläche der Säule (für Auswahl, Vorschau, Kollisionsprüfung)."""
    ra, rb = _align_rails(list(ra), list(rb))
    poly = Polygon(list(ra) + list(rb)[::-1])
    return poly.buffer(0) if not poly.is_valid else poly


CORNER_ANGLE = 35.0     # ° – ab diesem Knick bekommt eine Satinlinie eine Gehrungsecke


def corner_turns(pts, closed):
    """Knickwinkel (°) je Punkt eines Linienzugs (Endpunkte offener Linien: 0)."""
    n = len(pts)
    out = []
    for i in range(n):
        if not closed and (i == 0 or i == n - 1):
            out.append(0.0)
            continue
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        t1 = math.atan2(b[1] - a[1], b[0] - a[0])
        t2 = math.atan2(c[1] - b[1], c[0] - b[0])
        out.append(math.degrees(abs((t2 - t1 + math.pi) % (2 * math.pi) - math.pi)))
    return out


def corner_rails(coords, width, closed=False):
    """Zwei Schienen im Abstand width/2 links/rechts der Linie mit Gehrung an jeder Ecke und
    Stegen an den Ecken (wie »Mitre corners« in Wilcom/Hatch). Liefert (ra, rb, rungs) oder None,
    wenn die Linie keine spitze Ecke hat."""
    pts = []
    for p in coords:
        if not pts or _d(pts[-1], p) > 1e-6:
            pts.append((p[0], p[1]))
    if not closed and len(pts) > 3 and _d(pts[0], pts[-1]) < 0.05:
        closed = True                     # Schleife (Anfang = Ende) als geschlossen behandeln
    if closed and len(pts) > 2 and _d(pts[0], pts[-1]) < 0.05:
        pts = pts[:-1]
    if len(pts) < 3:
        return None
    want = pts[0]                         # gewünschter Anfang (vom Aufrufer gewählt)
    # winzige Bogenstücke (z. B. leicht abgerundete Ecken) zu einer Ecke zusammenfassen
    simple = LineString(pts + ([pts[0]] if closed else [])).simplify(min(0.15, width * 0.04))
    sp = list(simple.coords)
    if closed and len(sp) > 3:
        sp = sp[:-1]
    if len(sp) >= 3:
        pts = [(x, y) for x, y in sp]
    turns = corner_turns(pts, closed)
    if max(turns) < CORNER_ANGLE:
        return None
    if closed:
        # am gewünschten Anfang aufschneiden, aber mit Abstand zu den Ecken – Anfang und Ende
        # liegen so auf einem geraden Stück
        m = len(pts)
        segs = [LineString([pts[i], pts[(i + 1) % m]]) for i in range(m)]
        k = min(range(m), key=lambda i: segs[i].distance(Point(want)))
        L = segs[k].length
        margin = min(L / 2, 1.5 * width)
        t = min(max(segs[k].project(Point(want)), margin), L - margin)
        mid = segs[k].interpolate(t).coords[0]
        pts = [mid] + pts[k + 1:] + pts[:k + 1] + [mid]
        turns = corner_turns(pts[:-1], True) + [0.0]
        turns[0] = 0.0
    h = width / 2
    ra, rb, rungs = [], [], []
    n = len(pts)
    unit = lambda a, b: ((b[0] - a[0]) / (_d(a, b) or 1e-9), (b[1] - a[1]) / (_d(a, b) or 1e-9))
    for i, p in enumerate(pts):
        prev = pts[i - 1] if i > 0 else (pts[-2] if closed else None)
        nxt = pts[i + 1] if i < n - 1 else (pts[1] if closed else None)
        normals = []
        for a, b in ((prev, p), (p, nxt)):
            if a is None or b is None:
                continue
            u = unit(a, b)
            normals.append((-u[1], u[0]))
        nx = sum(v[0] for v in normals)
        ny = sum(v[1] for v in normals)
        L = math.hypot(nx, ny) or 1e-9
        nx, ny = nx / L, ny / L
        cos_half = max(0.55, nx * normals[0][0] + ny * normals[0][1])  # Gehrung, begrenzt
        k = h / cos_half
        A = (p[0] + nx * k, p[1] + ny * k)
        B = (p[0] - nx * k, p[1] - ny * k)
        ra.append(A)
        rb.append(B)
        if 0 < i < n - 1 and turns[i] >= CORNER_ANGLE:
            # Fächer um die Ecke: Innen bleibt der Einstich an der Gehrung, außen läuft er von
            # der Senkrechten vor der Ecke bis zur Senkrechten danach – die geraden Stücke
            # behalten senkrechte Stiche
            ui, uo = unit(prev, p), unit(p, nxt)
            ni, no = (-ui[1], ui[0]), (-uo[1], uo[0])
            left_turn = ui[0] * uo[1] - ui[1] * uo[0] > 0
            o = -1 if left_turn else 1                       # Außenseite: +1 = Schiene A
            th = math.radians(turns[i])
            d = min(h * math.tan(min(th, math.radians(120)) / 2),
                    0.45 * _d(prev, p), 0.45 * _d(p, nxt))
            inner = B if o == 1 else A
            ob = (p[0] - ui[0] * d + o * ni[0] * h, p[1] - ui[1] * d + o * ni[1] * h)
            oa = (p[0] + uo[0] * d + o * no[0] * h, p[1] + uo[1] * d + o * no[1] * h)
            ib = (inner[0] - ui[0] * 0.05, inner[1] - ui[1] * 0.05)
            ia = (inner[0] + uo[0] * 0.05, inner[1] + uo[1] * 0.05)
            for outer_pt, inner_pt in ((ob, ib), (None, None), (oa, ia)):
                if outer_pt is None:
                    rungs.append((A, B))
                else:
                    rungs.append((outer_pt, inner_pt) if o == 1 else (inner_pt, outer_pt))
    return ra, rb, rungs


def satin_corner_line(coords, width=3.0, spacing=0.4, closed=False, underlay=True,
                      pull=0.0):
    """Satinlinie mit sauberen Ecken: an spitzen Ecken laufen die Stiche als Fächer um die
    Ecke, innen werden sie verkürzt (keine Garnhäufung, kein Loch außen). None = keine Ecke."""
    rails = corner_rails(coords, width, closed)
    if rails is None:
        return None
    ra, rb, rungs = rails
    ul = underlay and width >= 1.2
    return satin_stitches(ra, rb, rungs, spacing=spacing, pull=pull, center_walk=ul,
                          zigzag_underlay=ul and width > 2.5, contour=ul and width > 5,
                          short_inset=0.3, short_dist=0.3, back=ul and not closed)
