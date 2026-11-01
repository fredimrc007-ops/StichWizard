"""Auto-Füllung wie in Profi-Software: Abschnitte einer Reihenfüllung so ordnen und verbinden,
dass möglichst selten gesprungen wird.

Die Fläche wird (im gedrehten Rahmen) in waagerechte Reihen zerlegt; übereinanderliegende
Reihenstücke bilden Abschnitte. Um von einem Abschnitt zum nächsten zu kommen, wird bevorzugt
*durch Reihen gestickt, die noch kommen* – diese Verbindungsstiche verschwinden später unter dem
Deckstich. Geht das nicht, läuft die Verbindung am Rand entlang, und nur wenn auch das nicht
möglich ist, wird gesprungen. Mehrere Reihenfolgen werden durchprobiert, die beste gewinnt.
"""
import bisect
import heapq
import math
import random

from shapely.geometry import LineString, Point
from shapely.ops import substring

TRAVEL_LEN = 2.5     # mm – Verbindungsstiche unter späteren Reihen
EDGE_LEN = 2.0       # mm – Verbindungsstiche am Rand entlang
EDGE_INSET = 0.25    # mm – so weit innen läuft der Randweg
DIRECT = 1.0         # mm – so kurze Wege immer direkt
JUMP_COST = 40.0     # Bewertung eines Sprungs (in mm Umweg)
SPLIT_COST = 14.0    # Rest zerfällt in getrennte Gruppen -> später Randweg/Sprung
DEADEND_COST = 5.0   # Abschnitt endet ohne offenen Nachbarn
TRIM_COST = 15.0     # zusätzlich, wenn der Sprung geschnitten werden muss
TRIM_DISTANCE = 5.0
EDGE_MAX = 40.0      # mm – so lange Randwege sind besser als ein Sprung
CRUMB = 2.0          # mm – kürzere Reststücke einer Füllung werden nicht eigens angesprungen


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _resample(path, step):
    """Polylinie -> Einstichpunkte im Abstand `step` (ohne den Startpunkt)."""
    out = []
    for p, q in zip(path, path[1:]):
        n = max(1, math.ceil(_d(p, q) / step))
        for k in range(1, n + 1):
            out.append((p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n))
    # sehr kurze Zwischenstiche zusammenfassen
    res = []
    for p in out:
        if res and _d(res[-1], p) < step * 0.35 and p is not out[-1]:
            continue
        res.append(p)
    return res


class _Rows:
    """Reihen-Graph einer Insel: Knoten = Reihenstücke, Kanten = überlappende Nachbarreihen."""

    def __init__(self, rows, spacing):
        self.rows = rows
        self.ys = [y for y, _ in rows]
        self.spacing = spacing
        self.nb = {}
        for ri in range(len(rows) - 1):
            for sj, (a, b) in enumerate(rows[ri][1]):
                for sk, (c, d) in enumerate(rows[ri + 1][1]):
                    lo, hi = max(a, c), min(b, d)
                    if hi - lo > 0.3:
                        self.nb.setdefault((ri, sj), []).append(((ri + 1, sk), lo, hi))
                        self.nb.setdefault((ri + 1, sk), []).append(((ri, sj), lo, hi))

    def sources(self, pos, allowed):
        """Reihenstücke, die von `pos` aus direkt erreichbar sind: [(kosten, knoten, x)]."""
        i = bisect.bisect_left(self.ys, pos[1])
        out = []
        for ri in range(max(0, i - 3), min(len(self.rows), i + 3)):
            y, segs = self.rows[ri]
            if abs(y - pos[1]) > self.spacing * 1.6 + 0.1:
                continue
            for sj, (a, b) in enumerate(segs):
                node = (ri, sj)
                if not allowed(node) or pos[0] < a - 0.8 or pos[0] > b + 0.8:
                    continue
                x = _clamp(pos[0], a, b)
                out.append((_d(pos, (x, y)), node, x))
        return out


def _clamp(x, lo, hi, m=0.15):
    if hi - lo <= 2 * m:
        return (lo + hi) / 2
    return min(max(x, lo + m), hi - m)


