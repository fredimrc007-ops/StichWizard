"""Stickschriften (aus Ink/Stitch umgewandelt): laden, Text setzen, Stiche erzeugen."""
import functools
import glob
import gzip
import json
import math
import os

from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from . import engine, satin

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
USER_PREFIX = "eigen_"          # eigene Schriften (Schrift-Werkstatt) im Benutzerordner


def user_dir():
    from PySide6.QtCore import QStandardPaths
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or \
        os.path.expanduser("~/.local/share/StickStudio")
    d = os.path.join(base, "schriften")
    os.makedirs(d, exist_ok=True)
    return d


def font_path(fid):
    if fid.startswith(USER_PREFIX):
        return os.path.join(user_dir(), fid + ".json.gz")
    return os.path.join(FONT_DIR, fid + ".json.gz")


def reload():
    """Nach dem Speichern einer eigenen Schrift: Verzeichnis neu einlesen."""
    font_index.cache_clear()
    load.cache_clear()
    render.cache_clear()
    letter_centers.cache_clear()


@functools.lru_cache(maxsize=None)
def font_index():
    """Alle verfügbaren Stickschriften: [(id, name, size, lizenz, schlagworte)]."""
    out = []
    paths = sorted(glob.glob(os.path.join(FONT_DIR, "*.json.gz")))
    try:
        paths += sorted(glob.glob(os.path.join(user_dir(), USER_PREFIX + "*.json.gz")))
    except OSError:
        pass
    for path in paths:
        fid = os.path.basename(path)[:-8]
        meta = load(fid)
        out.append({"id": fid, "name": meta["name"], "size": meta["size"],
                    "min": meta["size"] * meta["min_scale"], "max": meta["size"] * meta["max_scale"],
                    "license": meta["license"], "keywords": meta.get("keywords", []),
                    "description": meta.get("description", ""), "colors": len(meta["colors"]),
                    "noncommercial": "NC" in meta["license"].upper().replace("-", " ").split()
                    or "NC" in meta["license"].upper(),
                    "chars": {k.split(".")[0] for k in meta["glyphs"] if len(k.split(".")[0]) == 1},
                    "case": meta.get("letter_case", "")})
    out.sort(key=lambda f: f["name"].lower())
    return out


def missing_chars(info, text):
    """Zeichen aus `text`, die die Schrift nicht enthält (Leerzeichen zählen nicht)."""
    if info.get("case") == "upper":
        text = text.upper()
    elif info.get("case") == "lower":
        text = text.lower()
    return sorted({c for c in text if not c.isspace() and c not in info["chars"]})


@functools.lru_cache(maxsize=12)
def load(fid):
    with gzip.open(font_path(fid), "rt", encoding="utf-8") as f:
        return json.load(f)


def exists(fid):
    return bool(fid) and os.path.exists(font_path(fid))


def layout(font, text, letter_spacing=0.0):
    """Wie Ink/Stitch: Glyphen mit Vorschub, Kerning und Wortabstand setzen.
    Liefert [(glyphname, x, y)] in Schrifteinheiten (mm bei Maßstab 1)."""
    if font.get("letter_case") == "upper":
        text = text.upper()
    elif font.get("letter_case") == "lower":
        text = text.lower()
    gl = font["glyphs"]
    placed = []
    y = 0.0
    for line in text.split("\n"):
        x = 0.0
        last = None
        for i, ch in enumerate(line):
            if ch == " " or ch not in gl and ch.isspace():
                x += font["space"]
                last = None
                continue
            name = ch if ch in gl else _positional(gl, line, i)
            if name is None:
                name = font.get("default_glyph") if font.get("default_glyph") in gl else None
            if name is None:
                x += font["space"]
                last = None
                continue
            g = gl[name]
            if last is not None:
                k = font["kern"].get(f"{last} {name}", font["kern"].get(last + name, 0.0))
                x += g["mx"] - k + letter_spacing
            placed.append((name, x, y))
            adv = font["adv"].get(name, font["adv_default"] if font["adv_default"] is not None
                                  else g["w"] + g["mx"])
            x += adv - g["mx"]
            last = name
        y += font["leading"]
    return placed


