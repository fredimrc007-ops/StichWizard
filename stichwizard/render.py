"""Darstellung: Stickrahmen und realistisch gerenderte Stickobjekte."""
from PySide6.QtCore import QByteArray, QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPainterPathStroker, QPen, QPixmap)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QStyleOptionGraphicsItem

from .engine import JUMP, STITCH, lines_of, polygons_of


class ViewOptions:
    mode = "real"          # real | stitch
    show_jumps = False
    show_grid = True
    grid_step = 10
    wheel = "zoom"         # zoom | scroll


def stitch_lines(sts):
    """Teilt eine Stichliste in sichtbare Stich- und Sprunglinien."""
    lines, jumps = [], []
    prev = None
    for x, y, f in sts:
        if prev is not None:
            if f == STITCH:
                lines.append(QLineF(prev[0], prev[1], x, y))
            elif f == JUMP:
                jumps.append(QLineF(prev[0], prev[1], x, y))
        prev = (x, y)
    return lines, jumps


def paint_thread(painter, lines, color, mode, lod=1.0):
    col = QColor(color)
    if mode == "stitch":
        pen = QPen(col, 0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLines(lines)
        if lod > 2.5:
            pp = QPen(col.darker(160), 3)
            pp.setCosmetic(True)
            painter.setPen(pp)
            painter.drawPoints([l.p2() for l in lines])
        return
    shadow = QPen(col.darker(175), 0.46, Qt.SolidLine, Qt.RoundCap)
    base = QPen(col, 0.30, Qt.SolidLine, Qt.RoundCap)
    hi = QPen(col.lighter(150) if col.lightness() < 200 else QColor(255, 255, 255),
              0.10, Qt.SolidLine, Qt.RoundCap)
    dc = col.darker(185)
    dc.setAlpha(170)
    dent = QPen(dc, 0.2, Qt.SolidLine, Qt.RoundCap)
    # in Abschnitten zeichnen, damit spätere Stiche frühere korrekt überdecken
    step = 12
    for i in range(0, len(lines), step):
        chunk = lines[i:i + step]
        painter.setPen(shadow)
        painter.drawLines(chunk)
        if lod < 0.8:
            continue
        painter.setPen(base)
        painter.drawLines(chunk)
        if lod < 1.6:
            continue
        painter.setPen(hi)
        painter.translate(-0.05, -0.05)
        painter.drawLines(chunk)
        painter.translate(0.05, 0.05)
        if lod >= 2.5:
            # Einstichpunkte als kleine Vertiefung – macht Tatami-Muster sichtbar
            painter.setPen(dent)
            painter.drawPoints([l.p2() for l in chunk])


def geom_path(geom):
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    for poly in polygons_of(geom):
        for ring in [poly.exterior] + list(poly.interiors):
            pts = list(ring.coords)
            if len(pts) < 2:
                continue
            path.moveTo(*pts[0])
            for p in pts[1:]:
                path.lineTo(*p)
            path.closeSubpath()
    for line in lines_of(geom):
        pts = list(line.coords)
        if len(pts) < 2:
            continue
        lp = QPainterPath()
        lp.moveTo(*pts[0])
        for p in pts[1:]:
            lp.lineTo(*p)
        st = QPainterPathStroker()
        st.setWidth(3.0)
        path.addPath(st.createStroke(lp))
    return path


class HoopItem(QGraphicsItem):
    def __init__(self, opts):
        super().__init__()
        self.opts = opts
        self.w, self.h = 130, 180
        self.fabric = "#FFFFFF"
        self.cap = False
        self.setZValue(-1000)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    def set_hoop(self, w, h, fabric, cap=False):
        self.prepareGeometryChange()
        self.w, self.h, self.fabric, self.cap = w, h, fabric, cap
        self.update()

    def boundingRect(self):
        m = 22
        extra = self.h * 0.9 + 20 if self.cap else 0       # Schirm unter dem Kappenrahmen
        return QRectF(-self.w / 2 - m, -self.h / 2 - m, self.w + 2 * m, self.h + 2 * m + extra)

    def paint(self, p, option, widget=None):
        w, h = self.w, self.h
        p.setRenderHint(QPainter.Antialiasing)
        outer = QRectF(-w / 2 - 16, -h / 2 - 16, w + 32, h + 32)
        inner = QRectF(-w / 2 - 6, -h / 2 - 6, w + 12, h + 12)
        # Stoff
        fab = QColor(self.fabric)
        p.setPen(Qt.NoPen)
        p.setBrush(fab)
        p.drawRoundedRect(inner, 14, 14)
        # Stoffstruktur (nur ohne Raster – sonst wirken die Streifen wie liniertes Papier)
        if not self.opts.show_grid:
            weave = QPen(fab.darker(108) if fab.lightness() > 60 else fab.lighter(130), 0.15)
            p.setPen(weave)
            y = inner.top()
            while y < inner.bottom():
                p.drawLine(QPointF(inner.left() + 2, y), QPointF(inner.right() - 2, y))
                y += 1.2
        # Raster: Quadrate von der Rahmenmitte aus, jede 5. Linie kräftiger (wie Millimeterpapier)
        if self.opts.show_grid:
            light = fab.lightness() > 120
            minor = QPen(QColor(0, 0, 0, 38) if light else QColor(255, 255, 255, 45), 0)
            major = QPen(QColor(0, 0, 0, 80) if light else QColor(255, 255, 255, 90), 0)
            minor.setCosmetic(True)
            major.setCosmetic(True)
            step = self.opts.grid_step
            n = 0
            while n * step <= max(w, h) / 2:
                pen = major if n % 5 == 0 else minor
                p.setPen(pen)
                v = n * step
                for sgn in ((1,) if n == 0 else (1, -1)):
                    if v <= w / 2:
                        p.drawLine(QPointF(sgn * v, -h / 2), QPointF(sgn * v, h / 2))
                    if v <= h / 2:
                        p.drawLine(QPointF(-w / 2, sgn * v), QPointF(w / 2, sgn * v))
                n += 1
        # Stickfeld
        from . import style
        ac = QColor(style.accent())
        ac.setAlpha(170)
        fp = QPen(ac, 0, Qt.DashLine)
        fp.setCosmetic(True)
        p.setPen(fp)
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(-w / 2, -h / 2, w, h))
        # Mittelmarken
        ac.setAlpha(200)
        mp = QPen(ac, 0.4)
        p.setPen(mp)
        for a, b in (((-w / 2, 0), (-w / 2 + 6, 0)), ((w / 2, 0), (w / 2 - 6, 0)),
                     ((0, -h / 2), (0, -h / 2 + 6)), ((0, h / 2), (0, h / 2 - 6))):
            p.drawLine(QPointF(*a), QPointF(*b))
        if self.cap:
            self._paint_cap_frame(p, outer, inner)
            return
        # Rahmen (Kunststoff)
        ring = QPainterPath()
        ring.setFillRule(Qt.OddEvenFill)
        ring.addRoundedRect(outer, 22, 22)
        ring.addRoundedRect(inner, 14, 14)
        grad = QLinearGradient(outer.topLeft(), outer.bottomRight())
        grad.setColorAt(0, QColor("#5A6274"))
        grad.setColorAt(0.5, QColor("#3B4252"))
        grad.setColorAt(1, QColor("#2A2F3A"))
        p.setPen(QPen(QColor("#20242D"), 0.5))
        p.setBrush(QBrush(grad))
        p.drawPath(ring)
        p.setPen(QPen(QColor(255, 255, 255, 50), 0.6))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(outer.adjusted(1.2, 1.2, -1.2, -1.2), 21, 21)
        # Klemmschraube
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#9AA3B5"))
        p.drawRoundedRect(QRectF(-9, -h / 2 - 22, 18, 9), 3, 3)

    def _paint_cap_frame(self, p, outer, inner):
        """Kappenrahmen: Metallbügel um ein breites, flaches Feld, darunter der Schirm."""
        w, h = self.w, self.h
        fab = QColor(self.fabric)
        # Schirm (angedeutet, in Stofffarbe etwas dunkler)
        visor = QPainterPath(QPointF(-w / 2 - 10, h / 2 + 14))
        visor.cubicTo(-w / 2 + w * 0.1, h / 2 + 14 + h * 0.9, w / 2 - w * 0.1, h / 2 + 14 + h * 0.9,
                      w / 2 + 10, h / 2 + 14)
        visor.closeSubpath()
        vg = QLinearGradient(0, h / 2 + 14, 0, h / 2 + 14 + h * 0.7)
        vg.setColorAt(0, fab.darker(118))
        vg.setColorAt(1, fab.darker(140))
        p.setPen(QPen(fab.darker(170), 0.6))
        p.setBrush(QBrush(vg))
        p.drawPath(visor)
        seam = QPen(fab.darker(160), 0.35, Qt.DashLine)
        p.setPen(seam)
        p.setBrush(Qt.NoBrush)
        inner_v = QPainterPath(QPointF(-w / 2 + 2, h / 2 + 18))
        inner_v.cubicTo(-w / 2 + w * 0.12, h / 2 + 10 + h * 0.8, w / 2 - w * 0.12,
                        h / 2 + 10 + h * 0.8, w / 2 - 2, h / 2 + 18)
        p.drawPath(inner_v)
        # Metallbügel
        ring = QPainterPath()
        ring.setFillRule(Qt.OddEvenFill)
        ring.addRoundedRect(outer, 12, 12)
        ring.addRoundedRect(inner, 8, 8)
        grad = QLinearGradient(outer.topLeft(), outer.bottomLeft())
        grad.setColorAt(0, QColor("#DDE2EA"))
        grad.setColorAt(0.45, QColor("#9AA3B2"))
        grad.setColorAt(0.55, QColor("#C9CFD9"))
        grad.setColorAt(1, QColor("#7D8696"))
        p.setPen(QPen(QColor("#5B6271"), 0.5))
        p.setBrush(QBrush(grad))
        p.drawPath(ring)
        # Klammern links/rechts und Haltebügel oben
        p.setPen(QPen(QColor("#4A5060"), 0.4))
        p.setBrush(QColor("#6B7383"))
        for x in (-w / 2 - 16, w / 2 + 8):
            p.drawRoundedRect(QRectF(x, -6, 8, 12), 2, 2)
        p.drawRoundedRect(QRectF(-14, -h / 2 - 22, 28, 8), 3, 3)


