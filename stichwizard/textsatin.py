"""Schrift-Satin für Computerschriften (wie »TrueType-Lettering« in Profi-Programmen).

Schmale Striche eines Buchstabens werden als Satinsäule gestickt, die genau der Buchstabenform
folgt: entlang der Mittellinie wird alle paar Zehntelmillimeter quer zum Strich bis an den Rand
gemessen – so dreht sich der Satin mit jeder Kurve, wird an dünnen Stellen schmaler und läuft an
Strichenden spitz aus. Was übrig bleibt (Knotenpunkte, breite Bäuche), wird als Tatami gefüllt.
"""
import math

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

from . import embfont, engine, satin
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


def lettering_stitches(geom, fill, cap=None):
    """Stiche für einen Schriftzug aus einer Computerschrift: schmale Striche als Satin, breite
    Teile und Knotenpunkte als Tatami. Liefert eine Stichliste (wie fill_with_underlay)."""
    spacing = max(0.25, fill.get("density", 0.4))
    polys = sorted((p for p in polygons_of(geom) if p.area > 0.05), key=lambda p: p.bounds[0])
    out = []
    tat = dict(fill, type="tatami")
    for pi, poly in enumerate(polys):
        width = 2 * poly.area / max(poly.length, 1e-6)
        if width > MAX_SATIN * 0.9 or (cap and width > cap * 0.45):
            _append(out, engine.fill_with_underlay(poly, tat))
            continue
        cols = _columns(poly, spacing, width)
        inner = poly.buffer(0.1)
        quads = [[Polygon([a, b, d, c]).buffer(0.01) for (a, b), (c, d) in zip(col, col[1:])
                  if Polygon([a, b, d, c]).is_valid] for col in cols]
        covered = unary_union([q for qs in quads for q in qs]) if cols else None
        rest = poly if covered is None else poly.difference(covered.buffer(0.15))
        pieces = []
        for piece in polygons_of(rest):
            if piece.area >= 1.2 and 2 * piece.area / max(piece.length, 1e-6) > 0.5:
                runs = _runs_of(engine.fill_with_underlay(piece, dict(tat, underlay=False)))
                if runs:
                    pieces.append((piece, runs))
        pos = (out[-1][0], out[-1][1]) if out else None
        nxt = polys[pi + 1] if pi + 1 < len(polys) else None
        target = nearest_points(poly, nxt)[1].coords[0] if nxt is not None else None
        refill = (lambda pc, a, b: _runs_of(engine.fill_with_underlay(
            pc, dict(tat, underlay=False, start=a, end=b))))
        seq = _letter_route(cols, quads, pieces, pos, target, fill, width, inner, refill)
        for pts in seq:
            if len(pts) < 2:
                continue
            # kurzer Weg innerhalb des Buchstabens: sticken statt springen (kein Fadenschnitt)
            seg = LineString([out[-1][:2], pts[0]]) if out else None
            inside = seg is not None and seg.length <= 2.5 and inner.contains(seg)
            engine.connect(out, pts, 1e9 if inside else engine.DIRECT_TRAVEL)
    return out


def _column_parts(pairs, fill, width):
    """Säule in zwei Hälften: (hin, zurück). »hin« läuft als Unterlage vom Säulenanfang zum
    Ende (der Satin deckt sie später zu), »zurück« ist der Satin zum Anfang. Dazwischen darf
    die Nadel andere Säulen sticken – wie beim Auto-Satin in Profi-Programmen: in jeden
    Seitenarm hinein unter der Unterlage, zurück mit dem Satin, ohne Sprung."""
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
        return None
    top = satin.short_stitches(top, 0.15, 0.25)
    mid = [_mid(p) for p in pairs]
    down = engine.resample(mid, 2.0)
    if fill.get("underlay", True) and width > 3.0:     # breite Säule: Zickzack-Unterlage dazu
        step = max(1, int(round(2.0 / max(0.2, fill.get("density", 0.4)))))
        zz = []
        for k, (a, b) in enumerate(pairs[::-1][::step]):
            ins = 0.35 / max(math.hypot(b[0] - a[0], b[1] - a[1]), 1e-6)
            a2 = (a[0] + (b[0] - a[0]) * ins, a[1] + (b[1] - a[1]) * ins)
            b2 = (b[0] + (a[0] - b[0]) * ins, b[1] + (a[1] - b[1]) * ins)
            zz.append(a2 if k % 2 == 0 else b2)
        down = down + zz + engine.resample(mid, 2.0)[1:]
    up = []
    for k, (a, b) in enumerate(reversed(top)):
        up.extend((a, b) if k % 2 == 0 else (b, a))
    return down, up