def _positional(gl, line, i):
    """Schriften mit Anfangs-/Mittel-/Endformen (z. B. Monogramme): passende Form wählen."""
    ch = line[i]
    before = i > 0 and not line[i - 1].isspace()
    after = i + 1 < len(line) and not line[i + 1].isspace()
    form = ("medi" if before and after else "init" if after else "fina" if before else "isol")
    for f in (form, "isol", "init", "medi", "fina"):
        if f"{ch}.{f}" in gl:
            return f"{ch}.{f}"
    return None


def _glyph_xform(placed, font, s, arc, path=None, path_align="center", path_flip=False):
    """Je Glyphe eine Abbildung Glyphenkoordinaten -> mm: Maßstab, Position, ggf. Bogen bzw.
    Pfad (dann steht jede Glyphe mit ihrer Grundlinie auf dem Pfad)."""
    if not placed:
        return []
    widths = [font["glyphs"][n]["w"] for n, _, _ in placed]
    x0 = min(x for _, x, _ in placed)
    x1 = max(x + w for (_, x, _), w in zip(placed, widths))
    cx = (x0 + x1) / 2
    pp = None
    if path:
        from .textpath import PathPlacer
        pp = PathPlacer(path, path_flip)
        start = pp.start((x1 - x0) * s, path_align)
    out = []
    for (name, x, y), w in zip(placed, widths):
        if pp is not None:
            a = start + (x - x0) * s
            mx, my, th = pp.place(a, a + w * s)
            out.append(("arc", s, th, w / 2, mx, my))
        elif arc:
            th = (x + w / 2 - cx) * s / arc          # Winkel auf dem Kreis (Radius = arc mm)
            out.append(("arc", s, th, w / 2, arc * math.sin(th), arc * (1 - math.cos(th))))
        else:
            out.append(("lin", s, 0.0, 0.0, x * s, y * s))
    return out


def _apply(pts, xf):
    kind, s, th, half, tx, ty = xf
    if kind == "lin":
        return [(px * s + tx, py * s + ty) for px, py in pts]
    c, si = math.cos(th), math.sin(th)
    out = []
    for px, py in pts:
        lx, ly = (px - half) * s, py * s
        out.append((lx * c - ly * si + tx, lx * si + ly * c + ty))
    return out


def _rails(e, P):
    """Schienen in der Richtung, die die Schrift vorgibt (Ink/Stitch »reverse_rails«,
    »swap_satin_rails«). Liefert (a, b, automatisch_ausrichten)."""
    a, b = P(e["a"]), P(e["b"])
    rr = e.get("rr", "automatic")
    if rr in ("first", "both"):
        a = a[::-1]
    if rr in ("second", "both"):
        b = b[::-1]
    if e.get("sw"):
        a, b = b, a
    # »automatic« (und ältere Schriften ohne Angabe): Richtung selbst erkennen
    return a, b, rr in (None, "", "automatic")


def _satin_args(e, cfg):
    return dict(spacing=cfg["density"] or e["sp"], pull=e["pc"] + cfg["pull"],
                pull_pct=e.get("pp", 0.0), center_walk=e["cw"], contour=e["co"],
                zigzag_underlay=e["zu"] and cfg["underlay"], underlay_inset=e["in"],
                underlay_spacing=e["us"], max_len=e["mx"], kind=e.get("k", "satin"),
                short_inset=e.get("si", 15.0) / 100.0, short_dist=e.get("sd", 0.25))


def _ripple(e, P):
    """Ripple-Linien (Ink/Stitch »ripple stitch« zwischen zwei Schienen): n Linien zwischen
    Schiene A und B, im Zickzack hin und her gestickt; skip_start/skip_end lassen die äußeren
    Linien weg."""
    a, b, auto = _rails(e, P)
    rungs = [getattr(P, "plain", P)(r) for r in e.get("r", [])]
    prs = satin.pairs(a, b, rungs, 1.0, align=auto)
    n = max(2, int(e.get("n", 6)))
    out = []
    for k in range(int(e.get("s0", 0)), n - int(e.get("s1", 0))):
        t = k / (n - 1)
        line = [(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t) for p, q in prs]
        if len(out) % 2:
            line = line[::-1]
        out.append(line)
    seq = [p for line in out for p in line]
    return engine.running_stitch(seq, e.get("sl", 2.5)) if len(seq) >= 2 else []