class ObjectItem(QGraphicsItem):
    def __init__(self, obj, opts):
        super().__init__()
        self.obj = obj
        self.opts = opts
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        # Als Bild zwischenspeichern: Verschieben zeichnet dann keine Stiche neu
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self._rect = QRectF()
        self._orect = QRectF()
        self._overlay = []
        self._hit = QPainterPath()
        self.rebuild()

    def rebuild(self):
        self.prepareGeometryChange()
        self.setPos(self.obj.x, self.obj.y)
        self.setVisible(self.obj.visible and not getattr(self.obj, "_lhidden", False))
        locked = getattr(self.obj, "locked", False) or getattr(self.obj, "_llocked", False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, not locked)
        self.setFlag(QGraphicsItem.ItemIsMovable, not locked)
        self.setAcceptedMouseButtons(Qt.NoButton if locked else Qt.AllButtons)
        self.blocks = []
        xs, ys = [], []
        self._knock = getattr(self.obj, "_knock_key", None)   # gezeichnete Aussparung
        for color, sts in self.obj.stitch_blocks():
            lines, jumps = stitch_lines(sts)
            self.blocks.append((color, lines, jumps))
            xs.extend(s[0] for s in sts)
            ys.extend(s[1] for s in sts)
        geom = self.obj.shaped_geometry()
        if xs:
            self._rect = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        elif self.obj.kind in ("stones", "print") and geom is not None and not geom.is_empty:
            b = geom.bounds
            self._rect = QRectF(b[0], b[1], b[2] - b[0], b[3] - b[1])
        else:
            self._rect = QRectF(-5, -5, 10, 10)
        if geom is not None and not geom.is_empty:
            self._hit = geom_path(geom)
        else:
            self._hit = QPainterPath()
            self._hit.addRect(self._rect)
        st = QPainterPathStroker()
        st.setWidth(2.0)
        self._grab = self._hit.united(st.createStroke(self._hit))
        self._overlay = overlays(self.obj)
        pts = [q for _, ps in self._overlay for q in ps]
        self._orect = QRectF(self._rect)
        if pts:
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            self._orect = self._orect.united(QRectF(min(xs) - 2, min(ys) - 2,
                                                    max(xs) - min(xs) + 4, max(ys) - min(ys) + 4))
        self.update()

    def stitch_rect(self):
        return QRectF(self._rect)

    def boundingRect(self):
        if self.isSelected() and self._overlay:
            return self._orect.adjusted(-1.5, -1.5, 1.5, 1.5)
        return self._rect.adjusted(-1.5, -1.5, 1.5, 1.5)

    def shape(self):
        # Ausgewählte Objekte und Schriftzüge lassen sich überall in ihrem Rahmen greifen,
        # sonst genau an der Form (plus 1 mm Toleranz, damit dünne Teile greifbar sind).
        if self.isSelected() or self.obj.kind in ("text", "stitches", "stones", "print"):
            p = QPainterPath()
            p.addRect(self._rect.adjusted(-1, -1, 1, 1))
            return p
        return self._grab

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            self.prepareGeometryChange()
        return super().itemChange(change, value)

    def paint(self, p, option, widget=None):
        lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(p.worldTransform())
        p.setRenderHint(QPainter.Antialiasing, lod > 0.6)
        if self.obj.kind == "print":
            from .printapp import paint as paint_print
            paint_print(p, self.obj)
        if self.obj.kind in ("shape", "text") and self.obj.fill.get("type") == "applique" \
                and not self.obj.fill.get("print"):
            # aufgelegter Applikationsstoff (wird nicht gestickt)
            fab = QColor(self.obj.fill["color"])
            p.setPen(Qt.NoPen)
            p.setBrush(fab)
            p.drawPath(self._hit)
            p.setBrush(QBrush(fab.darker(112), Qt.Dense6Pattern))
            p.drawPath(self._hit)
        if self.obj.kind == "stones":
            from .stones import paint as paint_stones
            paint_stones(p, self.obj)
        for color, lines, jumps in self.blocks:
            if lines:
                paint_thread(p, lines, color, self.opts.mode, lod)
            if self.opts.show_jumps and jumps:
                jp = QPen(QColor(120, 120, 120, 180), 0, Qt.DashLine)
                jp.setCosmetic(True)
                p.setPen(jp)
                p.drawLines(jumps)
        if self.isSelected():
            from . import style
            sp = QPen(QColor(style.accent()), 1.4, Qt.DashLine)
            sp.setCosmetic(True)
            p.setPen(sp)
            p.setBrush(Qt.NoBrush)
            p.drawRect(self._rect.adjusted(-0.8, -0.8, 0.8, 0.8))
            paint_overlays(p, self._overlay)


