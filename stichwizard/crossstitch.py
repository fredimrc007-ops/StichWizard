"""Kreuzstich: ein Raster aus Kästchen mit vollen, halben und Viertelkreuzen plus Rückstich-
Linien – gespeichert im Objekt (kind »cross«, Attribut cross) und für die Stickmaschine in
Stiche umgerechnet. Das Kreuzstich-Atelier (CrossDialog) bearbeitet die Daten.

Daten (dict, wird beim Bearbeiten immer als neues dict gesetzt):
  cols, rows   Kästchen quer/hoch
  cell         Kästchengröße in mm
  passes       1 = jeder Schenkel einmal, 3 = hin-zurück-hin (kräftiger, wie zwei Fäden)
  palette      ["#RRGGBB", …]
  cells        [[x, y, farbindex, art], …]   art: "x" voll, "/" "\\" halb, "q0".."q3" viertel
               (Ecke oben links, oben rechts, unten rechts, unten links → Mitte)
  back         [[x0, y0, x1, y1, farbindex], …] Rückstich zwischen Rasterpunkten
"""
import math

from shapely.geometry import LineString, box
from shapely.ops import unary_union

from . import engine

KINDS = [("Volles Kreuz", "x"), ("Halbes Kreuz /", "/"), ("Halbes Kreuz \\", "\\"),
         ("Viertelkreuz", "q")]
CORNERS = [(0, 0), (1, 0), (1, 1), (0, 1)]       # q0..q3: oben links, oben rechts, unten …


def new(cols=40, rows=40, cell=2.5, palette=None):
    return {"cols": int(cols), "rows": int(rows), "cell": float(cell), "passes": 1,
            "palette": list(palette or ["#C62828", "#2E7D32", "#1565C0", "#212121"]),
            "cells": [], "back": []}


def to_mm(data, gx, gy):
    c = data["cell"]
    return (gx - data["cols"] / 2) * c, (gy - data["rows"] / 2) * c


def used_colors(data):
    return sorted({c[2] for c in data["cells"]} | {b[4] for b in data["back"]})


# ------------------------------------------------------------------ Stiche
def _leg(out, a, b, passes):
    """Ein Schenkel A→B (bei passes=3 hin-zurück-hin) an einen Punktzug anhängen."""
    if not out or out[-1] != a:
        out.append(a)
    out.append(b)
    if passes >= 3:
        out += [a, b]


def _runs(xs):
    """Zusammenhängende Läufe aufeinanderfolgender x-Werte."""
    out = []
    for x in sorted(xs):
        if out and x == out[-1][-1] + 1:
            out[-1].append(x)
        else:
            out.append([x])
    return out


def _back_paths(segs):
    """Rückstich-Strecken zu möglichst langen Wegen verketten."""
    segs = [((s[0], s[1]), (s[2], s[3])) for s in segs if (s[0], s[1]) != (s[2], s[3])]
    paths = []
    while segs:
        a, b = segs.pop(0)
        path = [a, b]
        grown = True
        while grown:
            grown = False
            for i, (p, q) in enumerate(segs):
                if p == path[-1]:
                    path.append(q)
                elif q == path[-1]:
                    path.append(p)
                elif p == path[0]:
                    path.insert(0, q)
                elif q == path[0]:
                    path.insert(0, p)
                else:
                    continue
                segs.pop(i)
                grown = True
                break
        paths.append(path)
    return paths


def color_runs(data, ci):
    """Punktzüge (Rasterkoordinaten) für die Kreuze einer Farbe – Reihe für Reihe:
    erst alle »/«-Schenkel hin, dann alle »\\«-Schenkel zurück (Zickzack-Methode, die
    Verbindungen liegen auf den Kästchenkanten)."""
    passes = int(data.get("passes", 1))
    rows = {}
    quarters = []
    for x, y, c, k in data["cells"]:
        if c != ci:
            continue
        if k.startswith("q"):
            quarters.append((x, y, int(k[1:])))
        else:
            r = rows.setdefault(y, {"/": set(), "\\": set()})
            if k in ("x", "/"):
                r["/"].add(x)
            if k in ("x", "\\"):
                r["\\"].add(x)
    chains = []
    for y in sorted(rows):
        r = rows[y]
        for run in _runs(r["/"]):                       # hin: unten links → oben rechts
            pts = []
            for x in run:
                if pts:
                    pts.append((x, y + 1))              # senkrecht an der Kästchenkante
                _leg(pts, (x, y + 1), (x + 1, y), passes)
            chains.append(pts)
        for run in reversed(_runs(r["\\"])):            # zurück: unten rechts → oben links
            pts = []
            for x in reversed(run):
                if pts:
                    pts.append((x + 1, y + 1))
                _leg(pts, (x + 1, y + 1), (x, y), passes)
            chains.append(pts)
    for x, y, q in sorted(quarters, key=lambda t: (t[1], t[0])):
        cx, cy = CORNERS[q]
        pts = []
        _leg(pts, (x + cx, y + cy), (x + 0.5, y + 0.5), passes)
        chains.append(pts)
    return chains


