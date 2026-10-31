"""Farben zusammenfassen: Farbblöcke so ordnen, dass möglichst wenige Farbwechsel entstehen.

Arbeitet auf Ebene der Farbblöcke (z. B. Füllung und Rand eines Objekts getrennt). Blöcke, die
sich überlagern, behalten ihre Reihenfolge – was oben liegt, bleibt oben. Ebenso bleibt die
Reihenfolge innerhalb eines Objekts erhalten.
"""
import math

import numpy as np
import shapely


def _hull(o, bi, sts):
    key = (o._skey, o.x, o.y, bi, len(sts))
    cache = o.__dict__.setdefault("_hulls", {})
    if key not in cache:
        cache.clear() if len(cache) > 32 else None
        if len(sts) >= 3:
            # alle Punkte auf einmal (ohne tausende Einzelobjekte) – deutlich schneller
            arr = np.asarray([(s[0], s[1]) for s in sts], dtype=float)
            cache[key] = shapely.convex_hull(shapely.multipoints(arr)).buffer(0.4)
        else:
            cache[key] = None
    return cache[key]


def sort_blocks(items, shortest=True):
    """items: [(objekt, blockindex, farbe, stiche)] in Objektreihenfolge -> neu sortiert.
    shortest=False: innerhalb einer Farbe die Reihenfolge der Objektliste beibehalten
    (von Hand festgelegte Stickreihenfolge)."""
    n = len(items)
    if n < 3:
        return items
    hulls = [_hull(o, bi, s) for o, bi, _, s in items]
    # Maschinenstopp (»Schnitt danach: Stopp«, z. B. Applikation, 3D-Puff) ist eine Sperre:
    # nichts aus der Zeit danach wird davor gestickt und umgekehrt
    seg, k = [], 0
    for idx, (o, *_) in enumerate(items):
        seg.append(k)
        nxt = items[idx + 1][0] if idx + 1 < n else None
        if getattr(o, "trim_after", "auto") == "stop" and nxt is not o:
            k += 1
    pred = [set() for _ in range(n)]
    for j in range(n):
        for i in range(j):
            if seg[i] < seg[j]:
                pred[j].add(i)
            elif items[i][0] is items[j][0]:
                pred[j].add(i)                     # Reihenfolge im Objekt beibehalten
            elif hulls[i] is not None and hulls[j] is not None and hulls[i].intersects(hulls[j]) \
                    and hulls[i].intersection(hulls[j]).area > 0.3:
                pred[j].add(i)
    cols = [c.upper() for _, _, c, _ in items]
    first = [next((s[:2] for s in sts if s[2] == 0), None) for _, _, _, sts in items]
    last = [next((s[:2] for s in reversed(sts) if s[2] == 0), None) for _, _, _, sts in items]

    def nearest(cands, pos):
        """Nächstgelegenen Block wählen (kurze Wege = kurze Sprünge); bei Gleichstand die
        ursprüngliche Reihenfolge."""
        if pos is None or not shortest:
            return min(cands)
        return min(cands, key=lambda j: (math.hypot(first[j][0] - pos[0], first[j][1] - pos[1])
                                         if first[j] else 1e9, j))

    placed, order, cur, pos = set(), [], None, None
    while len(order) < n:
        avail = [j for j in range(n) if j not in placed and pred[j] <= placed]
        same = [j for j in avail if cols[j] == cur]
        if same:
            # Blöcke desselben Objekts bleiben zusammen, sonst der nächstgelegene
            own = [j for j in same if order and items[j][0] is items[order[-1]][0]]
            pick = min(own) if own else nearest(same, pos)
        else:
            # die Farbe, von der gerade am meisten Blöcke stickbar sind
            counts = {}
            for j in avail:
                counts[cols[j]] = counts.get(cols[j], 0) + 1
            best = max(counts, key=lambda c: (counts[c], -min(j for j in avail if cols[j] == c)))
            group = _plan_color(items, best, cols, pred, placed, first, last, pos) if shortest else None
            if group:
                for j in group:
                    order.append(j)
                    placed.add(j)
                cur, pos = best, last[group[-1]] or pos
                continue
            pick = nearest([j for j in avail if cols[j] == best], pos)
        order.append(pick)
        placed.add(pick)
        cur = cols[pick]
        pos = last[pick] or pos
    return [items[i] for i in order]


def _plan_color(items, color, cols, pred, placed, first, last, pos):
    """Alle Blöcke einer Farbe, die jetzt am Stück gestickt werden können, als ganzen Weg planen
    (kürzeste Summe der Sprünge, siehe tour.py) statt immer zum nächstgelegenen Block zu
    springen – sonst bleibt leicht ein Teil liegen, zu dem quer übers Motiv zurückgesprungen
    wird. Blöcke eines Objekts bleiben zusammen und in ihrer Reihenfolge."""
    from . import engine, tour
    group, grew = [], True
    while grew:
        grew = False
        for j in range(len(items)):
            if j not in placed and j not in group and cols[j] == color and \
                    pred[j] <= placed | set(group):
                group.append(j)
                grew = True
    group.sort()
    units = {}
    for j in group:
        units.setdefault(id(items[j][0]), []).append(j)
    units = list(units.values())
    if len(units) < 2 or len(units) > tour.HEURISTIC or \
            any(first[u[0]] is None or last[u[-1]] is None for u in units):
        return None
    unit_of = {j: k for k, u in enumerate(units) for j in u}
    upred = [{unit_of[i] for j in u for i in pred[j] if i in unit_of} - {k}
             for k, u in enumerate(units)]

    def cost(a, b):
        p, q = last[units[a][-1]], first[units[b][0]]
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        return d + (2.0 if d > engine.TRIM_DISTANCE else 0.0)     # Fadenschnitt kostet extra

    def start(a):
        # Anfahrt nach dem Farbwechsel ist ohnehin ein Sprung – zählt nur bei Gleichstand
        if pos is None:
            return 0.0
        q = first[units[a][0]]
        return 0.05 * math.hypot(q[0] - pos[0], q[1] - pos[1])
    seq = tour.order(len(units), cost, start, upred)
    return [j for k in seq for j in units[k]] if seq is not None else None


def color_changes(blocks):
    return max(0, len(blocks) - 1)