JUMP = 40.0          # Bewertung eines Sprungs (mm Umweg)


class _Walk:
    """Stichfolge eines Buchstabens beim Planen: wo die Nadel steht, was noch kommt (darunter
    dürfen Verbindungswege verschwinden) und wie oft gesprungen wurde."""

    def __init__(self, parts, feet, pieces, pos, inner, atomic=frozenset()):
        self.parts, self.feet, self.pieces, self.inner = parts, feet, pieces, inner
        self.atomic = atomic                 # Einheiten ohne Hin/Zurück (ganz auf einmal)
        self.untouched = set(range(len(parts)))
        self.opened = []                     # Säulen mit Unterlage, aber noch ohne Satin
        self.done = set()
        self.left = set(range(len(pieces)))
        self.runs, self.cur, self.here = [], None, pos
        self.jumps, self.travel = 0, 0.0
        self._hide = None
        self._core = None

    def hide(self):
        """Bereich, der später noch bestickt wird (Wege darin bleiben unsichtbar)."""
        if self._hide is None:
            g = [self.feet[k] for k in self.untouched] + \
                [self.feet[k] for k, _ in self.opened] + [self.pieces[j][0] for j in self.left]
            # kleine Lücken zwischen Säulen (< 0,7 mm) überbrücken, aber im Buchstaben bleiben
            self._hide = unary_union(g).buffer(0.35).buffer(-0.35).intersection(self.inner) \
                .buffer(-0.15) if g else None
        return self._hide

    def path_to(self, start, limit=25.0):
        """Verdeckter Weg von der Nadel nach `start` (oder None = Sprung)."""
        from .optimize import _route
        if self.here is None:
            return None
        d = engine.dist(self.here, start)
        if d <= engine.DIRECT_TRAVEL and (not self.inner.contains(Point(self.here)) or
                                          self.inner.covers(LineString([self.here, start]))):
            return [self.here, start]
        h = self.hide()
        if d > limit or h is None or h.is_empty or not self.inner.contains(Point(self.here)):
            return None                        # Nadel außerhalb (voriger Buchstabe): springen
        # Anfang und Ende dürfen ein Stück (bis 1,2 mm) über fertigen Satin desselben
        # Buchstabens laufen – der Satin endet am Rand, der offene Bereich liegt daneben
        if self._core is None:
            self._core = self.inner.buffer(-0.25)
        ends = unary_union([Point(self.here).buffer(1.2, quad_segs=4),
                            Point(start).buffer(1.2, quad_segs=4)]).intersection(self._core)
        return _route(self.here, start, h.union(ends))

    def emit(self, pts, path):
        from .optimize import _travel_points
        if self.cur is not None and path is not None:
            if engine.dist(path[0], path[-1]) > 1e-6:
                self.cur.extend(_travel_points(path)[:-1])
                self.travel += sum(engine.dist(p, q) for p, q in zip(path, path[1:]))
            self.cur.extend(pts)
        elif self.cur is None and path is not None and self.here is not None:
            # erster Lauf, verdeckt von der Nadel aus erreicht: beginnt an der Nadel
            self.cur = [self.here] + (_travel_points(path)[:-1] if engine.dist(
                path[0], path[-1]) > 1e-6 else []) + list(pts)
        else:
            if self.cur is not None:
                self.runs.append(self.cur)
                self.jumps += 1
            self.cur = list(pts)
        self.here = self.cur[-1]
        self._hide = None

    def down(self, k, rev, path):
        self.untouched.discard(k)
        if k in self.atomic:
            self.done.add(k)
        else:
            self.opened.append((k, rev))
        self.emit(self.parts[k][rev][0], path)

    def up(self, k, rev, path):
        if k in self.atomic:
            return
        self.opened.remove((k, rev))
        self.done.add(k)
        self.emit(self.parts[k][rev][1], path)

    def piece(self, j, path, runs=None):
        self.left.discard(j)
        runs = runs or self.pieces[j][1]
        self.emit(runs[0], path)
        for r in runs[1:]:                     # Fläche zerfällt in mehrere Läufe
            self.emit(r, None)

    def result(self, target):
        runs = self.runs + ([self.cur] if self.cur else [])
        end = 0.0 if target is None or not runs else 0.05 * engine.dist(runs[-1][-1], target)
        return (self.jumps, self.travel + end), runs


