"""Sprünge und Fadenschnitte von Hand bearbeiten.

Sprünge *zwischen* Objekten werden über die Objekt-Eigenschaft »Fadenschnitt danach« gesteuert.
Sprünge *innerhalb* eines Objekts lassen sich direkt nur in Stichobjekten (importierte oder
umgewandelte Stickdateien) ändern – berechnete Formen werden dafür in Stiche umgewandelt.
"""
import math

import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union

from . import engine
from .engine import JUMP, STITCH, STOP, TRIM

TRAVEL_LEN = 2.5


def jump_list(doc, blocks_out=None):
    """Alle Sprünge mit Herkunft. blocks_out (Liste) erhält die zugehörigen Maschinenblöcke."""
    records = []
    blocks = doc.machine_blocks(records=records)
    if blocks_out is not None:
        blocks_out[:] = blocks
    for i, r in enumerate(records):
        r["index"] = i
        r["length"] = math.hypot(r["b"][0] - r["a"][0], r["b"][1] - r["a"][1])
    return records


class CoverageIndex:
    """Schnelle Prüfung, ob eine Strecke von später gestickten Stichen überdeckt wird."""

    def __init__(self, blocks):
        rows = []
        for mi, (_, sts) in enumerate(blocks):
            for k in range(1, len(sts)):
                if sts[k][2] == STITCH and sts[k - 1][2] == STITCH:
                    rows.append((mi, k, sts[k - 1][0], sts[k - 1][1], sts[k][0], sts[k][1]))
        self.a = np.array(rows, float) if rows else np.zeros((0, 6))

    def covered(self, rec):
        a = self.a
        if not len(a):
            return False
        (x0, y0), (x1, y1) = rec["a"], rec["b"]
        later = (a[:, 0] > rec["mblock"]) | ((a[:, 0] == rec["mblock"]) & (a[:, 1] > rec["mpos"]))
        near = ((np.minimum(a[:, 2], a[:, 4]) <= max(x0, x1) + 1) &
                (np.maximum(a[:, 2], a[:, 4]) >= min(x0, x1) - 1) &
                (np.minimum(a[:, 3], a[:, 5]) <= max(y0, y1) + 1) &
                (np.maximum(a[:, 3], a[:, 5]) >= min(y0, y1) - 1))
        sel = a[later & near]
        if not len(sel):
            return False
        line = LineString([rec["a"], rec["b"]])
        band = line.buffer(1.0)
        parts = [LineString([(r[2], r[3]), (r[4], r[5])]) for r in sel]
        parts = [p.buffer(0.3) for p in parts if p.intersects(band)]
        return bool(parts) and unary_union(parts).buffer(0.05).covers(line)


def is_covered(doc, rec):
    """Läge ein Verbindungsstich an dieser Stelle unter später gestickten Stichen?"""
    return CoverageIndex(doc.machine_blocks()).covered(rec)


def to_stitches(obj, optimize=False):
    """Berechnetes Objekt in ein Stichobjekt umwandeln (wie es gestickt würde)."""
    if obj.kind == "stitches":
        return
    merged = []
    for color, sts in obj.final_blocks(optimize):
        sts = [list(p) for p in sts]
        if merged and merged[-1]["color"].upper() == color.upper():
            cur = merged[-1]["stitches"]
            last = next(p for p in reversed(cur) if p[2] == STITCH)
            first = next((p for p in sts if p[2] == STITCH), None)
            if first and math.hypot(first[0] - last[0], first[1] - last[1]) > 5.0:
                cur.append([last[0], last[1], TRIM])
            cur.extend(sts)
        else:
            merged.append({"color": color, "stitches": sts})
    obj.kind = "stitches"
    obj.blocks = merged
    obj.sx = obj.sy = 1.0
    obj.rot = 0.0
    obj._gkey = obj._skey = obj._okey = None


def _block(doc, rec):
    o = doc.find(rec["obj"])
    if o is None or o.kind != "stitches":
        raise ValueError("Dieser Sprung liegt in einer berechneten Form – erst in Stiche umwandeln")
    return o, o.blocks[rec["block"]]["stitches"]