class _Section:
    def __init__(self, k, chain, rows):
        self.k = k
        self.chain = chain
        self.top, self.bot = chain[0], chain[-1]
        n = len(chain)
        self.entries = []          # (knoten, eintritt, austritt, umgekehrt, links→rechts)
        for rev in (False, True):
            seq = chain[::-1] if rev else chain
            for ltr in (True, False):
                y0, segs0 = rows[seq[0][0]]
                a0, b0 = segs0[seq[0][1]]
                y1, segs1 = rows[seq[-1][0]]
                a1, b1 = segs1[seq[-1][1]]
                last_ltr = ltr if (n - 1) % 2 == 0 else not ltr
                self.entries.append((seq[0], (a0 if ltr else b0, y0),
                                     (b1 if last_ltr else a1, y1), rev, ltr))


class _Edge:
    """Wege am Rand der Insel entlang (leicht nach innen versetzt)."""

    def __init__(self, poly):
        inner = poly.buffer(-EDGE_INSET, join_style=2)
        self.rings = []
        for p in getattr(inner, "geoms", [inner]):
            if p.is_empty or p.geom_type != "Polygon":
                continue
            for r in [p.exterior] + list(p.interiors):
                line = LineString(r.coords)
                if line.length > 1:
                    self.rings.append(line)
        self.cache = {}

    def locate(self, pt):
        key = (round(pt[0], 3), round(pt[1], 3))
        if key not in self.cache:
            best = None
            P = Point(pt)
            for i, r in enumerate(self.rings):
                d = r.distance(P)
                if best is None or d < best[0]:
                    best = (d, i, r.project(P))
            self.cache[key] = best
        return self.cache[key]

    def length(self, a, b):
        la, lb = self.locate(a), self.locate(b)
        if la is None or lb is None or la[1] != lb[1] or la[0] > 1.6 or lb[0] > 1.6:
            return None
        L = self.rings[la[1]].length
        f = (lb[2] - la[2]) % L
        return min(f, L - f) + la[0] + lb[0]

    def path(self, a, b):
        la, lb = self.locate(a), self.locate(b)
        ring = self.rings[la[1]]
        L = ring.length
        s0, s1 = la[2], lb[2]
        fwd = (s1 - s0) % L
        if fwd <= L - fwd:
            pts = _ring_part(ring, L, s0, fwd)
        else:
            pts = _ring_part(ring, L, s1, L - fwd)[::-1]
        return [a] + pts + [b]


def _ring_part(ring, L, s0, ln):
    """Punkte des Rings ab Position s0 über die Länge ln (mit Umlauf über den Startpunkt)."""
    s1 = s0 + ln
    if s1 <= L:
        return list(substring(ring, s0, s1).coords)
    return list(substring(ring, s0, L).coords) + list(substring(ring, 0, s1 - L).coords)[1:]


def _graph_search(G, secs, sec_of, pos, remaining, any_node, bound):
    """Dijkstra durch noch nicht gestickte Reihen. Liefert {eintrittsknoten: (kosten, x, vorg.)}."""
    allowed = (lambda n: True) if any_node else (lambda n: sec_of[n] in remaining)
    targets = {}
    for k in remaining:
        for e in secs[k].entries:
            targets.setdefault(e[0], []).append(k)
    dist, xs, prev = {}, {}, {}
    heap = []
    for c, node, x in G.sources(pos, allowed):
        if c < dist.get(node, 1e18):
            dist[node], xs[node], prev[node] = c, x, None
            heapq.heappush(heap, (c, node))
    found = {}
    done = set()
    while heap:
        c, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if c > bound:
            break
        if node in targets:
            found[node] = c
        x = xs[node]
        y = G.ys[node[0]]
        for nb, lo, hi in G.nb.get(node, ()):
            if nb in done or not allowed(nb):
                continue
            nx = _clamp(x, lo, hi)
            nc = c + math.hypot(G.ys[nb[0]] - y, nx - x)
            if nc < dist.get(nb, 1e18):
                dist[nb], xs[nb], prev[nb] = nc, nx, node
                heapq.heappush(heap, (nc, nb))
    return found, xs, prev


def _graph_path(G, xs, prev, node, pos):
    pts = []
    while node is not None:
        pts.append((xs[node], G.ys[node[0]]))
        node = prev[node]
    pts.append(pos)
    return pts[::-1]


def _components(adj, nodes):
    """Anzahl zusammenhängender Gruppen von Abschnitten."""
    seen, n = set(), 0
    for k in nodes:
        if k in seen:
            continue
        n += 1
        stack = [k]
        seen.add(k)
        while stack:
            for m in adj[stack.pop()]:
                if m in nodes and m not in seen:
                    seen.add(m)
                    stack.append(m)
    return n