def stitches(data):
    """[(farbe, stiche)] im Objektrahmen (mm, Mitte des Rasters = 0,0): zuerst die Kreuze
    jeder Farbe, danach die Rückstiche (liegen obenauf, wie beim Handsticken)."""
    out = []
    mm = lambda p: to_mm(data, *p)
    for ci in used_colors(data):
        sts = []
        for chain in color_runs(data, ci):
            engine.connect(sts, [mm(p) for p in chain])
        if sts:
            out.append((data["palette"][ci], engine.finish(sts)))
    triple = int(data.get("passes", 1)) >= 3
    for ci in sorted({b[4] for b in data["back"]}):
        sts = []
        for path in _back_paths([b for b in data["back"] if b[4] == ci]):
            pts = engine.running_stitch([mm(p) for p in path], min(data["cell"], 3.0), triple)
            engine.connect(sts, pts)
        if sts:
            out.append((data["palette"][ci], engine.finish(sts)))
    return out


def geometry(data):
    """Fläche der Kreuze und Rückstiche (Objektrahmen) – für Auswahl und Rahmen."""
    c = data["cell"]
    rects = []
    by_row = {}
    for x, y, _, _ in data["cells"]:
        by_row.setdefault(y, set()).add(x)
    for y, xs in by_row.items():
        for run in _runs(xs):
            x0, y0 = to_mm(data, run[0], y)
            rects.append(box(x0, y0, x0 + c * len(run), y0 + c))
    for x0, y0, x1, y1, _ in data["back"]:
        rects.append(LineString([to_mm(data, x0, y0), to_mm(data, x1, y1)]).buffer(c * 0.15))
    if not rects:
        return box(-c, -c, c, c)
    return unary_union(rects)


def stats(data):
    full = sum(1 for c in data["cells"] if c[3] == "x")
    half = sum(1 for c in data["cells"] if c[3] in ("/", "\\"))
    quarter = len(data["cells"]) - full - half
    return {"full": full, "half": half, "quarter": quarter, "back": len(data["back"]),
            "colors": len(used_colors(data)),
            "width": data["cols"] * data["cell"], "height": data["rows"] * data["cell"]}


# ------------------------------------------------------------------- Bild → Raster
def from_image(img, cols, n_colors=8, skip_light=True, threshold=245, kind="x", rows=None):
    """QImage → Kreuzstich-Daten (Farben per k-Means reduziert). Helle bzw. durchsichtige
    Pixel bleiben auf Wunsch frei (Stoff). Liefert (cells, palette, rows)."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    if rows is None:
        rows = max(1, round(cols * img.height() / max(1, img.width())))
    small = img.convertToFormat(QImage.Format_RGBA8888).scaled(
        cols, rows, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    ptr = small.constBits()
    arr = np.frombuffer(ptr, np.uint8, small.bytesPerLine() * rows).reshape(rows, -1)
    arr = arr[:, :cols * 4].reshape(rows, cols, 4).astype(float)
    rgb, alpha = arr[..., :3], arr[..., 3]
    mask = alpha > 128
    if skip_light:
        mask &= rgb.min(axis=2) < threshold
    pix = rgb[mask]
    if len(pix) == 0:
        return [], [], rows
    k = max(1, min(int(n_colors), len(np.unique(pix.round(), axis=0))))
    # k-Means++-Start, dann wenige Iterationen (Bild ist klein: höchstens einige 10 000 Pixel)
    rng = np.random.default_rng(1)
    cent = [pix[rng.integers(len(pix))]]
    for _ in range(1, k):
        d = np.min([((pix - c) ** 2).sum(1) for c in cent], axis=0)
        cent.append(pix[rng.choice(len(pix), p=d / d.sum())] if d.sum() > 0 else pix[0])
    cent = np.array(cent)
    for _ in range(20):
        lab = np.argmin(((pix[:, None, :] - cent[None]) ** 2).sum(2), axis=1)
        new = np.array([pix[lab == i].mean(0) if np.any(lab == i) else cent[i] for i in range(k)])
        if np.allclose(new, cent, atol=0.5):
            break
        cent = new
    lab = np.argmin(((pix[:, None, :] - cent[None]) ** 2).sum(2), axis=1)
    # Farben nach Häufigkeit sortieren (häufigste zuerst)
    order = np.argsort(-np.bincount(lab, minlength=k))
    remap = {int(o): i for i, o in enumerate(order)}
    palette = ["#%02X%02X%02X" % tuple(int(round(v)) for v in cent[o]) for o in order]
    ys, xs = np.nonzero(mask)
    cells = [[int(x), int(y), remap[int(c)], kind] for x, y, c in zip(xs, ys, lab)]
    return cells, palette, rows