def _el_stitches(e, P, cfg):
    t = e["t"]
    if t == "satin":
        a, b, auto = _rails(e, P)
        rungs = [getattr(P, "plain", P)(r) for r in e["r"]]
        return [satin.satin_stitches(a, b, rungs, align=auto, **_satin_args(e, cfg))]
    if t == "ripple":
        r = _ripple(e, P)
        return [r] if len(r) >= 2 else []
    if t == "fill":
        rings = [Polygon(P(r)).buffer(0) for r in e["rings"] if len(r) >= 3]
        geom = None
        for p in rings:
            geom = p if geom is None else geom.symmetric_difference(p)
        if geom is None or geom.is_empty:
            return []
        bounds = geom.bounds
        if e.get("ex"):                      # Fläche erweitern, damit sie unter den Rand reicht
            geom = geom.buffer(e["ex"], join_style=2)
        m = e.get("m", "tatami")
        fill = {"type": m if m in ("contour", "cross", "meander", "guided") else "tatami",
                "angle": e["an"], "density": e["rs"], "stitch_len": e["ml"],
                "underlay": e["ul"] and cfg["underlay"], "pull": max(0.1, e.get("pc", 0.0)),
                "size": e.get("ps", 3.0)}
        if m == "cross":
            # Kästchengröße wächst mit der Schrift; Raster an der Ecke der Form ausrichten,
            # damit die Kreuze genau auf den »Pixeln« der Schrift sitzen
            q0, q1 = getattr(P, "plain", P)([(0.0, 0.0), (1.0, 0.0)])
            scale = math.hypot(q1[0] - q0[0], q1[1] - q0[1]) or 1.0
            fill.update(size=2 * e.get("ps", 3.0) * scale, angle=e["an"] + 45,
                        grid_origin=(bounds[0], bounds[1]), underlay=False)
        if m == "guided" and e.get("g"):
            fill["guide"] = [list(q) for q in getattr(P, "plain", P)(e["g"])]
        out = engine.fill_with_underlay(geom, fill)
        runs, cur = [], []
        for x, y, f in out:            # an Sprüngen in einzelne Läufe teilen
            if f == engine.STITCH:
                cur.append((x, y))
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        return [r for r in runs if len(r) >= 2]
    res = []
    for line in e["lines"]:
        if t == "manual":                     # jeder Punkt ist genau ein Einstich
            res.append(engine.manual_stitch(getattr(P, "plain", P)(line)))
            continue
        pts = P(line)
        if t == "zigzag" and e["w"] >= 0.6:
            res.append(engine.satin_line(pts, e["w"], 0.4, closed=False, underlay=False))
            continue
        run = engine.running_stitch(pts, e["sl"], triple=e["bn"] >= 1)
        if e["rp"] > 1:
            seq = run
            for k in range(1, e["rp"]):
                seq = seq + (run[::-1] if k % 2 else run)[1:]
            run = seq
        res.append(run)
    return res


def _el_shape(e, P):
    if e["t"] in ("satin", "ripple"):
        return satin.outline(P(e["a"]), P(e["b"]))
    if e["t"] == "fill":
        return unary_union([Polygon(P(r)).buffer(0) for r in e["rings"] if len(r) >= 3])
    w = max(e.get("w", 0), 0.6)
    return unary_union([LineString(P(l)).buffer(w / 2) for l in e["lines"] if len(l) >= 2])


def _units(e, P, cfg):
    """Stickeinheiten eines Elements: [{"fwd": [läufe], "rev": [läufe] | None, "foot", "satin"}].
    Satinsäulen und Linien dürfen auch rückwärts gestickt werden (wie Ink/Stitch »Auto-Satin«)."""
    t = e["t"]
    if t == "satin":
        a, b, auto = _rails(e, P)
        rungs = [getattr(P, "plain", P)(r) for r in e["r"]]
        args = dict(_satin_args(e, cfg), align=auto)
        fwd = satin.satin_stitches(a, b, rungs, **args)
        rev = satin.satin_stitches(a[::-1], b[::-1], rungs, **args)
        if len(fwd) < 2:
            return []
        return [{"fwd": [fwd], "rev": [rev] if len(rev) >= 2 else None,
                 "foot": satin.outline(a, b), "satin": True}]
    runs = _el_stitches(e, P, cfg)
    if t == "fill":
        runs = [r for r in runs if len(r) >= 2]
        if not runs:
            return []
        return [{"fwd": runs, "rev": None, "foot": _el_shape(e, P), "satin": False}]
    out = []
    w = max(e.get("w", 0), 0.6)
    for r in runs:
        if len(r) >= 2:
            out.append({"fwd": [r], "rev": [r[::-1]], "foot": LineString(r).buffer(w / 2 + 0.2),
                        "satin": t == "zigzag"})
    return out