def _plan(G, secs, sec_of, edge, pos, rng, any_node, travel, adj, exit_nb):
    """Reihenfolge der Abschnitte festlegen. Gierig nach Wegkosten, aber mit Blick nach vorn:
    Abschnitte, deren Wegnahme den Rest zerteilt (später Randweg oder Sprung nötig), oder die
    in einer Sackgasse enden, werden gemieden (wie beim Fleury-Verfahren)."""
    remaining = set(range(len(secs)))
    moves, total = [], 0.0
    while remaining:
        cands = {}
        for k in remaining:
            for ei, e in enumerate(secs[k].entries):
                start = e[1]
                if pos is None:
                    cands[(k, ei)] = (start[1] * 1000 + start[0], "start", None)   # oben links
                    continue
                d = _d(pos, start)
                if d <= DIRECT:
                    cands[(k, ei)] = (d, "direct", None)
                    continue
                cost = d + JUMP_COST + (TRIM_COST if d > TRIM_DISTANCE else 0)
                how = "jump"
                if travel:
                    el = edge.length(pos, start)
                    if el is not None and el < max(25.0, d * 4) and el * 1.5 + 3 < cost:
                        cost, how = el * 1.5 + 3, "edge"
                cands[(k, ei)] = (cost, how, None)
        if travel and pos is not None:
            bound = min(c[0] for c in cands.values()) + 2 * SPLIT_COST
            found, xs, prev = _graph_search(G, secs, sec_of, pos, remaining, any_node, bound)
            for k in remaining:
                for ei, e in enumerate(secs[k].entries):
                    if e[0] in found:
                        cost = found[e[0]] + abs(xs[e[0]] - e[1][0])
                        if cost < cands[(k, ei)][0]:
                            cands[(k, ei)] = (cost, "graph", (xs, prev, e[0]))
        ranked = []
        for key, (cost, how, data) in cands.items():
            base = cost
            if rng is not None and how != "start":
                cost *= 1 + rng.random() * 0.6
            ranked.append((cost, key, how, data, base))
        ranked.sort(key=lambda r: r[0])
        if len(remaining) > 1 and pos is not None:
            before = _components(adj, remaining)
            split = {}
            best = None
            for cost, (k, ei), how, data, base in ranked[:12]:
                if k not in split:
                    split[k] = _components(adj, remaining - {k}) - before
                rest = remaining - {k}
                pen = split[k] * SPLIT_COST
                if not (exit_nb[k][ei] & rest):
                    pen += DEADEND_COST
                if best is None or cost + pen < best[0]:
                    best = (cost + pen, (k, ei), how, data, base)
            _, (k, ei), how, data, base = best
        else:
            _, (k, ei), how, data, base = ranked[0]
        e = secs[k].entries[ei]
        path = None
        if how == "graph":
            xs, prev, node = data
            path = _graph_path(G, xs, prev, node, pos) + [e[1]]
        elif how == "edge":
            path = edge.path(pos, e[1])
        moves.append((k, ei, how, path))
        if how != "start":
            total += base
        remaining.discard(k)
        pos = e[2]
    return total, moves


def _section_points(rows, sec, ei, length, offsets, row_points):
    _, _, _, rev, ltr = sec.entries[ei]
    seq = sec.chain[::-1] if rev else sec.chain
    pts = []
    for ri, sj in seq:
        y, segs = rows[ri]
        x0, x1 = segs[sj]
        a, b = (x0, x1) if ltr else (x1, x0)
        pts.extend(row_points(a, b, y, ri, length, offsets))
        ltr = not ltr
    return pts