def overlays(obj):
    """Hilfslinien eines Objekts im Objektrahmen: Führungslinie, Textpfad, Start/Ende."""
    out = []
    if obj.kind in ("shape", "text") and obj.fill.get("type") == "guided" and obj.fill.get("guide"):
        out.append(("guide", obj.shaped_points(obj.fill["guide"])))
    if obj.kind == "text" and obj.text.get("path"):
        out.append(("path", obj.shaped_points(obj.text["path"])))
    if obj.kind in ("shape", "text", "satin"):
        for k in ("start", "end"):
            if obj.fill.get(k):
                out.append((k, [obj.shaped_point(obj.fill[k])]))
    return out


def paint_overlays(p, items):
    for kind, pts in items:
        if kind in ("guide", "path"):
            pen = QPen(QColor("#7E57C2"), 1.6, Qt.DashLine if kind == "guide" else Qt.DotLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            path = QPainterPath(QPointF(*pts[0]))
            for q in pts[1:]:
                path.lineTo(QPointF(*q))
            p.drawPath(path)
            if kind == "guide":           # Pfeil = Richtung der Führungslinie
                p.setBrush(QColor("#7E57C2"))
                p.drawEllipse(QPointF(*pts[0]), 0.7, 0.7)
        else:
            x, y = pts[0]
            pen = QPen(QColor("white"), 1.4)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(QColor("#2E7D32") if kind == "start" else QColor("#C62828"))
            p.drawEllipse(QPointF(x, y), 1.3, 1.3)
            f = QFont("DejaVu Sans")
            f.setPixelSize(2)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(x - 1.3, y - 1.3, 2.6, 2.6), Qt.AlignCenter, "S" if kind == "start" else "E")


