"""Produktvorschau: der Entwurf in Originalgröße auf T-Shirt, Kappe, Tasche, Handtuch, Kissen
oder Lätzchen – damit man vor dem Sticken sieht, wie es ungefähr wirkt.

Alle Produkte sind in Millimetern gezeichnet (Mitte = 0, 0); der Entwurf wird im selben Maßstab
daraufgelegt. Das Fenster ist nicht modal und aktualisiert sich, sobald sich das Design ändert.
"""
import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPen, QRadialGradient)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from .render import paint_thread, stitch_lines
from .threads import FABRICS


# ---------------------------------------------------------------- Produkte (Maße in mm)
def _poly_path(pts):
    path = QPainterPath(QPointF(*pts[0]))
    for q in pts[1:]:
        path.lineTo(QPointF(*q))
    path.closeSubpath()
    return path


def shirt_shape():
    path = QPainterPath(QPointF(-95, -372))
    path.cubicTo(-70, -318, 70, -318, 95, -372)          # Halsausschnitt
    path.lineTo(225, -345)                                # Schulter
    path.lineTo(395, -170)                                # Ärmel außen
    path.lineTo(300, -100)                                # Ärmelsaum
    path.lineTo(258, -180)                                # Achsel
    path.cubicTo(262, -40, 262, 200, 262, 360)            # Seite
    path.lineTo(-262, 360)                                # Saum
    path.cubicTo(-262, 200, -262, -40, -258, -180)
    path.lineTo(-300, -100)
    path.lineTo(-395, -170)
    path.lineTo(-225, -345)
    path.closeSubpath()
    return path


def shirt_details(p, col):
    seam = QPen(col.darker(125), 1.6, Qt.DashLine)
    p.setPen(seam)
    p.setBrush(Qt.NoBrush)
    rib = QPainterPath(QPointF(-95, -372))
    rib.cubicTo(-70, -318, 70, -318, 95, -372)
    rib2 = QPainterPath(QPointF(-112, -366))
    rib2.cubicTo(-80, -298, 80, -298, 112, -366)
    p.setPen(QPen(col.darker(118), 9))
    p.drawPath(rib)
    p.setPen(seam)
    p.drawPath(rib2)
    for sgn in (1, -1):
        p.drawLine(QPointF(sgn * 225, -345), QPointF(sgn * 258, -180))          # Ärmelnaht
        p.drawLine(QPointF(sgn * 305, -112), QPointF(sgn * 382, -172))          # Ärmelsaum
    p.drawLine(QPointF(-258, 340), QPointF(258, 340))                           # Saum


def cap_shape():
    path = QPainterPath(QPointF(-118, 30))
    path.cubicTo(-122, -70, -70, -128, 0, -130)
    path.cubicTo(70, -128, 122, -70, 118, 30)
    path.cubicTo(80, 38, -80, 38, -118, 30)          # Unterkante folgt dem Schirm
    path.closeSubpath()
    return path


def cap_visor(p, col):
    """Schirm – liegt außerhalb des Kappenumrisses, wird daher ohne Zuschnitt gezeichnet."""
    visor = QPainterPath(QPointF(-128, 24))
    visor.cubicTo(-110, 100, 110, 100, 128, 24)
    visor.cubicTo(90, 34, -90, 34, -128, 24)       # Oberkante liegt an der Kappe an
    g = QLinearGradient(0, 26, 0, 92)
    g.setColorAt(0, col.darker(112))
    g.setColorAt(1, col.darker(135))
    p.setPen(QPen(col.darker(160), 1.2))
    p.setBrush(QBrush(g))
    p.drawPath(visor)
    p.setPen(QPen(col.darker(150), 1.2, Qt.DashLine))
    p.setBrush(Qt.NoBrush)
    for k in (1, 2, 3):
        v = QPainterPath(QPointF(-122 + k * 2, 32 + k * 5))
        v.cubicTo(-100, 88 - k * 4, 100, 88 - k * 4, 122 - k * 2, 32 + k * 5)
        p.drawPath(v)


def cap_details(p, col):
    # Nähte der Kappenteile, Knopf, Luftlöcher
    seam = QPen(col.darker(130), 1.4, Qt.DashLine)
    p.setPen(seam)
    for sgn in (1, -1):
        s = QPainterPath(QPointF(0, -128))
        s.cubicTo(sgn * 45, -110, sgn * 80, -40, sgn * 92, 28)
        p.drawPath(s)
    p.setPen(Qt.NoPen)
    p.setBrush(col.darker(120))
    p.drawEllipse(QPointF(0, -130), 9, 5)
    for sgn in (1, -1):
        p.setBrush(col.darker(150))
        p.drawEllipse(QPointF(sgn * 62, -88), 3.2, 3.2)


def bag_shape():
    return _poly_path([(-190, -150), (190, -150), (198, 250), (-198, 250)])