def set_trim(doc, rec, on):
    if rec["kind"] == "between":
        if rec.get("same"):
            raise ValueError("Wechsel zwischen Füllung und Rand desselben Objekts – erst in "
                             "Stiche umwandeln")
        doc.find(rec["obj"]).trim_after = "always" if on else "never"
        return
    o, sts = _block(doc, rec)
    gs, ge = rec["gs"], rec["ge"]
    gap = [p for p in sts[gs:ge] if p[2] != TRIM]
    if on:
        last = sts[gs - 1]
        gap.insert(0, [last[0], last[1], TRIM])
    if not any(p[2] == JUMP for p in gap):
        b = sts[ge]
        gap.append([b[0], b[1], JUMP])
    sts[gs:ge] = gap
    o._skey = None


def set_trim_mode(doc, rec, mode):
    """Zwischen Objekten: auto | always | never."""
    if rec["kind"] != "between" or rec.get("same"):
        raise ValueError("Nur für Sprünge zwischen zwei Objekten")
    doc.find(rec["obj"]).trim_after = mode


def connect(doc, rec):
    """Sprung durch Verbindungsstiche (Steppstich) ersetzen."""
    if rec["kind"] != "inside":
        raise ValueError("Sprünge zwischen zwei Objekten lassen sich nicht verbinden – dafür die "
                         "Objekte in Stiche umwandeln und kombinieren")
    o, sts = _block(doc, rec)
    gs, ge = rec["gs"], rec["ge"]
    a, b = sts[gs - 1], sts[ge]
    n = max(1, math.ceil(rec["length"] / TRAVEL_LEN))
    travel = [[a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, STITCH]
              for k in range(1, n)]
    sts[gs:ge] = travel
    o._skey = None


def find_stitch(doc, x, y, tol):
    """Nächstgelegener Stich (Strecke zwischen zwei Einstichen) in einem Stichobjekt."""
    best = None
    for o in doc.objects:
        if o.kind != "stitches" or not o.visible:
            continue
        for bi, (_, sts) in enumerate(o.stitch_blocks()):
            if len(sts) < 2:
                continue
            arr = np.array([(p[0] + o.x, p[1] + o.y) for p in sts])
            fl = np.array([p[2] for p in sts])
            p0, p1 = arr[:-1], arr[1:]
            ok = (fl[:-1] == STITCH) & (fl[1:] == STITCH)
            d = p1 - p0
            L2 = (d ** 2).sum(1)
            L2[L2 == 0] = 1e-9
            t = np.clip(((x - p0[:, 0]) * d[:, 0] + (y - p0[:, 1]) * d[:, 1]) / L2, 0, 1)
            proj = p0 + d * t[:, None]
            dist = np.hypot(proj[:, 0] - x, proj[:, 1] - y)
            dist[~ok] = 1e9
            k = int(np.argmin(dist))
            if dist[k] < tol and (best is None or dist[k] < best[0]):
                best = (dist[k], {"obj": o.id, "block": bi, "index": k + 1,
                                  "a": tuple(arr[k]), "b": tuple(arr[k + 1]),
                                  "length": float(math.sqrt(L2[k]))})
    return best[1] if best else None


def split_stitch(doc, hit, trim=False):
    """Einen Stich in einen Sprung umwandeln (optional mit Fadenschnitt davor)."""
    o = doc.find(hit["obj"])
    sts = o.blocks[hit["block"]]["stitches"]
    k = hit["index"]
    q, p = sts[k], sts[k - 1]
    new = ([[p[0], p[1], TRIM]] if trim else []) + [[q[0], q[1], JUMP], [q[0], q[1], STITCH]]
    sts[k:k + 1] = new
    o._skey = None


# ------------------------------------------------------------- Reihenfolge ändern
def stitch_order(doc):
    """Stickreihenfolge: [(objekt-id, blockindex, farbe)] wie sie gestickt wird."""
    doc.machine_blocks(records=[])
    return list(getattr(doc, "last_order", []))


