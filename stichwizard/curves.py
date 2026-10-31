"""Kurven wie in Profi-Sticksoftware: Eckpunkte (spitz) und Rundungspunkte (fließend).

Ein Pfad ist eine Liste von Punkten [x, y, typ] mit typ CORNER oder CURVE.
Zwischen zwei Eckpunkten verläuft eine Gerade; sobald ein Rundungspunkt beteiligt ist,
entsteht eine glatte Kurve (zentripetale Catmull-Rom-Spline), die exakt durch alle
Punkte läuft. An Eckpunkten bleibt ein Knick erhalten.

Bézier (wie in Inkscape): Zwischen zwei Kurvenpunkten dürfen ein oder zwei Anfasser
(typ CTRL) stehen – dann ist die Teilstrecke eine Bézierkurve. Ein Kurvenpunkt mit Anfassern
ist »spitz« (CORNER, Anfasser unabhängig) oder »glatt« (CURVE, Anfasser in einer Linie).
"""
import math

from shapely.geometry import LineString, Polygon

CORNER, CURVE, CTRL = 0, 1, 2
STEP = 0.25   # mm – Abtastabstand der Kurven


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _cr(p0, p1, p2, p3):
    """Zentripetale Catmull-Rom-Kurve von p1 nach p2 (inkl. beider Endpunkte)."""
    def tj(t, a, b):
        return t + max(_d(a, b), 1e-6) ** 0.5
    t0 = 0.0
    t1 = tj(t0, p0, p1)
    t2 = tj(t1, p1, p2)
    t3 = tj(t2, p2, p3)
    n = max(4, int(_d(p1, p2) / STEP))
    out = []
    for k in range(n + 1):
        t = t1 + (t2 - t1) * k / n

        def lerp(a, b, ta, tb):
            if tb - ta < 1e-12:
                return a
            u = (t - ta) / (tb - ta)
            return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        a1 = lerp(p0, p1, t0, t1)
        a2 = lerp(p1, p2, t1, t2)
        a3 = lerp(p2, p3, t2, t3)
        b1 = lerp(a1, a2, t0, t2)
        b2 = lerp(a2, a3, t1, t3)
        out.append(lerp(b1, b2, t1, t2))
    out[0], out[-1] = tuple(p1), tuple(p2)
    return out


def is_ctrl(p):
    return len(p) > 2 and p[2] == CTRL


def anchor_groups(pts, closed):
    """Kurvenpunkte und Anfasser: [(index_kurvenpunkt, [anfasser bis zum nächsten])]."""
    n = len(pts)
    anchors = [i for i, p in enumerate(pts) if not is_ctrl(p)]
    groups = []
    for k, a in enumerate(anchors):
        if k + 1 < len(anchors):
            nxt = anchors[k + 1]
        elif closed and anchors:
            nxt = anchors[0] + n
        else:
            nxt = None
        ctrl = [j % n for j in range(a + 1, nxt)] if nxt is not None else []
        groups.append((a, ctrl))
    return groups