def render_document(doc, px_per_mm=8, opts=None, margin=4, transparent=False):
    """Rendert alle sichtbaren Objekte in ein QImage (für PNG-Export / Vorschau)."""
    opts = opts or ViewOptions()
    blocks = doc.machine_blocks()
    from .stones import collect, paint as paint_stones
    from .printapp import paint as paint_print
    prints = [o for o in doc.objects if o.kind == "print" and o.visible and doc.layer_shown(o)]
    # Ausdehnung: Stiche, Strass-Steine und Druckbilder
    ext = [(x + k * d / 2, y + k * d / 2) for x, y, d, _, _ in collect(doc) for k in (-1, 1)]
    for o in prints:
        b = o.world_geometry().bounds
        ext += [(b[0], b[1]), (b[2], b[3])]
    xs = [s[0] for _, sts in blocks for s in sts] + [q[0] for q in ext]
    ys = [s[1] for _, sts in blocks for s in sts] + [q[1] for q in ext]
    if not xs:
        img = QImage(64, 64, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        return img
    minx, miny, maxx, maxy = min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin
    W, H = int((maxx - minx) * px_per_mm), int((maxy - miny) * px_per_mm)
    img = QImage(max(1, W), max(1, H), QImage.Format_ARGB32)
    img.fill(Qt.transparent if transparent else QColor(doc.fabric))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(px_per_mm, px_per_mm)
    p.translate(-minx, -miny)
    for o in prints:                     # Druckbilder liegen unter den Stichen
        paint_print(p, o, world=True)
    for color, sts in blocks:
        lines, _ = stitch_lines(sts)
        paint_thread(p, lines, color, "real", 3.0)
    for o in doc.objects:                # Steine liegen obenauf
        if o.kind == "stones" and o.visible and doc.layer_shown(o):
            paint_stones(p, o, world=True)
    p.end()
    return img


class TemplateItem(QGraphicsPixmapItem):
    """Bildvorlage zum Nachzeichnen. Liegt über dem Stoff, unter den Stickobjekten."""

    def __init__(self):
        super().__init__()
        self.setZValue(-500)
        self.setTransformationMode(Qt.SmoothTransformation)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.data = None
        self._png = None
        self.on_moved = None
        self.setVisible(False)

    def apply(self, t):
        """Übernimmt die Einstellungen aus dem Dokument (dict oder None)."""
        self.data = t
        if not t:
            self._png = None
            self.setPixmap(QPixmap())
            self.setVisible(False)
            return
        if t["png"] != self._png:
            pm = QPixmap()
            pm.loadFromData(QByteArray.fromBase64(t["png"].encode("ascii")), "PNG")
            self.setPixmap(pm)
            self._png = t["png"]
        pm = self.pixmap()
        if pm.isNull():
            self.setVisible(False)
            return
        self.setOffset(-pm.width() / 2, -pm.height() / 2)
        self.setScale(t["width"] / pm.width())
        self.setPos(t["x"], t["y"])
        self.setOpacity(t["opacity"])
        self.setVisible(t["visible"])
        locked = t["locked"]
        self.setFlag(QGraphicsItem.ItemIsMovable, not locked)
        self.setAcceptedMouseButtons(Qt.NoButton if locked else Qt.LeftButton)
        self.setCursor(Qt.ArrowCursor if locked else Qt.SizeAllCursor)

    def height_mm(self):
        pm = self.pixmap()
        return pm.height() * self.scale() if not pm.isNull() else 0

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.data:
            self.data["x"], self.data["y"] = self.pos().x(), self.pos().y()
            if self.on_moved:
                self.on_moved()
        return super().itemChange(change, value)
