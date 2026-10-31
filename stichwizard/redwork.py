"""Redwork und Autoroute für Steppstichlinien (wie die Ink/Stitch-Erweiterungen).

Alle Linien werden zu einem Netz verknüpft (Kreuzungen und Berührungen werden zu Knoten),
dann wird ein durchgehender Weg gesucht:

* Redwork: jede Strecke genau zweimal (hin und zurück), Ende am Anfang – ohne Sprung.
* Autoroute: jede Strecke einmal; nur wo es nicht anders geht, wird eine Strecke ein zweites
  Mal gestickt (nie öfter).

Nicht zusammenhängende Linien ergeben getrennte Wege (dazwischen springt die Maschine).
"""
import heapq
import math

from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points, unary_union

from .engine import lines_of

SNAP = 0.6        # mm – so nahe Linienenden werden mit der Nachbarlinie verbunden
MERGE = 0.05      # mm – so nahe Knoten gelten als derselbe Punkt


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _snap_ends(lines, tol):
    """Linienenden, die knapp neben einer anderen Linie enden, bis auf diese verlängern."""
    out = []
    for i, ln in enumerate(lines):
        pts = list(ln.coords)
        others = [o for j, o in enumerate(lines) if j != i]
        if not others:
            out.append(ln)
            continue
        rest = unary_union(others)
        for end in (0, -1):
            p = Point(pts[end])
            d = rest.distance(p)
            if 1e-9 < d <= tol:
                q = nearest_points(rest, p)[0].coords[0]
                # minimal über die Nachbarlinie hinaus, damit dort sicher ein Knoten entsteht
                ux, uy = q[0] - pts[end][0], q[1] - pts[end][1]
                f = 1 + 0.02 / max(d, 1e-9)
                q = (pts[end][0] + ux * f, pts[end][1] + uy * f)
                if end == 0:
                    pts.insert(0, q)
                else:
                    pts.append(q)
        out.append(LineString(pts))
    return out


class Graph:
    def __init__(self, polylines, snap=SNAP):
        lines = [LineString(p) for p in polylines if len(p) >= 2 and LineString(p).length > 1e-6]
        lines = _snap_ends(lines, snap)
        noded = unary_union(MultiLineString(lines)) if lines else None
        self.nodes = []           # Koordinaten
        self.edges = []           # (u, v, koordinaten u->v, länge)
        self.adj = {}
        for seg in lines_of(noded):
            c = list(seg.coords)
            if seg.length < 1e-6:
                continue
            u, v = self._node(c[0]), self._node(c[-1])
            c[0], c[-1] = self.nodes[u], self.nodes[v]
            self._add(u, v, c, seg.length)
        self._drop_stubs()

    def _node(self, p):
        for i, q in enumerate(self.nodes):
            if _d(p, q) <= MERGE:
                return i
        self.nodes.append(tuple(p[:2]))
        return len(self.nodes) - 1

    def _add(self, u, v, coords, length):
        k = len(self.edges)
        self.edges.append((u, v, coords, length))
        self.adj.setdefault(u, []).append(k)
        self.adj.setdefault(v, []).append(k)

    def _drop_stubs(self):
        """Winzige Überstände vom Einrasten entfernen (Kante < 0.1 mm an einem freien Ende)."""
        keep = []
        deg = {n: len(e) for n, e in self.adj.items()}
        for k, (u, v, c, ln) in enumerate(self.edges):
            if ln < 0.1 and (deg[u] == 1 or deg[v] == 1) and u != v:
                continue
            keep.append((u, v, c, ln))
        self.edges, self.adj = [], {}
        for e in keep:
            self._add(*e)

    def components(self):
        """Kantengruppen, die zusammenhängen: [[kante, …], …]."""
        seen, comps = set(), []
        for k in range(len(self.edges)):
            if k in seen:
                continue
            comp, stack = [], [k]
            seen.add(k)
            while stack:
                e = stack.pop()
                comp.append(e)
                u, v = self.edges[e][:2]
                for n in (u, v):
                    for f in self.adj[n]:
                        if f not in seen:
                            seen.add(f)
                            stack.append(f)
            comps.append(sorted(comp))
        return comps

    def other(self, k, n):
        u, v = self.edges[k][:2]
        return v if n == u else u

    def coords(self, k, frm):
        u, _, c, _ = self.edges[k]
        return c if frm == u else c[::-1]

    def shortest(self, src, edges):
        """Dijkstra innerhalb der Kanten `edges`: (abstand, vorgänger-kante) je Knoten."""
        allowed = set(edges)
        dist, prev = {src: 0.0}, {src: None}
        heap = [(0.0, src)]
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist[n]:
                continue
            for k in self.adj[n]:
                if k not in allowed:
                    continue
                m = self.other(k, n)
                nd = d + self.edges[k][3]
                if nd < dist.get(m, 1e18):
                    dist[m], prev[m] = nd, k
                    heapq.heappush(heap, (nd, m))
        return dist, prev