def bag_details(p, col):
    p.setBrush(Qt.NoBrush)
    for sgn in (1, -1):
        h = QPainterPath(QPointF(sgn * 40, -150))
        h.cubicTo(sgn * 40, -330, sgn * 140, -330, sgn * 140, -150)
        p.setPen(QPen(col.darker(130), 22, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(h)
        p.setPen(QPen(col.darker(108), 16, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(h)
    p.setPen(QPen(col.darker(125), 1.6, Qt.DashLine))
    p.drawLine(QPointF(-186, -132), QPointF(186, -132))


def towel_shape():
    path = QPainterPath()
    path.addRoundedRect(QRectF(-300, -180, 600, 360), 10, 10)
    return path


def towel_details(p, col):
    p.setPen(Qt.NoPen)
    p.setBrush(col.darker(112))
    p.drawRect(QRectF(-300, 120, 600, 34))                         # Webkante/Bordüre
    p.setPen(QPen(col.darker(122), 1.2))
    for y in (124, 150):
        p.drawLine(QPointF(-300, y), QPointF(300, y))
    # Frottee-Schlingen angedeutet
    p.setPen(QPen(col.darker(108), 1.6, Qt.SolidLine, Qt.RoundCap))
    for j, y in enumerate(range(-172, 176, 8)):
        if 118 < y < 156:
            continue
        for x in range(-294 + (j % 2) * 4, 296, 8):
            p.drawPoint(QPointF(x, y))


def pillow_shape():
    path = QPainterPath(QPointF(-200, -200))
    path.cubicTo(-100, -184, 100, -184, 200, -200)
    path.cubicTo(184, -100, 184, 100, 200, 200)
    path.cubicTo(100, 184, -100, 184, -200, 200)
    path.cubicTo(-184, 100, -184, -100, -200, -200)
    path.closeSubpath()
    return path


def pillow_details(p, col):
    p.setPen(QPen(col.darker(125), 1.6, Qt.DashLine))
    p.setBrush(Qt.NoBrush)
    inner = QPainterPath(QPointF(-188, -186))
    inner.cubicTo(-95, -172, 95, -172, 188, -186)
    inner.cubicTo(172, -95, 172, 95, 188, 186)
    inner.cubicTo(95, 172, -95, 172, -188, 186)
    inner.cubicTo(-172, 95, -172, -95, -188, -186)
    p.drawPath(inner)


def bib_shape():
    path = QPainterPath(QPointF(-55, -150))
    path.cubicTo(-55, -95, 55, -95, 55, -150)                      # Halsausschnitt
    path.cubicTo(80, -150, 112, -120, 112, -60)
    path.cubicTo(118, 60, 80, 150, 0, 150)
    path.cubicTo(-80, 150, -118, 60, -112, -60)
    path.cubicTo(-112, -120, -80, -150, -55, -150)
    path.closeSubpath()
    return path


def bib_details(p, col):
    p.setPen(QPen(col.darker(130), 6))
    p.setBrush(Qt.NoBrush)
    p.drawPath(bib_shape())
    p.setPen(QPen(col.darker(140), 1.4, Qt.DashLine))
    edge = QPainterPath(QPointF(-48, -150))
    edge.cubicTo(-48, -103, 48, -103, 48, -150)
    p.drawPath(edge)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#D9D9D9"))
    p.drawEllipse(QPointF(-84, -128), 7, 7)                         # Druckknopf


def shirt_back_shape():
    """T-Shirt von hinten: Ausschnitt hoch und flach."""
    path = QPainterPath(QPointF(-95, -372))
    path.cubicTo(-60, -355, 60, -355, 95, -372)
    path.lineTo(225, -345)
    path.lineTo(395, -170)
    path.lineTo(300, -100)
    path.lineTo(258, -180)
    path.cubicTo(262, -40, 262, 200, 262, 360)
    path.lineTo(-262, 360)
    path.cubicTo(-262, 200, -262, -40, -258, -180)
    path.lineTo(-300, -100)
    path.lineTo(-395, -170)
    path.lineTo(-225, -345)
    path.closeSubpath()
    return path


def shirt_back_details(p, col):
    seam = QPen(col.darker(125), 1.6, Qt.DashLine)
    p.setPen(QPen(col.darker(118), 9))
    p.setBrush(Qt.NoBrush)
    rib = QPainterPath(QPointF(-95, -372))
    rib.cubicTo(-60, -355, 60, -355, 95, -372)
    p.drawPath(rib)
    p.setPen(seam)
    for sgn in (1, -1):
        p.drawLine(QPointF(sgn * 225, -345), QPointF(sgn * 258, -180))
        p.drawLine(QPointF(sgn * 305, -112), QPointF(sgn * 382, -172))
    p.drawLine(QPointF(-258, 340), QPointF(258, 340))


def hoodie_shape():
    path = QPainterPath(QPointF(-110, -360))
    path.cubicTo(-80, -300, 80, -300, 110, -360)          # Ausschnitt unter der Kapuze
    path.lineTo(240, -330)                                # Schulter
    path.lineTo(420, 120)                                 # langer Ärmel außen
    path.lineTo(350, 150)                                 # Bündchen
    path.lineTo(268, -150)                                # Ärmel innen
    path.cubicTo(272, 0, 272, 220, 270, 380)
    path.lineTo(-270, 380)
    path.cubicTo(-272, 220, -272, 0, -268, -150)
    path.lineTo(-350, 150)
    path.lineTo(-420, 120)
    path.lineTo(-240, -330)
    path.closeSubpath()
    return path


def hoodie_details(p, col):
    seam = QPen(col.darker(125), 1.6, Qt.DashLine)
    p.setBrush(Qt.NoBrush)
    p.setPen(seam)
    p.drawLine(QPointF(-260, 330), QPointF(260, 330))                 # Bund
    pocket = QPainterPath(QPointF(-150, 300))
    pocket.lineTo(-120, 130)
    pocket.lineTo(120, 130)
    pocket.lineTo(150, 300)
    p.drawPath(pocket)                                                # Bauchtasche
    p.setPen(QPen(col.darker(140), 2))
    for sgn in (1, -1):                                               # Kordeln
        p.drawLine(QPointF(sgn * 35, -320), QPointF(sgn * 40, -220))
        p.drawEllipse(QPointF(sgn * 40, -215), 4, 6)


def hoodie_hood(p, col):
    hood = QPainterPath(QPointF(-110, -360))
    hood.cubicTo(-170, -430, -120, -520, 0, -525)
    hood.cubicTo(120, -520, 170, -430, 110, -360)
    hood.cubicTo(80, -300, -80, -300, -110, -360)
    p.setPen(QPen(col.darker(150), 1.4))
    p.setBrush(col.darker(112))
    p.drawPath(hood)
    inner = QPainterPath(QPointF(-75, -350))
    inner.cubicTo(-110, -420, -70, -480, 0, -482)
    inner.cubicTo(70, -480, 110, -420, 75, -350)
    p.setBrush(col.darker(145))
    p.drawPath(inner)


def polo_details(p, col):
    shirt_details(p, col)
    p.setPen(QPen(col.darker(130), 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(-14, -335, 28, 120))                          # Knopfleiste
    p.setPen(Qt.NoPen)
    p.setBrush(col.darker(160))
    for y in (-310, -275, -240):
        p.drawEllipse(QPointF(0, y), 3.5, 3.5)


def polo_collar(p, col):
    p.setPen(QPen(col.darker(150), 1.4))
    p.setBrush(col.darker(108))
    for sgn in (1, -1):
        c = QPainterPath(QPointF(sgn * 2, -335))
        c.lineTo(sgn * 100, -378)
        c.lineTo(sgn * 92, -352)
        c.lineTo(sgn * 45, -300)
        c.closeSubpath()
        p.drawPath(c)


def apron_shape():
    path = QPainterPath(QPointF(-110, -300))
    path.lineTo(110, -300)
    path.lineTo(110, -170)
    path.cubicTo(150, -120, 250, -110, 270, -90)            # Taille
    path.lineTo(250, 380)
    path.lineTo(-250, 380)
    path.lineTo(-270, -90)
    path.cubicTo(-250, -110, -150, -120, -110, -170)
    path.closeSubpath()
    return path


def apron_details(p, col):
    p.setPen(QPen(col.darker(125), 1.6, Qt.DashLine))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(-120, 120, 240, 130))                   # Tasche
    p.drawLine(QPointF(0, 120), QPointF(0, 250))


def apron_straps(p, col):
    p.setPen(QPen(col.darker(130), 16, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    neck = QPainterPath(QPointF(-100, -300))
    neck.cubicTo(-110, -430, 110, -430, 100, -300)
    p.drawPath(neck)
    for sgn in (1, -1):
        p.drawLine(QPointF(sgn * 265, -92), QPointF(sgn * 340, -60))


# Platzierungen: (Name, Mitte x, Mitte y, größte sinnvolle Breite, Höhe) in mm
PRODUCTS = {
    "shirt": dict(name="T-Shirt", shape=shirt_shape, details=shirt_details,
                  bounds=QRectF(-400, -380, 800, 745), collar=-331,
                  places=[("Brust links", 125, -215, 100, 100), ("Brust Mitte", 0, -175, 280, 300),
                          ("Groß Mitte", 0, -40, 300, 380)]),
    "shirt_back": dict(name="T-Shirt Rückseite", shape=shirt_back_shape, details=shirt_back_details,
                       bounds=QRectF(-400, -380, 800, 745), collar=-358,
                       places=[("Rücken oben", 0, -200, 300, 120), ("Rücken groß", 0, -60, 300, 380),
                               ("Nacken", 0, -315, 90, 35)]),
    "hoodie": dict(name="Kapuzenpulli", shape=hoodie_shape, details=hoodie_details,
                   outside=hoodie_hood, bounds=QRectF(-425, -530, 850, 915), collar=-315,
                   places=[("Brust links", 125, -200, 100, 100), ("Brust Mitte", 0, -150, 280, 220),
                           ("Ärmel links", 330, -40, 80, 220, 68)]),
    "polo": dict(name="Polo-Shirt", shape=shirt_shape, details=polo_details, outside=polo_collar,
                 bounds=QRectF(-400, -385, 800, 750), collar=-331,
                 places=[("Brust links", 125, -215, 100, 90), ("Ärmel links", 330, -150, 70, 60, 46)]),
    "apron": dict(name="Schürze", shape=apron_shape, details=apron_details, outside=apron_straps,
                  bounds=QRectF(-345, -420, 690, 805),
                  places=[("Latz", 0, -210, 180, 140), ("Tasche", 0, 185, 220, 110),
                          ("Unten", 0, 320, 400, 90)]),
    "cap": dict(name="Kappe", shape=cap_shape, details=cap_details, outside=cap_visor,
                bounds=QRectF(-135, -140, 270, 240),
                places=[("Vorne Mitte", 0, -42, 125, 58)], curved=True),
    "bag": dict(name="Tragetasche", shape=bag_shape, details=bag_details, outside=bag_details,
                bounds=QRectF(-205, -330, 410, 585),
                places=[("Mitte", 0, 50, 280, 280), ("Oben", 0, -60, 280, 100)]),
    "towel": dict(name="Handtuch", shape=towel_shape, details=towel_details,
                  bounds=QRectF(-305, -185, 610, 370),
                  places=[("Über der Bordüre", 0, 78, 420, 70), ("Ecke rechts unten", 205, 70, 140, 80),
                          ("Mitte", 0, -20, 450, 250)]),
    "pillow": dict(name="Kissen 40 × 40 cm", shape=pillow_shape, details=pillow_details,
                   bounds=QRectF(-205, -205, 410, 410), places=[("Mitte", 0, 0, 300, 300)]),
    "bib": dict(name="Lätzchen", shape=bib_shape, details=bib_details, bounds=QRectF(-120, -155, 240, 310),
                places=[("Mitte", 0, 35, 150, 140)]),
}


def default_product(doc):
    from .threads import is_cap_hoop
    if is_cap_hoop(doc.hoop) or doc.fabric_type == "cap":
        return "cap"
    if doc.fabric_type == "towel":
        return "towel"
    return "shirt"


# ---------------------------------------------------------------- Entwurf als Bild
def design_image(doc, px_per_mm):
    """(QImage mit transparentem Hintergrund, (minx, miny, maxx, maxy) in mm) oder (None, None)."""
    blocks = doc.machine_blocks()
    pts = [s for _, sts in blocks for s in sts]
    if not pts:
        return None, None
    m = 1.0
    minx, miny = min(s[0] for s in pts) - m, min(s[1] for s in pts) - m
    maxx, maxy = max(s[0] for s in pts) + m, max(s[1] for s in pts) + m
    W = max(1, int((maxx - minx) * px_per_mm))
    H = max(1, int((maxy - miny) * px_per_mm))
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(px_per_mm, px_per_mm)
    p.translate(-minx, -miny)
    for color, sts in blocks:
        lines, _ = stitch_lines(sts)
        paint_thread(p, lines, color, "real", 3.0)
    p.end()
    return img, (minx, miny, maxx, maxy)


def draw_curved(p, img, target, radius):
    """Entwurf auf eine gewölbte Fläche (Kappe) legen: in schmalen Streifen, zur Seite hin
    gestaucht, leicht nach unten gebogen und zu den Seiten abgedunkelt (nur die Fäden)."""
    shaded = img.copy()
    sp = QPainter(shaded)
    sp.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    g = QLinearGradient(0, 0, shaded.width(), 0)
    g.setColorAt(0, QColor(0, 0, 0, 80))
    g.setColorAt(0.3, QColor(0, 0, 0, 0))
    g.setColorAt(0.7, QColor(0, 0, 0, 0))
    g.setColorAt(1, QColor(0, 0, 0, 80))
    sp.fillRect(shaded.rect(), QBrush(g))
    sp.end()
    n = max(8, min(240, shaded.width() // 2))
    sw = shaded.width() / n
    w_mm = target.width()
    for k in range(n):
        x0 = (k / n - 0.5) * w_mm
        x1 = ((k + 1) / n - 0.5) * w_mm
        a0, a1 = x0 / radius, x1 / radius
        X0, X1 = radius * math.sin(a0), radius * math.sin(a1)
        am = (a0 + a1) / 2
        dy = radius * (1 - math.cos(am)) * 0.55
        r = QRectF(target.center().x() + X0, target.top() + dy, X1 - X0 + 0.05, target.height())
        p.drawImage(r, shaded, QRectF(k * sw, 0, sw, shaded.height()))


def view_scale(rect, prod, zoom):
    b = prod["bounds"]
    return min(rect.width() / (b.width() * 1.08), rect.height() / (b.height() * 1.08)) * zoom


def view_origin(rect, prod, s, pan):
    """Bildschirmpunkt der Weltkoordinate (0, 0): Mitte des Produkts + Verschiebung (mm)."""
    c = prod["bounds"].center() + QPointF(*pan)
    return rect.center() - c * s


def place_of(prod, idx):
    pl = prod["places"][min(idx, len(prod["places"]) - 1)]
    name, cx, cy, maxw, maxh = pl[:5]
    rot = pl[5] if len(pl) > 5 else 0.0
    return name, cx, cy, maxw, maxh, rot


def design_frame(prod, st, bb):
    """Lage des Motivs auf dem Produkt: (mitte, drehung, maßstab, breite, höhe) in mm."""
    _, cx, cy, _, _, rot0 = place_of(prod, st.get("place", 0))
    dw, dh = bb[2] - bb[0], bb[3] - bb[1]
    k = st.get("scale", 100.0) / 100.0
    return QPointF(cx + st.get("dx", 0.0), cy + st.get("dy", 0.0)), rot0 + st.get("rot", 0.0), k, dw, dh


def paint_mockup(p, rect, doc, product, color, place_idx, zoom=1.0, cache=None, st=None):
    """Zeichnet Produkt + Entwurf in rect (Gerätepixel). st: Ansicht und Anordnung
    (pan, dx, dy, rot, scale, guides) – ohne st wie früher (Zoom auf die Stelle).
    Liefert den Info-Text."""
    prod = PRODUCTS[product]
    col = QColor(color)
    st = dict(st or {})
    st["place"] = place_idx
    name, cx, cy, maxw, maxh, _ = place_of(prod, place_idx)
    if "pan" not in st:                      # alte Aufrufe: bei Zoom auf die Stelle schauen
        b = prod["bounds"]
        st["pan"] = (cx - b.center().x(), cy - b.center().y()) if zoom > 1.0 else (0.0, 0.0)
    s = view_scale(rect, prod, zoom)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.fillRect(rect, QColor("#EEF0F4"))
    o = view_origin(rect, prod, s, st["pan"])
    p.translate(o)
    p.scale(s, s)
    shape = prod["shape"]()
    p.save()                                  # Schatten
    p.translate(6, 10)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 35))
    p.drawPath(shape)
    p.restore()
    p.setPen(QPen(col.darker(150), 1.4))      # Stoff
    p.setBrush(col)
    p.drawPath(shape)
    p.save()
    p.setClipPath(shape)
    prod["details"](p, col)
    p.restore()
    if prod.get("outside"):
        prod["outside"](p, col)              # Henkel, Schirm, Kapuze, Kragen
    # Entwurf
    ppm = max(1.0, min(16.0, s * p.device().devicePixelRatioF() * 1.2 * st.get("scale", 100) / 100))
    key = (doc.to_json(), round(ppm, 1))
    if cache is not None and cache.get("key") == key:
        img, bb = cache["img"], cache["bb"]
    else:
        img, bb = design_image(doc, ppm)
        if cache is not None:
            cache.update(key=key, img=img, bb=bb)
    lines = []
    if img is not None:
        c, rot, k, dw, dh = design_frame(prod, st, bb)
        target = QRectF(-dw / 2, -dh / 2, dw, dh)
        p.save()
        p.setClipPath(shape)
        p.translate(c)
        p.rotate(rot)
        p.scale(k, k)
        if prod.get("curved"):
            draw_curved(p, img, target, 112.0 / k)
        else:
            p.drawImage(target, img)
        p.restore()
        w_mm, h_mm = (dw - 2) * k, (dh - 2) * k
        lines.append(f"Motiv {w_mm:.0f} × {h_mm:.0f} mm"
                     + (f" (Vorschau {st.get('scale', 100):.0f} %)" if abs(k - 1) > 1e-3 else ""))
        if w_mm > maxw + 0.5 or h_mm > maxh + 0.5:
            lines.append(f"größer als üblich für »{name}« (bis ca. {maxw} × {maxh} mm)")
        if prod.get("collar") is not None:
            top = c.y() - h_mm / 2
            dist = (top - prod["collar"]) / 10.0
            lines.append(f"Oberkante {dist:.1f} cm unter dem Kragen".replace(".", ","))
        if st.get("guides", True):
            _guides(p, prod, cx, cy, maxw, maxh, c, h_mm, s)
    else:
        lines.append("Noch kein Entwurf – zeichne etwas, die Vorschau aktualisiert sich von selbst.")
    # Licht und Falten über alles (wirkt wie echter Stoff)
    p.save()
    p.setClipPath(shape)
    br = shape.boundingRect()
    lg = QRadialGradient(br.center() + QPointF(-br.width() * 0.2, -br.height() * 0.25),
                         max(br.width(), br.height()) * 0.75)
    lg.setColorAt(0, QColor(255, 255, 255, 40))
    lg.setColorAt(0.6, QColor(255, 255, 255, 0))
    lg.setColorAt(1, QColor(0, 0, 0, 55))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(lg))
    p.drawRect(br)
    p.restore()
    p.restore()
    return " · ".join(lines)


def _guides(p, prod, cx, cy, maxw, maxh, c, h_mm, s):
    """Hilfslinien: üblicher Bereich der Position, Mittellinie und Abstand zum Kragen."""
    pen = QPen(QColor(233, 30, 99, 170), 1.2 / s * 1.6, Qt.DashLine)
    pen.setCosmetic(True)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(cx - maxw / 2, cy - maxh / 2, maxw, maxh))
    mid = QPen(QColor(233, 30, 99, 90), 1, Qt.DotLine)
    mid.setCosmetic(True)
    p.setPen(mid)
    p.drawLine(QPointF(cx, cy - maxh / 2 - 15), QPointF(cx, cy + maxh / 2 + 15))
    if prod.get("collar") is not None:
        top = c.y() - h_mm / 2
        dim = QPen(QColor("#E91E63"), 1.5)
        dim.setCosmetic(True)
        p.setPen(dim)
        x = c.x()
        ref = QPen(QColor(233, 30, 99, 120), 1, Qt.DotLine)   # Bezug: tiefster Kragenpunkt
        ref.setCosmetic(True)
        p.setPen(ref)
        p.drawLine(QPointF(0, prod["collar"]), QPointF(x, prod["collar"]))
        p.setPen(dim)
        p.drawLine(QPointF(x, prod["collar"]), QPointF(x, top))
        for y in (prod["collar"], top):
            p.drawLine(QPointF(x - 6, y), QPointF(x + 6, y))
        # Beschriftung in Bildschirmgröße (unabhängig vom Zoom)
        at = p.transform().map(QPointF(x, (prod["collar"] + top) / 2))
        p.save()
        p.resetTransform()
        f = QFont("DejaVu Sans")
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        txt = f"{(top - prod['collar']) / 10:.1f} cm".replace(".", ",")
        tw = p.fontMetrics().horizontalAdvance(txt) + 10
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 220))
        p.drawRoundedRect(QRectF(at.x() + 8, at.y() - 10, tw, 20), 4, 4)
        p.setPen(QColor("#C2185B"))
        p.drawText(QRectF(at.x() + 8, at.y() - 10, tw, 20), Qt.AlignCenter, txt)
        p.restore()


# ---------------------------------------------------------------- Fenster
class MockupView(QWidget):
    """Vorschau mit Mausrad-Zoom, Verschieben (Ziehen neben dem Motiv) und Motiv-Ziehen."""

    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self.setMinimumSize(420, 420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self._drag = None

    def _xf(self):
        prod = PRODUCTS[self.dlg.product]
        s = view_scale(QRectF(self.rect()), prod, self.dlg.zoom)
        return prod, s, view_origin(QRectF(self.rect()), prod, s, self.dlg.pan)

    def to_world(self, pos):
        _, s, o = self._xf()
        return (QPointF(pos) - o) / s

    def on_design(self, pos):
        """Liegt der Bildschirmpunkt auf dem Motiv?"""
        bb = self.dlg.cache.get("bb")
        if not bb:
            return False
        prod = PRODUCTS[self.dlg.product]
        c, rot, k, dw, dh = design_frame(prod, self.dlg.state(), bb)
        w = self.to_world(pos) - c
        a = math.radians(-rot)
        lx = w.x() * math.cos(a) - w.y() * math.sin(a)
        ly = w.x() * math.sin(a) + w.y() * math.cos(a)
        return abs(lx) <= dw * k / 2 + 2 and abs(ly) <= dh * k / 2 + 2

    def paintEvent(self, ev):
        p = QPainter(self)
        d = self.dlg
        info = paint_mockup(p, QRectF(self.rect()), d.window.doc, d.product, d.color, d.place,
                            d.zoom, d.cache, d.state())
        p.end()
        d.set_info(info)

    def wheelEvent(self, ev):
        """Zoom an der Mausposition."""
        steps = ev.angleDelta().y() / 120.0
        if not steps:
            return
        d = self.dlg
        pos = ev.position()
        before = self.to_world(pos)
        d.zoom = max(0.5, min(12.0, d.zoom * (1.18 ** steps)))
        prod, s, _ = self._xf()
        c = prod["bounds"].center()
        # Weltpunkt unter der Maus bleibt stehen
        d.pan = (before.x() - c.x() - (pos.x() - self.width() / 2) / s,
                 before.y() - c.y() - (pos.y() - self.height() / 2) / s)
        d.zoom_changed()
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.on_design(ev.position()):
            self._drag = ("design", ev.position(), self.dlg.dx, self.dlg.dy)
            self.setCursor(Qt.ClosedHandCursor)
        elif ev.button() in (Qt.LeftButton, Qt.MiddleButton, Qt.RightButton):
            self._drag = ("pan", ev.position(), *self.dlg.pan)
            self.setCursor(Qt.SizeAllCursor)

    def mouseMoveEvent(self, ev):
        d = self.dlg
        if self._drag is None:
            self.setCursor(Qt.OpenHandCursor if self.on_design(ev.position()) else Qt.ArrowCursor)
            return
        kind, start, a, b = self._drag
        _, s, _ = self._xf()
        delta = (ev.position() - start) / s
        if kind == "design":
            if ev.modifiers() & Qt.ShiftModifier:          # nur waagerecht oder senkrecht
                if abs(delta.x()) > abs(delta.y()):
                    delta.setY(0)
                else:
                    delta.setX(0)
            d.dx, d.dy = round(a + delta.x(), 1), round(b + delta.y(), 1)
            d.layout_changed()
        else:
            d.pan = (a - delta.x(), b - delta.y())
        self.update()

    def mouseReleaseEvent(self, ev):
        self._drag = None
        self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, ev):
        self.dlg.fit_view()

    def keyPressEvent(self, ev):
        d = self.dlg
        step = 10.0 if ev.modifiers() & Qt.ShiftModifier else 1.0
        moves = {Qt.Key_Left: (-step, 0), Qt.Key_Right: (step, 0), Qt.Key_Up: (0, -step),
                 Qt.Key_Down: (0, step)}
        if ev.key() in moves:
            mx, my = moves[ev.key()]
            d.dx, d.dy = d.dx + mx, d.dy + my
            d.layout_changed()
            self.update()
        elif ev.key() in (Qt.Key_Plus, Qt.Key_Equal):
            d.set_zoom(d.zoom * 1.25)
        elif ev.key() == Qt.Key_Minus:
            d.set_zoom(d.zoom / 1.25)
        else:
            super().keyPressEvent(ev)


class MockupDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        from .controls import SliderSpin
        self.window = window
        self.setWindowTitle("Produktvorschau")
        self.setModal(False)
        self.resize(1080, 760)
        self.cache = {}
        self.product = default_product(window.doc)
        self.color = window.doc.fabric
        self.place = 0
        self.zoom = 1.0
        self.pan = (0.0, 0.0)
        self.dx = self.dy = 0.0
        self.rot = 0.0
        self.scale = 100.0
        self.guides = True
        self._seen = (window.doc.hoop, window.doc.fabric)
        lay = QHBoxLayout(self)
        side = QVBoxLayout()
        form = QFormLayout()
        self.prod_cb = QComboBox()
        for k, d in PRODUCTS.items():
            self.prod_cb.addItem(d["name"], k)
        self.color_cb = QComboBox()
        from . import icons
        for name, c in FABRICS:
            self.color_cb.addItem(icons.swatch(c, 16), name, c)
        self.place_cb = QComboBox()
        self.zoom_cb = QComboBox()                 # schnelle Ansichten (Mausrad zoomt frei)
        for label, z in (("Ganzes Produkt", 1.0), ("Näher (2×)", 2.0), ("Nah (3,5×)", 3.5)):
            self.zoom_cb.addItem(label, z)
        form.addRow("Produkt", self.prod_cb)
        form.addRow("Farbe", self.color_cb)
        form.addRow("Position", self.place_cb)
        form.addRow("Ansicht", self.zoom_cb)
        side.addLayout(form)
        zrow = QHBoxLayout()
        for label, tip, fn in (("−", "Verkleinern", lambda: self.set_zoom(self.zoom / 1.25)),
                               ("+", "Vergrößern", lambda: self.set_zoom(self.zoom * 1.25)),
                               ("Einpassen", "Ganzes Produkt zeigen (Doppelklick)", self.fit_view),
                               ("Auf Motiv", "Auf das Motiv zoomen", self.zoom_to_design)):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            zrow.addWidget(b)
        self.zoom_lbl = QLabel()
        self.zoom_lbl.setObjectName("muted")
        side.addLayout(zrow)
        side.addWidget(self.zoom_lbl)
        box = QLabel("<b>Motiv anordnen</b>")
        side.addWidget(box)
        form2 = QFormLayout()
        self.rot_s = SliderSpin(-180, 180, 1, 0, " °")
        self.scale_s = SliderSpin(20, 300, 5, 0, " %")
        self.scale_s.setValue(100)
        form2.addRow("Drehung", self.rot_s)
        form2.addRow("Größe", self.scale_s)
        side.addLayout(form2)
        self.pos_lbl = QLabel()
        self.pos_lbl.setObjectName("muted")
        side.addWidget(self.pos_lbl)
        arow = QHBoxLayout()
        reset = QPushButton("Zurücksetzen")
        reset.setToolTip("Verschiebung, Drehung und Größe der Vorschau zurücksetzen")
        reset.clicked.connect(self.reset_layout)
        self.apply_btn = QPushButton("Übernehmen")
        self.apply_btn.setToolTip("Größe und Drehung aus der Vorschau auf das Design anwenden "
                                  "(rückgängig mit Strg+Z)")
        self.apply_btn.clicked.connect(self.apply_to_design)
        arow.addWidget(reset)
        arow.addWidget(self.apply_btn)
        side.addLayout(arow)
        self.guides_cb = QCheckBox("Hilfslinien (Bereich, Abstand zum Kragen)")
        self.guides_cb.setChecked(True)
        side.addWidget(self.guides_cb)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setObjectName("muted")
        side.addWidget(self.info)
        hint = QLabel("Mausrad = zoomen · Motiv ziehen = verschieben (Umschalt = gerade) · daneben "
                      "ziehen = Ansicht verschieben · Pfeiltasten = Motiv um 1 mm (Umschalt 10 mm). "
                      "Die Vorschau aktualisiert sich beim Weiterarbeiten.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        side.addWidget(hint)
        side.addStretch(1)
        save = QPushButton("Als Bild speichern …")
        save.clicked.connect(self.save_image)
        close = QPushButton("Schließen")
        close.clicked.connect(self.close)
        side.addWidget(save)
        side.addWidget(close)
        sw = QWidget()
        sw.setLayout(side)
        sw.setFixedWidth(300)
        lay.addWidget(sw)
        self.view = MockupView(self)
        lay.addWidget(self.view, 1)
        self._sync_controls()
        self.prod_cb.currentIndexChanged.connect(self._product_changed)
        self.color_cb.currentIndexChanged.connect(self._changed)
        self.place_cb.currentIndexChanged.connect(self._place_changed)
        self.zoom_cb.currentIndexChanged.connect(self._zoom_preset)
        self.rot_s.valueChanged.connect(self._arrange)
        self.scale_s.valueChanged.connect(self._arrange)
        self.guides_cb.toggled.connect(self._arrange)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.view.update)
        self.zoom_changed()
        self.layout_changed()

    # ---------------------------------------------------- Zustand
    def state(self):
        return {"pan": self.pan, "dx": self.dx, "dy": self.dy, "rot": self.rot,
                "scale": self.scale, "guides": self.guides, "place": self.place}

    def _sync_controls(self):
        for cb in (self.prod_cb, self.color_cb, self.place_cb):
            cb.blockSignals(True)
        self.prod_cb.setCurrentIndex(self.prod_cb.findData(self.product))
        i = self.color_cb.findData(self.color)
        if i < 0:
            from . import icons
            self.color_cb.addItem(icons.swatch(self.color, 16), "Stofffarbe des Designs", self.color)
            i = self.color_cb.count() - 1
        self.color_cb.setCurrentIndex(i)
        self.place_cb.clear()
        for pl in PRODUCTS[self.product]["places"]:
            self.place_cb.addItem(pl[0])
        self.place_cb.setCurrentIndex(min(self.place, self.place_cb.count() - 1))
        for cb in (self.prod_cb, self.color_cb, self.place_cb):
            cb.blockSignals(False)

    def _product_changed(self):
        self.product = self.prod_cb.currentData()
        self.place = 0
        self._sync_controls()
        self.reset_layout(update=False)
        self.fit_view()

    def _changed(self):
        self.color = self.color_cb.currentData()
        self.view.update()

    def _place_changed(self):
        self.place = max(0, self.place_cb.currentIndex())
        self.reset_layout(update=False)
        if self.zoom > 1.0:
            self.zoom_to_design()
        self.view.update()

    def _zoom_preset(self, *_):
        z = self.zoom_cb.currentData() or 1.0
        if z <= 1.0:
            self.fit_view()
        else:
            self.zoom = z
            self._center_on_design()
            self.zoom_changed()
            self.view.update()

    def _arrange(self, *_):
        self.rot = float(self.rot_s.value())
        self.scale = float(self.scale_s.value())
        self.guides = self.guides_cb.isChecked()
        self.layout_changed()
        self.view.update()

    def layout_changed(self):
        self.pos_lbl.setText(f"Verschoben: {self.dx:+.0f} mm waagerecht, {self.dy:+.0f} mm senkrecht"
                             .replace("+0 ", "0 ").replace("-0 ", "0 "))
        self.apply_btn.setEnabled(abs(self.scale - 100) > 0.01 or abs(self.rot) > 0.01)

    def zoom_changed(self):
        self.zoom_lbl.setText(f"Zoom {self.zoom * 100:.0f} %")

    # ---------------------------------------------------- Ansicht
    def set_zoom(self, z):
        self.zoom = max(0.5, min(12.0, z))
        self.zoom_changed()
        self.view.update()

    def fit_view(self):
        self.zoom, self.pan = 1.0, (0.0, 0.0)
        self.zoom_changed()
        self.view.update()

    def _center_on_design(self):
        prod = PRODUCTS[self.product]
        _, cx, cy, *_ = place_of(prod, self.place)
        c = prod["bounds"].center()
        self.pan = (cx + self.dx - c.x(), cy + self.dy - c.y())

    def zoom_to_design(self):
        prod = PRODUCTS[self.product]
        bb = self.cache.get("bb")
        _, _, _, maxw, maxh, _ = place_of(prod, self.place)
        w = (bb[2] - bb[0]) * self.scale / 100 if bb else maxw
        h = (bb[3] - bb[1]) * self.scale / 100 if bb else maxh
        w, h = max(w, maxw), max(h, maxh)        # die ganze Stelle samt Hilfsrahmen zeigen
        b = prod["bounds"]
        _, cx, cy, *_ = place_of(prod, self.place)
        top, bottom = cy + self.dy - h / 2, cy + self.dy + h / 2
        if prod.get("collar") is not None and self.guides:
            top = min(top, prod["collar"] - 8)    # Kragen mit ins Bild (Abstandsmaß)
        h = bottom - top
        self.zoom = max(1.0, min(12.0, min(b.width() / (w * 1.6), b.height() / (h * 1.25))))
        c = b.center()
        self.pan = (cx + self.dx - c.x(), (top + bottom) / 2 - c.y())
        self.zoom_changed()
        self.view.update()
        return
        self.zoom_changed()
        self.view.update()

    # ---------------------------------------------------- Motiv
    def reset_layout(self, update=True):
        self.dx = self.dy = 0.0
        for w, v in ((self.rot_s, 0), (self.scale_s, 100)):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)
        self.rot, self.scale = 0.0, 100.0
        self.layout_changed()
        if update:
            self.view.update()

    def apply_to_design(self):
        """Größe und Drehung der Vorschau auf das Design anwenden."""
        from .canvas import transform_objects
        w = self.window
        objs = [o for o in w.doc.objects if o.visible]
        if not objs:
            return
        bb = self.cache.get("bb")
        if bb:
            center = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
        else:
            center = (0.0, 0.0)
        transform_objects(objs, center, scale=self.scale / 100.0, angle=self.rot)
        w.rebuild(objs)
        w.sync_items([o.id for o in w.selected_objects()])
        w.commit()
        w.lbl_tip.setText(f"Design aus der Vorschau übernommen: Größe {self.scale:.0f} %, "
                          f"Drehung {self.rot:.0f}° – rückgängig mit Strg+Z.")
        self.reset_layout()

    # ---------------------------------------------------- Hauptfenster
    def set_info(self, text):
        if self.info.text() != text:
            self.info.setText(text)

    def follow_document(self):
        """Rahmen oder Stofffarbe im Hauptfenster geändert: Produkt bzw. Farbe mitnehmen."""
        doc = self.window.doc
        hoop, fabric = doc.hoop, doc.fabric
        old_hoop, old_fabric = self._seen
        self._seen = (hoop, fabric)
        changed = False
        if hoop != old_hoop and default_product(doc) != self.product:
            self.product, self.place = default_product(doc), 0
            changed = True
        if fabric != old_fabric and fabric != self.color:
            self.color = fabric
            changed = True
        if changed:
            self._sync_controls()

    def schedule(self):
        """Vom Hauptfenster nach jeder Änderung aufgerufen."""
        if self.isVisible():
            self.follow_document()
            self.timer.start()

    def render_image(self, size=QSize(1600, 1200)):
        img = QImage(size, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor("#EEF0F4"))
        p = QPainter(img)
        st = self.state()
        st["guides"] = False                  # Kundenbild ohne Hilfslinien
        if self.zoom > 1.0 and self.pan == (0.0, 0.0):
            st.pop("pan")                     # Zoom ohne eigene Verschiebung: auf die Stelle
        paint_mockup(p, QRectF(0, 0, size.width(), size.height()), self.window.doc, self.product,
                     self.color, self.place, self.zoom, None, st)
        p.end()
        return img

    def save_image(self, path=None):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Vorschau speichern",
                                                  f"Vorschau {PRODUCTS[self.product]['name']}.png",
                                                  "PNG-Bild (*.png);;JPEG-Bild (*.jpg)")
        if path:
            self.render_image().save(path)
            self.window.lbl_tip.setText(f"Vorschau gespeichert: {path}")
        return path