def _letter_route(cols, quads, pieces, pos, target, fill, width, inner, refill=None, trials=6):
    """Säulen und Restflächen eines Buchstabens ordnen: möglichst jede Verbindung als Weg unter
    noch nicht gesticktem Satin (bzw. noch offenen Flächen) statt als Sprung. Probiert mehrere
    Varianten und vergleicht mit der einfachen Reihenfolge (ganze Säulen nacheinander)."""
    parts = []
    feet = []
    for col, qs in zip(cols, quads):
        fw, bw = _column_parts(col, fill, width), _column_parts(col[::-1], fill, width)
        if fw is None or not qs:
            continue
        parts.append((fw, bw))
        feet.append(unary_union(qs))
    if not parts and not pieces:
        return []
    best = plan_parts(parts, feet, pieces, pos, target, inner, refill, trials=trials)
    # Vergleich: ganze Säulen nacheinander (bisheriges Verfahren über embfont-Routing)
    try:
        units = [{"fwd": [fw[0] + fw[1][1:]], "rev": [bw[0] + bw[1][1:]], "foot": f,
                  "satin": True} for (fw, bw), f in zip(parts, feet)]
        units += [{"fwd": runs, "rev": None, "foot": pc, "satin": False} for pc, runs in pieces]
        seq, _ = embfont._best_route(units, pos, target, split=False)

        def jumps(seq):
            return sum(1 for a, b in zip(seq, seq[1:])
                       if not (engine.dist(a[-1], b[0]) <= 2.5 and
                               inner.contains(LineString([a[-1], b[0]]))))
        if jumps(seq) < jumps(best[1]):
            return seq
    except Exception:
        pass
    return best[1]


def plan_parts(parts, feet, pieces, pos, target, inner, refill=None, atomic=frozenset(),
               trials=6):
    """Beste Folge für Einheiten mit Hin- und Rückweg (parts[k][rev] = (hin, zurück)) und
    Restflächen. Liefert ((sprünge, weglänge), läufe)."""
    import random
    # Restflächen (Knotenpunkte) kommen nach den Säulen, die sie berühren – wie bisher obenauf
    after = [{k for k, f in enumerate(feet) if f.intersects(pc.buffer(0.2))} for pc, _ in pieces]
    # Nachbarn: Säulen, die sich berühren oder über eine Restfläche verbunden sind
    n = len(parts)
    nb = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if feet[i].distance(feet[j]) < 0.7:
                nb[i].add(j)
                nb[j].add(i)
    for grp in after:
        for i in grp:
            nb[i] |= grp - {i}
    candidates = []
    for root in _roots(parts, pos, target):
        if candidates and min(candidates)[0][0] == 0:
            break                              # ohne Sprung – besser geht es nicht
        try:
            candidates.append(_dfs_plan(parts, feet, pieces, after, nb, pos, target, inner, root,
                                        refill, atomic))
        except Exception:
            pass
    rng = random.Random(5)
    for t in range(trials + 1 if n > 1 else 1):
        if candidates and min(candidates)[0][0] == 0:
            break
        candidates.append(_greedy_plan(parts, feet, pieces, after, pos, target, inner,
                                       rng if t else None, atomic))
    best = min(candidates, key=lambda c: c[0])
    return best


def _roots(parts, pos, target):
    """Anfänge zum Ausprobieren: nächstes Säulenende zur Nadel (ohne Nadel: links, bzw. weit
    weg vom nächsten Buchstaben) – die besten paar."""
    ends = [(k, rev, parts[k][rev][0][0]) for k in range(len(parts)) for rev in (0, 1)]
    if pos is not None:
        key = lambda e: engine.dist(pos, e[2])
    elif target is not None:
        key = lambda e: -engine.dist(e[2], target)
    else:
        key = lambda e: e[2][0]
    return [(k, rev) for k, rev, _ in sorted(ends, key=key)[:4]]


