"""Vektor-Icons, direkt mit QPainter gezeichnet (keine Icon-Dateien nötig)."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QTransform)

_cache = {}


def _poly(*pts):
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _draw(name, p, c, accent):
    pen = QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if name == "select":
        p.setBrush(c)
        p.drawPolygon(_poly((6, 3), (6, 19), (10, 15), (13, 21), (15.5, 20), (12.5, 14), (18, 14)))
    elif name == "rect":
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(4, 6, 16, 12), 2, 2)
    elif name == "ellipse":
        p.setBrush(accent)
        p.drawEllipse(QRectF(3.5, 5.5, 17, 13))
    elif name == "polygon":
        p.setBrush(accent)
        p.drawPolygon(_poly((5, 18), (4, 8), (12, 4), (20, 9), (17, 19)))
    elif name == "line":
        path = QPainterPath(QPointF(3, 18))
        path.cubicTo(8, 2, 14, 24, 21, 6)
        p.setPen(QPen(accent, 3, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(pen)
        p.setBrush(c)
        for x, y in ((3, 18), (21, 6)):
            p.drawEllipse(QPointF(x, y), 1.6, 1.6)
    elif name == "pen":
        path = QPainterPath(QPointF(3, 19))
        path.cubicTo(6, 6, 16, 22, 21, 6)
        p.setPen(QPen(accent, 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(QPen(c, 1.0))
        p.drawLine(QPointF(3, 19), QPointF(6, 6))
        p.drawLine(QPointF(21, 6), QPointF(16, 22))
        p.setBrush(QColor("white"))
        for x, y in ((6, 6), (16, 22)):
            p.drawEllipse(QPointF(x, y), 1.6, 1.6)
        p.setBrush(c)
        for x, y in ((3, 19), (21, 6)):
            p.drawRect(QRectF(x - 1.7, y - 1.7, 3.4, 3.4))
    elif name == "freehand":
        path = QPainterPath(QPointF(3, 15))
        path.cubicTo(6, 6, 9, 22, 12, 13)
        path.cubicTo(15, 4, 18, 18, 21, 9)
        p.setPen(QPen(accent, 2.6, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
    elif name == "text":
        f = QFont("DejaVu Serif", 15, QFont.Bold)
        p.setFont(f)
        p.setPen(c)
        p.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, "A")
        p.setPen(QPen(accent, 2))
        p.drawLine(QPointF(5, 21), QPointF(19, 21))
    elif name == "image":
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawPolygon(_poly((5, 17), (10, 10), (14, 15), (16, 12), (19, 17)))
        p.drawEllipse(QPointF(16, 8.5), 1.6, 1.6)
    elif name == "new":
        p.drawPolygon(_poly((6, 3), (14, 3), (19, 8), (19, 21), (6, 21)))
        p.drawPolyline(_poly((14, 3), (14, 8), (19, 8)))
        p.setPen(QPen(accent, 2))
        p.drawLine(QPointF(12.5, 11), QPointF(12.5, 18))
        p.drawLine(QPointF(9, 14.5), QPointF(16, 14.5))
    elif name == "open":
        p.drawPolyline(_poly((3, 19), (3, 5), (9, 5), (11, 7), (19, 7), (19, 10)))
        p.setBrush(accent)
        p.drawPolygon(_poly((3, 19), (6, 10), (22, 10), (19, 19)))
    elif name == "save":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        p.setBrush(accent)
        p.drawRect(QRectF(7, 4, 10, 6))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(7, 13, 10, 7))
    elif name == "export":
        p.drawPolyline(_poly((8, 9), (4, 9), (4, 20), (20, 20), (20, 9), (16, 9)))
        p.setPen(QPen(accent, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(12, 3), QPointF(12, 15))
        p.drawPolyline(_poly((8, 7), (12, 3), (16, 7)))
    elif name == "import":
        p.drawPolyline(_poly((8, 9), (4, 9), (4, 20), (20, 20), (20, 9), (16, 9)))
        p.setPen(QPen(accent, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(12, 3), QPointF(12, 15))
        p.drawPolyline(_poly((8, 11), (12, 15), (16, 11)))
    elif name in ("undo", "redo"):
        p.save()
        if name == "redo":
            p.translate(24, 0)
            p.scale(-1, 1)
        path = QPainterPath(QPointF(6, 10))
        path.cubicTo(10, 5, 20, 6, 19, 14)
        path.cubicTo(18.5, 18, 15, 19, 12, 19)
        p.drawPath(path)
        p.setBrush(c)
        p.drawPolygon(_poly((4, 6), (4, 13), (10.5, 11.5)))
        p.restore()
    elif name == "play":
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(2, 2, 20, 20))
        p.setBrush(QColor("white"))
        p.drawPolygon(_poly((10, 7.5), (10, 16.5), (17, 12)))
    elif name == "pause":
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(7, 5, 3.5, 14))
        p.drawRect(QRectF(13.5, 5, 3.5, 14))
    elif name in ("zoomin", "zoomout", "fit"):
        p.drawEllipse(QRectF(4, 4, 12, 12))
        p.drawLine(QPointF(14.5, 14.5), QPointF(20, 20))
        if name != "fit":
            p.drawLine(QPointF(7, 10), QPointF(13, 10))
        if name == "zoomin":
            p.drawLine(QPointF(10, 7), QPointF(10, 13))
        if name == "fit":
            p.setPen(QPen(accent, 1.6))
            p.drawRect(QRectF(7.5, 7.5, 5, 5))
    elif name == "delete":
        p.drawLine(QPointF(4, 6), QPointF(20, 6))
        p.drawPolyline(_poly((9, 6), (9, 3.5), (15, 3.5), (15, 6)))
        p.drawPolygon(_poly((6, 6), (7, 21), (17, 21), (18, 6)))
        p.drawLine(QPointF(10, 10), QPointF(10, 17))
        p.drawLine(QPointF(14, 10), QPointF(14, 17))
    elif name == "duplicate":
        p.drawRoundedRect(QRectF(3, 3, 12, 12), 2, 2)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(9, 9, 12, 12), 2, 2)
    elif name == "mirror_h":
        p.setPen(QPen(c, 1.2, Qt.DashLine))
        p.drawLine(QPointF(12, 2), QPointF(12, 22))
        p.setPen(pen)
        p.setBrush(accent)
        p.drawPolygon(_poly((10, 6), (10, 18), (3, 18)))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(_poly((14, 6), (14, 18), (21, 18)))
    elif name == "mirror_v":
        p.setPen(QPen(c, 1.2, Qt.DashLine))
        p.drawLine(QPointF(2, 12), QPointF(22, 12))
        p.setPen(pen)
        p.setBrush(accent)
        p.drawPolygon(_poly((6, 10), (18, 10), (18, 3)))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(_poly((6, 14), (18, 14), (18, 21)))
    elif name == "center":
        p.drawRect(QRectF(3, 3, 18, 18))
        p.setPen(QPen(accent, 2))
        p.drawLine(QPointF(12, 7), QPointF(12, 17))
        p.drawLine(QPointF(7, 12), QPointF(17, 12))
    elif name in ("up", "down"):
        p.save()
        if name == "down":
            p.translate(0, 24)
            p.scale(1, -1)
        p.setPen(QPen(accent, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(12, 5), QPointF(12, 20))
        p.drawPolyline(_poly((6, 11), (12, 5), (18, 11)))
        p.restore()
    elif name == "grid":
        for i in (4, 10, 16):
            p.drawLine(QPointF(i + 2, 3), QPointF(i + 2, 21))
            p.drawLine(QPointF(3, i + 2), QPointF(21, i + 2))
    elif name == "jumps":
        p.setPen(QPen(c, 1.4, Qt.DashLine))
        p.drawLine(QPointF(5, 18), QPointF(19, 6))
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(5, 18), 2.5, 2.5)
        p.drawEllipse(QPointF(19, 6), 2.5, 2.5)
    elif name == "stitchview":
        p.setPen(QPen(accent, 1.2))
        pts = [(3, 18), (7, 6), (11, 18), (15, 6), (19, 18), (21, 10)]
        p.drawPolyline(_poly(*pts))
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        for x, y in pts:
            p.drawEllipse(QPointF(x, y), 1.4, 1.4)
    elif name == "realview":
        for i in range(6):
            p.setPen(QPen(accent.darker(130), 3.0, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(4 + i * 3, 19), QPointF(7 + i * 3, 5))
            p.setPen(QPen(accent.lighter(140), 1.0, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(3.6 + i * 3, 18), QPointF(6.6 + i * 3, 6))
    elif name == "hoop":
        p.setPen(QPen(c, 2.6))
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 4, 4)
        p.setPen(QPen(accent, 1, Qt.DashLine))
        p.drawRect(QRectF(7, 8, 10, 8))
    elif name == "fabric":
        p.setBrush(accent)
        path = QPainterPath(QPointF(3, 6))
        path.cubicTo(8, 3, 14, 9, 21, 5)
        path.lineTo(21, 18)
        path.cubicTo(14, 22, 8, 16, 3, 19)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "needle":
        p.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(5, 19), QPointF(19, 5))
        p.drawEllipse(QRectF(16, 3, 4, 4))
        p.setPen(QPen(accent, 1.4))
        path = QPainterPath(QPointF(18, 5))
        path.cubicTo(24, 12, 10, 14, 6, 22)
        p.drawPath(path)
    elif name == "vector":
        # Zeichenstift-Spitze mit Pfad und Ankerpunkten
        path = QPainterPath(QPointF(3, 20))
        path.cubicTo(5, 10, 12, 16, 13, 5)
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(QPen(c, 1.0))
        p.setBrush(QColor("white"))
        for x, y in ((3, 20), (13, 5)):
            p.drawRect(QRectF(x - 1.5, y - 1.5, 3, 3))
        p.setBrush(c)
        p.drawPolygon(_poly((17, 9), (21, 13), (19, 21), (15, 21), (13, 13)))
        p.setPen(QPen(QColor("white"), 1.0))
        p.drawLine(QPointF(17, 14), QPointF(17, 19))
    elif name == "trace":
        # Pixeltreppe links, glatter Pfad mit Knoten rechts
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c.red(), c.green(), c.blue(), 110))
        for x, y in ((3, 15), (6, 12), (6, 15), (9, 9), (9, 12), (9, 15), (3, 18), (6, 18), (9, 18)):
            p.drawRect(QRectF(x, y, 3, 3))
        path = QPainterPath(QPointF(3, 15))
        path.cubicTo(6, 6, 14, 3, 21, 5)
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(QPen(c, 1.0))
        p.setBrush(QColor("white"))
        for x, y in ((3, 15), (12, 5.6), (21, 5)):
            p.drawRect(QRectF(x - 1.4, y - 1.4, 2.8, 2.8))
    elif name == "wand":
        p.setPen(QPen(c, 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(4, 20), QPointF(15, 9))
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        for x, y, r in ((18, 6, 2.6), (11, 4, 1.3), (20, 13, 1.3)):
            pts = []
            for i in range(8):
                rr = r if i % 2 == 0 else r * 0.4
                a = math.pi * i / 4
                pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
            p.drawPolygon(_poly(*pts))
    elif name == "info":
        p.drawEllipse(QRectF(3, 3, 18, 18))
        p.setPen(QPen(accent, 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(12, 11), QPointF(12, 17))
        p.drawPoint(QPointF(12, 7.5))
    elif name == "eye":
        path = QPainterPath(QPointF(2, 12))
        path.quadTo(12, 2, 22, 12)
        path.quadTo(12, 22, 2, 12)
        p.drawPath(path)
        p.setBrush(accent)
        p.drawEllipse(QPointF(12, 12), 3.2, 3.2)
    elif name == "nodes":
        path = QPainterPath(QPointF(4, 18))
        path.cubicTo(6, 6, 14, 4, 20, 8)
        p.drawPath(path)
        p.setPen(QPen(c, 1.2))
        p.setBrush(QColor("white"))
        for x, y in ((4, 18), (20, 8)):
            p.drawRect(QRectF(x - 2.2, y - 2.2, 4.4, 4.4))
        p.setBrush(accent)
        p.drawRect(QRectF(9.3 - 2.5, 7.6 - 2.5, 5, 5))
    elif name == "eraser":
        p.save()
        p.translate(12, 12)
        p.rotate(-40)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(-8, -4.5, 9, 9), 1.5, 1.5)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, -4.5, 7, 9), 1.5, 1.5)
        p.restore()
        p.drawLine(QPointF(10, 20.5), QPointF(20, 20.5))
    elif name == "split":
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(3, 6, 8, 12), 2, 2)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(14, 6, 8, 12), 2, 2)
        p.setPen(QPen(c, 1.2, Qt.DashLine))
        p.drawLine(QPointF(12.5, 3), QPointF(12.5, 21))
    elif name == "merge":
        p.setBrush(accent)
        path = QPainterPath()
        path.addEllipse(QRectF(3, 6, 12, 12))
        path2 = QPainterPath()
        path2.addEllipse(QRectF(10, 6, 12, 12))
        p.drawPath(path.united(path2))
    elif name == "convert":
        f = QFont("DejaVu Serif", 11, QFont.Bold)
        p.setFont(f)
        p.drawText(QRectF(1, 2, 12, 14), Qt.AlignCenter, "A")
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(9, 18), QPointF(15, 18))
        p.drawPolyline(_poly((13, 15.5), (15.5, 18), (13, 20.5)))
        p.setPen(QPen(c, 1.2))
        p.setBrush(QColor("white"))
        for x, y in ((18, 6), (22, 14), (17, 21)):
            p.drawRect(QRectF(x - 1.8, y - 1.8, 3.6, 3.6))
    elif name == "simplify":
        p.setPen(QPen(c, 1.2))
        p.drawPolyline(_poly((3, 10), (5, 7), (7, 9), (9, 5), (11, 8)))
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(5, 14), QPointF(10, 14))
        p.drawPolyline(_poly((8, 12), (10, 14), (8, 16)))
        p.setPen(QPen(c, 1.6))
        path = QPainterPath(QPointF(12, 20))
        path.quadTo(16, 8, 21, 18)
        p.drawPath(path)
    elif name == "sheet":
        p.drawPolygon(_poly((5, 2.5), (15, 2.5), (19, 6.5), (19, 21.5), (5, 21.5)))
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(8, 7, 8, 6), 1, 1)
        p.setPen(QPen(c, 1.2))
        for yy in (16, 18.5):
            p.drawLine(QPointF(8, yy), QPointF(16, yy))
    elif name == "browse":
        for i, (x, y) in enumerate(((3, 4), (13, 4), (3, 13), (13, 13))):
            p.setBrush(accent if i == 0 else Qt.NoBrush)
            p.drawRoundedRect(QRectF(x, y, 8, 7), 1.5, 1.5)
    elif name == "colorsort":
        p.setPen(Qt.NoPen)
        for i, col in enumerate(("#E53935", "#E53935", "#1E88E5", "#1E88E5")):
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(3 + i * 4.6, 6, 3.6, 12), 1.2, 1.2)
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(3, 21), QPointF(21, 21))
    elif name == "satin":
        a = QPainterPath(QPointF(3, 8))
        a.cubicTo(8, 2, 14, 12, 21, 6)
        b = QPainterPath(QPointF(3, 17))
        b.cubicTo(8, 11, 14, 21, 21, 15)
        p.setPen(QPen(accent, 1.1))
        for i in range(10):
            t = 0.05 + i * 0.1
            pa, pb = a.pointAtPercent(t), b.pointAtPercent(min(1, t + 0.05))
            p.drawLine(pa, pb)
        p.setPen(QPen(c, 1.6))
        p.drawPath(a)
        p.drawPath(b)
    elif name == "corner":
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.MiterJoin))
        p.drawPolyline(_poly((4, 19), (12, 5), (20, 19)))
        p.setPen(QPen(c, 1.2))
        p.setBrush(accent)
        p.drawRect(QRectF(9.5, 2.5, 5, 5))
    elif name == "addnode":
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(_poly((3, 17), (9, 9), (15, 13), (21, 5)))
        p.setPen(QPen(c, 1.2))
        p.setBrush(QColor("white"))
        p.drawRect(QRectF(7, 7, 4, 4))
        p.drawRect(QRectF(19, 3, 4, 4))
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(15.5, 17.5), 5, 5)
        p.setPen(QPen(QColor("white"), 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(13, 17.5), QPointF(18, 17.5))
        p.drawLine(QPointF(15.5, 15), QPointF(15.5, 20))
    elif name == "tosatin":
        p.setPen(QPen(c, 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(3, 20), QPointF(9, 14))
        p.setPen(QPen(accent, 1.2))
        for k in range(6):
            x = 11 + k * 2
            p.drawLine(QPointF(x - 2, 12 - k * 0.3 + 3), QPointF(x + 2, 12 - k * 0.3 - 3))
        p.setPen(QPen(c, 1.4))
        p.drawLine(QPointF(8.5, 6), QPointF(10.5, 8))
    elif name == "toline":
        p.setPen(QPen(accent, 1.2))
        for k in range(5):
            x = 3 + k * 2
            p.drawLine(QPointF(x - 2, 15), QPointF(x + 2, 9))
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(14, 12), QPointF(22, 12))
    elif name == "flip":
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(_poly((4, 8), (18, 8)))
        p.drawPolyline(_poly((15, 5), (19, 8), (15, 11)))
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(_poly((20, 16), (6, 16)))
        p.drawPolyline(_poly((9, 13), (5, 16), (9, 19)))
    elif name == "textpath":
        path = QPainterPath(QPointF(3, 19))
        path.quadTo(12, 7, 21, 19)
        p.setPen(QPen(accent, 1.6, Qt.DashLine, Qt.RoundCap))
        p.drawPath(path)
        f = QFont("DejaVu Sans", 7, QFont.Bold)
        p.setFont(f)
        p.setPen(c)
        for ch, x, y, a in (("A", 6.5, 13.5, -38), ("b", 12, 10.5, 0), ("c", 17.5, 13.5, 38)):
            p.save()
            p.translate(x, y)
            p.rotate(a)
            p.drawText(QRectF(-4, -6, 8, 8), Qt.AlignCenter, ch)
            p.restore()
    elif name == "guided":
        p.setPen(QPen(c, 1.2))
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 2, 2)
        p.setPen(QPen(accent, 1.1))
        for k in range(5):
            y = 7 + k * 2.6
            path = QPainterPath(QPointF(4, y))
            path.cubicTo(9, y - 4, 15, y + 4, 20, y)
            p.drawPath(path)
        p.setPen(QPen(c, 1.6, Qt.DashLine, Qt.RoundCap))
        path = QPainterPath(QPointF(4, 12))
        path.cubicTo(9, 8, 15, 16, 20, 12)
        p.drawPath(path)
    elif name == "detach":
        path = QPainterPath(QPointF(3, 18))
        path.quadTo(8, 10, 12, 14)
        p.setPen(QPen(accent, 2, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(14, 7), QPointF(21, 7))
        p.drawPolyline(_poly((17, 4), (14, 7), (17, 10)))
    elif name in ("redwork", "autoroute"):
        p.setPen(QPen(c, 1.2))
        p.drawLine(QPointF(3, 8), QPointF(21, 8))
        p.drawLine(QPointF(3, 16), QPointF(21, 16))
        p.drawLine(QPointF(8, 4), QPointF(8, 20))
        p.drawLine(QPointF(16, 4), QPointF(16, 20))
        p.setPen(QPen(accent, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if name == "redwork":
            p.drawPolyline(_poly((3, 8), (8, 8), (8, 16), (16, 16), (16, 8), (8, 8)))
        else:
            p.drawPolyline(_poly((8, 4), (8, 16), (21, 16)))
        p.setBrush(accent)
        p.drawEllipse(QPointF(3 if name == "redwork" else 8, 8 if name == "redwork" else 4), 1.6, 1.6)
    elif name in ("startpt", "endpt"):
        p.setPen(QPen(c, 1.2))
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 3, 3)
        col = QColor("#2E7D32") if name == "startpt" else QColor("#C62828")
        p.setPen(QPen(QColor("white"), 1.2))
        p.setBrush(col)
        p.drawEllipse(QPointF(12, 12), 5.2, 5.2)
        f = QFont("DejaVu Sans", 6, QFont.Bold)
        p.setFont(f)
        p.drawText(QRectF(6, 6, 12, 12), Qt.AlignCenter, "S" if name == "startpt" else "E")
    elif name == "cutsatin":
        p.setPen(QPen(accent, 1.2))
        for k in range(8):
            x = 3 + k * 2.4
            if 10 < x < 14:
                continue
            p.drawLine(QPointF(x - 1.5, 16), QPointF(x + 1.5, 8))
        p.setPen(QPen(c, 1.8, Qt.DashLine, Qt.RoundCap))
        p.drawLine(QPointF(12, 3), QPointF(12, 21))
    elif name == "palette":
        path = QPainterPath(QPointF(12, 3))
        path.cubicTo(20, 3, 22, 10, 21, 13)
        path.cubicTo(20, 17, 15, 14, 14, 18)
        path.cubicTo(13, 21, 9, 21, 6, 19)
        path.cubicTo(1, 15, 2, 3, 12, 3)
        p.setPen(QPen(c, 1.4))
        p.setBrush(QColor("white"))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        for (x, y), col in (((8, 8), "#E53935"), ((12.5, 6.5), "#FDD835"), ((16.5, 9), accent),
                            ((6.5, 13), "#1E88E5")):
            p.setBrush(QColor(col))
            p.drawEllipse(QPointF(x, y), 1.8, 1.8)
    elif name == "fontshop":
        f = QFont("DejaVu Serif", 13, QFont.Bold)
        p.setFont(f)
        p.setPen(c)
        p.drawText(QRectF(0, 0, 17, 22), Qt.AlignCenter, "A")
        p.setPen(QPen(accent, 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(14, 20), QPointF(21, 9))
        p.setPen(QPen(c, 1.2))
        p.drawLine(QPointF(19.5, 7.5), QPointF(22, 9.5))
    elif name == "templates":
        p.setPen(QPen(c, 1.3))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(3, 3, 18, 18), 2.5, 2.5)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QPointF(12, 10), 4.5, 4.5)
        p.setBrush(c)
        p.drawRect(QRectF(6, 16, 12, 2))
    elif name in ("layer", "layers"):
        for k, y in enumerate((14, 9, 4) if name == "layers" else (9,)):
            p.setPen(QPen(c, 1.3))
            p.setBrush(accent if (name == "layer" or k == 2) else QColor(255, 255, 255, 200))
            p.drawPolygon(_poly((12, y), (21, y + 4), (12, y + 8), (3, y + 4)))
    elif name in ("lock", "unlock"):
        p.drawRoundedRect(QRectF(5, 11, 14, 10), 2, 2)
        path = QPainterPath(QPointF(8, 11))
        if name == "lock":
            path.lineTo(8, 7.5)
            path.arcTo(QRectF(8, 3, 8, 9), 180, -180)
            path.lineTo(16, 11)
        else:
            path.lineTo(8, 7.5)
            path.arcTo(QRectF(8, 3, 8, 9), 180, -150)
        p.drawPath(path)
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(12, 16), 1.6, 1.6)
    elif name in ("intersect", "exclude", "divide"):
        from PySide6.QtGui import QPainterPath as _P
        a, b = _P(), _P()
        a.addEllipse(QRectF(3, 5, 12, 12))
        b.addEllipse(QRectF(9, 7, 12, 12))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(c, 1.2))
        p.drawPath(a)
        p.drawPath(b)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        if name == "intersect":
            p.drawPath(a.intersected(b))
        elif name == "exclude":
            p.drawPath(a.united(b).subtracted(a.intersected(b)))
        else:
            p.drawPath(a.subtracted(b))
            p.setBrush(QColor("#E53935"))
            p.drawPath(a.intersected(b))
    elif name in ("align", "distribute"):
        p.setPen(QPen(c, 1.6))
        if name == "align":
            p.drawLine(QPointF(4, 3), QPointF(4, 21))
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawRect(QRectF(6, 5, 13, 5))
            p.drawRect(QRectF(6, 13, 8, 5))
        else:
            p.drawLine(QPointF(3, 3), QPointF(3, 21))
            p.drawLine(QPointF(21, 3), QPointF(21, 21))
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            for x in (5, 10.5, 16):
                p.drawRect(QRectF(x, 7, 3, 10))
    elif name in ("grow", "shrink"):
        p.setPen(QPen(c, 1.2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(3, 3, 18, 18) if name == "grow" else QRectF(7, 7, 10, 10), 3, 3)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(7, 7, 10, 10) if name == "grow" else QRectF(3, 3, 18, 18), 3, 3)
        if name == "shrink":
            p.setPen(QPen(c, 1.2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(7, 7, 10, 10), 3, 3)
    elif name == "outline_ring":
        p.setPen(QPen(accent, 2.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(2.5, 4.5, 19, 15), 5, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(QRectF(8, 8.5, 8, 7))
    elif name in ("copygrid", "copycircle"):
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        if name == "copygrid":
            for x in (4, 10, 16):
                for y in (5, 13):
                    p.drawRoundedRect(QRectF(x, y, 4.5, 5), 1, 1)
        else:
            import math as _m
            for k in range(6):
                a = _m.radians(k * 60)
                p.drawEllipse(QPointF(12 + 7 * _m.sin(a), 12 - 7 * _m.cos(a)), 2.2, 2.2)
    elif name == "staricon":
        import math as _m
        pts = [(12 + (9 if k % 2 == 0 else 4) * _m.cos(_m.radians(-90 + 36 * k)),
                12.5 + (9 if k % 2 == 0 else 4) * _m.sin(_m.radians(-90 + 36 * k))) for k in range(10)]
        p.setBrush(accent)
        p.drawPolygon(_poly(*pts))
    elif name == "spiral":
        import math as _m
        path = QPainterPath(QPointF(12, 12))
        t = 0.0
        while t < 6 * _m.pi:
            r = 0.5 + 9 * t / (6 * _m.pi)
            path.lineTo(12 + r * _m.cos(t), 12 + r * _m.sin(t))
            t += 0.2
        p.setPen(QPen(accent, 1.8))
        p.drawPath(path)
    elif name == "pipette":
        p.setPen(QPen(c, 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(5, 19), QPointF(14, 10))
        p.setBrush(c)
        p.drawPolygon(_poly((13, 7), (17, 11), (20, 8), (16, 4)))
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QPointF(5, 19), 2.2, 2.2)
    elif name == "snap":
        p.setPen(QPen(c, 1.0, Qt.DotLine))
        for x in (6, 12, 18):
            p.drawLine(QPointF(x, 3), QPointF(x, 21))
        p.setPen(QPen(accent, 2.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(6, 6), QPointF(6, 14))
        p.drawLine(QPointF(6, 14), QPointF(18, 14))
    elif name == "pdf":
        p.drawPolygon(_poly((6, 3), (14, 3), (19, 8), (19, 21), (6, 21)))
        p.drawPolyline(_poly((14, 3), (14, 8), (19, 8)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E53935"))
        p.drawRoundedRect(QRectF(3, 11, 13, 7), 1.5, 1.5)
        f = QFont("DejaVu Sans", 4)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(3, 11, 13, 7), Qt.AlignCenter, "PDF")
    elif name == "cutfile":
        p.setPen(QPen(c, 1.4, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        heart = QPainterPath(QPointF(12, 20))
        heart.cubicTo(3, 13, 3, 5, 8.5, 5)
        heart.cubicTo(10.5, 5, 12, 6.5, 12, 8)
        heart.cubicTo(12, 6.5, 13.5, 5, 15.5, 5)
        heart.cubicTo(21, 5, 21, 13, 12, 20)
        p.drawPath(heart)
        p.setPen(QPen(accent, 1.6))
        p.drawEllipse(QPointF(5, 19), 2, 2)
        p.drawEllipse(QPointF(9, 21.5), 2, 2)
        p.drawLine(QPointF(6.5, 18), QPointF(12, 13))
        p.drawLine(QPointF(10.5, 20.5), QPointF(13, 15))
    elif name == "measure":
        p.setPen(QPen(c, 1.5))
        p.setBrush(Qt.NoBrush)
        p.save()
        p.translate(12, 12)
        p.rotate(-35)
        p.drawRect(QRectF(-10, -3.5, 20, 7))
        for k in range(-8, 9, 3):
            p.drawLine(QPointF(k, -3.5), QPointF(k, -3.5 + (3 if k % 2 == 0 else 1.8)))
        p.restore()
        p.setPen(QPen(accent, 1.6))
        p.drawLine(QPointF(4, 21), QPointF(20, 21))
    elif name == "ruler":
        p.setPen(QPen(c, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3, 3, 18, 5))
        p.drawRect(QRectF(3, 3, 5, 18))
        p.setPen(QPen(accent, 1.4))
        for k in (11, 14, 17):
            p.drawLine(QPointF(k, 3), QPointF(k, 5.5))
            p.drawLine(QPointF(3, k), QPointF(5.5, k))
    elif name == "multihoop":
        p.setPen(QPen(c, 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(2.5, 5, 11, 14), 2, 2)
        p.setPen(QPen(accent, 1.5))
        p.drawRoundedRect(QRectF(10.5, 5, 11, 14), 2, 2)
        p.setPen(QPen(QColor("#E53935"), 1.3))
        p.drawLine(QPointF(12, 8), QPointF(12, 11))
        p.drawLine(QPointF(10.5, 9.5), QPointF(13.5, 9.5))
    elif name == "shadow":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c.red(), c.green(), c.blue(), 110))
        p.drawRoundedRect(QRectF(7.5, 8.5, 13, 12), 2.5, 2.5)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(3.5, 4, 13, 12), 2.5, 2.5)
    elif name == "envelope":
        p.setPen(QPen(c, 1.4, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        top = QPainterPath(QPointF(3, 9))
        top.quadTo(12, 1, 21, 9)
        bot = QPainterPath(QPointF(3, 20))
        bot.quadTo(12, 15, 21, 20)
        p.drawPath(top)
        p.drawPath(bot)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        for x, h in ((5, 9), (9.5, 11.5), (14, 11.5), (18.5, 9)):
            p.drawRoundedRect(QRectF(x - 1.4, 18.5 - h, 2.8, h), 0.8, 0.8)
    elif name == "machine":
        p.setPen(QPen(c, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(4, 20))
        path.lineTo(4, 7)
        path.quadTo(4, 4, 7, 4)
        path.lineTo(19, 4)
        path.quadTo(21, 4, 21, 6.5)
        path.lineTo(21, 12)
        path.lineTo(9, 12)
        path.lineTo(9, 20)
        p.drawPath(path)
        p.drawLine(QPointF(2, 20), QPointF(22, 20))
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(17, 12), QPointF(17, 16.5))
        for x in (11.5, 14, 16.5):
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawEllipse(QPointF(x, 7.5), 1.1, 1.1)
    elif name == "tshirt":
        p.setPen(QPen(c, 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor(255, 255, 255, 0))
        p.drawPolygon(_poly((8, 3.5), (3, 6.5), (5, 11), (7, 10), (7, 21), (17, 21), (17, 10),
                            (19, 11), (21, 6.5), (16, 3.5), (14, 5), (10, 5)))
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawPolygon(_poly((12.2, 9), (13.2, 11.2), (15.4, 11.4), (13.7, 12.9), (14.2, 15.2),
                            (12.2, 14), (10.2, 15.2), (10.7, 12.9), (9, 11.4), (11.2, 11.2)))
    elif name == "puff":
        p.setPen(QPen(c, 1.4))
        p.setBrush(accent)
        path = QPainterPath(QPointF(3, 19))
        path.cubicTo(3, 8, 9, 5, 12, 5)
        path.cubicTo(15, 5, 21, 8, 21, 19)
        path.closeSubpath()
        p.drawPath(path)
        p.setPen(QPen(QColor("#FFFFFF"), 1.2))
        for x in (8, 12, 16):
            p.drawLine(QPointF(x, 9), QPointF(x, 17))
        p.setPen(QPen(c, 1.6))
        p.drawLine(QPointF(2, 20), QPointF(22, 20))
    elif name == "overlap":
        p.setPen(QPen(c, 1.4, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3, 3, 12, 12))
        p.setPen(QPen(c, 1.6))
        p.setBrush(accent)
        p.drawRect(QRectF(9, 9, 12, 12))
    elif name == "knockout":
        # untere Fläche mit Aussparung, darüber das verschobene Objekt (Pfeil = wandert mit)
        p.setPen(QPen(c, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(_poly((3, 3), (17, 3), (17, 9), (9, 9), (9, 17), (3, 17)))
        p.setBrush(accent)
        p.drawRect(QRectF(10, 10, 11, 11))
        p.setPen(QPen(c, 1.3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(19.5, 3.5), QPointF(19.5, 7.5))
        p.drawLine(QPointF(17.5, 5.5), QPointF(21.5, 5.5))
    elif name == "cleanup":
        p.setPen(QPen(c, 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(17, 3), QPointF(9, 15))
        p.setBrush(accent)
        p.drawPolygon(_poly((5, 14), (13, 18), (11, 21), (3, 21)))
        p.setBrush(c)
        for x, y in ((17, 18), (20, 14), (19, 21)):
            p.drawEllipse(QPointF(x, y), 0.9, 0.9)
    elif name in ("group", "ungroup"):
        p.setPen(QPen(c, 1.2, Qt.DashLine if name == "group" else Qt.SolidLine))
        if name == "group":
            p.drawRoundedRect(QRectF(2.5, 2.5, 19, 19), 2, 2)
        p.setPen(QPen(c, 1.6))
        p.setBrush(accent)
        p.drawRect(QRectF(5, 5, 8, 8) if name == "group" else QRectF(3, 3, 8, 8))
        p.setBrush(QColor("#E53935"))
        p.drawEllipse(QRectF(11, 11, 8, 8) if name == "group" else QRectF(13, 13, 8, 8))
    elif name == "autosatin":
        p.setPen(QPen(accent, 1.1))
        for k in range(5):                       # zwei Säulen …
            p.drawLine(QPointF(3 + k * 1.6, 5), QPointF(5 + k * 1.6, 11))
            p.drawLine(QPointF(13 + k * 1.6, 13), QPointF(15 + k * 1.6, 19))
        p.setPen(QPen(c, 1.4, Qt.DashLine, Qt.RoundCap))   # … verdeckt verbunden
        path = QPainterPath(QPointF(11, 9))
        path.cubicTo(15, 9, 11, 15, 14, 16)
        p.drawPath(path)
    elif name == "multisatin":
        for k, col in enumerate((accent, c, QColor("#E53935"))):
            p.setPen(QPen(col, 1.2))
            for j in range(7):
                x = 3 + j * 2.7
                p.drawLine(QPointF(x, 5 + k * 5), QPointF(x + 1.6, 9 + k * 5))
    elif name == "centerline":
        p.setPen(QPen(c, 1.2))
        p.setBrush(QColor(0, 0, 0, 0))
        p.drawRoundedRect(QRectF(3, 7, 18, 10), 5, 5)
        p.setPen(QPen(accent, 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(7, 12), QPointF(17, 12))
    elif name == "outline":
        p.setPen(QPen(accent, 1.0))
        for k in range(5):
            p.drawLine(QPointF(6 + k * 3, 17), QPointF(9 + k * 3, 7))
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor(0, 0, 0, 0))
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 4, 4)
    elif name == "knockdown":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 90))
        p.drawRoundedRect(QRectF(2, 6, 20, 14), 4, 4)
        p.setPen(QPen(accent, 1.0))
        for k in range(6):
            p.drawLine(QPointF(4 + k * 3, 18), QPointF(7 + k * 3, 8))
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(8, 4), QPointF(8, 13))
        p.drawLine(QPointF(16, 4), QPointF(16, 13))
    elif name == "density":
        for (x, y, a) in ((4, 4, 60), (10, 4, 140), (16, 4, 230), (4, 10, 140), (10, 10, 230),
                          (16, 10, 140), (4, 16, 60), (10, 16, 140), (16, 16, 60)):
            col = QColor("#E53935") if a > 200 else QColor("#FBC02D") if a > 100 else QColor("#43A047")
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRect(QRectF(x, y, 5, 5))
    elif name == "multiexport":
        p.setPen(QPen(c, 1.4))
        p.setBrush(QColor("white"))
        for k in range(3):
            p.drawRoundedRect(QRectF(3 + k * 3.5, 3 + k * 3.5, 11, 13), 1.5, 1.5)
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(_poly((17, 15), (17, 21)))
        p.drawPolyline(_poly((14.5, 18.5), (17, 21), (19.5, 18.5)))
    elif name == "layout":
        p.setPen(QPen(c, 1.6))
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 2.5, 2.5)
        p.drawLine(QPointF(3, 8.5), QPointF(21, 8.5))
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(15, 10, 4.5, 8.5))
        p.setBrush(c)
        p.drawRect(QRectF(5, 10, 2.5, 8.5))
    elif name == "star":
        pts = []
        for k in range(10):
            r = 9 if k % 2 == 0 else 4
            a = math.pi / 2 + k * math.pi / 5
            pts.append((12 + r * math.cos(a), 12.5 - r * math.sin(a)))
        p.setBrush(accent)
        p.setPen(QPen(c, 1.2))
        p.drawPolygon(_poly(*pts))
    elif name == "photo":
        p.setPen(QPen(c, 1.6))
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2.5, 2.5)
        p.setPen(QPen(accent, 1.2))
        for k in range(7):
            amp = (0.6, 1.4, 2.4, 3.0, 2.2, 1.2, 0.5)[k]
            x = 5.5 + k * 2.2
            p.drawLine(QPointF(x, 12 - amp), QPointF(x + 1.1, 12 + amp))
            p.drawLine(QPointF(x + 1.1, 12 + amp), QPointF(x + 2.2, 12 - amp))
    elif name == "connectline":
        p.setPen(QPen(accent, 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(6, 18), QPointF(18, 6))
        p.setPen(QPen(c, 1.3))
        p.setBrush(QColor("white"))
        p.drawRect(QRectF(3, 15, 6, 6))
        p.drawRect(QRectF(15, 3, 6, 6))
        p.setPen(QPen(c, 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(2, 6), QPointF(8, 6))
        p.drawLine(QPointF(16, 18), QPointF(22, 18))
    elif name == "joinnode":
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(2, 18), QPointF(8, 12))
        p.drawLine(QPointF(16, 12), QPointF(22, 18))
        p.setPen(QPen(accent, 1.6, Qt.DashLine, Qt.RoundCap))
        p.drawLine(QPointF(9, 12), QPointF(15, 12))
        p.setPen(QPen(c, 1.2))
        p.setBrush(accent)
        p.drawRect(QRectF(6, 10, 4, 4))
        p.drawRect(QRectF(14, 10, 4, 4))
        p.setPen(QPen(c, 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(9, 4), QPointF(12, 7))
        p.drawLine(QPointF(15, 4), QPointF(12, 7))
    elif name == "breaknode":
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(2, 16), QPointF(9.5, 12))
        p.drawLine(QPointF(14.5, 12), QPointF(22, 16))
        p.setPen(QPen(c, 1.2))
        p.setBrush(accent)
        p.drawRect(QRectF(8, 10, 3.5, 3.5))
        p.drawRect(QRectF(12.5, 10, 3.5, 3.5))
        p.setPen(QPen(accent, 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(12, 2), QPointF(12, 7))
        p.drawLine(QPointF(12, 17), QPointF(12, 22))
    elif name == "curvept":
        path = QPainterPath(QPointF(3, 19))
        path.cubicTo(6, 2, 18, 2, 21, 19)
        p.drawPath(path)
        p.setPen(QPen(c, 1.2))
        p.setBrush(accent)
        p.drawEllipse(QPointF(12, 6.3), 2.8, 2.8)
    elif name == "autocurve":
        p.setPen(QPen(c, 1.1))
        p.drawPolyline(_poly((2, 12), (3, 8), (5, 6), (7, 5), (9, 6)))
        p.setPen(QPen(accent, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(8, 11), QPointF(13, 11))
        p.drawPolyline(_poly((11, 9), (13, 11), (11, 13)))
        p.setPen(QPen(c, 1.8))
        path = QPainterPath(QPointF(13, 21))
        path.cubicTo(14, 13, 20, 12, 22, 16)
        p.drawPath(path)
    elif name == "cut":
        p.setBrush(accent)
        outer = QPainterPath()
        outer.addRoundedRect(QRectF(3, 4, 18, 16), 3, 3)
        hole = QPainterPath()
        hole.addEllipse(QRectF(8, 7, 8, 10))
        p.drawPath(outer.subtracted(hole))
        p.setPen(QPen(c, 1.2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(8, 7, 8, 10))
    elif name == "ai":
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        for x, y, r in ((10, 12, 6.5), (18, 6, 3.2), (18.5, 17.5, 2.4)):
            pts = []
            for i in range(8):
                rr = r if i % 2 == 0 else r * 0.32
                a = math.pi * i / 4 - math.pi / 2
                pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
            p.drawPolygon(_poly(*pts))
    elif name == "optimizer":
        p.setPen(QPen(c, 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawRoundedRect(QRectF(2.5, 4, 19, 15), 3, 3)
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawPolygon(_poly((9.5, 8), (9.5, 15), (15.5, 11.5)))
        p.setPen(QPen(QColor("#E53935"), 1.3, Qt.DashLine))
        p.drawLine(QPointF(4.5, 21.5), QPointF(19.5, 21.5))
    elif name == "gear":
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        body = QPainterPath()
        body.addEllipse(QPointF(12, 12), 7, 7)
        for i in range(8):
            tooth = QPainterPath()
            tooth.addRoundedRect(QRectF(-2, -10.5, 4, 5), 0.8, 0.8)
            t = QTransform()
            t.translate(12, 12)
            t.rotate(45 * i)
            body = body.united(t.map(tooth))
        hole = QPainterPath()
        hole.addEllipse(QPointF(12, 12), 3, 3)
        p.drawPath(body.subtracted(hole))
    elif name == "keyboard":
        p.drawRoundedRect(QRectF(2.5, 6, 19, 12), 2.5, 2.5)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        for row, y in enumerate((8.6, 11.4)):
            for i in range(6):
                p.drawRect(QRectF(4.6 + i * 2.6 + row * 1.2, y, 1.6, 1.6))
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(7, 14.4, 10, 1.8), 0.9, 0.9)
    elif name == "help":
        p.drawEllipse(QRectF(3, 3, 18, 18))
        f = QFont("DejaVu Sans", 11, QFont.Bold)
        p.setFont(f)
        p.setPen(accent)
        p.drawText(QRectF(3, 3, 18, 18), Qt.AlignCenter, "?")
    elif name == "encore":
        # Motiv im Kreis wiederholt
        p.setPen(Qt.NoPen)
        for i in range(8):
            a = math.radians(45 * i)
            p.setBrush(accent if i % 2 == 0 else c)
            p.drawEllipse(QPointF(12 + 7.5 * math.sin(a), 12 - 7.5 * math.cos(a)), 2.3, 2.3)
        p.setBrush(accent)
        p.drawEllipse(QPointF(12, 12), 1.6, 1.6)
    elif name == "ornament":
        # Rahmen mit Eckschnörkeln
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 2, 2)
        p.setPen(QPen(accent, 1.4, Qt.SolidLine, Qt.RoundCap))
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            cx, cy = 12 - sx * 5.5, 12 - sy * 4.5
            path = QPainterPath(QPointF(cx - sx * 2.5, cy - sy * 2))
            path.cubicTo(cx, cy - sy * 2, cx + sx * 1.5, cy, cx + sx * 0.3, cy + sy * 1.2)
            p.drawPath(path)
    elif name in ("stones", "stonesheet"):
        if name == "stonesheet":
            p.drawRect(QRectF(3.5, 3.5, 17, 17))
        p.setBrush(QColor("#FFFFFF"))
        for k, (x, y) in enumerate(((8, 8), (16, 8), (12, 12), (8, 16), (16, 16))):
            p.setPen(QPen(c, 1.0))
            p.setBrush(QColor("#FFFFFF") if name == "stonesheet" else (accent if k == 2 else c))
            p.drawEllipse(QPointF(x, y), 2.6, 2.6)
            if name == "stones":
                p.setPen(QPen(QColor(255, 255, 255, 200), 0.8))
                p.drawLine(QPointF(x - 1.2, y - 0.6), QPointF(x - 0.2, y - 1.4))
    elif name == "spiro":
        # kleine Spirograph-Blüte (Innenrad)
        path = QPainterPath()
        for i in range(361):
            t = math.radians(i * 3)
            x = 12 + 5.0 * math.cos(t) + 4.5 * math.cos(5 * t / 3 * 2)
            y = 12 + 5.0 * math.sin(t) - 4.5 * math.sin(5 * t / 3 * 2)
            if i:
                path.lineTo(x, y)
            else:
                path.moveTo(x, y)
        p.setPen(QPen(accent, 1.2))
        p.drawPath(path)
    elif name == "wordsculpt":
        # Herz aus Textzeilen
        heart = QPainterPath(QPointF(12, 20.5))
        heart.cubicTo(3, 14, 2.5, 6.5, 7.5, 5)
        heart.cubicTo(10, 4.3, 11.5, 6, 12, 7.5)
        heart.cubicTo(12.5, 6, 14, 4.3, 16.5, 5)
        heart.cubicTo(21.5, 6.5, 21, 14, 12, 20.5)
        p.drawPath(heart)
        p.setClipPath(heart)
        p.setPen(QPen(accent, 1.6, Qt.SolidLine, Qt.RoundCap))
        for y in (7.5, 10.5, 13.5, 16.5):
            p.drawLine(QPointF(3, y), QPointF(21, y))
        p.setClipping(False)
    elif name == "ith":
        # Stickrahmen mit genähtem Täschchen darin
        p.drawRoundedRect(QRectF(2.5, 3, 19, 18), 4, 4)
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(7, 8.5, 10, 8), 1.5, 1.5)
        p.setPen(QPen(QColor("#FFFFFF"), 1.0, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(8.4, 9.9, 7.2, 5.2), 1, 1)
        p.setPen(QPen(c, 1.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(12, 3), QPointF(12, 6))
    elif name == "cross":
        # Zählmuster: Raster mit ein paar Kreuzchen
        p.setPen(QPen(c, 0.6))
        for i in range(5):
            p.drawLine(QPointF(3 + i * 4.5, 3), QPointF(3 + i * 4.5, 21))
            p.drawLine(QPointF(3, 3 + i * 4.5), QPointF(21, 3 + i * 4.5))
        p.setPen(QPen(accent, 1.6, Qt.SolidLine, Qt.RoundCap))
        for cx, cy in ((0, 0), (1, 1), (2, 0), (2, 2), (3, 1), (1, 3)):
            x0, y0 = 3 + cx * 4.5 + 0.8, 3 + cy * 4.5 + 0.8
            p.drawLine(QPointF(x0, y0), QPointF(x0 + 2.9, y0 + 2.9))
            p.drawLine(QPointF(x0, y0 + 2.9), QPointF(x0 + 2.9, y0))
    elif name == "quilt":
        # Quiltblock: Quadrat mit Echo-Linien um ein Herz
        p.drawRect(QRectF(3, 3, 18, 18))
        p.setPen(QPen(c, 0.8, Qt.DashLine))
        p.drawRoundedRect(QRectF(5.5, 5.5, 13, 13), 4, 4)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        heart = QPainterPath(QPointF(12, 16.5))
        heart.cubicTo(7, 13, 7.5, 8, 10, 8.3)
        heart.cubicTo(11, 8.4, 11.8, 9.2, 12, 10)
        heart.cubicTo(12.2, 9.2, 13, 8.4, 14, 8.3)
        heart.cubicTo(16.5, 8, 17, 13, 12, 16.5)
        p.drawPath(heart)
    elif name == "family":
        # Baum mit drei Namensschildchen
        p.setPen(QPen(c, 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(12, 21), QPointF(12, 12))
        p.drawLine(QPointF(12, 13), QPointF(6, 8))
        p.drawLine(QPointF(12, 13), QPointF(18, 8))
        p.drawLine(QPointF(12, 12), QPointF(12, 5))
        p.setPen(QPen(c, 1.0))
        p.setBrush(accent)
        for x, y in ((6, 7), (18, 7), (12, 4)):
            p.drawRoundedRect(QRectF(x - 3.5, y - 2, 7, 4), 1.5, 1.5)
    elif name == "paint":
        # Pinsel mit Farbklecks
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QRectF(3, 13, 9, 7))
        p.setPen(QPen(c, 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(10, 14), QPointF(20, 4))
        p.setPen(QPen(c, 3.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(9, 15), QPointF(10.5, 13.5))
    elif name == "printsheet":
        # Drucker mit Blatt
        p.drawRoundedRect(QRectF(3, 9, 18, 8), 2, 2)
        p.drawRect(QRectF(7, 4, 10, 5))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(QRectF(7, 14, 10, 7))
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QRectF(10, 16, 4, 3.4))
    elif name == "sketch":
        # Stift, der eine mehrfach gezogene Linie zeichnet
        p.setPen(QPen(accent, 1.0, Qt.SolidLine, Qt.RoundCap))
        for dy in (-0.8, 0.0, 0.8):
            path = QPainterPath(QPointF(3, 19 + dy))
            path.cubicTo(7, 12 + dy, 10, 22 + dy, 14, 15 + dy)
            p.drawPath(path)
        p.setPen(QPen(c, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolygon(_poly((14, 14), (20, 4), (22, 5.5), (16, 15.5)))
        p.drawLine(QPointF(14, 14), QPointF(13.5, 16.5))
    elif name == "stitchedit":
        # Stichpunkte mit einem gewählten (gefüllten) Punkt
        p.setPen(QPen(c, 1.2))
        pts = [(3, 18), (8, 7), (12, 17), (16, 6), (21, 16)]
        for a, b in zip(pts, pts[1:]):
            p.drawLine(QPointF(*a), QPointF(*b))
        for i, (x, y) in enumerate(pts):
            p.setBrush(accent if i == 2 else QColor("#FFFFFF"))
            p.drawEllipse(QPointF(x, y), 2.2 if i == 2 else 1.5, 2.2 if i == 2 else 1.5)
    elif name == "usb":
        # USB-Stick mit Pfeil zur Maschine
        p.drawRoundedRect(QRectF(5, 9, 11, 12), 2, 2)
        p.drawRect(QRectF(7.5, 4, 6, 5))
        p.setBrush(c)
        p.drawRect(QRectF(9, 5.5, 1.2, 1.4))
        p.drawRect(QRectF(11, 5.5, 1.2, 1.4))
        p.setPen(QPen(accent, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(17, 15), QPointF(22, 15))
        p.drawLine(QPointF(19.5, 12.5), QPointF(22, 15))
        p.drawLine(QPointF(19.5, 17.5), QPointF(22, 15))
    elif name == "video":
        # Filmstreifen mit Abspielpfeil
        p.drawRoundedRect(QRectF(2.5, 5, 19, 14), 2, 2)
        p.setBrush(c)
        for x in (4, 7.5, 11, 14.5, 18):
            p.drawRect(QRectF(x, 6.2, 1.8, 1.6))
            p.drawRect(QRectF(x, 16.2, 1.8, 1.6))
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawPolygon(_poly((10, 9.3), (10, 14.7), (14.8, 12)))
    elif name == "png":
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        f = QFont("DejaVu Sans", 6, QFont.Bold)
        p.setFont(f)
        p.setPen(accent)
        p.drawText(QRectF(3, 5, 18, 14), Qt.AlignCenter, "PNG")


FG = "#2B2D3A"          # Symbolfarbe des aktuellen Farbschemas (dunkel: hell)


ACCENT = "#0FA3A3"      # Akzentfarbe der Symbole (Farbschema)


def icon(name, color=None, accent=None, size=48):
    color = color or FG
    accent = accent or ACCENT
    key = (name, color, accent, size)
    if key in _cache:
        return _cache[key]
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    _draw(name, p, QColor(color), QColor(accent))
    p.end()
    ic = QIcon(pm)
    _cache[key] = ic
    return ic


def swatch(color, size=18, border="#00000040", radius=4):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(QPen(QColor(border), 1))
    p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), radius, radius)
    p.end()
    return QIcon(pm)


def _star(p, x, y, r, color):
    """Vierzackiger Funkelstern."""
    path = QPainterPath(QPointF(x, y - r))
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        path.quadTo(x, y, x + dx * r, y + dy * r)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path)


def app_logo(size=256):
    """Programmsymbol von StichWizard: Zauberer mit Sticknadel als Zauberstab."""
    from PySide6.QtGui import QLinearGradient
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 100.0, size / 100.0)
    bg = QLinearGradient(0, 0, 0, 100)
    bg.setColorAt(0, QColor("#3A2F7A"))
    bg.setColorAt(1, QColor("#161A33"))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(3, 3, 94, 94), 21, 21)
    gold, teal = QColor("#F7C548"), QColor("#3FE0D0")
    for x, y, r in ((17, 20, 4.5), (11, 46, 2.6), (27, 9, 2.2), (88, 74, 2.6)):
        _star(p, x, y, r, gold)
    skin, robe, hat, beard = QColor("#F3C9A1"), QColor("#5A45C8"), QColor("#7058E8"), QColor("#F6F4FA")
    # Gewand
    p.setBrush(robe)
    p.drawPolygon(_poly((24, 97), (76, 97), (66, 62), (34, 62)))
    p.setBrush(QColor("#00000030"))
    p.drawPolygon(_poly((48, 97), (52, 97), (51, 66), (49, 66)))
    # erhobener Arm
    p.setPen(QPen(robe, 10, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(62, 68), QPointF(75, 52))
    # Kopf und Bart
    p.setPen(Qt.NoPen)
    p.setBrush(skin)
    p.drawEllipse(QPointF(50, 51), 11.5, 10.5)
    b = QPainterPath(QPointF(37.5, 52))
    b.cubicTo(41, 57, 46, 55, 50, 58)
    b.cubicTo(54, 55, 59, 57, 62.5, 52)
    b.cubicTo(64, 64, 60, 76, 50, 88)
    b.cubicTo(40, 76, 36, 64, 37.5, 52)
    p.setBrush(beard)
    p.drawPath(b)
    p.setBrush(QColor("#2A2440"))
    p.drawEllipse(QPointF(45.5, 49.5), 1.6, 1.8)
    p.drawEllipse(QPointF(54.5, 49.5), 1.6, 1.8)
    p.setBrush(QColor("#E8A985"))
    p.drawEllipse(QPointF(50, 54), 2.6, 2.2)
    # Hut mit Krempe, Band und Stern
    h = QPainterPath(QPointF(35, 44))
    h.cubicTo(40, 30, 43, 18, 36, 7)
    h.cubicTo(50, 9, 60, 24, 65, 44)
    h.closeSubpath()
    p.setBrush(hat)
    p.drawPath(h)
    p.setBrush(gold)
    p.drawPolygon(_poly((36, 44), (64.5, 44), (63.5, 39.5), (37.5, 39.5)))
    p.setBrush(robe)
    p.drawEllipse(QRectF(27, 41, 46, 8))
    _star(p, 50, 29, 5, gold)
    # Sticknadel als Zauberstab, Faden mit Stichen
    needle = _poly((70.6, 60.5), (73.4, 59.5), (88.6, 19), (90.5, 10), (85.9, 18))
    p.setPen(QPen(QColor("#20243A"), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor("#E4E9F0"))
    p.drawPolygon(needle)
    p.setPen(QPen(QColor("#20243A"), 1.1))
    p.setBrush(QColor("#3A2F7A"))
    p.drawEllipse(QPointF(75.2, 51.5), 0.9, 2.6)
    thread = QPainterPath(QPointF(75.2, 51.5))
    thread.cubicTo(96, 50, 96, 80, 80, 90)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(teal, 2.6, Qt.DashLine, Qt.RoundCap))
    p.drawPath(thread)
    p.setPen(Qt.NoPen)
    p.setBrush(skin)
    p.drawEllipse(QPointF(74.5, 56.5), 5, 5)
    _star(p, 91, 9, 6, gold)
    _star(p, 91, 9, 2.5, QColor("#FFFFFF"))
    p.end()
    return pm