def _route_units(units, pos, target=None, fixed=False):
    """Einheiten eines Buchstabens (eine Farbe) so ordnen und verbinden, dass möglichst wenig
    gesprungen wird. Verbindungen laufen als Steppstich unter Einheiten, die noch kommen.
    target: Startpunkt des nächsten Buchstabens – die letzte Einheit soll nah daran enden.
    fixed: Reihenfolge des Schriftgestalters beibehalten, nur Richtung und Verbindungen wählen.
    Liefert Läufe; ein Lauf, der an `pos` ansetzt, beginnt mit `pos`."""
    from .optimize import _route, _travel_points
    n = len(units)
    if n == 0:
        return [], pos
    pred = [set() for _ in range(n)]
    for j in range(n):
        for i in range(j):
            fi, fj = units[i]["foot"], units[j]["foot"]
            if fi is None or fj is None or fi.is_empty or fj.is_empty or not fi.intersects(fj):
                continue
            ov = fi.intersection(fj).area
            if units[i]["satin"] and units[j]["satin"]:
                if ov > 0.4 * min(fi.area, fj.area):          # übereinanderliegende Säulen
                    pred[j].add(i)
            elif ov > 0.2:
                pred[j].add(i)
    done, out = set(), []
    while len(done) < n:
        avail = [len(done)] if fixed else [j for j in range(n) if j not in done and pred[j] <= done]
        rest = [units[j]["foot"] for j in range(n) if j not in done and units[j]["foot"] is not None]
        cover = unary_union(rest).buffer(-0.15) if rest else None
        cands = []
        for j in avail:
            for runs in (units[j]["fwd"], units[j]["rev"]):
                if runs is None:
                    continue
                start = runs[0][0]
                if pos is None:
                    cands.append((0 if not cands else 1e9, j, runs, None))
                    continue
                d = engine.dist(pos, start)
                if d <= engine.DIRECT_TRAVEL:
                    cands.append((d, j, runs, None))
                elif cover is not None and not cover.is_empty and d < 30 and \
                        cover.covers(LineString([pos, start])):
                    cands.append((d * 1.1, j, runs, [pos, start]))
                else:
                    cands.append((d + 40 + (15 if d > engine.TRIM_DISTANCE else 0), j, runs, "?"))
        if target is not None and len(avail) == 1 and len(done) == n - 1:
            cands = [(c[0] + 0.8 * engine.dist(c[2][-1][-1], target),) + c[1:] for c in cands]
        cands.sort(key=lambda c: c[0])
        # für die nächstgelegenen Kandidaten einen Umweg unter späteren Einheiten suchen
        best = cands[0]
        tried = 0
        for c in sorted(cands, key=lambda c: engine.dist(pos, c[2][0][0]) if pos else 0):
            if c[3] != "?" or tried >= 3 or c[0] - 40 > best[0]:
                continue
            tried += 1
            path = _route(pos, c[2][0][0], cover)
            if path is not None:
                ln = sum(engine.dist(p, q) for p, q in zip(path, path[1:]))
                extra = c[0] - (engine.dist(pos, c[2][0][0]) + 40 +
                                (15 if engine.dist(pos, c[2][0][0]) > engine.TRIM_DISTANCE else 0))
                if ln * 1.2 + extra < best[0]:
                    best = (ln * 1.2 + extra, c[1], c[2], path)
        _, j, runs, path = best
        runs = [list(r) for r in runs]
        if isinstance(path, list) and pos is not None:
            runs[0] = [pos] + _travel_points(path)[:-1] + runs[0]
        out.extend(runs)
        done.add(j)
        pos = runs[-1][-1]
    return out, pos


