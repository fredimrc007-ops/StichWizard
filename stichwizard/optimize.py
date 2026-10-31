"""Sprungstich-Optimierung für fertige Stichfolgen (auch importierte Maschinendateien).

Vorgehen wie in Profi-Software:
1. Jeder Farbblock wird in Stichläufe zerlegt (Stiche zwischen zwei Sprüngen).
2. Läufe werden neu sortiert, damit die Wege kurz werden. Überlappen sich zwei Läufe,
   bleibt ihre ursprüngliche Reihenfolge erhalten (Unterlage bleibt unter dem Deckstich).
   Läufe ohne innere Überkreuzungen dürfen auch rückwärts gestickt werden.
3. Verbindungen, die vollständig in Bereichen liegen, die *später* noch bestickt werden,
   werden zu Verbindungsstichen (Steppstich unter dem späteren Deckstich) – auch auf
   Umwegen um Ecken herum. Alles andere bleibt ein Sprung (bei langen Wegen mit Schnitt).
"""
import heapq
import math

import numpy as np
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from . import engine
from .engine import JUMP, STITCH, STOP, TRIM

THREAD = 0.3        # mm – halbe Breite, die ein Stich abdeckt
DIRECT = 1.0        # mm – so kurze Wege immer direkt sticken
TRAVEL_LEN = 2.5    # mm – Stichlänge der Verbindungsstiche
GRID = 0.4          # mm – Raster für die Wegsuche


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def split_runs(stitches):
    """Stichliste -> Liste von Läufen (nur Einstiche, ohne Sprung-/Schnittmarken)."""
    runs, cur, broken = [], [], True
    for x, y, f in stitches:
        if f == STITCH:
            if broken and cur:
                runs.append(cur)
                cur = []
            broken = False
            cur.append((x, y))
        else:
            broken = True
    if cur:
        runs.append(cur)
    return runs


def _footprint(run):
    if len(run) == 1:
        return Point(run[0]).buffer(THREAD)
    return LineString(run).buffer(THREAD, quad_segs=3)


def _strip_ties(run):
    """Kurze Vor-/Zurück-Vernähstiche an den Enden für die Kreuzungsprüfung weglassen."""
    a, b = 0, len(run)
    while a < min(5, b - 2) and _d(run[a], run[0]) < 1.5 and _d(run[a + 1], run[0]) < 1.5:
        a += 1
    while b > max(a + 2, len(run) - 5) and _d(run[b - 1], run[-1]) < 1.5 and \
            _d(run[b - 2], run[-1]) < 1.5:
        b -= 1
    return run[a:b]


def _reversible(run):
    core = _strip_ties(run)
    if len(core) < 3:
        return True
    return LineString(core).is_simple


class _Block:
    def __init__(self, runs):
        self.runs = runs
        self.foot = [_footprint(r) for r in runs]
        self.rev = [_reversible(r) for r in runs]
        tree = shapely.STRtree(self.foot)
        n = len(runs)
        # Vorgänger: frühere Läufe, die diesen Lauf überlappen
        self.pred = [set() for _ in range(n)]
        for j in range(n):
            for i in tree.query(self.foot[j]):
                i = int(i)
                if i < j and self.foot[i].intersection(self.foot[j]).area > 0.3:
                    self.pred[j].add(i)


