"""Text -> Flächengeometrie (über Qt-Schriftpfade)."""
import math

from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath, QTransform
from shapely import affinity
from shapely.geometry import Polygon

_BASE = 200.0  # interne Pixelgröße für sauberes Abtasten


def _make_font(font, bold, italic):
    f = QFont(font)
    f.setPixelSize(int(_BASE))
    f.setBold(bold)
    f.setItalic(italic)
    return f


def _path_to_geom(path):
    geom = None
    for qpoly in path.toSubpathPolygons():
        pts = [(p.x(), p.y()) for p in qpoly]
        if len(pts) < 3:
            continue
        poly = Polygon(pts).buffer(0)
        if poly.is_empty:
            continue
        geom = poly if geom is None else geom.symmetric_difference(poly)
    return geom


def _char_paths(text, f, fm, scale, arc, line_spacing, guide, path_align, path_flip):
    """[(index, zeichen, QPainterPath in Schrifteinheiten)] – je Buchstabe ein Pfad, damit
    Buchstaben einzeln verschoben werden können. index zählt Zeichen ohne Leerraum."""
    lines = text.split("\n") if text else [" "]
    out, idx = [], 0
    if guide:
        from .textpath import PathPlacer
        line = " ".join(lines)
        pp = PathPlacer(guide, path_flip)
        total = fm.horizontalAdvance(line)
        s0 = pp.start(total * scale, path_align)
        for i, ch in enumerate(line):
            if ch.isspace():
                continue
            adv = fm.horizontalAdvance(ch)
            x0 = fm.horizontalAdvance(line[:i])
            mx, my, th = pp.place(s0 + x0 * scale, s0 + (x0 + adv) * scale)
            gp = QPainterPath()
            gp.addText(-adv / 2, 0, f, ch)
            t = QTransform()
            t.translate(mx / scale, my / scale)
            t.rotate(math.degrees(th))
            out.append((idx, ch, t.map(gp)))
            idx += 1
    elif arc and len(lines) == 1:
        line = lines[0]
        r = arc / scale
        total = fm.horizontalAdvance(line)
        for i, ch in enumerate(line):
            if ch.isspace():
                continue
            adv = fm.horizontalAdvance(ch)
            xc = fm.horizontalAdvance(line[:i]) + adv / 2 - total / 2
            theta = xc / r
            gp = QPainterPath()
            gp.addText(-adv / 2, 0, f, ch)
            t = QTransform()
            t.translate(r * math.sin(theta), r - r * math.cos(theta))
            t.rotate(math.degrees(theta))
            out.append((idx, ch, t.map(gp)))
            idx += 1
    else:
        lh = fm.lineSpacing() * line_spacing
        for li, line in enumerate(lines):
            w = fm.horizontalAdvance(line)
            for i, ch in enumerate(line):
                if ch.isspace():
                    continue
                gp = QPainterPath()
                gp.addText(-w / 2 + fm.horizontalAdvance(line[:i]), li * lh, f, ch)
                out.append((idx, ch, gp))
                idx += 1
    return out


def _letter_adjusted(chars, letters, scale):
    """Einzeln verschobene/gedrehte/skalierte Buchstaben anwenden (Werte in mm)."""
    from .textfx import letter_map
    lmap = letter_map(letters)
    if not lmap:
        return chars
    out = []
    for i, ch, gp in chars:
        if i in lmap:
            dx, dy, rot, sc = lmap[i]
            c = gp.boundingRect().center()
            t = QTransform()
            t.translate(c.x() + dx / scale, c.y() + dy / scale)
            t.rotate(rot)
            t.scale(sc / 100.0, sc / 100.0)
            t.translate(-c.x(), -c.y())
            gp = t.map(gp)
        out.append((i, ch, gp))
    return out