def _score(runs, pos, target):
    """Bewertung einer Stichfolge: Sprünge, Schnitte und Weg zum nächsten Buchstaben."""
    cost, last = 0.0, pos
    for r in runs:
        if last is not None:
            d = engine.dist(last, r[0])
            if d > engine.DIRECT_TRAVEL:
                cost += 10 + (6 if d > engine.TRIM_DISTANCE else 0) + d * 0.05
        last = r[-1]
    if target is not None and last is not None:
        d = engine.dist(last, target)
        cost += d * 0.05 + (6 if d > engine.TRIM_DISTANCE else 0)
    return cost


def _best_route(units, pos, target):
    """Original, Originalreihenfolge mit besten Richtungen oder frei optimiert – je nachdem,
    was am wenigsten springt (gut digitalisierte Schriften bleiben so, wie sie sind)."""
    raw = [r for u in units for r in u["fwd"]]
    options = [(raw, raw[-1][-1] if raw else pos)]
    for fixed in (True, False):
        try:
            options.append(_route_units(units, pos, target, fixed))
        except Exception:
            pass
    return min(options, key=lambda o: _score(o[0], pos, target))


def _center(placed, xfs, font, outline, letters, envelope):
    """Mitte für das Zentrieren – immer vom Schriftzug ohne einzeln verschobene Buchstaben, damit
    das Verschieben eines Buchstabens die anderen nicht mitbewegt."""
    if letters:
        base = _glyph_mappers(placed, xfs, font, (), envelope)
        shapes = [_el_shape(e, P) for (name, _, _), P in zip(placed, base)
                  for e in font["glyphs"][name]["e"]]
        outline = unary_union([sh for sh in shapes if sh is not None and not sh.is_empty])
    minx, miny, maxx, maxy = outline.bounds
    return (minx + maxx) / 2, (miny + maxy) / 2


def _glyph_points(g, P):
    pts = []
    for e in g["e"]:
        if e["t"] in ("satin", "ripple"):
            pts += P(e["a"]) + P(e["b"])
        elif e["t"] == "fill":
            for r in e["rings"]:
                pts += P(r)
        else:
            for line in e["lines"]:
                pts += P(line)
    return pts