def _dfs_plan(parts, feet, pieces, after, nb, pos, target, inner, root, refill=None,
              atomic=frozenset()):
    """Wie Auto-Satin: in jede Säule mit der Unterlage hinein, von ihrem Ende aus erst die
    angrenzenden Säulen (Weg unter der eigenen, noch offenen Säule), dann mit dem Satin zurück
    zum Anfang. So hängt ein zusammenhängender Buchstabe ohne Sprung zusammen.
    Restflächen (breite Knotenpunkte) werden unterwegs gefüllt, sobald die Nadel daran
    vorbeikommt – beginnend und endend an dieser Stelle (refill), der Satin der offenen Säule
    deckt den Weg dorthin."""
    w = _Walk(parts, feet, pieces, pos, inner, atomic)
    seen = set()

    def do_piece(j):
        pc = w.pieces[j][0]
        runs = None
        if refill is not None and w.here is not None:
            entry = nearest_points(pc, Point(w.here))[0].coords[0]
            try:
                runs = refill(pc, entry, entry)
            except Exception:
                runs = None
        runs = runs or w.pieces[j][1]
        w.piece(j, w.path_to(runs[0][0]), runs)

    def visit(k, rev):
        seen.add(k)
        start = parts[k][rev][0][0]
        w.down(k, rev, w.path_to(start))
        while True:
            # nächste angrenzende Säule (vom aktuellen Nadelpunkt aus) – hinein an dem Ende,
            # das an diese Säule grenzt: der Satin kommt dorthin zurück, und von da geht es
            # unter dieser (noch offenen) Säule weiter
            cand = []
            for m in nb[k]:
                if m in seen:
                    continue
                r = min((0, 1), key=lambda r: (round(feet[k].distance(
                    Point(parts[m][r][0][0])), 1), engine.dist(w.here, parts[m][r][0][0])))
                cand.append((engine.dist(w.here, parts[m][r][0][0]), m, r))
            for j in w.left:
                if k in after[j]:
                    cand.append((w.pieces[j][0].distance(Point(w.here)), -1, j))
            if not cand:
                break
            _, m, r = min(cand)
            if m < 0:
                do_piece(r)
            else:
                visit(m, r)
        up = parts[k][rev][1]
        w.up(k, rev, w.path_to(up[0]))

    visit(*root)
    while len(seen) < len(parts):              # weitere, nicht verbundene Teile
        cand = [(engine.dist(w.here, parts[m][r][0][0]), m, r)
                for m in range(len(parts)) if m not in seen for r in (0, 1)]
        _, m, r = min(cand)
        visit(m, r)
    while w.left:
        j = min(w.left, key=lambda j: w.pieces[j][0].distance(Point(w.here)) if w.here else j)
        do_piece(j)
    return w.result(target)


def _greedy_plan(parts, feet, pieces, after, pos, target, inner, rng, atomic=frozenset()):
    """Gierig: immer der günstigste nächste Schritt (Unterlage hinein, Satin zurück, Restfläche)."""
    w = _Walk(parts, feet, pieces, pos, inner, atomic)
    while w.untouched or w.opened or w.left:
        cands = []
        for k in w.untouched:
            for rev in (0, 1):
                cands.append((0.0, ("down", k, rev), parts[k][rev][0][0]))
        for i, (k, rev) in enumerate(w.opened):
            cands.append((3.0 if i == len(w.opened) - 1 else 6.0, ("up", k, rev),
                          parts[k][rev][1][0]))
        for j in w.left:
            if after[j] <= w.done:
                cands.append((4.0, ("piece", j, 0), pieces[j][1][0][0]))
        scored = []
        for bias, move, start in cands:
            if w.here is None:
                x = start[0] if target is None else -engine.dist(start, target)
                scored.append([bias + 0.01 * x, move, start, None, True])
                continue
            d = engine.dist(w.here, start)
            scored.append([bias + (d if d <= engine.DIRECT_TRAVEL else JUMP + d), move, start,
                           [w.here, start] if d <= engine.DIRECT_TRAVEL else None,
                           d <= engine.DIRECT_TRAVEL])
        if rng is not None:
            for c in scored:
                c[0] *= 1 + rng.random() * 0.4
        best = min(scored, key=lambda c: c[0])
        if w.here is not None:
            # verdeckte Wege für die nächstgelegenen Kandidaten suchen
            for c in sorted(scored, key=lambda c: engine.dist(w.here, c[2]))[:6]:
                if c[4]:
                    continue
                path = w.path_to(c[2])
                if path is None:
                    continue
                ln = sum(engine.dist(p, q) for p, q in zip(path, path[1:]))
                cost = c[0] - JUMP - engine.dist(w.here, c[2]) + ln
                if cost < best[0]:
                    best = [cost, c[1], c[2], path, True]
        _, (kind, k, rev), _, path, _ = best
        getattr(w, kind)(*((k, rev, path) if kind != "piece" else (k, path)))
    return w.result(target)


def _runs_of(sts):
    """Stichliste -> Läufe (Punktlisten zwischen Sprüngen)."""
    runs, run = [], []
    for x, y, f in sts or []:
        if f == engine.STITCH:
            run.append((x, y))
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    return [r for r in runs if len(r) >= 2]


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