def _layout(text, font, size, bold, italic, spacing, arc, line_spacing, path, path_align,
            path_flip, letters):
    guide = path if path and len(path) >= 2 else None
    f = _make_font(font, bold, italic)
    fm = QFontMetricsF(f)
    cap = fm.capHeight() or fm.ascent() * 0.7
    scale = size / cap
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing / scale)
        fm = QFontMetricsF(f)
    chars = _char_paths(text, f, fm, scale, arc, line_spacing, guide, path_align, path_flip)
    return _letter_adjusted(chars, letters, scale), scale, guide, chars


def _chars_geom(chars):
    """Buchstaben vereinigen (überlappende, verschobene Buchstaben dürfen sich nicht
    gegenseitig ausschneiden)."""
    from shapely.ops import unary_union
    parts = [g for g in (_path_to_geom(gp) for _, _, gp in chars) if g is not None and not g.is_empty]
    return unary_union(parts) if parts else None


def text_geometry(text="Text", font="DejaVu Sans", size=20.0, bold=False,
                  italic=False, spacing=0.0, arc=0.0, line_spacing=1.25, path=None,
                  path_align="center", path_flip=False, env="none", env_amount=0.3,
                  letters=None, **_):
    """Liefert zentrierte shapely-Geometrie. size = Höhe der Großbuchstaben in mm,
    arc = Bogenradius in mm (0 = gerade, >0 Bogen nach oben, <0 nach unten).
    path: Polygonzug in mm – der Text steht dann auf diesem Pfad (nicht zentriert, damit er
    genau auf der Linie liegt); path_align: start | center | end, path_flip: andere Seite.
    env/env_amount: Hüllform (textfx.ENVELOPES); letters: einzeln verschobene Buchstaben."""
    chars, scale, guide, raw_chars = _layout(text, font, size, bold, italic, spacing, arc,
                                             line_spacing, path, path_align, path_flip, letters)
    geom = _chars_geom(chars)
    if geom is None:
        return Polygon()
    geom = affinity.scale(geom, scale, scale, origin=(0, 0))
    # Hüllform und Mitte immer vom unverschobenen Schriftzug (andere Buchstaben bleiben stehen)
    raw = geom if raw_chars is chars else affinity.scale(_chars_geom(raw_chars), scale, scale,
                                                          origin=(0, 0))
    warp = None
    if env and env != "none" and not geom.is_empty:
        from .textfx import make_warp, warp_geometry
        warp = make_warp(env, env_amount, raw.bounds)
        geom = warp_geometry(geom, warp)
        raw = geom if raw_chars is chars else warp_geometry(raw, warp)
    if guide:
        return geom.simplify(0.04)
    minx, miny, maxx, maxy = raw.bounds
    geom = affinity.translate(geom, -(minx + maxx) / 2, -(miny + maxy) / 2)
    return geom.simplify(0.04)


def letter_centers(text="Text", font="DejaVu Sans", size=20.0, bold=False, italic=False,
                   spacing=0.0, arc=0.0, line_spacing=1.25, path=None, path_align="center",
                   path_flip=False, env="none", env_amount=0.3, letters=None, **_):
    """Buchstabenmitten im selben Koordinatensystem wie text_geometry: [(index, zeichen, x, y)]."""
    chars, scale, guide, raw_chars = _layout(text, font, size, bold, italic, spacing, arc,
                                             line_spacing, path, path_align, path_flip, letters)
    if not chars:
        return []
    pts = []
    for i, ch, gp in chars:
        c = gp.boundingRect().center()
        pts.append((i, ch, c.x() * scale, c.y() * scale))
    g = _chars_geom(raw_chars)
    raw = affinity.scale(g, scale, scale, origin=(0, 0)) if g is not None else None
    if raw is None or raw.is_empty:
        return []
    warp = None
    if env and env != "none":
        from .textfx import make_warp, warp_geometry
        warp = make_warp(env, env_amount, raw.bounds)
        raw = warp_geometry(raw, warp)
    if warp is not None:
        pts = [(i, ch) + warp(x, y) for i, ch, x, y in pts]
    if guide:
        return pts
    minx, miny, maxx, maxy = raw.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    return [(i, ch, x - cx, y - cy) for i, ch, x, y in pts]
