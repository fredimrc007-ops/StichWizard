"""Mittellinie einer Fläche (wie Ink/Stitch »Fill to Stroke«): aus schmalen Formen, z. B.
digitalisierter Schrift, werden Linien, die sich als Stepp- oder Satinstich sticken lassen.

Verfahren: Voronoi-Diagramm der dicht abgetasteten Kontur, nur Kanten im Inneren behalten
(= Mittelachse), kurze Seitenäste abschneiden, glätten.
"""

from shapely.geometry import MultiPoint
import random

import shapely
from shapely.ops import unary_union, voronoi_diagram

from .engine import lines_of, polygons_of


def _prune(lines, limit, rounds=20):
    """Kurze Seitenäste entfernen: Linien mit einem freien Ende, deren anderes Ende an einer
    Verzweigung hängt und die kürzer als `limit` sind – bis nichts mehr wegfällt."""
    key = lambda p: (round(p[0], 3), round(p[1], 3))
    for _ in range(rounds):
        deg = {}
        for ln in lines:
            for p in (ln.coords[0], ln.coords[-1]):
                deg[key(p)] = deg.get(key(p), 0) + 1
        keep, changed = [], False
        for ln in lines:
            da, db = deg[key(ln.coords[0])], deg[key(ln.coords[-1])]
            spur = (da == 1 and db >= 3) or (db == 1 and da >= 3)
            if spur and ln.length < limit:
                changed = True
                continue
            keep.append(ln)
        merged = shapely.line_merge(unary_union(keep)) if keep else None
        lines = [ln for ln in lines_of(merged)] if merged is not None else []
        if not changed:
            break
    return lines


def centerlines(geom, step=0.4, prune=1.5, rounds=20):
    """Mittellinien einer (Multi-)Fläche als Liste von Punktlisten."""
    out = []
    for poly in polygons_of(geom):
        if poly.area < 1.0:
            continue
        width = 2 * poly.area / max(poly.length, 1e-6)          # grobe Strichbreite
        dense = poly.segmentize(step)
        rnd = random.Random(3)            # minimal verrauschen: vermeidet entartete Voronoi-Kanten
        pts = [(x + rnd.uniform(-0.004, 0.004), y + rnd.uniform(-0.004, 0.004))
               for r in [dense.exterior] + list(dense.interiors) for x, y in r.coords[:-1]]
        if len(pts) < 4:
            continue
        edges = voronoi_diagram(MultiPoint(pts), edges=True)
        inner = poly.buffer(-min(0.05, width * 0.05))
        keep = [ln for ln in lines_of(edges) if ln.length > 1e-6 and inner.contains(ln)]
        if not keep:
            continue
        merged = shapely.line_merge(unary_union(keep))
        lines = _prune(list(lines_of(merged)), max(0.6, width * prune), rounds)
        for ln in lines:
            ln = ln.simplify(0.2)
            if ln.length >= max(0.6 if prune < 1.5 else 1.0, width * 0.5):
                out.append([(x, y) for x, y in ln.coords])
    return out