def _bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _glyph_mappers(placed, xfs, font, letters, envelope):
    """Je Glyphe die Abbildung Glyphenpunkte -> mm, inkl. einzeln verschobener Buchstaben und
    Hüllform. Die Funktion hat ein Attribut »plain« ohne Unterteilung (für Satin-Sprossen)."""
    from . import textfx
    lmap = {int(i): tuple(v) for i, *v in (letters or ())}
    mappers, allpts = [], []
    for gi, ((name, _, _), xf) in enumerate(zip(placed, xfs)):
        g = font["glyphs"][name]
        base = (lambda pts, xf=xf: _apply(pts, xf))
        pts = _glyph_points(g, base)
        if gi in lmap and pts:
            b = _bbox(pts)
            lt = textfx.letter_transform(lmap[gi], ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
            fn = (lambda q, base=base, lt=lt: [lt(x, y) for x, y in base(q)])
        else:
            fn = base
        mappers.append(fn)
        allpts += pts                 # Grenzen ohne Verschiebung: andere Buchstaben bleiben stehen
    warp = None
    if envelope and allpts:
        warp = textfx.make_warp(envelope[0], envelope[1], _bbox(allpts))
    out = []
    for fn in mappers:
        if warp is None:
            fn.plain = fn
            out.append(fn)
            continue
        f = (lambda q, fn=fn: [warp(x, y) for x, y in textfx.densify(fn(q))])
        f.plain = (lambda q, fn=fn: [warp(x, y) for x, y in fn(q)])
        out.append(f)
    return out


@functools.lru_cache(maxsize=64)
def render(fid, text, size, letter_spacing=0.0, arc=0.0, density=0.0, pull=0.0,
           underlay=True, color=None, path=None, path_align="center", path_flip=False,
           envelope=None, letters=()):
    """Text in Stickschrift -> (blöcke [(farbe, stiche)], umriss) zentriert im Ursprung.
    path: Tupel von Punkten (mm) – Text entlang dieses Pfads, dann ohne Zentrieren.
    size: Höhe der Großbuchstaben in mm. Farbe None = Objektfarbe (einfarbige Schriften);
    mehrfarbige Schriften behalten ihre Originalfarben. Ergebnis ist zwischengespeichert –
    nicht verändern. envelope: (art, stärke) Hüllform; letters: ((index, dx, dy, drehung,
    größe%), …) einzeln verschobene Buchstaben."""
    font = load(fid)
    s = size / font["size"]
    if path:
        text = " ".join(text.split("\n"))
    placed = layout(font, text, letter_spacing / max(s, 1e-6))
    xfs = _glyph_xform(placed, font, s, arc, path, path_align, path_flip)
    single = len(font["colors"]) <= 1
    cfg = {"density": density, "pull": pull, "underlay": underlay}
    shapes, groups = [], []          # groups: [(farbe, einheiten)] in Stickreihenfolge
    mappers = _glyph_mappers(placed, xfs, font, letters, envelope)
    for (name, gx, gy), xf, P in zip(placed, xfs, mappers):
        g = font["glyphs"][name]
        for e in g["e"]:
            col = color if single or not e.get("c") else e["c"]
            units = _units(e, P, cfg)
            if groups and groups[-1][0] == col and groups[-1][2] == name and groups[-1][3] is xf:
                groups[-1][1].extend(units)
            else:
                groups.append((col, units, name, xf))
            shapes.append(_el_shape(e, P))
    # gleichfarbige Elemente eines Buchstabens: Reihenfolge und Richtung optimieren
    runs, pos = [], None
    for gi, (col, units, _, _) in enumerate(groups):
        if runs and runs[-1][0] != col:
            pos = None
        nxt = groups[gi + 1] if gi + 1 < len(groups) else None
        target = nxt[1][0]["fwd"][0][0] if nxt and nxt[0] == col and nxt[1] else None
        seq, pos = _best_route(units, pos, target)
        runs.extend((col, pts) for pts in seq if len(pts) >= 2)
    outline = unary_union([sh for sh in shapes if sh is not None and not sh.is_empty])
    if outline.is_empty:
        return [], outline
    cx, cy = (0.0, 0.0) if path else _center(placed, xfs, font, outline, letters, envelope)
    outline = affinity.translate(outline, -cx, -cy)
    # Läufe gleicher Farbe nacheinander zu Blöcken verbinden (Sprünge/Schnitte automatisch)
    blocks = []
    for col, pts in runs:
        pts = [(x - cx, y - cy) for x, y in pts]
        if not blocks or blocks[-1][0] != col:
            blocks.append((col, []))
        engine.connect(blocks[-1][1], pts)
    return [(c, engine.finish(b)) for c, b in blocks if b], outline


@functools.lru_cache(maxsize=32)
def letter_centers(fid, text, size, letter_spacing=0.0, arc=0.0, path=None, path_align="center",
                   path_flip=False, envelope=None, letters=()):
    """Mitten der einzelnen Buchstaben im selben Koordinatensystem wie render():
    [(index, zeichen, x, y)] – für die Anfasser beim Verschieben einzelner Buchstaben."""
    font = load(fid)
    s = size / font["size"]
    if path:
        text = " ".join(text.split("\n"))
    placed = layout(font, text, letter_spacing / max(s, 1e-6))
    xfs = _glyph_xform(placed, font, s, arc, path, path_align, path_flip)
    mappers = _glyph_mappers(placed, xfs, font, letters, envelope)
    shapes, centers = [], []
    for gi, ((name, _, _), P) in enumerate(zip(placed, mappers)):
        g = font["glyphs"][name]
        pts = _glyph_points(g, getattr(P, "plain", P))
        for e in g["e"]:
            shapes.append(_el_shape(e, P))
        if pts:
            b = _bbox(pts)
            ch = name.split(".")[0]
            centers.append((gi, ch, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
    outline = unary_union([sh for sh in shapes if sh is not None and not sh.is_empty])
    if outline.is_empty:
        return []
    cx, cy = (0.0, 0.0) if path else _center(placed, xfs, font, outline, letters, envelope)
    return [(i, ch, x - cx, y - cy) for i, ch, x, y in centers]