def bezier(A, c1, c2, B, step=None):
    """Kubische Bézierkurve abtasten (inkl. beider Endpunkte)."""
    est = _d(A, c1) + _d(c1, c2) + _d(c2, B)
    n = max(6, int(est / (step or STEP)))
    out = []
    for k in range(n + 1):
        t = k / n
        u = 1 - t
        out.append((u ** 3 * A[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * B[0],
                    u ** 3 * A[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * B[1]))
    out[0], out[-1] = tuple(A), tuple(B)
    return out


def cubic_controls(A, ctrl, B):
    """Ein oder zwei Anfasser -> (c1, c2) einer kubischen Kurve."""
    if len(ctrl) == 1:
        C = ctrl[0]
        return ((A[0] + 2 * (C[0] - A[0]) / 3, A[1] + 2 * (C[1] - A[1]) / 3),
                (B[0] + 2 * (C[0] - B[0]) / 3, B[1] + 2 * (C[1] - B[1]) / 3))
    return tuple(ctrl[0][:2]), tuple(ctrl[-1][:2])


def split_cubic(A, c1, c2, B, t):
    """De-Casteljau: Kurve bei t teilen -> (c1a, c2a, M, c1b, c2b)."""
    lerp = lambda p, q: (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
    p01, p12, p23 = lerp(A, c1), lerp(c1, c2), lerp(c2, B)
    p012, p123 = lerp(p01, p12), lerp(p12, p23)
    M = lerp(p012, p123)
    return p01, p012, M, p123, p23


def fit_cubic(seg, ta, tb):
    """Kubische Bézierkurve durch Anfang/Ende von `seg` mit Richtungen ta/tb so anpassen, dass
    sie möglichst genau auf den Punkten von seg liegt. Liefert (c1, c2, größte Abweichung)."""
    A, B = seg[0], seg[-1]
    cum = [0.0]
    for p, q in zip(seg, seg[1:]):
        cum.append(cum[-1] + _d(p, q))
    total = cum[-1] or 1e-9
    m11 = m12 = m22 = r1 = r2 = 0.0
    for Q, c in zip(seg, cum):
        u = c / total
        b0, b1, b2, b3 = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
        bx = A[0] * (b0 + b1) + B[0] * (b2 + b3)
        by = A[1] * (b0 + b1) + B[1] * (b2 + b3)
        v1, v2 = (ta[0] * b1, ta[1] * b1), (tb[0] * b2, tb[1] * b2)
        rx, ry = Q[0] - bx, Q[1] - by
        m11 += v1[0] ** 2 + v1[1] ** 2
        m12 += v1[0] * v2[0] + v1[1] * v2[1]
        m22 += v2[0] ** 2 + v2[1] ** 2
        r1 += v1[0] * rx + v1[1] * ry
        r2 += v2[0] * rx + v2[1] * ry
    det = m11 * m22 - m12 * m12
    L = total / 3
    alpha, beta = ((r1 * m22 - r2 * m12) / det, (m11 * r2 - m12 * r1) / det) \
        if abs(det) > 1e-12 else (L, L)
    if alpha <= 1e-3 or beta <= 1e-3:
        alpha = beta = L
    c1 = (A[0] + ta[0] * alpha, A[1] + ta[1] * alpha)
    c2 = (B[0] + tb[0] * beta, B[1] + tb[1] * beta)
    curve = LineString(bezier(A, c1, c2, B))
    from shapely.geometry import Point as _P
    err = max(curve.distance(_P(q)) for q in seg[::max(1, len(seg) // 24)])
    return c1, c2, err


def bezier_pieces(seg, ta, tb, tol=0.2, depth=0):
    """Abgetastete Kurve als Folge kubischer Stücke: [(c1, c2, endpunkt)] – teilt so lange
    in der Mitte, bis jedes Stück höchstens `tol` mm abweicht."""
    c1, c2, err = fit_cubic(seg, ta, tb)
    if err <= tol or depth >= 4 or len(seg) < 8:
        return [(c1, c2, tuple(seg[-1]))]
    mid = len(seg) // 2
    u, v = seg[mid - 1], seg[mid + 1]
    d = _d(u, v) or 1e-9
    tm = ((v[0] - u[0]) / d, (v[1] - u[1]) / d)
    left = bezier_pieces(seg[:mid + 1], ta, (-tm[0], -tm[1]), tol, depth + 1)
    right = bezier_pieces(seg[mid:], tm, tb, tol, depth + 1)
    return left + right


def segment_pieces(pts, closed, k, tol=0.2):
    """Abschnitt k als Bézierstücke [(c1, c2, endpunkt)] – Grundlage für »Anfasser
    hinzufügen«: die Form bleibt bis auf `tol` mm erhalten."""
    groups = anchor_groups(pts, closed)
    na = len(groups)
    a, b = groups[k][0], groups[(k + 1) % na][0]
    A, B = tuple(pts[a][:2]), tuple(pts[b][:2])
    seg = segments(pts, closed)[k]
    unit = lambda u, v: ((v[0] - u[0]) / (_d(u, v) or 1e-9), (v[1] - u[1]) / (_d(u, v) or 1e-9))
    if len(seg) <= 2:                                   # Gerade
        third = lambda u, v: (u[0] + (v[0] - u[0]) / 3, u[1] + (v[1] - u[1]) / 3)
        return [(third(A, B), third(B, A), B)]
    return bezier_pieces(seg, unit(seg[0], seg[1]), unit(seg[-1], seg[-2]), tol)


def segment_handles(pts, closed, k):
    """Anfasser (c1, c2), mit denen Abschnitt k als Bézierkurve fast genau so verläuft wie
    bisher (Catmull-Rom -> Bézier; bei zwei Ecken: Gerade mit Anfassern auf der Strecke)."""
    groups = anchor_groups(pts, closed)
    na = len(groups)
    anchors = [a for a, _ in groups]
    xy = [(p[0], p[1]) for p in pts]
    ty = [p[2] if len(p) > 2 else CORNER for p in pts]
    a, b = anchors[k], anchors[(k + 1) % na]
    A, B = xy[a], xy[b]
    if ty[a] == CURVE and (closed or k > 0):
        P0 = xy[anchors[(k - 1) % na]]
    else:
        P0 = (2 * A[0] - B[0], 2 * A[1] - B[1]) if ty[a] == CURVE else None
    if ty[b] == CURVE and (closed or k + 1 < na - 1):
        P3 = xy[anchors[(k + 2) % na]]
    else:
        P3 = (2 * B[0] - A[0], 2 * B[1] - A[1]) if ty[b] == CURVE else None
    third = lambda u, v: (u[0] + (v[0] - u[0]) / 3, u[1] + (v[1] - u[1]) / 3)
    if P0 is None and P3 is None:
        return third(A, B), third(B, A)
    # Länge der Anfasser an die tatsächliche Kurve anpassen (zentripetal)
    seg = segments(pts, closed)[k]
    def tangent(i0, i1):
        u, v = seg[i0], seg[i1]
        d = _d(u, v) or 1e-9
        return ((v[0] - u[0]) / d, (v[1] - u[1]) / d)
    L = sum(_d(p, q) for p, q in zip(seg, seg[1:])) / 3
    ta = tangent(0, 1) if P0 is not None else None
    tb = tangent(-1, -2) if P3 is not None else None
    if ta is None:
        ta = ((B[0] - A[0]) / (_d(A, B) or 1e-9), (B[1] - A[1]) / (_d(A, B) or 1e-9))
    if tb is None:
        tb = ((A[0] - B[0]) / (_d(A, B) or 1e-9), (A[1] - B[1]) / (_d(A, B) or 1e-9))
    # Anfasserlängen per Ausgleichsrechnung an die bisherige Kurve anpassen (Schneider)
    cum = [0.0]
    for p, q in zip(seg, seg[1:]):
        cum.append(cum[-1] + _d(p, q))
    total = cum[-1] or 1e-9
    m11 = m12 = m22 = r1 = r2 = 0.0
    for Q, c in zip(seg, cum):
        u = c / total
        b0, b1, b2, b3 = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
        base = (A[0] * (b0 + b1) + B[0] * (b2 + b3), A[1] * (b0 + b1) + B[1] * (b2 + b3))
        v1 = (ta[0] * b1, ta[1] * b1)
        v2 = (tb[0] * b2, tb[1] * b2)
        rx, ry = Q[0] - base[0], Q[1] - base[1]
        m11 += v1[0] * v1[0] + v1[1] * v1[1]
        m12 += v1[0] * v2[0] + v1[1] * v2[1]
        m22 += v2[0] * v2[0] + v2[1] * v2[1]
        r1 += v1[0] * rx + v1[1] * ry
        r2 += v2[0] * rx + v2[1] * ry
    det = m11 * m22 - m12 * m12
    if abs(det) > 1e-12:
        alpha = (r1 * m22 - r2 * m12) / det
        beta = (m11 * r2 - m12 * r1) / det
    else:
        alpha = beta = L
    if alpha <= 1e-3 or beta <= 1e-3:
        alpha = beta = L
    c1 = (A[0] + ta[0] * alpha, A[1] + ta[1] * alpha)
    c2 = (B[0] + tb[0] * beta, B[1] + tb[1] * beta)
    return c1, c2


def segments(pts, closed):
    """Eine abgetastete Teilstrecke je Abschnitt zwischen zwei Kurvenpunkten (Anfasser zählen
    nicht als eigene Punkte) – für Geometrie und Trefferprüfung."""
    groups = anchor_groups(pts, closed)
    na = len(groups)
    if na < 2:
        return []
    xy = [(p[0], p[1]) for p in pts]
    ty = [p[2] if len(p) > 2 else CORNER for p in pts]
    anchors = [a for a, _ in groups]
    m = na if closed else na - 1
    segs = []
    for k in range(m):
        a, b = anchors[k], anchors[(k + 1) % na]
        A, B = xy[a], xy[b]
        ctrl = groups[k][1]
        if ctrl:
            c1, c2 = cubic_controls(A, [xy[j] for j in ctrl], B)
            segs.append(bezier(A, c1, c2, B))
            continue
        if _d(A, B) < 1e-9:
            segs.append([A, B])
            continue
        if ty[a] == CORNER and ty[b] == CORNER:
            segs.append([A, B])
            continue
        if ty[a] == CURVE and (closed or k > 0):
            P0 = xy[anchors[(k - 1) % na]]
        else:
            P0 = (2 * A[0] - B[0], 2 * A[1] - B[1])
        if ty[b] == CURVE and (closed or k + 1 < na - 1):
            P3 = xy[anchors[(k + 2) % na]]
        else:
            P3 = (2 * B[0] - A[0], 2 * B[1] - A[1])
        segs.append(_cr(P0, A, B, P3))
    return segs


def polyline(pts, closed):
    out = []
    for seg in segments(pts, closed):
        out.extend(seg if not out else seg[1:])
    return out


def ring_polygon(pts):
    line = polyline(pts, True)
    if len(line) < 3:
        return Polygon()
    return Polygon(line).buffer(0)


def rings_geometry(rings):
    """Mehrere geschlossene Pfade, gerade/ungerade kombiniert: innere Ringe werden Löcher."""
    geom = None
    for r in rings:
        p = ring_polygon(r)
        if p.is_empty:
            continue
        geom = p if geom is None else geom.symmetric_difference(p)
    return geom if geom is not None else Polygon()


def line_geometry(pts, closed=False):
    line = polyline(pts, closed)
    if closed and line:
        line = line + [line[0]]
    return LineString(line) if len(line) >= 2 else LineString()


# --------------------------------------------------------- Kurven erkennen
def _turn(a, b, c):
    """Richtungsänderung in Grad am Punkt b."""
    a1 = math.atan2(b[1] - a[1], b[0] - a[0])
    a2 = math.atan2(c[1] - b[1], c[0] - b[0])
    d = abs(math.degrees(a2 - a1)) % 360
    return 360 - d if d > 180 else d


def _intersect(a, b, c, d):
    """Schnittpunkt der Geraden a-b und c-d (oder None)."""
    x1, y1, x2, y2 = a[0], a[1], b[0], b[1]
    x3, y3, x4, y4 = c[0], c[1], d[0], d[1]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def auto_ring(coords, closed=True, tolerance=0.35, corner_angle=40.0):
    """Wandelt einen eckigen Polygonzug (z. B. digitalisiert) in wenige Eck- und
    Rundungspunkte um. Knicke ab `corner_angle` bleiben Ecken."""
    pts = [tuple(c[:2]) for c in coords]
    if closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return [[x, y, CORNER] for x, y in pts]
    line = LineString(pts + [pts[0]] if closed else pts).simplify(tolerance)
    s = list(line.coords)
    if closed and len(s) > 1 and s[0] == s[-1]:
        s = s[:-1]
    # Abgeschnittene Spitzen (zwei sehr nahe Punkte zwischen langen Kanten) wieder spitz machen
    changed = True
    while changed and len(s) > 3:
        changed = False
        n = len(s)
        for i in range(n):
            j = (i + 1) % n
            if not closed and (i == 0 or j >= n - 1):
                continue
            a, p, q, c = s[(i - 1) % n], s[i], s[j], s[(j + 1) % n]
            if _d(p, q) < 1.6 and _d(a, p) > 3 and _d(q, c) > 3:
                x = _intersect(a, p, q, c)
                tip = x if x and _d(x, p) < 3 and _d(x, q) < 3 else \
                    ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                s[i] = tip
                del s[j]
                changed = True
                break
    # Punkte mitten auf geraden Strecken sind überflüssig
    changed = True
    while changed and len(s) > 3:
        changed = False
        n = len(s)
        for i in range(n):
            if not closed and i in (0, n - 1):
                continue
            a, p, c = s[(i - 1) % n], s[i], s[(i + 1) % n]
            if _turn(a, p, c) < 6 and min(_d(a, p), _d(p, c)) > 3.0:
                del s[i]
                changed = True
                break
    n = len(s)
    out = []
    for i, p in enumerate(s):
        if not closed and i in (0, n - 1):
            out.append([p[0], p[1], CORNER])
            continue
        a, c = s[(i - 1) % n], s[(i + 1) % n]
        # kurze Nachbarabschnitte deuten auf eine Rundung hin, lange gerade auf Ecken
        sharp = _turn(a, p, c) >= corner_angle
        straight = min(_d(a, p), _d(p, c)) > 6.0 and _turn(a, p, c) > 12
        out.append([p[0], p[1], CORNER if sharp or straight else CURVE])
    return out


def auto_geometry_rings(geom, tolerance=0.35, corner_angle=40.0):
    """Polygon(e) -> Ringliste mit erkannten Ecken/Rundungen."""
    from .engine import polygons_of
    rings = []
    for poly in polygons_of(geom):
        rings.append(auto_ring(poly.exterior.coords, True, tolerance, corner_angle))
        for r in poly.interiors:
            rings.append(auto_ring(r.coords, True, tolerance, corner_angle))
    return [r for r in rings if len(r) >= 3]


def polygon_rings(geom):
    """Polygon(e) -> Ringliste, alle Punkte als Ecken (exakt dieselbe Form)."""
    from .engine import polygons_of
    rings = []
    for poly in polygons_of(geom):
        for ring in [poly.exterior] + list(poly.interiors):
            c = list(ring.coords)[:-1]
            if len(c) >= 3:
                rings.append([[x, y, CORNER] for x, y in c])
    return rings