def _route(a, b, cover, detour=(2.5, 6.0), within=None, prefer=None, penalty=5.0):
    """Weg von a nach b, der ganz innerhalb von `cover` liegt (oder None).
    detour: erlaubte Weglänge = gerade Strecke × detour[0] + detour[1].
    within: Suchbereich auf diese Grenzen (minx, miny, maxx, maxy) erweitern – für Umwege
    innerhalb eines ganzen Elements.
    prefer: Bereich, in dem der Weg bevorzugt laufen soll (z. B. unter einem später gestickten
    Rand); außerhalb kostet jeder Schritt `penalty`-mal so viel."""
    if cover is None or cover.is_empty:
        return None
    seg = LineString([a, b])
    if cover.covers(seg) and (prefer is None or prefer.covers(seg)):
        return [a, b]
    straight = _d(a, b)
    pad = 6 + straight * 0.5
    minx, maxx = min(a[0], b[0]) - pad, max(a[0], b[0]) + pad
    miny, maxy = min(a[1], b[1]) - pad, max(a[1], b[1]) + pad
    if within is not None:
        minx, miny = min(minx, within[0] - 1), min(miny, within[1] - 1)
        maxx, maxy = max(maxx, within[2] + 1), max(maxy, within[3] + 1)
    grid = GRID
    nx, ny = int((maxx - minx) / grid) + 1, int((maxy - miny) / grid) + 1
    while nx * ny > 250_000 and within is not None and grid < 1.6:   # großes Element: gröberes Raster
        grid *= 1.5
        nx, ny = int((maxx - minx) / grid) + 1, int((maxy - miny) / grid) + 1
    if nx * ny > 250_000:
        return None
    xs = minx + np.arange(nx) * grid
    ys = miny + np.arange(ny) * grid
    gx, gy = np.meshgrid(xs, ys)
    free = shapely.contains_xy(cover, gx, gy)
    cheap = shapely.contains_xy(prefer, gx, gy) if prefer is not None else None
    def cell(p):
        return (min(ny - 1, max(0, round((p[1] - miny) / grid))),
                min(nx - 1, max(0, round((p[0] - minx) / grid))))
    s, t = cell(a), cell(b)
    free[s] = free[t] = True
    # A*-Suche im Raster (8 Nachbarn)
    dist = {s: 0.0}
    prev = {}
    heap = [(0.0, s)]
    steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1),
             (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
    found = False
    while heap:
        _, c = heapq.heappop(heap)
        if c == t:
            found = True
            break
        dc = dist[c]
        for dy, dx, w in steps:
            n = (c[0] + dy, c[1] + dx)
            if not (0 <= n[0] < ny and 0 <= n[1] < nx) or not free[n]:
                continue
            nd = dc + (w if cheap is None or cheap[n] else w * penalty)
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                prev[n] = c
                h = math.hypot(n[0] - t[0], n[1] - t[1])
                heapq.heappush(heap, (nd + h, n))
    if not found:
        return None
    cells = [t]
    while cells[-1] != s:
        cells.append(prev[cells[-1]])
    cells.reverse()
    pts = [a] + [(minx + c[1] * grid, miny + c[0] * grid) for c in cells[1:-1]] + [b]
    # Weg straffen: Punkte überspringen, solange die Abkürzung im Bereich bleibt
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1:
            sg = LineString([pts[i], pts[j]])
            if cover.covers(sg) and (prefer is None or prefer.covers(sg) or not prefer.intersects(sg)):
                break
            j -= 1
        out.append(pts[j])
        i = j
    length = sum(_d(p, q) for p, q in zip(out, out[1:]))
    if length > straight * detour[0] + detour[1]:
        return None
    return out


def _travel_points(path):
    pts = []
    for p, q in zip(path, path[1:]):
        n = max(1, math.ceil(_d(p, q) / TRAVEL_LEN))
        for k in range(1, n + 1):
            pts.append((p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n))
    return pts


def _covered_fast(blk, rest, later, a, b):
    """Schnelltest: liegt die Strecke a–b komplett auf noch zu stickenden Läufen?"""
    n = max(2, int(_d(a, b) / 0.4) + 1)
    xs = np.linspace(a[0], b[0], n)
    ys = np.linspace(a[1], b[1], n)
    pts = shapely.points(xs, ys)
    ok = np.zeros(n, bool)
    if later is not None:
        ok |= shapely.contains_xy(later, xs, ys)
    if not ok.all():
        pi, ti = blk.tree.query(pts, predicate="intersects")
        for p_, t_ in zip(pi, ti):
            if int(t_) in rest:
                ok[p_] = True
    return bool(ok.all())


def _order_block(blk, cur, later, rng=None, travel=True):
    n = len(blk.runs)
    placed, order, remaining = set(), [], set(range(n))
    while remaining:
        avail = [j for j in remaining if blk.pred[j] <= placed]
        best = None
        for j in avail:
            ends = [(False, blk.runs[j][0])]
            if blk.rev[j]:
                ends.append((True, blk.runs[j][-1]))
            for rev, start in ends:
                d = 0.0 if cur is None else _d(cur, start)
                cost = d
                if travel and cur is not None and d > DIRECT and \
                        _covered_fast(blk, remaining, later, cur, start):
                    cost = d * 0.15        # verdeckt stickbar: fast kostenlos
                elif cur is not None and d > DIRECT:
                    cost = d + 20          # echter Sprung: teuer
                if rng is not None:
                    cost *= 1 + rng.random() * 0.35
                key = (cost, j)
                if best is None or key < best[0]:
                    best = (key, j, rev)
        _, j, rev = best
        run = blk.runs[j][::-1] if rev else blk.runs[j]
        order.append((j, run))
        placed.add(j)
        remaining.discard(j)
        cur = run[-1]
    return order


def _plan_block(blk, pos):
    """Reihenfolge mit der kürzesten Summe aller Sprünge (ganzer Weg geplant, siehe tour.py) –
    vermeidet einzelne liegengebliebene Teile, zu denen am Ende weit zurückgesprungen wird."""
    from . import tour
    runs = blk.runs
    n = len(runs)
    if n < 3 or n > tour.HEURISTIC:
        return None

    def cost(i, j):
        d = _d(runs[i][-1], runs[j][0])
        return d + (20 if d > DIRECT else 0)          # jeder echte Sprung zählt viel

    def start(j):
        # Anfahrt nach dem Farbwechsel ist ohnehin ein Sprung – zählt nur bei Gleichstand
        return 0.0 if pos is None else 0.05 * _d(pos, runs[j][0])
    seq = tour.order(n, cost, start, blk.pred)
    return [(j, runs[j]) for j in seq] if seq is not None else None


def _build_block(blk, order, pos, later, travel=True):
    """Stiche einer Reihenfolge aufbauen. Liefert (stiche, sprünge, sprunglänge)."""
    out, rest, last = [], set(range(len(blk.runs))), pos
    jumps, jlen = 0, 0.0
    for k, (j, run) in enumerate(order):
        rest.discard(j)
        start = run[0]
        if last is None:
            out.append((start[0], start[1], JUMP))
            out.extend((x, y, STITCH) for x, y in run)
            last = run[-1]
            continue
        d = _d(last, start)
        path = None
        if d <= DIRECT:
            path = [last, start]
        elif travel:
            line = LineString([last, start])
            area = line.buffer(8 + d * 0.6)
            parts = [blk.foot[i] for i in blk.tree.query(area) if int(i) in rest or int(i) == j]
            if later is not None:
                parts.append(later.intersection(area))
            if parts:
                path = _route(last, start, unary_union(parts).buffer(-0.12))
        if path is not None:
            out.extend((x, y, STITCH) for x, y in _travel_points(path)[:-1])
        else:
            if k > 0:
                jumps += 1
                jlen += d
            if k > 0 and d > engine.TRIM_DISTANCE:    # beim Farbwechsel schneidet die Maschine ohnehin
                out.append((last[0], last[1], TRIM))
            out.append((start[0], start[1], JUMP))
        out.extend((x, y, STITCH) for x, y in run)
        last = run[-1]
    return out, jumps, jlen


def optimize_blocks(blocks, reorder=True, travel=True, trials=12, progress=None):
    """blocks: [(farbe, [(x, y, flag), …]), …] -> (optimierte Blöcke, Statistik).
    Probiert mehrere Reihenfolgen und behält die mit den wenigsten Sprüngen."""
    import random
    parsed = [_Block(split_runs(sts)) for _, sts in blocks]
    for blk in parsed:
        blk.tree = shapely.STRtree(blk.foot) if blk.foot else None
    later_cover = [None] * len(parsed)
    acc = []
    for bi in range(len(parsed) - 1, -1, -1):
        later_cover[bi] = unary_union(acc) if acc else None
        if later_cover[bi] is not None:
            shapely.prepare(later_cover[bi])
        acc.extend(parsed[bi].foot)
    result, pos = [], None
    before = after = 0
    for bi, ((color, sts), blk) in enumerate(zip(blocks, parsed)):
        n = len(blk.runs)
        before += max(0, n - 1)
        if n == 0:
            continue
        if any(f == STOP for _, _, f in sts):     # Stopps (Applikation) nie umsortieren
            result.append((color, list(sts)))
            after += max(0, n - 1)
            pos = next((s[:2] for s in reversed(sts) if s[2] == STITCH), pos)
            continue
        later = later_cover[bi]
        # Ausgangspunkt: ursprüngliche Reihenfolge (nur Verbindungen verbessert)
        candidates = [[(j, blk.runs[j]) for j in range(n)]]
        if reorder:
            rng = random.Random(7)
            candidates.append(_order_block(blk, pos, later, None, travel))
            planned = _plan_block(blk, pos)
            if planned is not None:
                candidates.append(planned)
            for _ in range(trials):
                candidates.append(_order_block(blk, pos, later, rng, travel))
        best = None
        for t, order in enumerate(candidates):
            out, jumps, jlen = _build_block(blk, order, pos, later, travel)
            key = (jumps, jlen)
            if best is None or key < best[0]:
                best = (key, out, order)
            if progress:
                progress((bi + (t + 1) / len(candidates)) / len(parsed))
        (jumps, _), out, order = best
        after += jumps
        result.append((color, out))
        pos = order[-1][1][-1]
    return result, {"jumps_before": before, "jumps_after": after}


def count_jumps(blocks):
    """Sprünge innerhalb der Farbblöcke (ohne Farbwechsel-Anfahrt)."""
    return sum(max(0, len(split_runs(sts)) - 1) for _, sts in blocks)
