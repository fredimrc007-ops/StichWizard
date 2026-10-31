"""Garnfarben-Palette und Stickrahmen."""

THREADS = [
    ("Weiß", "#FAFAFA"), ("Creme", "#F3E9D2"), ("Elfenbein", "#FFF8E1"),
    ("Zitrone", "#FFEE58"), ("Sonnengelb", "#FFC107"), ("Gold", "#D4A017"),
    ("Orange", "#FB8C00"), ("Mandarine", "#F4511E"), ("Koralle", "#FF7F6E"),
    ("Rot", "#E53935"), ("Kirschrot", "#C62828"), ("Weinrot", "#7B1F2B"),
    ("Rosa", "#F8BBD0"), ("Pink", "#EC407A"), ("Magenta", "#C2185B"),
    ("Flieder", "#CE93D8"), ("Lila", "#8E24AA"), ("Aubergine", "#4A148C"),
    ("Lavendel", "#B39DDB"), ("Indigo", "#3949AB"), ("Marine", "#1A237E"),
    ("Himmelblau", "#81D4FA"), ("Azur", "#1E88E5"), ("Royalblau", "#1565C0"),
    ("Türkis", "#26C6DA"), ("Petrol", "#00838F"), ("Mint", "#A5D6A7"),
    ("Grasgrün", "#43A047"), ("Tannengrün", "#1B5E20"), ("Limette", "#C0CA33"),
    ("Oliv", "#827717"), ("Salbei", "#8DA38A"), ("Sand", "#D7C29E"),
    ("Karamell", "#B9773C"), ("Braun", "#6D4C41"), ("Schokolade", "#3E2723"),
    ("Hautton hell", "#F6D3B8"), ("Hautton mittel", "#D9A07A"), ("Hautton dunkel", "#8D5A3B"),
    ("Silbergrau", "#BDBDBD"), ("Mittelgrau", "#757575"), ("Anthrazit", "#424242"),
    ("Schwarz", "#1A1A1A"),
]

FABRICS = [
    ("Weiß", "#FFFFFF"), ("Leinen", "#EDE3D1"), ("Grau meliert", "#C9C9C9"),
    ("Jeans", "#4A6A8C"), ("Marine", "#22304A"), ("Schwarz", "#1E1E1E"),
    ("Rosé", "#F2D7D5"), ("Mint", "#D4ECE3"), ("Senf", "#D9A93B"), ("Bordeaux", "#5E1A26"),
]

HOOPS = [
    ("100 × 100 mm", 100, 100),
    ("130 × 180 mm", 130, 180),
    ("150 × 150 mm", 150, 150),
    ("160 × 260 mm", 160, 260),
    ("200 × 200 mm", 200, 200),
    ("240 × 150 mm", 240, 150),
    ("260 × 200 mm", 260, 200),
    ("360 × 200 mm", 360, 200),
    ("Kappe 130 × 60 mm", 130, 60),          # Kappenrahmen (z. B. Brother PR, Janome)
    ("Kappe breit 360 × 75 mm", 360, 75),    # 270°-Kappenrahmen (z. B. Tajima)
]
N_BUILTIN_HOOPS = len(HOOPS)        # dahinter folgen die eigenen Rahmen (Einstellungen/Datei)
HOOP_LIMITS = (20, 1500)            # mm – kleinster/größter eigener Rahmen


def hoop_label(w, h, name=""):
    size = f"{w:g} × {h:g} mm"
    return f"{name} – {size}" if name else f"{size} (eigen)"


def is_cap_hoop(i):
    """Kappenrahmen: feste Kappen-Größen und eigene Rahmen mit »Kappe«/»Cap« im Namen."""
    if not 0 <= i < len(HOOPS):
        return False
    label = HOOPS[i][0].lower()
    return "kappe" in label or "cap" in label


def is_custom_hoop(i):
    return N_BUILTIN_HOOPS <= i < len(HOOPS)