def _euler(g, mult, start):
    """Hierholzer: Weg über alle Kanten (Kante k mult[k]-mal) ab `start` -> [(kante, von)]."""
    left = dict(mult)
    inc = {}
    for k, m in left.items():
        u, v = g.edges[k][:2]
        for n in {u, v}:
            inc.setdefault(n, []).append(k)
    stack, path = [(start, None, None)], []
    while stack:
        n, k_in, frm = stack[-1]
        nxt = None
        for k in inc.get(n, ()):
            if left[k] > 0:
                nxt = k
                break
        if nxt is None:
            stack.pop()
            if k_in is not None:
                path.append((k_in, frm))
            continue
        left[nxt] -= 1
        stack.append((g.other(nxt, n), nxt, n))
    return path[::-1]


def _redwork_walk(g, comp, start):
    """Tiefensuche: jede Kante hin und sofort nach dem Teilbaum zurück -> [(kante, von)]."""
    allowed = set(comp)
    used, visited, path = set(), {start}, []
    stack = [(start, iter(sorted(g.adj[start], key=lambda k: -g.edges[k][3])))]
    back = []                 # Rückweg je Stapelebene
    while stack:
        n, it = stack[-1]
        k = next((e for e in it if e in allowed and e not in used), None)
        if k is None:
            stack.pop()
            if back:
                path.append(back.pop())
            continue
        used.add(k)
        m = g.other(k, n)
        path.append((k, n))
        if m in visited:                      # Querkante: gleich wieder zurück
            path.append((k, m))
            continue
        visited.add(m)
        back.append((k, m))
        stack.append((m, iter(sorted(g.adj[m], key=lambda e: -g.edges[e][3]))))
    return path


def _autoroute_mult(g, comp, start_pref):
    """Wie oft jede Kante gestickt wird (1 oder 2) und wo der Weg beginnt."""
    deg = {}
    for k in comp:
        u, v = g.edges[k][:2]
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1
    odd = [n for n, d in deg.items() if d % 2]
    mult = {k: 1 for k in comp}
    if len(odd) > 2:
        sp = {n: g.shortest(n, comp) for n in odd}
        pairs = sorted((sp[a][0].get(b, 1e18), a, b) for i, a in enumerate(odd) for b in odd[i + 1:])
        # der ungerade Knoten am gewünschten Start bleibt Wegende
        keep = min(odd, key=lambda n: _d(g.nodes[n], start_pref)) if start_pref else None
        free = set(odd) - {keep}
        for d, a, b in pairs:                 # nächstgelegene ungerade Knoten verbinden
            if len(free) <= (1 if keep is not None else 2):
                break
            if a in free and b in free:
                free -= {a, b}
                n, prev = b, sp[a][1]
                while prev[n] is not None:
                    k = prev[n]
                    mult[k] += 1
                    n = g.other(k, n)
        odd = sorted(free | ({keep} if keep is not None else set()))
    for k in mult:                            # nie öfter als zweimal (Parität bleibt gleich)
        while mult[k] > 2:
            mult[k] -= 2
    nodes = odd if odd else list(deg)
    start = min(nodes, key=lambda n: _d(g.nodes[n], start_pref)) if start_pref else nodes[0]
    return mult, start


def route(polylines, mode="redwork", start=None, snap=SNAP):
    """Linien -> durchgehende Wege. mode: redwork | autoroute. start: bevorzugter Startpunkt.
    Liefert (wege [[(x, y), …], …], info {"edges", "doubled", "paths"})."""
    g = Graph(polylines, snap)
    comps = g.components()
    paths, doubled = [], 0
    pos = tuple(start) if start else None
    todo = list(comps)
    while todo:
        # nächstgelegene Gruppe zuerst
        if pos is None:
            comp = todo.pop(0)
        else:
            def dist_to(c):
                return min(_d(pos, g.nodes[n]) for k in c for n in g.edges[k][:2])
            comp = todo.pop(min(range(len(todo)), key=lambda i: dist_to(todo[i])))
        if mode == "redwork":
            nodes = {n for k in comp for n in g.edges[k][:2]}
            s = min(nodes, key=lambda n: _d(g.nodes[n], pos)) if pos else g.edges[comp[0]][0]
            walk = _redwork_walk(g, comp, s)
            doubled += len(comp)
        else:
            mult, s = _autoroute_mult(g, comp, pos)
            walk = _euler(g, mult, s)
            doubled += sum(1 for m in mult.values() if m > 1)
        pts = [g.nodes[s]]
        for k, frm in walk:
            pts.extend(g.coords(k, frm)[1:])
        paths.append(pts)
        pos = pts[-1]
    return paths, {"edges": len(g.edges), "doubled": doubled, "paths": len(paths)}