def move_object(doc, oid, delta):
    """Objekt innerhalb seiner Farbe einen Platz früher (delta < 0) oder später sticken.
    Schaltet die Reihenfolge auf »von Hand«. Liefert eine Meldung oder löst ValueError aus."""
    order = stitch_order(doc)
    pos = [k for k, (o, _, _) in enumerate(order) if o == oid]
    if not pos:
        raise ValueError("Objekt wird nicht gestickt (ausgeblendet?)")
    k = pos[0] if delta < 0 else pos[-1]
    color = order[k][2].upper()
    rng = range(k - 1, -1, -1) if delta < 0 else range(k + 1, len(order))
    other = next((order[i][0] for i in rng if order[i][0] != oid and order[i][2].upper() == color), None)
    if other is None:
        raise ValueError("Das ist schon das " + ("erste" if delta < 0 else "letzte") +
                         " Teil in dieser Farbe")
    objs = doc.objects
    if doc.order_mode != "manual":
        # erst die gerade sichtbare (automatisch geplante) Reihenfolge dieser Farbe in die
        # Objektliste übernehmen – »von Hand« folgt der Liste, sonst springt sie beim Umschalten
        seq = []
        for o, _, c in order:
            if c.upper() == color and doc.find(o) not in seq:
                seq.append(doc.find(o))
        slots = sorted(objs.index(o) for o in seq)
        for k, o in zip(slots, seq):
            objs[k] = o
    me = doc.find(oid)
    objs.remove(me)
    j = objs.index(doc.find(other))
    objs.insert(j if delta < 0 else j + 1, me)
    doc.order_mode = "manual"
    return f"»{me.name}« wird jetzt {'vor' if delta < 0 else 'nach'} »{doc.find(other).name}« gestickt."


def _runs(sts):
    """Stichliste -> (vorspann, [läufe]); ein Lauf = zusammenhängende Einstiche."""
    head, runs, cur = [], [], None
    for p in sts:
        if p[2] == STITCH:
            if cur is None:
                cur = []
                runs.append(cur)
            cur.append(list(p))
        else:
            if not runs:
                head.append(list(p))
            cur = None
    return head, runs


def _join(head, runs):
    out = [list(p) for p in head]
    if out and out[-1][2] == JUMP and runs:          # Anfahrt zum (neuen) ersten Teil
        out[-1][0], out[-1][1] = runs[0][0][0], runs[0][0][1]
    for k, run in enumerate(runs):
        if k:
            a, b = out[-1], run[0]
            if math.hypot(b[0] - a[0], b[1] - a[1]) > engine.TRIM_DISTANCE:
                out.append([a[0], a[1], TRIM])
            out.append([b[0], b[1], JUMP])
        out.extend(run)
    return out


def _run_after(doc, rec):
    if rec["kind"] != "inside":
        raise ValueError("Nur für Sprünge innerhalb eines Objekts")
    o, sts = _block(doc, rec)
    if any(p[2] == STOP for p in sts):
        raise ValueError("Teile mit Stopp (Applikation) werden nicht umsortiert")
    head, runs = _runs(sts)
    # Lauf, der am Ende des Sprungs beginnt (Index ge in der Stichliste)
    idx, count = None, 0
    for k, p in enumerate(sts):
        if p[2] == STITCH and (k == 0 or sts[k - 1][2] != STITCH):
            if k == rec["ge"]:
                idx = count
                break
            count += 1
    if idx is None:
        raise ValueError("Teil nach dem Sprung nicht gefunden")
    return o, head, runs, idx


def move_run(doc, rec, delta):
    """Das Teil nach einem Sprung (innerhalb eines Stichobjekts) früher/später sticken."""
    o, head, runs, k = _run_after(doc, rec)
    j = k + (-1 if delta < 0 else 1)
    if j < 0 or j >= len(runs):
        raise ValueError("Das ist schon das " + ("erste" if delta < 0 else "letzte") + " Teil")
    runs[k], runs[j] = runs[j], runs[k]
    o.blocks[rec["block"]]["stitches"] = _join(head, runs)
    o._skey = None
    return f"Teil {k + 1} wird jetzt als Teil {j + 1} gestickt."


def reverse_run(doc, rec):
    """Das Teil nach einem Sprung rückwärts sticken (Start und Ende tauschen)."""
    o, head, runs, k = _run_after(doc, rec)
    runs[k] = runs[k][::-1]
    o.blocks[rec["block"]]["stitches"] = _join(head, runs)
    o._skey = None
    return f"Teil {k + 1} wird jetzt rückwärts gestickt."
