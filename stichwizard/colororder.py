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


def sort_blocks(items, shortest=True, anchor=None, geometric=False):
    """items: [(objekt, blockindex, farbe, stiche)] in Objektreihenfolge -> neu sortiert.
    shortest=False: innerhalb einer Farbe die Reihenfolge der Objektliste beibehalten
    (von Hand festgelegte Stickreihenfolge).
    anchor: (x, y) unten in der Mitte des Designs – Kappen-Reihenfolge wie in Profi-Programmen:
    von der Mitte nach außen und von unten nach oben (gegen Verzug auf der gewölbten Kappe).
    geometric: Abstände zwischen den Formen statt zwischen erstem/letztem Stich messen – mit
    automatischem Ein-/Ausstieg passen sich die Stiche ohnehin der Reihenfolge an, und das
    Ergebnis hängt so nicht davon ab, wie das Design vorher gestickt wurde."""
    n = len(items)
    if n < 3:
        return items
    hulls = [_hull(o, bi, s) for o, bi, _, s in items]
    cols = [c.upper() for _, _, c, _ in items]
    first = [next((s[:2] for s in sts if s[2] == 0), None) for _, _, _, sts in items]
    last = [next((s[:2] for s in reversed(sts) if s[2] == 0), None) for _, _, _, sts in items]
    geo = None
    if geometric:
        # Formen wählen Ein- und Ausstieg frei: ihre ganze Fläche zählt. Schrift, Säulen und
        # Linien beginnen/enden an einem ihrer beiden Enden: nur diese zählen.
        from .model import _join_geom, joinable
        geo = []
        for j, (o, bi, *_) in enumerate(items):
            g = _join_geom(o) if o.kind == "shape" and joinable(o) else None
            if g is not None and o._stitches and bi < len(o._stitches) and \
                    o._stitches[bi][0][0] == "border" and g.geom_type in ("Polygon", "MultiPolygon"):
                g = g.boundary          # der Rand liegt auf der Kontur
            if g is None and first[j] is not None and last[j] is not None:
                g = shapely.multipoints([first[j], last[j]])
            geo.append(g if g is not None else hulls[j])

    gaps = {}
    boxes = [g.bounds if g is not None and not g.is_empty else None for g in geo] if geo else None

    def gap(i, j):
        """Abstand Block i -> Block j (mm, gerundet, damit Gleichstände stabil bleiben)."""
        key = (i, j) if i < j else (j, i)
        if key not in gaps:
            gaps[key] = 1e9 if geo[i] is None or geo[j] is None else \
                round(geo[i].distance(geo[j]), 1)
        return gaps[key]

    def gaps_from(i, cands):
        """Abstände von Block i zu vielen Blöcken auf einmal (schnell)."""
        todo = [j for j in cands if ((i, j) if i < j else (j, i)) not in gaps]
        if todo and geo[i] is not None:
            ok = [j for j in todo if geo[j] is not None]
            if ok:
                ds = shapely.distance(geo[i], np.array([geo[j] for j in ok], dtype=object))
                for j, dv in zip(ok, ds):
                    gaps[(i, j) if i < j else (j, i)] = round(float(dv), 1)
        return {j: gap(i, j) for j in cands}
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

    mids = [h.centroid.coords[0] if h is not None else None for h in hulls]

    def outward(j):
        """Kappe: Abstand von der Mitte (waagrecht) zählt am meisten, dann von unten nach oben."""
        if mids[j] is None:
            return (1e9, j)
        return (abs(mids[j][0] - anchor[0]) + 0.3 * max(0.0, anchor[1] - mids[j][1]), j)

    def nearest(cands, pos):
        """Nächstgelegenen Block wählen (kurze Wege = kurze Sprünge); bei Gleichstand die
        ursprüngliche Reihenfolge."""
        if anchor is not None and shortest:
            return min(cands, key=outward)
        if pos is None or not shortest:
            return min(cands)
        if geo is not None and order:
            # Abstand der Begrenzungsrechtecke ist eine untere Schranke: genau rechnen nur, solange
            # ein Kandidat noch näher sein kann (bei vielen Objekten viel schneller)
            i = order[-1]
            if boxes[i] is None:
                return min(cands)
            lo = []
            for j in cands:
                b = boxes[j]
                if b is None:
                    continue
                dx = max(0.0, b[0] - boxes[i][2], boxes[i][0] - b[2])
                dy = max(0.0, b[1] - boxes[i][3], boxes[i][1] - b[3])
                lo.append((math.hypot(dx, dy), j))
            if not lo:
                return min(cands)
            lo.sort()
            best = None
            for k in range(0, len(lo), 8):
                if best is not None and lo[k][0] > best[0] + 0.05:
                    break
                dd = gaps_from(i, [j for _, j in lo[k:k + 8]])
                for j, dv in dd.items():
                    if best is None or (dv, j) < best:
                        best = (dv, j)
            return best[1]
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
            group = _plan_color(items, best, cols, pred, placed, first, last, pos,
                                gap if geo is not None else None,
                                order[-1] if order else None) \
                if shortest and anchor is None else None
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


def _plan_color(items, color, cols, pred, placed, first, last, pos, gap=None, prev=None):
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
    _geom_of = None
    x0 = 0.0
    if gap is not None:
        from .model import _join_geom
        _geom_of = lambda j: _join_geom(items[j][0])
        xs = [g.bounds[0] for u in units for g in [_geom_of(u[0])] if g is not None]
        x0 = min(xs) if xs else 0.0
    upred = [{unit_of[i] for j in u for i in pred[j] if i in unit_of} - {k}
             for k, u in enumerate(units)]

    def cost(a, b):
        if gap is not None:             # Abstand der Formen (Ein-/Ausstieg passt sich an)
            d = gap(units[a][-1], units[b][0])
        else:
            p, q = last[units[a][-1]], first[units[b][0]]
            d = math.hypot(q[0] - p[0], q[1] - p[1])
        return d + (2.0 if d > engine.TRIM_DISTANCE else 0.0)     # Fadenschnitt kostet extra

    def start(a):
        # Anfahrt nach dem Farbwechsel ist ohnehin ein Sprung – zählt nur bei Gleichstand
        if gap is not None:
            if prev is not None:
                return 0.05 * gap(prev, units[a][0])
            g = _geom_of(units[a][0])       # ganz am Anfang: links beginnen (eindeutig)
            return 0.001 * (g.bounds[0] - x0) if g is not None else 0.0
        if pos is None:
            return 0.0
        q = first[units[a][0]]
        return 0.05 * math.hypot(q[0] - pos[0], q[1] - pos[1])
    seq = tour.order(len(units), cost, start, upred)
    return [j for k in seq for j in units[k]] if seq is not None else None


def color_changes(blocks):
    return max(0, len(blocks) - 1)
