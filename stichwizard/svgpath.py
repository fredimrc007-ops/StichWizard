"""Kleiner SVG-Pfadleser: Pfaddaten und Transformationen -> Polygonzüge.

Unterstützt alle Pfadbefehle (M L H V C S Q T A Z, absolut und relativ) sowie
transform="matrix|translate|scale|rotate|skewX|skewY(...)".
"""
import math
import re

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_TOKEN = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(" + _NUM + ")")


def _tokens(d):
    for cmd, num in _TOKEN.findall(d or ""):
        yield cmd if cmd else float(num)


def _bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        out.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                    mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def _seg_count(*pts, step=0.6):
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    return max(2, min(200, int(length / step) + 1))


def _arc(p0, rx, ry, phi, large, sweep, p1):
    """Elliptischer Bogen (SVG-Endpunktform) -> Punkte."""
    if rx == 0 or ry == 0 or p0 == p1:
        return [p1]
    rx, ry = abs(rx), abs(ry)
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    cx = cp * cx1 - sp * cy1 + (p0[0] + p1[0]) / 2
    cy = sp * cx1 + cp * cy1 + (p0[1] + p1[1]) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(4, int(abs(dt) * max(rx, ry) / 0.6) + 1)
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    out[-1] = p1
    return out


def parse_path(d):
    """SVG-Pfaddaten -> Liste von Teilpfaden: (punkte, geschlossen, anzahl_knoten)."""
    toks = list(_tokens(d))
    subs = []
    cur = []
    nodes = 0
    pos = (0.0, 0.0)
    start = pos
    last_ctrl = None
    cmd = None
    i = 0

    def take(k):
        nonlocal i
        vals = toks[i:i + k]
        i += k
        return vals

    def close_sub(closed):
        nonlocal cur, nodes
        if len(cur) > 1:
            subs.append((cur, closed, nodes))
        cur, nodes = [], 0

    while i < len(toks):
        if isinstance(toks[i], str):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if cur and cur[-1] != start:
                    cur.append(start)
                close_sub(True)
                pos = start
                last_ctrl = None
                continue
        elif cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            x, y = take(2)
            if rel:
                x, y = x + pos[0], y + pos[1]
            close_sub(False)
            pos = start = (x, y)
            cur, nodes = [pos], 1
            cmd = "l" if rel else "L"     # weitere Koordinaten = Linien
            last_ctrl = None
            continue
        if not cur:
            cur, nodes = [pos], 1
        if c == "L":
            x, y = take(2)
            p = (x + pos[0], y + pos[1]) if rel else (x, y)
            cur.append(p)
            pos, last_ctrl = p, None
        elif c == "H":
            (x,) = take(1)
            p = (x + pos[0] if rel else x, pos[1])
            cur.append(p)
            pos, last_ctrl = p, None
        elif c == "V":
            (y,) = take(1)
            p = (pos[0], y + pos[1] if rel else y)
            cur.append(p)
            pos, last_ctrl = p, None
        elif c in "CS":
            if c == "C":
                x1, y1, x2, y2, x, y = take(6)
                if rel:
                    x1, y1, x2, y2 = x1 + pos[0], y1 + pos[1], x2 + pos[0], y2 + pos[1]
                p1 = (x1, y1)
            else:
                x2, y2, x, y = take(4)
                if rel:
                    x2, y2 = x2 + pos[0], y2 + pos[1]
                p1 = (2 * pos[0] - last_ctrl[0], 2 * pos[1] - last_ctrl[1]) if last_ctrl else pos
            if rel:
                x, y = x + pos[0], y + pos[1]
            p2, p3 = (x2, y2), (x, y)
            cur.extend(_bezier(pos, p1, p2, p3, _seg_count(pos, p1, p2, p3)))
            pos, last_ctrl = p3, p2
        elif c in "QT":
            if c == "Q":
                x1, y1, x, y = take(4)
                if rel:
                    x1, y1 = x1 + pos[0], y1 + pos[1]
                q = (x1, y1)
            else:
                x, y = take(2)
                q = (2 * pos[0] - last_ctrl[0], 2 * pos[1] - last_ctrl[1]) if last_ctrl else pos
            if rel:
                x, y = x + pos[0], y + pos[1]
            p3 = (x, y)
            c1 = (pos[0] + 2 / 3 * (q[0] - pos[0]), pos[1] + 2 / 3 * (q[1] - pos[1]))
            c2 = (p3[0] + 2 / 3 * (q[0] - p3[0]), p3[1] + 2 / 3 * (q[1] - p3[1]))
            cur.extend(_bezier(pos, c1, c2, p3, _seg_count(pos, q, p3)))
            pos, last_ctrl = p3, q
        elif c == "A":
            rx, ry, phi, large, sweep, x, y = take(7)
            if rel:
                x, y = x + pos[0], y + pos[1]
            cur.extend(_arc(pos, rx, ry, phi, int(large), int(sweep), (x, y)))
            pos, last_ctrl = (x, y), None
        else:
            i += 1          # unerwartete Zahl (z. B. nach Z) überspringen
            continue
        nodes += 1
    close_sub(False)
    return subs


def parse_transform(s):
    """transform-Attribut -> Matrix (a, b, c, d, e, f)."""
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(x) for x in re.findall(_NUM, args)]
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            r = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                t = mul(mul((1, 0, 0, 1, v[1], v[2]), r), (1, 0, 0, 1, -v[1], -v[2]))
            else:
                t = r
        elif name == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        m = mul(m, t)
    return m


def mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2,
            a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def apply(m, pts):
    a, b, c, d, e, f = m
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in pts]
