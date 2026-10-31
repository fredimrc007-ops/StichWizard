"""Wandelt Ink/Stitch-Stickschriften (SVG + font.json) in das kompakte StichWizard-Format um.

Aufruf: python tools/convert_inkstitch_fonts.py <ink-stitch-fonts/src> <zielordner>
Jede Schrift wird zu <id>.json.gz: Metriken in mm und je Glyphe die Stickelemente
(Satinsäulen mit Schienen/Stegen, Steppstiche, Flächen) samt Ink/Stitch-Parametern.
"""
import gzip
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shapely.geometry import LineString  # noqa: E402

from stichwizard import svgpath  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"
INK = "{http://www.inkscape.org/namespaces/inkscape}"
SODI = "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}"
IS = "{http://inkstitch.org/namespace}"
PX = 25.4 / 96      # mm pro px
UNITS = {"px": 1, "": 1, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96, "pt": 96 / 72, "pc": 16}


def length_px(v):
    m = re.match(r"\s*([-+0-9.eE]+)\s*([a-z%]*)", v or "")
    if not m:
        return None
    return float(m.group(1)) * UNITS.get(m.group(2), 1)


def style_of(el):
    st = {}
    for part in (el.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            st[k.strip()] = v.strip()
    for k in ("fill", "stroke", "stroke-width", "stroke-dasharray", "display"):
        if el.get(k) is not None and k not in st:
            st[k] = el.get(k)
    return st


def color_of(v):
    if not v or v == "none" or v.startswith("url"):
        return None
    if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return v.upper()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", v):
        return "#" + "".join(c * 2 for c in v[1:]).upper()
    return "#000000"


def params(el):
    return {k[len(IS):]: v for k, v in el.attrib.items() if k.startswith(IS)}


def as_bool(v, default=False):
    if v is None or v == "":
        return default
    return str(v).lower() in ("true", "1", "yes")


def as_float(v, default):
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def rnd(pts, mm, ox, oy, simplify=0.01):
    p = [((x - ox) * mm, (y - oy) * mm) for x, y in pts]
    if simplify and len(p) > 2:
        p = list(LineString(p).simplify(simplify).coords)
    return [[round(x, 3), round(y, 3)] for x, y in p]


def find_baseline(root, doc_h, glyph_bottoms):
    cands = []
    for g in root.iter(SODI + "guide"):
        if (g.get(INK + "label") or "").lower() == "baseline":
            y = float(g.get("position").replace(",", " ").split()[1])
            cands += [y, doc_h - y]
    if not cands:
        return 0.0
    if glyph_bottoms:
        ref = sorted(glyph_bottoms)[len(glyph_bottoms) // 2]
        return min(cands, key=lambda c: abs(c - ref))
    return cands[0]


def is_guide(st, el):
    """Führungslinie einer geführten Füllung (Ink/Stitch-Marker) – wird nie gestickt."""
    marker = (st.get("marker-start") or "") + (el.get("marker-start") or "")
    return "guide-line" in marker or (el.get(IS + "guide") or "").lower() == "true"


def pick_rails(subs):
    """Die beiden Schienen einer Satinsäule finden (wie Ink/Stitch): Stege schneiden beide
    Schienen. Bei genau zwei Pfaden sind das die Schienen; sonst das Paar, das die meisten
    übrigen Pfade kreuzen (bei Gleichstand das längere)."""
    if len(subs) == 2:
        return subs[0], subs[1], []
    lines = [LineString(s[0]) if len(s[0]) >= 2 else None for s in subs]
    best = None
    for i in range(len(subs)):
        for j in range(i + 1, len(subs)):
            if lines[i] is None or lines[j] is None:
                continue
            hits = sum(1 for k, ln in enumerate(lines)
                       if k not in (i, j) and ln is not None
                       and ln.intersects(lines[i]) and ln.intersects(lines[j]))
            key = (hits, lines[i].length + lines[j].length)
            if best is None or key > best[0]:
                best = (key, i, j)
    _, i, j = best
    rungs = [s for k, s in enumerate(subs) if k not in (i, j) and len(s[0]) >= 2]
    return subs[i], subs[j], rungs


def collect(el, m, out, hidden=False):
    """Alle sichtbaren Pfade einer Glyphe mit Gesamttransformation sammeln."""
    for c in el:
        tag = c.tag
        st = style_of(c)
        if tag == SVG + "g":
            collect(c, svgpath.mul(m, svgpath.parse_transform(c.get("transform"))), out)
        elif tag == SVG + "path":
            if st.get("display") == "none" or c.get(INK + "connection-start") or \
                    c.get(INK + "connection-end"):
                continue
            out.append((c, svgpath.mul(m, svgpath.parse_transform(c.get("transform"))), st))


def convert_font(folder, dest):
    meta = json.load(open(os.path.join(folder, "font.json"), encoding="utf-8"))
    if meta.get("text_direction", "ltr") == "rtl":
        return None
    svgs = [f for f in os.listdir(folder) if f.endswith(".svg")]
    pick = next((f for f in ("ltr.svg", "→.svg") if f in svgs), svgs[0] if svgs else None)
    if not pick:
        return None
    root = ET.parse(os.path.join(folder, pick)).getroot()
    vb = [float(v) for v in re.split(r"[ ,]+", root.get("viewBox", "").strip()) if v] or None
    wpx = length_px(root.get("width"))
    hpx = length_px(root.get("height"))
    scale = (wpx / vb[2]) if (vb and wpx) else 1.0
    mm = scale * 25.4 / 96
    doc_h = vb[3] if vb else (hpx or 0)

    layers = {}
    for g in root.iter(SVG + "g"):
        lbl = g.get(INK + "label") or ""
        if lbl.startswith("GlyphLayer-"):
            layers[lbl[len("GlyphLayer-"):]] = g

    raw = {}
    bottoms = []
    for name, g in layers.items():
        items = []
        collect(g, svgpath.parse_transform(g.get("transform")), items)
        if not items:
            continue
        raw[name] = items
        if name in ("H", "n", "x", "E", "I", "l"):
            ys = [y for el, m, _ in items for pts, _, _ in svgpath.parse_path(el.get("d"))
                  for _, y in svgpath.apply(m, pts)]
            if ys:
                bottoms.append(max(ys))
    base = find_baseline(root, doc_h, bottoms)

    glyphs = {}
    colors = set()
    for name, items in raw.items():
        geo = []
        for el, m, st in items:
            subs = [(svgpath.apply(m, pts), closed, n) for pts, closed, n in svgpath.parse_path(el.get("d"))]
            subs = [s for s in subs if len(s[0]) >= 2]
            if subs:
                geo.append((el, m, st, subs))
        if not geo:
            continue
        min_x = min(x for _, _, _, subs in geo for pts, _, _ in subs for x, _ in pts)
        max_x = max(x for _, _, _, subs in geo for pts, _, _ in subs for x, _ in pts)
        els = []
        guides = [rnd(subs[0][0], mm, min_x, base) for el, m, st, subs in geo if is_guide(st, el)]
        for el, m, st, subs in geo:
            if is_guide(st, el):
                continue
            p = params(el)
            fill, stroke = color_of(st.get("fill")), color_of(st.get("stroke"))
            dashed = st.get("stroke-dasharray") not in (None, "", "none")
            det = abs(m[0] * m[3] - m[1] * m[2]) ** 0.5 or 1.0
            method = p.get("stroke_method", "")
            if method == "ripple_stitch" and len(subs) >= 2:
                ra, rb, rungs = pick_rails(subs)
                e = {"t": "ripple", "a": rnd(ra[0], mm, min_x, base), "b": rnd(rb[0], mm, min_x, base),
                     "r": [rnd([s[0][0], s[0][-1]], mm, min_x, base, 0) for s in rungs],
                     "n": max(2, int(as_float(p.get("line_count"), 10))),
                     "s0": int(as_float(p.get("skip_start"), 0)), "s1": int(as_float(p.get("skip_end"), 0)),
                     "sl": as_float(p.get("running_stitch_length_mm"), 2.5) or 2.5,
                     "rr": p.get("reverse_rails", "automatic") or "automatic",
                     "c": stroke or fill}
            elif as_bool(p.get("satin_column")) and len(subs) >= 2:
                ra, rb, rungs = pick_rails(subs)
                sm = p.get("satin_method", "satin_column")
                kind = ("estitch" if as_bool(p.get("e_stitch")) or sm == "e_stitch" else
                        "zigzag" if sm in ("zigzag", "s_stitch") else "satin")
                e = {"t": "satin",
                     "a": rnd(ra[0], mm, min_x, base), "b": rnd(rb[0], mm, min_x, base),
                     "rr": p.get("reverse_rails", "automatic") or "automatic",
                     "sw": as_bool(p.get("swap_satin_rails")),
                     "si": as_float(p.get("short_stitch_inset"), 15.0),
                     "sd": as_float(p.get("short_stitch_distance_mm"), 0.25),
                     "pp": as_float(p.get("pull_compensation_percent"), 0.0),
                     "k": kind,
                     "r": [rnd([s[0][0], s[0][-1]], mm, min_x, base, 0) for s in rungs],
                     "sp": as_float(p.get("zigzag_spacing_mm"), 0.4),
                     "pc": as_float(p.get("pull_compensation_mm"), 0.0),
                     "cw": as_bool(p.get("center_walk_underlay")),
                     "co": as_bool(p.get("contour_underlay")),
                     "zu": as_bool(p.get("zigzag_underlay")),
                     "in": as_float(p.get("zigzag_underlay_inset_mm"), 0.0),
                     "us": as_float(p.get("zigzag_underlay_spacing_mm"), 3.0),
                     "mx": as_float(p.get("max_stitch_length_mm"), 8.0) or 8.0,
                     "c": stroke or fill}
            elif fill and not dashed and any(s[1] or len(s[0]) > 3 for s in subs):
                method = p.get("fill_method", "auto_fill")
                m_ = {"contour_fill": "contour", "cross_stitch": "cross", "meander_fill": "meander",
                      "guided_fill": "guided"}.get(method, "tatami")
                e = {"t": "fill", "rings": [rnd(s[0], mm, min_x, base) for s in subs if len(s[0]) >= 3],
                     "an": as_float(p.get("angle"), 0.0),
                     "rs": as_float(p.get("row_spacing_mm"), 0.25),
                     "ml": as_float(p.get("max_stitch_length_mm"), 3.0),
                     "ul": as_bool(p.get("fill_underlay"), True),
                     "m": m_,
                     "ex": as_float(p.get("expand_mm"), 0.0),
                     "pc": as_float(p.get("pull_compensation_mm"), 0.0),
                     "ps": as_float(p.get("pattern_size_mm"), 3.0) or 3.0,
                     "c": fill}
                if m_ == "guided":
                    if guides:
                        e["g"] = guides[0]
                    else:
                        e["m"] = "tatami"
            elif stroke:
                width = as_float(st.get("stroke-width", "").replace("px", ""), 0.0) * det * mm
                # Steppstich, wenn die Linie gestrichelt/dünn ist oder Steppstich-Angaben hat
                # (aktuelles Ink/Stitch: Linien sind Steppstich, Zickzack nur ausdrücklich)
                run_params = any(p.get(k) not in (None, "") for k in
                                 ("running_stitch_length_mm", "bean_stitch_repeats", "repeats"))
                kind = "run" if dashed or width < 0.6 or run_params or method == "running_stitch" \
                    else "zigzag"
                if method == "manual_stitch" or as_bool(p.get("manual_stitch")):
                    kind = "manual"
                elif method == "zigzag_stitch":
                    kind = "zigzag"
                    width = max(width, 1.0)
                reps = int(as_float(p.get("repeats"), 1))
                bean = str(p.get("bean_stitch_repeats") or "0").split()[0]
                e = {"t": kind, "lines": [rnd(s[0], mm, min_x, base) for s in subs],
                     "sl": as_float(p.get("running_stitch_length_mm"), 2.5) or 2.5,
                     "rp": max(1, reps), "bn": int(as_float(bean, 0)), "w": round(width, 3),
                     "c": stroke}
            else:
                continue
            colors.add(e["c"])
            els.append(e)
        if els:
            glyphs[name] = {"w": round((max_x - min_x) * mm, 3), "mx": round(min_x * mm, 3),
                            "e": els}

    fid = os.path.basename(folder.rstrip("/"))
    lic_text = ""
    for lf in ("LICENSE", "license", "LICENSE.txt", "LICENSE.md"):
        if os.path.exists(os.path.join(folder, lf)):
            lic_text = open(os.path.join(folder, lf), encoding="utf-8", errors="replace").read()
            break
    adv_def = meta.get("horiz_adv_x_default")
    out = {
        "id": fid, "name": meta.get("name", fid), "description": meta.get("description", ""),
        "keywords": meta.get("keywords", []), "license": meta.get("font_license", ""),
        "license_text": lic_text, "original_font": meta.get("original_font", ""),
        "size": float(meta.get("size") or 0) or None,
        "min_scale": float(meta.get("min_scale") or 1), "max_scale": float(meta.get("max_scale") or 1),
        # Abstände stehen in font.json immer in px (96 dpi) – auch wenn die Glyphen in mm sind
        "leading": float(meta.get("leading", 100)) * PX,
        "space": float(meta.get("horiz_adv_x_space", 20)) * PX,
        "adv_default": float(adv_def) * PX if adv_def not in (None, "") else None,
        "adv": {k: float(v) * PX for k, v in (meta.get("horiz_adv_x") or {}).items()},
        "kern": {k: float(v) * PX for k, v in (meta.get("kerning_pairs") or {}).items()
                 if abs(float(v)) > 1e-9},
        "letter_case": meta.get("letter_case", ""), "default_glyph": meta.get("default_glyph", ""),
        "colors": sorted(c for c in colors if c), "glyphs": glyphs,
    }
    if not glyphs:
        return None
    if not out["size"]:
        h = glyphs.get("H") or glyphs.get("A")
        out["size"] = round(max(-y for e in h["e"] for pts in _pts(e) for _, y in pts), 2) if h else 10
    with gzip.open(os.path.join(dest, fid + ".json.gz"), "wt", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return out


def _pts(e):
    if e["t"] in ("satin", "ripple"):
        return [e["a"], e["b"]]
    if e["t"] == "fill":
        return e["rings"]
    return e["lines"]


if __name__ == "__main__":
    src, dest = sys.argv[1], sys.argv[2]
    os.makedirs(dest, exist_ok=True)
    ok = 0
    for name in sorted(os.listdir(src)):
        folder = os.path.join(src, name)
        if not os.path.isfile(os.path.join(folder, "font.json")):
            continue
        try:
            res = convert_font(folder, dest)
        except Exception as ex:     # einzelne defekte Schrift überspringen
            print(f"  ✗ {name}: {ex}")
            continue
        if res:
            ok += 1
            print(f"  ✓ {name}: {len(res['glyphs'])} Zeichen, {res['size']:.1f} mm, {res['license']}")
    print(f"{ok} Schriften umgewandelt")