def island_runs(poly, spacing, length, offsets, pos, row_points, scan_rows, chains_of,
                travel=True, any_node=False, trials=None, keep=None, end=None):
    """Eine zusammenhängende Fläche (Reihenrahmen) füllen.
    end: Endpunkt – unter den Reihenfolgen gewinnt die, die möglichst nah daran endet.
    pos: aktuelle Nadelposition oder None. any_node: Verbindungen dürfen auch über bereits
    gestickte Reihen laufen (Unterlage – wird ohnehin überdeckt).
    keep: nur Reihen sticken, für deren Höhe keep(y) wahr ist (z. B. Farbverlauf).
    Liefert (läufe, endposition); beginnt der erste Lauf an `pos`, ist pos sein erster Punkt."""
    rows = scan_rows(poly, spacing)
    gap = spacing
    if keep is not None:
        rows = [r for r in rows if keep(r[0])]
        if len(rows) > 1:
            gap = min(spacing * 6, max(b[0] - a[0] for a, b in zip(rows, rows[1:])))
    chains = chains_of(rows)
    chains = [c for c in chains if c]
    if not chains:
        return [], pos
    G = _Rows(rows, gap)
    secs = [_Section(k, ch, rows) for k, ch in enumerate(chains)]
    sec_of = {node: s.k for s in secs for node in s.chain}
    edge = _Edge(poly) if travel else None
    adj = [set() for _ in secs]
    for node, lst in G.nb.items():
        for nb, _, _ in lst:
            if sec_of[node] != sec_of[nb]:
                adj[sec_of[node]].add(sec_of[nb])
    exit_nb = []
    for sec in secs:
        row = []
        for e in sec.entries:
            last = sec.chain[0] if e[3] else sec.chain[-1]
            row.append({sec_of[nb] for nb, _, _ in G.nb.get(last, ())} - {sec.k})
        exit_nb.append(row)
    n = len(secs)
    if trials is None:
        trials = 0 if n <= 1 else (10 if n <= 12 else 6 if n <= 40 else 3 if n <= 120 else 1)
    if end is not None:
        trials = max(trials, 8 if n <= 120 else 3)
    plans = [_plan(G, secs, sec_of, edge, pos, None, any_node, travel, adj, exit_nb)]
    rng = random.Random(11)
    for _ in range(trials):
        plans.append(_plan(G, secs, sec_of, edge, pos, rng, any_node, travel, adj, exit_nb))

    def score(plan):
        total, moves = plan
        if end is None or not moves:
            return total
        k, ei = moves[-1][:2]
        return total + 3.0 * _d(secs[k].entries[ei][2], end)
    _, moves = min(plans, key=score)
    runs, cur, last = [], [], pos
    inside = poly.buffer(-0.15) if travel else None
    done = set()
    for k, ei, how, path in moves:
        pts = _section_points(rows, secs[k], ei, length, offsets, row_points)
        if how == "jump" and inside is not None and last is not None and cur:
            # kein Sprung innerhalb einer Fläche: lieber ein Weg in der Fläche – aber nur unter
            # noch nicht gestickten Reihen. Läge er sichtbar auf fertigen Reihen, bleibt es ein
            # Sprung (lange Sprünge werden geschnitten, es bleibt kein Faden sichtbar).
            from shapely.geometry import LineString as _LS, box as _box
            from shapely.ops import unary_union as _uu
            from .optimize import _route
            later = _uu([_box(rows[ri][1][si][0], rows[ri][0] - gap * 0.6,
                              rows[ri][1][si][1], rows[ri][0] + gap * 0.6)
                         for sec in secs if sec.k not in done for ri, si in sec.chain])
            route = _route(last, secs[k].entries[ei][1], inside, detour=(8.0, 60.0),
                           within=poly.bounds, prefer=later, penalty=8.0)
            if route is not None and _LS(route).difference(later.buffer(0.3)).length <= 2.0:
                how, path = "edge", route
        if how == "jump" and edge is not None and last is not None and cur:
            # sonst am Rand entlang (knapp innen, dort deckt ein Rand bzw. der Randabschluss
            # der Füllung den Weg) – auch auf längerem Weg lieber als Sprung mit Fadenschnitt
            start = secs[k].entries[ei][1]
            el = edge.length(last, start)
            if el is not None and el <= max(EDGE_MAX, _d(last, start) * 5):
                how, path = "edge", edge.path(last, start)
        if how == "jump" and cur and len(secs) > 1 and \
                sum(_d(p, q) for p, q in zip(pts, pts[1:])) < CRUMB:
            done.add(k)                # Krümel (1–2 kurze Reihenstücke): weglassen statt springen
            continue
        done.add(k)
        if how in ("start", "jump"):
            if cur:
                runs.append(cur)
            cur = list(pts)
        else:
            if not cur:
                cur = [last]          # setzt direkt an der aktuellen Position an
            if path:
                step = EDGE_LEN if how == "edge" else TRAVEL_LEN
                cur.extend(_resample(path, step)[:-1])
            cur.extend(pts)
        last = secs[k].entries[ei][2]
    if cur:
        runs.append(cur)
    return runs, last