def hoop_for_size(w, h, name=""):
    """Index eines Rahmens mit genau dieser Größe; gibt es keinen, wird ein eigener angehängt."""
    w, h = float(w), float(h)
    for i, (_, hw, hh) in enumerate(HOOPS):
        if abs(hw - w) < 0.05 and abs(hh - h) < 0.05:
            return i
    lo, hi = HOOP_LIMITS
    if not (lo <= w <= hi and lo <= h <= hi):
        raise ValueError(f"Rahmengröße muss zwischen {lo} und {hi} mm liegen")
    w, h = round(w, 1), round(h, 1)
    HOOPS.append((hoop_label(w, h, name), w, h))
    return len(HOOPS) - 1


def remove_custom_hoop(i):
    if is_custom_hoop(i):
        del HOOPS[i]


def custom_hoops():
    """Eigene Rahmen zum Speichern in den Einstellungen: [[name, breite, höhe]]."""
    out = []
    for label, w, h in HOOPS[N_BUILTIN_HOOPS:]:
        name = label.rsplit(" – ", 1)[0] if " – " in label else ""
        out.append([name, w, h])
    return out


def load_custom_hoops(items):
    del HOOPS[N_BUILTIN_HOOPS:]
    for it in items or []:
        try:
            name, w, h = it
            hoop_for_size(w, h, str(name or ""))
        except (TypeError, ValueError):
            continue


def thread_name(hex_color):
    if CURRENT_CHART:
        lab = chart_label(hex_color)
        if lab:
            return lab
    hc = hex_color.upper()
    for name, c in THREADS:
        if c.upper() == hc:
            return name
    return nearest_thread(hex_color)[0]


def nearest_thread(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    best, bd = THREADS[0], 1e9
    for name, c in THREADS:
        r2, g2, b2 = hex_to_rgb(c)
        d = (r - r2) ** 2 * 0.3 + (g - g2) ** 2 * 0.59 + (b - b2) ** 2 * 0.11
        if d < bd:
            best, bd = (name, c), d
    return best


def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r, g, b):
    return "#%02X%02X%02X" % (int(r), int(g), int(b))


# ------------------------------------------------------------- Garnkarten
import functools as _ft
import gzip as _gzip
import json as _json
import os as _os

CURRENT_CHART = ""      # leer = StichWizard-Standardpalette


@_ft.lru_cache(maxsize=1)
def charts():
    path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "threadcharts.json.gz")
    try:
        with _gzip.open(path, "rt", encoding="utf-8") as f:
            return _json.load(f)
    except OSError:
        return {}


def chart_names():
    return sorted(charts(), key=str.lower)


def set_chart(name):
    global CURRENT_CHART
    CURRENT_CHART = name if name in charts() else ""


def palette():
    """Aktuelle Palette: [(anzeigename, hex)]."""
    if CURRENT_CHART:
        return [((f"{num} " if num else "") + name, col) for name, num, col in charts()[CURRENT_CHART]]
    return list(THREADS)


def _lab(hex_color):
    r, g, b = (v / 255 for v in hex_to_rgb(hex_color))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def chart_match(hex_color, chart=None):
    """Nächste Garnfarbe der Karte: (name, nummer, hex, exakt)."""
    return _chart_match(hex_color.upper(), chart if chart is not None else CURRENT_CHART)


@_ft.lru_cache(maxsize=8192)
def _chart_match(hex_color, chart):
    rows = charts().get(chart)
    if not rows:
        return None
    hc = hex_color.upper()
    for name, num, col in rows:
        if col.upper() == hc:
            return name, num, col, True
    L1, a1, b1 = _lab(hc)
    best = min(rows, key=lambda r: sum((p - q) ** 2 for p, q in zip(_lab(r[2]), (L1, a1, b1))))
    return best[0], best[1], best[2], False


def chart_label(hex_color):
    m = chart_match(hex_color)
    if not m:
        return None
    name, num, _, exact = m
    return ("" if exact else "≈ ") + (f"{num} " if num else "") + name
