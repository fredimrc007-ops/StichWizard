"""Arbeitsfläche: Zoom, Verschieben, Zeichenwerkzeuge, Griffe zum Skalieren/Drehen."""
import json
import math

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QApplication, QGraphicsPathItem, QGraphicsView, QMenu
from shapely.geometry import LineString, Point, Polygon, box

from . import curves
from .curves import CORNER, CTRL, CURVE

from .render import ObjectItem, geom_path

ACCENT = QColor("#0FA3A3")         # Akzentfarbe – vom Hauptfenster je nach Farbschema gesetzt


def _tint(alpha):
    c = QColor(ACCENT)
    c.setAlpha(alpha)
    return c


def transform_objects(objs, center, scale=1.0, angle=0.0, fx=None, fy=None):
    """Objekte gemeinsam um `center` skalieren bzw. drehen (Positionen und Objekte selbst).
    fx/fy: ungleichmäßig skalieren (nur bei Drehungen um Vielfache von 90° exakt möglich)."""
    cx, cy = center
    fx = scale if fx is None else fx
    fy = scale if fy is None else fy
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for o in objs:
        dx, dy = o.x - cx, o.y - cy
        if angle:
            dx, dy = dx * ca - dy * sa, dx * sa + dy * ca
            o.rot = (o.rot + angle) % 360
        o.x, o.y = cx + dx * fx, cy + dy * fy
        if fx != 1.0 or fy != 1.0:
            swap = round(o.rot / 90) % 2 == 1     # um 90°/270° gedreht: Achsen vertauscht
            o.sx *= fy if swap else fx
            o.sy *= fx if swap else fy


class Canvas(QGraphicsView):
    objectCreated = Signal(str, object)     # art, Geometrie/Punkte
    itemsTransformed = Signal(list)         # Liste von EmbObject
    textRequested = Signal(float, float)
    crossRequested = Signal(object)         # Doppelklick auf ein Kreuzstich-Objekt
    cursorMoved = Signal(float, float)
    zoomChanged = Signal(float)
    toolFinished = Signal()
    escapePressed = Signal()
    nodesEdited = Signal(object)            # EmbObject
    joinRequested = Signal()                # Punkte verbinden (Hauptfenster entscheidet)
    breakRequested = Signal()               # Linie am gewählten Punkt auftrennen
    connectNodesRequested = Signal()        # zwei gewählte Punkte mit einer Linie verbinden
    eraseRequested = Signal(object)         # wegzuschneidende Fläche (shapely, Arbeitsfläche)
    eraserSizeChanged = Signal(float)       # Radierer-Durchmesser in mm ([ und ])
    jumpClicked = Signal(float, float, object)   # x, y, globale Position
    pointPicked = Signal(float, float)      # Werkzeug »pick«: Start-/Endpunkt angeklickt
    letterPicked = Signal(int)              # Punkte-Werkzeug: Buchstabe eines Schriftzugs angefasst
    measured = Signal(str)                  # Messwerkzeug: Ergebnis als Text
    letterMoved = Signal(object, int, float, float)   # Schriftzug, Index, dx, dy (Objektmaße)

    def __init__(self, scene, opts):
        super().__init__(scene)
        self.opts = opts
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # Zoom-Anker selbst berechnen (siehe set_zoom) – Qts "unter der Maus" nutzt die letzte
        # Mausbewegung, die viele Werkzeuge hier selbst verarbeiten, und springt dann.
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._scroll_rest = [0.0, 0.0]
        self.setBackgroundBrush(QBrush(QColor("#E6E9EF")))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.tool = "select"
        self.pts = []
        self.drag_start = None
        self._pan = None
        self._space = False
        self._xf = None
        self.snap = True           # Einrasten beim Verschieben (Ansicht › Raster ▾)
        self.snap_grid = True      # Ziele: Raster, andere Objekte, Rahmenmitte
        self.snap_objects = True
        self.snap_center = True
        self._snap_ctx = None      # beim Ziehen: Ziele und Ausgangslage
        self.snap_lines = []       # gezeigte Hilfslinien [("x"|"y", wert)]
        self._nodes = None          # Zustand des Punkte-Werkzeugs
        self._node_sel = set()      # (ring, index)
        self._node_drag = None
        self.show_rulers = True       # Lineale oben und links (mm ab Rahmenmitte)
        self._measure = None          # Messwerkzeug: [Start, Ende] in Weltkoordinaten
        self._measuring = False
        self._mouse = None            # letzte Mausposition (für die Lineal-Markierung)
        self.eraser_size = 3.0        # Radierer: Pinsel-Durchmesser in mm
        self.eraser_lasso = False     # Radierer: Bereich umfahren statt wie ein Pinsel radieren
        self._erase_lasso = False     # laufender Strich wird als Lasso behandelt (Umschalt)
        self._erase_hover = False     # Maus über der Fläche: Pinselkreis zeigen
        self._letters = None          # Anfasser der Buchstaben (Punkte-Werkzeug auf Schriftzug)
        self._letter_drag = None
        self.letter_sel = -1
        self._band = None
        self._edge_hover = None     # Vorschau »Punkt einfügen« (Weltkoordinaten)
        self.merge_undo = False     # Einfügen + Ziehen = ein Rückgängig-Schritt
        self._conn_a = None         # Werkzeug »Mit Linie verbinden«: erster Punkt
        self._conn_hover = None     # eingerasteter Punkt unter der Maus
        self._snap_cache = None
        self.jump_records = []      # vom Hauptfenster gesetzt (Sprung-Editor)
        self._jump_hover = None
        self.preview = QGraphicsPathItem()
        pen = QPen(ACCENT, 1.5, Qt.DashLine)
        pen.setCosmetic(True)
        self.preview.setPen(pen)
        self.preview.setBrush(_tint(40))
        self.preview.setZValue(10_000)
        scene.addItem(self.preview)
        self.set_tool("select")

    # ------------------------------------------------------------ Werkzeuge
    def set_tool(self, tool):
        self.tool = tool
        self.pts = []
        self.ptypes = []
        self.drag_start = None
        self.preview.setPath(QPainterPath())
        self._node_sel = set()
        self._node_drag = self._band = self._edge_hover = None
        self._conn_a = self._conn_hover = self._snap_cache = None
        self._pen = []            # Bézier-Stift: [{"p", "hin", "hout"}]
        self._pen_drag = None
        self._pen_cursor = None
        eraser = tool == "eraser"
        pen = QPen(QColor("#E53935") if eraser else ACCENT, 1.5, Qt.DashLine)
        pen.setCosmetic(True)
        self.preview.setPen(pen)
        self.preview.setBrush(QColor(229, 57, 53, 45) if eraser else _tint(40))
        if tool == "select":
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
        elif tool in ("connect", "pick"):
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        elif tool in ("nodes", "jumps"):
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.IBeamCursor if tool == "text" else Qt.CrossCursor)
        self.viewport().update()

    def zoom(self):
        return self.transform().m11()

    def set_zoom(self, z, at=None):
        """Zoomt so, dass der Punkt `at` (Viewport-Pixel, Standard: Mitte) an Ort und Stelle
        bleibt."""
        z = max(0.4, min(80.0, z))
        f = z / self.zoom()
        if abs(f - 1) < 1e-9:
            return
        p = QPointF(at) if at is not None else QPointF(self.viewport().rect().center())
        scene_pt = self.viewportTransform().inverted()[0].map(p)
        self.scale(f, f)
        moved = self.viewportTransform().map(scene_pt) - p
        self._scroll_by(-moved.x(), -moved.y())
        self.zoomChanged.emit(self.zoom())

    def zoom_by(self, f, at=None):
        self.set_zoom(self.zoom() * f, at)

    def fit_rect(self, rect):
        self.fitInView(rect, Qt.KeepAspectRatio)
        self.zoomChanged.emit(self.zoom())

    def wheelEvent(self, ev):
        """Mausrad: zoomen. Touchpad (zwei Finger): verschieben, mit Strg: zoomen.
        Umschalt + Mausrad: waagrecht verschieben."""
        touchpad = not ev.pixelDelta().isNull() or ev.phase() != Qt.NoScrollPhase
        mods = ev.modifiers()
        if touchpad and not mods & Qt.ControlModifier:
            d = ev.pixelDelta() if not ev.pixelDelta().isNull() else ev.angleDelta() / 4
            self._scroll_by(d.x(), d.y())
            return
        if mods & Qt.ShiftModifier:
            d = ev.angleDelta()
            self._scroll_by(d.y() or d.x(), 0)
            return
        if self.opts.wheel == "scroll" and not mods & Qt.ControlModifier:
            d = ev.angleDelta()
            self._scroll_by(d.x() / 2, d.y() / 2)
            return
        d = ev.angleDelta().y()
        if d:
            self.zoom_by(1.15 ** (d / 120.0), ev.position())

    def _scroll_by(self, dx, dy):
        """Ansicht verschieben; Bruchteile von Pixeln werden aufgehoben statt verworfen."""
        rx = self._scroll_rest[0] - dx
        ry = self._scroll_rest[1] - dy
        ix, iy = round(rx), round(ry)
        self._scroll_rest = [rx - ix, ry - iy]
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + ix)
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + iy)

    def viewportEvent(self, ev):
        # Zwei-Finger-Zoom (Pinch) auf dem Touchpad
        if ev.type() == QEvent.NativeGesture and ev.gestureType() == Qt.ZoomNativeGesture:
            self.zoom_by(1.0 + ev.value(), ev.position())
            return True
        return super().viewportEvent(ev)

    # --------------------------------------------------------------- Griffe
    def _selected_items(self):
        return [i for i in self.scene().selectedItems() if isinstance(i, ObjectItem)]

    def _handles(self):
        """Griffe um die Auswahl – bei mehreren Objekten (z. B. einer Gruppe) um alle zusammen."""
        sel = [i for i in self._selected_items() if i.isVisible()]
        if not sel:
            return None
        r = sel[0].mapRectToScene(sel[0].stitch_rect())
        for it in sel[1:]:
            r = r.united(it.mapRectToScene(it.stitch_rect()))
        r = r.adjusted(-0.8, -0.8, 0.8, 0.8)
        corners = [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]
        rot = QPointF(r.center().x(), r.top() - 26 / self.zoom())
        return sel, r, corners, rot

    def _hit_handle(self, scene_pt):
        h = self._handles()
        if not h:
            return None
        it, r, corners, rot = h
        tol = 9 / self.zoom()
        if (scene_pt - rot).manhattanLength() < tol * 1.4:
            return it, "rotate"
        for c in corners:
            if abs(scene_pt.x() - c.x()) < tol and abs(scene_pt.y() - c.y()) < tol:
                return it, "scale"
        return None

    def drawForeground(self, p, rect):
        self._draw_tool_fg(p, rect)
        if self.tool == "measure" and self._measure:
            p.save()
            self._draw_measure(p)
            p.restore()
        if self.show_rulers:
            p.save()
            self._draw_rulers(p)
            p.restore()

    # ------------------------------------------------------------ Lineal & Messen
    RULER = 20                    # Breite der Lineale in Pixeln

    def _ruler_step(self):
        z = self.zoom()
        for step in (0.5, 1, 2, 5, 10, 20, 50, 100):
            if step * z >= 6:
                return step
        return 200

    def _draw_rulers(self, p):
        from . import style
        p.resetTransform()
        vw, vh = self.viewport().width(), self.viewport().height()
        R = self.RULER
        dark = style.CURRENT_THEME == "dark" if hasattr(style, "CURRENT_THEME") else False
        bg = QColor("#2A2D38") if dark else QColor("#F7F8FA")
        fg = QColor("#AEB4C4") if dark else QColor("#5B6070")
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, 0, vw, R))
        p.drawRect(QRectF(0, 0, R, vh))
        p.setPen(QPen(QColor(fg.red(), fg.green(), fg.blue(), 90), 1))
        p.drawLine(QPointF(0, R), QPointF(vw, R))
        p.drawLine(QPointF(R, 0), QPointF(R, vh))
        step = self._ruler_step()
        major = step * (10 if step < 5 else 5 if step < 50 else 2)
        tl = self.mapToScene(0, 0)
        br = self.mapToScene(vw, vh)
        f = QFont("DejaVu Sans")
        f.setPixelSize(9)
        p.setFont(f)
        p.setPen(QPen(fg, 1))
        v = math.floor(tl.x() / step) * step
        while v <= br.x():
            x = self.mapFromScene(QPointF(v, 0)).x()
            if x > R:
                big = abs(v / major - round(v / major)) < 1e-6
                p.drawLine(QPointF(x, R), QPointF(x, R - (9 if big else 4)))
                if big:
                    p.drawText(QPointF(x + 2, 9), f"{v:g}")
            v += step
        v = math.floor(tl.y() / step) * step
        while v <= br.y():
            y = self.mapFromScene(QPointF(0, v)).y()
            if y > R:
                big = abs(v / major - round(v / major)) < 1e-6
                p.drawLine(QPointF(R, y), QPointF(R - (9 if big else 4), y))
                if big:
                    p.save()
                    p.translate(9, y + 2)
                    p.rotate(-90)
                    p.drawText(QPointF(-20, 0), f"{v:g}")
                    p.restore()
            v += step
        if self._mouse is not None:                     # Mausposition auf beiden Linealen
            q = self.mapFromScene(self._mouse)
            p.setPen(QPen(ACCENT, 1.5))
            p.drawLine(QPointF(q.x(), 0), QPointF(q.x(), R))
            p.drawLine(QPointF(0, q.y()), QPointF(R, q.y()))
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, 0, R, R))

    def _measure_text(self):
        a, b = self._measure
        dx, dy = b.x() - a.x(), b.y() - a.y()
        d = math.hypot(dx, dy)
        ang = -math.degrees(math.atan2(dy, dx))
        t = f"{d:.1f} mm  (→ {dx:.1f}  ↓ {dy:.1f}  ∠ {ang:.0f}°)"
        return t.replace(".", ",")

    def _draw_measure(self, p):
        a, b = self._measure
        z = self.zoom()
        pen = QPen(QColor("#E91E63"), 1.6)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawLine(a, b)
        for q in (a, b):
            p.drawEllipse(q, 2.5 / z, 2.5 / z)
        p.resetTransform()
        mid = self.mapFromScene((a + b) / 2)
        f = QFont("DejaVu Sans")
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        txt = self._measure_text()
        w = p.fontMetrics().horizontalAdvance(txt) + 12
        box = QRectF(mid.x() + 8, mid.y() - 26, w, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(30, 30, 40, 210))
        p.drawRoundedRect(box, 5, 5)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(box, Qt.AlignCenter, txt)

    def _draw_tool_fg(self, p, rect):
        if self.tool == "eraser":
            self._draw_eraser_cursor(p)
            return
        if self.tool == "pen":
            self._draw_pen(p)
            return
        if self.tool == "connect":
            self._draw_connect(p)
            return
        if self.tool == "nodes":
            if self._letter_state():
                self._draw_letters(p)
                return
            self._draw_nodes(p)
            return
        if self.tool == "jumps":
            self._draw_jumps(p)
            return
        if self.tool != "select" or self._xf:
            return
        if self.snap_lines:
            pen = QPen(QColor("#E91E63"), 1, Qt.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            vr = self.mapToScene(self.viewport().rect()).boundingRect()
            for axis, v in self.snap_lines:
                if axis == "x":
                    p.drawLine(QPointF(v, vr.top()), QPointF(v, vr.bottom()))
                else:
                    p.drawLine(QPointF(vr.left(), v), QPointF(vr.right(), v))
        h = self._handles()
        if not h:
            return
        it, r, corners, rot = h
        z = self.zoom()
        s = 4.5 / z
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(ACCENT, 1.5)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawLine(QPointF(r.center().x(), r.top()), rot)
        p.setBrush(QColor("white"))
        for c in corners:
            p.drawRect(QRectF(c.x() - s, c.y() - s, 2 * s, 2 * s))
        p.setBrush(ACCENT)
        p.drawEllipse(rot, s * 1.2, s * 1.2)

    # ---------------------------------------------------------------- Bézier-Stift
    def _pen_nodes(self, extra=None, closed=False):
        """Gezeichnete Punkte -> Kurvenpunkte mit Anfassern [[x, y, typ], …] (Welt)."""
        an = list(self._pen) + ([extra] if extra else [])
        out = []
        n = len(an)
        for k, a in enumerate(an):
            out.append([a["p"][0], a["p"][1], CURVE if (a["hin"] or a["hout"]) else CORNER])
            if k + 1 < n or (closed and n > 2):
                b = an[(k + 1) % n]
                if a["hout"] or b["hin"]:
                    c1 = a["hout"] or a["p"]
                    c2 = b["hin"] or b["p"]
                    out += [[c1[0], c1[1], CTRL], [c2[0], c2[1], CTRL]]
        return out

    def _pen_press(self, ev, sp):
        if ev.button() == Qt.RightButton:
            self._pen_finish(False)
            return
        if ev.button() != Qt.LeftButton:
            return
        p = (sp.x(), sp.y())
        tol = 7 / self.zoom()
        if len(self._pen) >= 2:
            f = self._pen[0]["p"]
            if abs(p[0] - f[0]) < tol and abs(p[1] - f[1]) < tol:
                self._pen_finish(True)                # Klick auf den Startpunkt schließt
                return
        self._pen.append({"p": p, "hin": None, "hout": None})
        self._pen_drag = {"start": p}
        self._pen_preview()

    def _pen_move(self, ev, sp):
        self._pen_cursor = (sp.x(), sp.y())
        if self._pen_drag and ev.buttons() & Qt.LeftButton and self._pen:
            a = self._pen[-1]
            p = a["p"]
            if math.hypot(sp.x() - p[0], sp.y() - p[1]) * self.zoom() > 3:
                a["hout"] = (sp.x(), sp.y())
                if not ev.modifiers() & Qt.AltModifier:      # Alt: nur den Ausgangs-Anfasser
                    a["hin"] = (2 * p[0] - sp.x(), 2 * p[1] - sp.y())
        self._pen_preview()

    def _pen_release(self, ev, sp):
        self._pen_drag = None
        self._pen_preview()

    def _pen_preview(self):
        path = QPainterPath()
        if self._pen:
            extra = None
            if self._pen_cursor and not self._pen_drag:
                extra = {"p": self._pen_cursor, "hin": None, "hout": None}
            nodes = self._pen_nodes(extra)
            line = curves.polyline(nodes, False) if len(nodes) > 1 else [tuple(nodes[0][:2])]
            path.moveTo(QPointF(*line[0]))
            for q in line[1:]:
                path.lineTo(QPointF(*q))
        self.preview.setBrush(Qt.NoBrush)
        self.preview.setPath(path)
        self.viewport().update()

    def _draw_pen(self, p):
        if not self._pen:
            return
        s = 3.2 / self.zoom()
        p.setRenderHint(QPainter.Antialiasing)
        hp = QPen(QColor("#7E57C2"), 1)
        hp.setCosmetic(True)
        ap = QPen(ACCENT, 1.4)
        ap.setCosmetic(True)
        for k, a in enumerate(self._pen):
            for h in (a["hin"], a["hout"]):
                if h:
                    p.setPen(hp)
                    p.drawLine(QPointF(*a["p"]), QPointF(*h))
                    p.setBrush(QColor("white"))
                    p.drawEllipse(QPointF(*h), s * 0.9, s * 0.9)
            p.setPen(ap)
            p.setBrush(ACCENT if k == 0 else QColor("white"))
            x, y = a["p"]
            p.drawRect(QRectF(x - s, y - s, 2 * s, 2 * s))

    def _pen_finish(self, closed):
        nodes = self._pen_nodes(closed=closed) if self._pen else []
        anchors = [q for q in nodes if q[2] != CTRL]
        self._pen, self._pen_drag = [], None
        self.preview.setPath(QPainterPath())
        self.viewport().update()
        if closed and len(anchors) >= 2:
            if curves.ring_polygon(nodes).area > 1:
                self.objectCreated.emit("curve", {"rings": [nodes], "add": bool(
                    QApplication.keyboardModifiers() & Qt.ControlModifier)})
                self.toolFinished.emit()
        elif len(anchors) >= 2:
            self.objectCreated.emit("curveline", nodes)

    # ---------------------------------------------------------------- Einrasten
    def _start_snap(self):
        """Ziele für das Einrasten sammeln (Raster, Rahmenmitte, andere Objekte)."""
        sel = self._selected_items()
        if not sel or not self.snap:
            self._snap_ctx = None
            return
        xs, ys = ({0.0}, {0.0}) if self.snap_center else (set(), set())
        if self.snap_grid:
            step = self.opts.grid_step
            lim = 400
            k = int(lim / step)
            xs |= {i * step for i in range(-k, k + 1)}
            ys |= {i * step for i in range(-k, k + 1)}
        for it in (self.scene().items() if self.snap_objects else ()):
            if isinstance(it, ObjectItem) and it not in sel and it.isVisible():
                r = it.mapRectToScene(it.stitch_rect())
                xs |= {r.left(), r.center().x(), r.right()}
                ys |= {r.top(), r.center().y(), r.bottom()}
        self._snap_ctx = {"items": sel, "xs": sorted(xs), "ys": sorted(ys)}

    def _apply_snap(self, enabled):
        ctx = self._snap_ctx
        lines = []
        if ctx and enabled and self.snap:
            items = ctx["items"]
            r = items[0].mapRectToScene(items[0].stitch_rect())
            for it in items[1:]:
                r = r.united(it.mapRectToScene(it.stitch_rect()))
            tol = 8 / self.zoom()
            best = {}
            for axis, feats, targets in (("x", (r.left(), r.center().x(), r.right()), ctx["xs"]),
                                         ("y", (r.top(), r.center().y(), r.bottom()), ctx["ys"])):
                cand = None
                for f in feats:
                    for t in targets:
                        d = t - f
                        if abs(d) <= tol and (cand is None or abs(d) < abs(cand[0])):
                            cand = (d, t)
                if cand:
                    best[axis] = cand
            dx = best["x"][0] if "x" in best else 0.0
            dy = best["y"][0] if "y" in best else 0.0
            if dx or dy:
                for it in items:
                    it.setPos(it.pos().x() + dx, it.pos().y() + dy)
            lines = [(a, best[a][1]) for a in ("x", "y") if a in best]
        if lines != self.snap_lines:
            self.snap_lines = lines
            self.viewport().update()

    # ---------------------------------------------------------------- Maus
    def mousePressEvent(self, ev):
        sp = self.mapToScene(ev.position().toPoint())
        if ev.button() == Qt.MiddleButton or (self._space and ev.button() == Qt.LeftButton):
            self._pan = ev.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if self.tool == "select":
            if ev.button() == Qt.LeftButton:
                hit = self._hit_handle(sp)
                if hit:
                    items, mode = hit
                    # ein Objekt: um seinen Bezugspunkt, mehrere: um die Mitte der Auswahl
                    center = items[0].pos() if len(items) == 1 else self._handles()[1].center()
                    self._xf = {"items": items, "mode": mode, "start": sp,
                                "center": center, "f": 1.0, "a": 0.0}
                    return
            super().mousePressEvent(ev)
            self._start_snap()
            return
        if self.tool == "measure":
            if ev.button() == Qt.LeftButton:
                self._measure = [sp, sp]
                self._measuring = True
                self.viewport().update()
            return
        if self.tool == "nodes":
            if ev.button() == Qt.LeftButton and self._letters_press(sp):
                return
            self._nodes_press(ev, sp)
            return
        if self.tool == "connect":
            self._connect_press(ev, sp)
            return
        if self.tool == "pen":
            self._pen_press(ev, sp)
            return
        if self.tool == "jumps":
            if ev.button() in (Qt.LeftButton, Qt.RightButton):
                self.jumpClicked.emit(sp.x(), sp.y(), ev.globalPosition().toPoint())
            return
        if self.tool == "pick":
            if ev.button() == Qt.LeftButton:
                self.pointPicked.emit(sp.x(), sp.y())
            elif ev.button() == Qt.RightButton:
                self.escapePressed.emit()
            return
        if self.tool in ("polygon", "line", "satin") and ev.button() in (Qt.LeftButton, Qt.RightButton):
            # Profi-Eingabe: Linksklick = Eckpunkt, Rechtsklick = Rundungspunkt
            if (self.tool == "polygon" and len(self.pts) >= 3 and
                    max(abs(sp.x() - self.pts[0][0]), abs(sp.y() - self.pts[0][1])) < 7 / self.zoom()):
                self._finish_poly()      # Klick auf den Startpunkt schließt die Form
                return
            self.pts.append((sp.x(), sp.y()))
            self.ptypes.append(CURVE if ev.button() == Qt.RightButton else CORNER)
            self._update_poly_preview(sp)
            return
        if ev.button() == Qt.RightButton:
            self._finish_poly()
            return
        if ev.button() != Qt.LeftButton:
            return
        if self.tool in ("rect", "ellipse"):
            self.drag_start = sp
        elif self.tool == "eraser":
            self._erase_lasso = self.eraser_lasso or bool(ev.modifiers() & Qt.ShiftModifier)
            self.pts = [(sp.x(), sp.y())]
            if not self._erase_lasso:
                self.preview.setPath(geom_path(self.eraser_stroke(self.pts)))
        elif self.tool in ("freehand", "sketch"):
            self.pts = [(sp.x(), sp.y())]
        elif self.tool == "text":
            self.textRequested.emit(sp.x(), sp.y())

    def mouseMoveEvent(self, ev):
        sp = self.mapToScene(ev.position().toPoint())
        self.cursorMoved.emit(sp.x(), sp.y())
        self._mouse = sp
        if self.show_rulers:
            self.viewport().update(0, 0, self.viewport().width(), self.RULER)
            self.viewport().update(0, 0, self.RULER, self.viewport().height())
        if self.tool == "measure" and self._measuring:
            if ev.modifiers() & Qt.ShiftModifier:            # waagerecht/senkrecht/45°
                a = self._measure[0]
                d = sp - a
                ang = round(math.atan2(d.y(), d.x()) / (math.pi / 4)) * (math.pi / 4)
                r = math.hypot(d.x(), d.y())
                sp = a + QPointF(r * math.cos(ang), r * math.sin(ang))
            self._measure[1] = sp
            self.measured.emit(self._measure_text())
            self.viewport().update()
            return
        if self._pan is not None:
            d = ev.position() - self._pan
            self._pan = ev.position()
            self._scroll_by(d.x(), d.y())
            return
        if self._xf:
            xf = self._xf
            c, s0 = xf["center"], xf["start"]
            if xf["mode"] == "scale":
                d0 = math.hypot(s0.x() - c.x(), s0.y() - c.y()) or 1
                d1 = math.hypot(sp.x() - c.x(), sp.y() - c.y())
                xf["f"] = max(0.05, d1 / d0)
                for it in xf["items"]:
                    a = c - it.pos()
                    it.setTransform(QTransform().translate(a.x(), a.y()).scale(xf["f"], xf["f"])
                                    .translate(-a.x(), -a.y()))
            else:
                a0 = math.atan2(s0.y() - c.y(), s0.x() - c.x())
                a1 = math.atan2(sp.y() - c.y(), sp.x() - c.x())
                a = math.degrees(a1 - a0)
                if ev.modifiers() & Qt.ShiftModifier:
                    a = round(a / 15) * 15
                xf["a"] = a
                for it in xf["items"]:
                    v = c - it.pos()
                    it.setTransform(QTransform().translate(v.x(), v.y()).rotate(a)
                                    .translate(-v.x(), -v.y()))
            self.viewport().update()
            return
        if self.tool == "nodes":
            if self._letter_drag is not None:
                d = sp - self._letter_drag["start"]
                if ev.modifiers() & Qt.ShiftModifier:          # nur waagerecht (Laufweite)
                    d.setY(0)
                self._letter_drag["d"] = d
                self.viewport().update()
                return
            self._nodes_move(ev, sp)
            return
        if self.tool == "connect":
            self._connect_move(ev, sp)
            return
        if self.tool == "pen":
            self._pen_move(ev, sp)
            return
        if self.tool == "jumps":
            h = self.hit_jump(sp.x(), sp.y())
            if h != self._jump_hover:
                self._jump_hover = h
                self.viewport().update()
            self.viewport().setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)
            return
        if self.tool == "select":
            hit = self._hit_handle(sp)
            if hit:
                self.viewport().setCursor(Qt.SizeFDiagCursor if hit[1] == "scale" else Qt.CrossCursor)
            else:
                self.viewport().setCursor(Qt.ArrowCursor)
            super().mouseMoveEvent(ev)
            if ev.buttons() & Qt.LeftButton:
                self._apply_snap(not (ev.modifiers() & Qt.AltModifier))
            return
        if self.tool in ("rect", "ellipse") and self.drag_start is not None:
            path = QPainterPath()
            r = QRectF(self.drag_start, sp).normalized()
            if ev.modifiers() & Qt.ShiftModifier:
                m = max(r.width(), r.height())
                r = QRectF(r.topLeft(), r.topLeft() + QPointF(m, m))
            if self.tool == "rect":
                path.addRect(r)
            else:
                path.addEllipse(r)
            self.preview.setPath(path)
        elif self.tool in ("polygon", "line", "satin") and self.pts:
            self._update_poly_preview(sp)
        if self.tool == "eraser":
            self._erase_hover = True
            self._update_eraser_cursor()        # Pinselkreis folgt der Maus
        if self.tool == "eraser" and self.pts and ev.buttons() & Qt.LeftButton \
                and not self._erase_lasso:
            last = self.pts[-1]
            if math.hypot(sp.x() - last[0], sp.y() - last[1]) > min(0.4, self.eraser_size / 6):
                self.pts.append((sp.x(), sp.y()))
                self.preview.setPath(geom_path(self.eraser_stroke(self.pts)))
        elif self.tool in ("freehand", "eraser", "sketch") and self.pts and ev.buttons() & Qt.LeftButton:
            last = self.pts[-1]
            if math.hypot(sp.x() - last[0], sp.y() - last[1]) > 0.4:
                self.pts.append((sp.x(), sp.y()))
            path = QPainterPath(QPointF(*self.pts[0]))
            for p in self.pts[1:]:
                path.lineTo(QPointF(*p))
            if self.tool == "eraser":
                path.closeSubpath()
            self.preview.setPath(path)

    def mouseReleaseEvent(self, ev):
        sp = self.mapToScene(ev.position().toPoint())
        if self._pan is not None:
            self._pan = None
            self.viewport().setCursor(Qt.ArrowCursor if self.tool == "select" else Qt.CrossCursor)
            return
        if self.tool == "measure":
            self._measuring = False
            if self._measure:
                self.measured.emit(self._measure_text())
            return
        if self.tool == "nodes":
            if self._letter_drag is not None:
                self._letters_release()
                return
            self._nodes_release(ev, sp)
            return
        if self.tool in ("jumps", "pick"):
            return
        if self.tool == "pen":
            self._pen_release(ev, sp)
            return
        if self.tool == "eraser":
            pts, self.pts = self.pts, []
            self.preview.setPath(QPainterPath())
            if not pts:
                return
            if self._erase_lasso:
                if len(pts) > 2 and Polygon(pts).buffer(0).area > 1:
                    self.eraseRequested.emit(Polygon(pts).buffer(0))
            else:
                pts.append((sp.x(), sp.y()))
                self.eraseRequested.emit(self.eraser_stroke(pts))
            return
        if self._xf:
            xf, self._xf = self._xf, None
            for it in xf["items"]:
                it.setTransform(QTransform())
            objs = [it.obj for it in xf["items"]]
            c = xf["center"]
            if xf["mode"] == "scale" and abs(xf["f"] - 1) > 1e-3:
                transform_objects(objs, (c.x(), c.y()), scale=xf["f"])
                self.itemsTransformed.emit(objs)
            elif xf["mode"] == "rotate" and abs(xf["a"]) > 1e-3:
                transform_objects(objs, (c.x(), c.y()), angle=xf["a"])
                self.itemsTransformed.emit(objs)
            self.viewport().update()
            return
        if self.tool == "select":
            super().mouseReleaseEvent(ev)
            self._snap_ctx = None
            if self.snap_lines:
                self.snap_lines = []
                self.viewport().update()
            moved = []
            for it in self._selected_items():
                o = it.obj
                if abs(it.pos().x() - o.x) > 1e-4 or abs(it.pos().y() - o.y) > 1e-4:
                    o.x, o.y = it.pos().x(), it.pos().y()
                    moved.append(o)
            if moved:
                self.itemsTransformed.emit(moved)
            self.viewport().update()
            return
        if self.tool in ("rect", "ellipse") and self.drag_start is not None:
            r = QRectF(self.drag_start, sp).normalized()
            if ev.modifiers() & Qt.ShiftModifier:
                m = max(r.width(), r.height())
                r = QRectF(r.topLeft(), r.topLeft() + QPointF(m, m))
            self.drag_start = None
            self.preview.setPath(QPainterPath())
            if r.width() > 2 and r.height() > 2:
                if self.tool == "rect":
                    self.objectCreated.emit("shape", box(r.left(), r.top(), r.right(), r.bottom()))
                else:
                    # Ellipse aus wenigen Rundungspunkten – lässt sich gut nachbearbeiten
                    a, b = r.width() / 2, r.height() / 2
                    n = 12 if max(a, b) > 2 * min(a, b) else 8
                    c = r.center()
                    nodes = [[c.x() + a * math.cos(2 * math.pi * k / n),
                              c.y() + b * math.sin(2 * math.pi * k / n), CURVE] for k in range(n)]
                    self.objectCreated.emit("curve", {"rings": [nodes], "add": False})
                self.toolFinished.emit()
        elif self.tool in ("freehand", "sketch") and len(self.pts) > 2:
            ls = LineString(self.pts).simplify(0.25)
            pts = list(ls.coords)
            self.pts = []
            self.preview.setPath(QPainterPath())
            if ls.length > 3:
                self.objectCreated.emit("line" if self.tool == "freehand" else "sketch", pts)

    def mouseDoubleClickEvent(self, ev):
        if self.tool == "nodes":
            sp = self.mapToScene(ev.position().toPoint())
            if not self._hit_node(sp):      # der erste Klick hat den Punkt schon eingefügt
                self._insert_node(sp)
            return
        if self.tool in ("polygon", "line", "satin"):
            self._finish_poly()
        elif self.tool == "pen":
            if self._pen and len(self._pen) > 1:
                last, prev = self._pen[-1]["p"], self._pen[-2]["p"]
                if math.hypot(last[0] - prev[0], last[1] - prev[1]) < 0.5:   # Doppelklick-Rest
                    self._pen.pop()
            self._pen_finish(False)
        else:
            it = self.itemAt(ev.position().toPoint())
            obj = getattr(it, "obj", None)
            if self.tool == "select" and obj is not None and obj.kind in ("cross", "print", "stitches"):
                self.crossRequested.emit(obj)
                return
            super().mouseDoubleClickEvent(ev)

    def _update_poly_preview(self, cursor):
        if self.tool == "satin":
            self._update_satin_preview(cursor)
            return
        nodes = [[x, y, t] for (x, y), t in zip(self.pts, self.ptypes)]
        nodes.append([cursor.x(), cursor.y(), CORNER])
        closed = self.tool == "polygon" and len(nodes) > 2
        line = curves.polyline(nodes, closed)
        path = QPainterPath(QPointF(*line[0]))
        for p in line[1:]:
            path.lineTo(QPointF(*p))
        if closed:
            path.closeSubpath()
        r = 1.2 / max(self.zoom() / 4, 0.25)
        for (x, y), t in zip(self.pts, self.ptypes):
            if t == CURVE:
                path.addEllipse(QPointF(x, y), r, r)
            else:
                path.addRect(QRectF(x - r, y - r, 2 * r, 2 * r))
        self.preview.setPath(path)

    def _update_satin_preview(self, cursor):
        """Säulen-Satin: Punkte abwechselnd linke/rechte Schiene, Paare = Stege."""
        nodes = [[x, y, t] for (x, y), t in zip(self.pts, self.ptypes)]
        nodes.append([cursor.x(), cursor.y(), CORNER])
        a, b = nodes[0::2], nodes[1::2]
        path = QPainterPath()
        for rail in (a, b):
            if len(rail) >= 2:
                line = curves.polyline(rail, False)
                path.moveTo(QPointF(*line[0]))
                for p in line[1:]:
                    path.lineTo(QPointF(*p))
        for p, q in zip(a, b):                  # Stege
            path.moveTo(QPointF(p[0], p[1]))
            path.lineTo(QPointF(q[0], q[1]))
        r = 1.2 / max(self.zoom() / 4, 0.25)
        for k, ((x, y), t) in enumerate(zip(self.pts, self.ptypes)):
            if t == CURVE:
                path.addEllipse(QPointF(x, y), r, r)
            else:
                path.addRect(QRectF(x - r, y - r, 2 * r, 2 * r))
        self.preview.setPath(path)

    def _finish_poly(self):
        nodes = []
        for (x, y), t in zip(self.pts, self.ptypes):   # Doppelklick-Duplikate entfernen
            if not nodes or math.hypot(x - nodes[-1][0], y - nodes[-1][1]) > 0.3:
                nodes.append([x, y, t])
        add = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        self._satin_pts, self._satin_types = list(self.pts), list(self.ptypes)
        if self.tool == "satin" and len(self._satin_pts) % 2 == 1 and len(self._satin_pts) > 4:
            last, prev = self._satin_pts[-1], self._satin_pts[-3]
            if math.hypot(last[0] - prev[0], last[1] - prev[1]) < 0.3:   # Doppelklick-Rest
                self._satin_pts.pop()
                self._satin_types.pop()
        self.pts, self.ptypes = [], []
        self.preview.setPath(QPainterPath())
        if self.tool == "polygon" and len(nodes) >= 3:
            if curves.ring_polygon(nodes).area > 4:
                self.objectCreated.emit("curve", {"rings": [nodes], "add": add})
                self.toolFinished.emit()
        elif self.tool == "line" and len(nodes) >= 2:
            self.objectCreated.emit("curveline", nodes)
        elif self.tool == "satin":
            raw = [[x, y, t] for (x, y), t in zip(self._satin_pts, self._satin_types)]
            n = len(raw) // 2
            if n >= 2:
                self.objectCreated.emit("satin", {"a": raw[0:2 * n:2], "b": raw[1:2 * n:2]})

    # ------------------------------------------------------------- Tastatur
    # ---------------------------------------------------------------- Radierer
    def eraser_stroke(self, pts):
        """Fläche, die der runde Radierer entlang des Strichs überstreicht (wie im Malprogramm)."""
        r = max(self.eraser_size, 0.05) / 2
        pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        if len(pts) == 1:
            return Point(pts[0]).buffer(r, 24)
        return LineString(pts).buffer(r, 24)

    def set_eraser_size(self, mm):
        self.eraser_size = round(max(0.3, min(50.0, float(mm))), 2)
        self.eraserSizeChanged.emit(self.eraser_size)
        self.viewport().update()

    def _draw_eraser_cursor(self, p):
        """Kreis in Radiergröße am Mauszeiger."""
        if self.eraser_lasso or self._erase_lasso and self.pts or not self._erase_hover \
                or self._mouse is None:
            return
        r = self.eraser_size / 2
        for col, w in ((QColor(255, 255, 255, 200), 3), (QColor("#E53935"), 1.2)):
            pen = QPen(col, w)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(self._mouse, r, r)

    def _update_eraser_cursor(self):
        """Nur den Bereich um den alten und neuen Pinselkreis neu zeichnen."""
        if self._mouse is None:
            return
        r = self.eraser_size / 2
        rect = self.mapFromScene(QRectF(self._mouse.x() - r, self._mouse.y() - r, 2 * r, 2 * r)) \
            .boundingRect().adjusted(-4, -4, 4, 4)
        old, self._erase_rect = getattr(self, "_erase_rect", None), rect
        self.viewport().update(rect.united(old) if old is not None else rect)

    def leaveEvent(self, ev):
        if self._erase_hover:
            self._erase_hover = False
            self.viewport().update()
        super().leaveEvent(ev)

    def keyPressEvent(self, ev):
        if self.tool == "eraser" and ev.key() in (Qt.Key_BracketLeft, Qt.Key_BracketRight):
            f = 1.25 if ev.key() == Qt.Key_BracketRight else 1 / 1.25
            self.set_eraser_size(self.eraser_size * f)
            return
        if ev.key() == Qt.Key_Space and not ev.isAutoRepeat():
            self._space = True
            self.viewport().setCursor(Qt.OpenHandCursor)
            return
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.tool == "pen":
                self._pen_finish(False)
                return
            self._finish_poly()
            return
        if self.tool == "pen" and ev.key() == Qt.Key_Escape and self._pen:
            self._pen = []
            self._pen_drag = None
            self.preview.setPath(QPainterPath())
            self.viewport().update()
            return
        if self.tool == "pen" and ev.key() == Qt.Key_Backspace and self._pen:
            self._pen.pop()
            self._pen_preview()
            return
        if ev.key() == Qt.Key_Escape:
            if self.tool == "connect" and self._conn_a:
                self._conn_a = None
                self.preview.setPath(QPainterPath())
                self.viewport().update()
                return
            if self.tool == "nodes" and self._node_sel:
                self._node_sel = set()
                self.viewport().update()
                return
            if self.pts or self.drag_start is not None:
                self.set_tool(self.tool)
            else:
                self.escapePressed.emit()
            return
        if ev.key() == Qt.Key_Backspace and self.pts:
            self.pts.pop()
            self.ptypes.pop()
            if self.pts:
                self._update_poly_preview(self.mapToScene(self.mapFromGlobal(self.cursor().pos())))
            else:
                self.preview.setPath(QPainterPath())
            return
        super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Space and not ev.isAutoRepeat():
            self._space = False
            self.viewport().setCursor(Qt.ArrowCursor if self.tool == "select" else Qt.CrossCursor)
            return
        super().keyReleaseEvent(ev)

    # ======================================================= Punkte bearbeiten
    # ------------------------------------------------------ einzelne Buchstaben
    def _letter_state(self):
        """Buchstaben-Anfasser des gewählten Schriftzugs: {"obj", "pts": [(i, zeichen, QPointF)]}."""
        sel = self._selected_items()
        if len(sel) != 1 or sel[0].obj.kind != "text":
            self._letters = None
            return None
        o = sel[0].obj
        key = (o.id, json.dumps(o.text, sort_keys=True, default=str), o.x, o.y, o.rot, o.sx, o.sy)
        if self._letters and self._letters["key"] == key:
            return self._letters
        try:
            centers = o.letter_centers()
        except Exception:
            centers = []
        pts = [(i, ch, QPointF(*o.to_world(x, y))) for i, ch, x, y in centers]
        self._letters = {"key": key, "obj": o, "pts": pts}
        return self._letters

    def _draw_letters(self, p):
        st = self._letter_state()
        z = self.zoom()
        r = 4.0 / z
        p.setRenderHint(QPainter.Antialiasing)
        drag = self._letter_drag
        for i, ch, q in st["pts"]:
            if drag is not None and drag["i"] == i:
                q = q + drag["d"]
            sel = i == self.letter_sel
            pen = QPen(ACCENT.darker(140), 1.2)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(ACCENT if sel else QColor("#FFFFFF"))
            poly = QPolygonF([q + QPointF(0, -r * 1.4), q + QPointF(r * 1.4, 0),
                              q + QPointF(0, r * 1.4), q + QPointF(-r * 1.4, 0)])
            p.drawPolygon(poly)

    def _letters_press(self, sp):
        st = self._letter_state()
        if not st:
            return False
        z = self.zoom()
        best = None
        for i, ch, q in st["pts"]:
            d = math.hypot(q.x() - sp.x(), q.y() - sp.y()) * z
            if d < 9 and (best is None or d < best[0]):
                best = (d, i)
        if best is None:
            return False
        self.letter_sel = best[1]
        self._letter_drag = {"i": best[1], "start": sp, "d": QPointF(0, 0), "obj": st["obj"]}
        self.letterPicked.emit(best[1])
        self.viewport().update()
        return True

    def _letters_release(self):
        drag, self._letter_drag = self._letter_drag, None
        o = drag["obj"]
        d = drag["d"]
        if abs(d.x()) + abs(d.y()) < 1e-3:
            self.viewport().update()
            return
        # Verschiebung auf der Arbeitsfläche -> Objektmaße (Drehung/Spiegelung/Skalierung heraus)
        c, s = math.cos(math.radians(-o.rot)), math.sin(math.radians(-o.rot))
        lx, ly = d.x() * c - d.y() * s, d.x() * s + d.y() * c
        lx /= o.sx or 1
        ly /= o.sy or 1
        self.letterMoved.emit(o, drag["i"], lx, ly)
        self.viewport().update()

    def edit_target(self):
        sel = self._selected_items()
        if len(sel) == 1 and sel[0].obj.kind in ("shape", "line", "satin"):
            return sel[0].obj
        return None

    def _node_state(self):
        """Pfade der Zielform: Punkte [x, y, typ] in Objekt- und Weltkoordinaten."""
        o = self.edit_target()
        if o is None:
            self._nodes = None
            return None
        geo_key = json.dumps(o._gkey_source())
        key = (o.id, geo_key, o.x, o.y, o.rot, o.sx, o.sy)
        if self._nodes and self._nodes["key"] == key:
            return self._nodes
        if o.kind == "line":
            rings = [{"closed": o.closed, "pts": o.line_nodes()}]
        elif o.kind == "satin":
            rings = [{"closed": False, "pts": [list(p) for p in r]} for r in o.curve]
        else:
            src = o.curve or curves.polygon_rings(o.raw_geometry())
            rings = [{"closed": True, "pts": [list(p) for p in r]} for r in src]
        for r in rings:
            r["world"] = [o.to_world(p[0], p[1]) for p in r["pts"]]
        if self._nodes is None or self._nodes["key"][:2] != key[:2]:
            self._node_sel = set()
        self._nodes = {"key": key, "obj": o, "rings": rings}
        return self._nodes

    @staticmethod
    def _ctrl_owner(r):
        """Anfasser -> zugehörige Kurvenpunkte {anfasser: {kurvenpunkt, …}} und Abschnitte."""
        groups = curves.anchor_groups(r["pts"], r["closed"])
        owner = {}
        na = len(groups)
        for k, (a, ctrl) in enumerate(groups):
            b = groups[(k + 1) % na][0] if na else a
            for m, j in enumerate(ctrl):
                if len(ctrl) == 1:
                    owner[j] = {a, b}
                else:
                    owner[j] = {a} if m == 0 else {b}
        return owner, groups

    def _visible_ctrls(self, st):
        """Anfasser, die gezeigt werden: an gewählten Kurvenpunkten und gewählte Anfasser."""
        vis = set()
        for ri, r in enumerate(st["rings"]):
            owner, _ = self._ctrl_owner(r)
            sel_a = {i for rj, i in self._node_sel if rj == ri}
            for j, anchors in owner.items():
                if (anchors & sel_a) or j in sel_a:
                    vis.add((ri, j))
                    for k, o2 in owner.items():          # Geschwister am selben Kurvenpunkt
                        if j in sel_a and o2 & anchors:
                            vis.add((ri, k))
        return vis

    def _hit_node(self, sp):
        st = self._node_state()
        if not st:
            return None
        tol = 7 / self.zoom()
        best, bd = None, tol
        vis = self._visible_ctrls(st)
        for ri, r in enumerate(st["rings"]):
            for i, (x, y) in enumerate(r["world"]):
                if r["pts"][i][2] == CTRL and (ri, i) not in vis:
                    continue
                d = max(abs(x - sp.x()), abs(y - sp.y()))
                if d < bd or (d <= bd + 1e-9 and r["pts"][i][2] == CTRL):
                    best, bd = (ri, i), d
        return best

    def _draw_nodes(self, p):
        st = self._node_state()
        if not st:
            return
        o = st["obj"]
        z = self.zoom()
        s = 3.2 / z
        dx, dy = self._node_drag["d"] if self._node_drag else (0, 0)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(ACCENT, 1.4)
        pen.setCosmetic(True)
        moving = self._moving_set(st) if self._node_drag else set()
        for ri, r in enumerate(st["rings"]):
            world = [(x + dx, y + dy) if (ri, i) in moving else (x, y)
                     for i, (x, y) in enumerate(r["world"])]
            if len(world) < 2:
                continue
            local = [[*o.to_local(*w), q[2]] for w, q in zip(world, r["pts"])]
            line = [o.to_world(*q) for q in curves.polyline(local, r["closed"])]
            path = QPainterPath(QPointF(*line[0]))
            for q in line[1:]:
                path.lineTo(QPointF(*q))
            if r["closed"]:
                path.closeSubpath()
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            owner, _ = self._ctrl_owner(r)
            vis = self._visible_ctrls(st)
            hp = QPen(QColor("#7E57C2"), 1)
            hp.setCosmetic(True)
            for j, anchors in owner.items():           # Bézier-Anfasser mit Hebelarm
                if (ri, j) not in vis:
                    continue
                for a in anchors:
                    p.setPen(hp)
                    p.drawLine(QPointF(*world[a]), QPointF(*world[j]))
                p.setPen(hp)
                p.setBrush(QColor("#7E57C2") if (ri, j) in self._node_sel else QColor("white"))
                p.drawEllipse(QPointF(*world[j]), s * 0.9, s * 0.9)
            p.setPen(pen)
            for i, (x, y) in enumerate(world):
                if r["pts"][i][2] == CTRL:
                    continue
                sel = (ri, i) in self._node_sel
                p.setBrush(ACCENT if sel else QColor("white"))
                if r["pts"][i][2] == CURVE:
                    p.drawEllipse(QPointF(x, y), s * 1.15, s * 1.15)
                else:
                    p.drawRect(QRectF(x - s, y - s, 2 * s, 2 * s))
        if self._edge_hover and not self._node_drag and not self._band:
            x, y = self._edge_hover
            p.setPen(pen)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(x, y), s * 2.0, s * 2.0)
            k = s * 1.2
            p.drawLine(QPointF(x - k, y), QPointF(x + k, y))
            p.drawLine(QPointF(x, y - k), QPointF(x, y + k))
        if self._band:
            bp = QPen(ACCENT, 1, Qt.DashLine)
            bp.setCosmetic(True)
            p.setPen(bp)
            p.setBrush(_tint(30))
            p.drawRect(QRectF(self._band[0], self._band[1]).normalized())

    def _nodes_press(self, ev, sp):
        hit = self._hit_node(sp)
        edge = None if hit else self._hit_edge(sp)
        if ev.button() == Qt.RightButton:
            m = QMenu(self)
            if hit:
                if hit not in self._node_sel:
                    self._node_sel = {hit}
                self.viewport().update()
                st_kind = self._node_state()["obj"].kind
                m.addAction("Eckpunkt (spitz)", lambda: self.set_node_type(CORNER))
                m.addAction("Rundungspunkt (fließend)", lambda: self.set_node_type(CURVE))
                if st_kind != "satin":
                    m.addAction("Bézier-Anfasser hinzufügen", self.add_handles)
                    m.addAction("Bézier-Anfasser entfernen", self.remove_handles)
                m.addSeparator()
                m.addAction("Punkt danach einfügen", self.insert_nodes)
                if len(self._node_sel) >= 2:
                    m.addAction("Punkte verbinden", lambda: self.joinRequested.emit())
                if len(self._node_sel) == 2:
                    m.addAction("Mit Linie verbinden", lambda: self.connectNodesRequested.emit())
                if st_kind == "line":
                    m.addAction("Linie hier auftrennen", lambda: self.breakRequested.emit())
                m.addAction("Punkt löschen", self.delete_nodes)
            elif edge:
                m.addAction("Punkt hier einfügen", lambda: self._insert_edge(edge))
                m.addAction("Rundungspunkt hier einfügen", lambda: self._insert_edge(edge, CURVE))
                m.addAction("Eckpunkt hier einfügen", lambda: self._insert_edge(edge, CORNER))
            elif self._open_end(sp):
                m.addAction("Linie bis hierher verlängern", lambda: self._append_node(sp))
            else:
                return
            m.exec(ev.globalPosition().toPoint())
            return
        if ev.button() != Qt.LeftButton:
            return
        if not hit and edge:
            # Klick auf die Kante: Punkt einfügen und gleich ziehen
            hit = self._insert_edge(edge)
            if hit is None:
                return
            sp = QPointF(*edge["pt"])
            self._edge_hover = None
            self.merge_undo = True
        elif not hit and ev.modifiers() & Qt.ControlModifier and self._open_end(sp):
            hit = self._append_node(sp)
            if hit is None:
                return
        if hit:
            if ev.modifiers() & Qt.ShiftModifier:
                self._node_sel ^= {hit}
            elif hit not in self._node_sel:
                self._node_sel = {hit}
            self._node_drag = {"start": sp, "d": (0.0, 0.0)}
        else:
            if not ev.modifiers() & Qt.ShiftModifier:
                self._node_sel = set()
            self._band = [sp, sp]
        self.viewport().update()

    def _nodes_move(self, ev, sp):
        if self._node_drag:
            s0 = self._node_drag["start"]
            self._node_drag["d"] = (sp.x() - s0.x(), sp.y() - s0.y())
            self.viewport().update()
        elif self._band:
            self._band[1] = sp
            self.viewport().update()
        else:
            node = self._hit_node(sp)
            edge = None if node else self._hit_edge(sp)
            pt = edge["pt"] if edge else None
            if pt != self._edge_hover:
                self._edge_hover = pt
                self.viewport().update()
            self.viewport().setCursor(Qt.SizeAllCursor if node else
                                      Qt.PointingHandCursor if edge else Qt.ArrowCursor)

    def _nodes_release(self, ev, sp):
        if self._node_drag:
            dx, dy = self._node_drag["d"]
            self._node_drag = None
            if abs(dx) > 1e-3 or abs(dy) > 1e-3:
                self.move_nodes(dx, dy)
            self.merge_undo = False
            self.viewport().update()
            return
        if self._band:
            a, b = self._band
            self._band = None
            r = QRectF(a, b).normalized()
            if r.width() * self.zoom() < 4 and r.height() * self.zoom() < 4:
                # Klick ins Leere: anderes Objekt zum Bearbeiten wählen
                item = self.itemAt(ev.position().toPoint())
                if isinstance(item, ObjectItem):
                    self.scene().clearSelection()
                    item.setSelected(True)
            else:
                st = self._node_state()
                if st:
                    for ri, ring in enumerate(st["rings"]):
                        for i, (x, y) in enumerate(ring["world"]):
                            if r.contains(QPointF(x, y)) and ring["pts"][i][2] != CTRL:
                                self._node_sel.add((ri, i))
            self.viewport().update()

    def has_node_selection(self):
        return self.tool == "nodes" and bool(self._node_sel) and self._node_state() is not None

    def _moving_set(self, st):
        """Gewählte Punkte plus die Anfasser gewählter Kurvenpunkte (wandern mit)."""
        move = set(self._node_sel)
        for ri, r in enumerate(st["rings"]):
            owner, _ = self._ctrl_owner(r)
            sel_a = {i for rj, i in self._node_sel if rj == ri and r["pts"][i][2] != CTRL}
            for j, anchors in owner.items():
                if anchors & sel_a:
                    move.add((ri, j))
        return move

    def move_nodes(self, dx, dy):
        st = self._node_state()
        if not st or not self._node_sel:
            return
        o = st["obj"]
        for ri, i in self._moving_set(st):
            wx, wy = st["rings"][ri]["world"][i]
            st["rings"][ri]["pts"][i][:2] = o.to_local(wx + dx, wy + dy)
        # einzelner Anfasser an einem glatten Punkt: Gegenstück in einer Linie halten
        if len(self._node_sel) == 1:
            ri, j = next(iter(self._node_sel))
            r = st["rings"][ri]
            if r["pts"][j][2] == CTRL:
                owner, _ = self._ctrl_owner(r)
                for a in owner.get(j, ()):
                    if r["pts"][a][2] != CURVE:
                        continue
                    for k, anchors in owner.items():
                        if k != j and anchors == {a} and owner[j] == {a}:
                            A = r["pts"][a]
                            vx, vy = r["pts"][j][0] - A[0], r["pts"][j][1] - A[1]
                            L = math.hypot(vx, vy)
                            ln = math.hypot(r["pts"][k][0] - A[0], r["pts"][k][1] - A[1])
                            if L > 1e-9:
                                r["pts"][k][:2] = [A[0] - vx / L * ln, A[1] - vy / L * ln]
        self._apply_rings(st, keep_selection=True)

    def set_node_type(self, t):
        st = self._node_state()
        if not st or not self._node_sel:
            return
        for ri, i in self._node_sel:
            r = st["rings"][ri]
            if r["pts"][i][2] == CTRL:
                continue
            r["pts"][i][2] = t
            if t == CURVE:                         # Anfasser in eine Linie bringen
                owner, _ = self._ctrl_owner(r)
                hs = [j for j, an in owner.items() if an == {i}]
                if len(hs) == 2:
                    A = r["pts"][i]
                    h1, h2 = r["pts"][hs[0]], r["pts"][hs[1]]
                    vx, vy = h2[0] - h1[0], h2[1] - h1[1]
                    L = math.hypot(vx, vy) or 1e-9
                    l1 = math.hypot(h1[0] - A[0], h1[1] - A[1])
                    l2 = math.hypot(h2[0] - A[0], h2[1] - A[1])
                    h1[:2] = [A[0] - vx / L * l1, A[1] - vy / L * l1]
                    h2[:2] = [A[0] + vx / L * l2, A[1] + vy / L * l2]
        self._apply_rings(st, keep_selection=True)

    def delete_nodes(self):
        st = self._node_state()
        if not st or not self._node_sel:
            return
        if st["obj"].kind == "satin":           # immer ganze Paare (Stege) löschen
            idx = {i for _, i in self._node_sel}
            if len(st["rings"][0]["pts"]) - len(idx) < 2:
                return
            for ring in st["rings"]:
                ring["pts"] = [q for i, q in enumerate(ring["pts"]) if i not in idx]
        else:
            for ri, ring in enumerate(st["rings"]):
                owner, groups = self._ctrl_owner(ring)
                drop = {i for rj, i in self._node_sel if rj == ri}
                # mit einem Kurvenpunkt verschwinden seine eigenen Anfasser; die äußeren der
                # Nachbarn bleiben und formen die neue Strecke
                for j, anchors in owner.items():
                    if anchors and anchors <= drop:
                        drop.add(j)
                ring["pts"] = [q for i, q in enumerate(ring["pts"]) if i not in drop]
        self._node_sel = set()
        self._apply_rings(st)

    def add_handles(self):
        """Strecken an den gewählten Punkten in Bézierkurven mit Anfassern umwandeln – die
        aktuelle Form bleibt erhalten (Anfasser aus der Kurvenrichtung)."""
        st = self._node_state()
        if not st or not self._node_sel or st["obj"].kind == "satin":
            return
        for ri, r in enumerate(st["rings"]):
            pts = r["pts"]
            groups = curves.anchor_groups(pts, r["closed"])
            na = len(groups)
            m = na if r["closed"] else na - 1
            sel = {i for rj, i in self._node_sel if rj == ri}
            todo = [k for k in range(m) if not groups[k][1] and
                    (groups[k][0] in sel or groups[(k + 1) % na][0] in sel)]
            pieces = {k: curves.segment_pieces(pts, r["closed"], k) for k in todo}
            for k in sorted(todo, reverse=True):
                a = groups[k][0]
                ins = []
                for m_, (c1, c2, end) in enumerate(pieces[k]):
                    ins += [[c1[0], c1[1], CTRL], [c2[0], c2[1], CTRL]]
                    if m_ < len(pieces[k]) - 1:          # Zwischenpunkt (glatt)
                        ins.append([end[0], end[1], CURVE])
                pts[a + 1:a + 1] = ins
        self._apply_rings(st, keep_selection=False)

    def remove_handles(self):
        """Anfasser an den gewählten Punkten entfernen (Strecken wieder Ecke/Rundung)."""
        st = self._node_state()
        if not st or not self._node_sel:
            return
        for ri, r in enumerate(st["rings"]):
            owner, _ = self._ctrl_owner(r)
            sel = {i for rj, i in self._node_sel if rj == ri}
            drop = {j for j, anchors in owner.items() if anchors & sel or j in sel}
            r["pts"] = [q for j, q in enumerate(r["pts"]) if j not in drop]
        self._node_sel = set()
        self._apply_rings(st)

    def _hit_edge(self, sp):
        """Kante unter dem Mauszeiger: {ri, i, t, pt} (t = Anteil entlang der Teilstrecke)."""
        st = self._node_state()
        if not st:
            return None
        o = st["obj"]
        tol = 6 / self.zoom()
        here = Point(sp.x(), sp.y())
        best = None
        for ri, r in enumerate(st["rings"]):
            for i, seg in enumerate(curves.segments(r["pts"], r["closed"])):
                wl = LineString([o.to_world(*q) for q in seg])
                if wl.length < 1e-9:
                    continue
                d = wl.distance(here)
                if d < tol and (best is None or d < best[0]):
                    pos = wl.project(here)
                    q = wl.interpolate(pos)
                    best = (d, {"ri": ri, "i": i, "t": pos / wl.length, "pt": (q.x, q.y)})
        return best[1] if best else None

    def _split_ring(self, st, ri, i, t, kind=None):
        """Punkt in Ring ri auf Teilstrecke i (zwischen zwei Kurvenpunkten) bei Anteil t
        einfügen (Objektkoordinaten). Liefert den Index des neuen Punkts."""
        r = st["rings"][ri]
        pts = r["pts"]
        groups = curves.anchor_groups(pts, r["closed"])
        a, ctrl = groups[i]
        b = groups[(i + 1) % len(groups)][0]
        t = max(0.0, min(1.0, t))
        if ctrl:
            # Bézier-Strecke: genau teilen (De Casteljau), Form bleibt erhalten
            A, B = pts[a][:2], pts[b][:2]
            c1, c2 = curves.cubic_controls(A, [pts[j] for j in ctrl], B)
            c1a, c2a, M, c1b, c2b = curves.split_cubic(A, c1, c2, B, t)
            new = [[*c1a, CTRL], [*c2a, CTRL], [*M, CURVE if kind is None else kind],
                   [*c1b, CTRL], [*c2b, CTRL]]
            keep = [q for j, q in enumerate(pts) if j not in set(ctrl)]
            pos = keep.index(pts[a]) + 1
            pts[:] = keep[:pos] + new + keep[pos:]
            return pos + 2
        seg = curves.segments(pts, r["closed"])[i]
        ls = LineString(seg)
        q = ls.interpolate(t, normalized=True) if ls.length > 1e-9 else Point(seg[0])
        if kind is None:
            nb = (pts[a][2], pts[b][2])
            kind = CURVE if CURVE in nb else CORNER
        pts.insert(a + 1, [q.x, q.y, kind])
        return a + 1

    def _insert_edge(self, edge, kind=None):
        """Punkt auf einer Kante einfügen; bei Säulen-Satin auf beiden Schienen (als Steg)."""
        st = self._node_state()
        if not st:
            return None
        ri, i, t = edge["ri"], edge["i"], edge["t"]
        if st["obj"].kind == "satin":
            for rj in range(len(st["rings"])):
                idx = self._split_ring(st, rj, i, t, kind)
        else:
            idx = self._split_ring(st, ri, i, t, kind)
        self._node_sel = {(ri, idx)}
        self._apply_rings(st, keep_selection=True)
        return (ri, idx)

    def _insert_node(self, sp):
        edge = self._hit_edge(sp)
        if edge:
            self._insert_edge(edge)

    def insert_nodes(self):
        """Neue Punkte in der Mitte der Kanten: zwischen benachbarten ausgewählten Punkten,
        bei einzelnen ausgewählten Punkten jeweils nach dem Punkt."""
        st = self._node_state()
        if not st or not self._node_sel:
            return False
        satin = st["obj"].kind == "satin"
        todo = {}
        for ri, r in enumerate(st["rings"]):
            groups = curves.anchor_groups(r["pts"], r["closed"])
            na = len(groups)
            m = na if r["closed"] else na - 1
            seg_of = {a: k for k, (a, _) in enumerate(groups)}
            sel = {seg_of[i] for rj, i in self._node_sel if (rj == ri or satin) and i in seg_of}
            pairs = {k for k in range(m) if k in sel and (k + 1) % na in sel}
            if not pairs:
                pairs = {k for k in sel if k < m}
            todo[ri] = pairs
        if satin:                                  # beide Schienen gleich behandeln
            both = set().union(*todo.values())
            todo = {ri: both for ri in todo}
        if not any(todo.values()):
            return False
        new = set()
        for ri, segs in todo.items():
            made = []
            for k in sorted(segs, reverse=True):
                idx = self._split_ring(st, ri, k, 0.5)
                made.append(st["rings"][ri]["pts"][idx])
            pts = st["rings"][ri]["pts"]
            new |= {(ri, j) for j, q in enumerate(pts) if any(q is m_ for m_ in made)}
        self._node_sel = new
        self._apply_rings(st, keep_selection=True)
        return True

    def join_nodes(self):
        """Punkte verbinden. Liefert einen Hinweistext (oder None, wenn nichts ging).
        - beide Endpunkte einer offenen Linie gewählt: Linie schließen
        - benachbarte Punkte gewählt: zu einem Punkt in ihrer Mitte zusammenfassen"""
        st = self._node_state()
        if not st or len(self._node_sel) < 2:
            return None
        o = st["obj"]
        if o.kind == "satin":
            return "Bei Säulen-Satin lassen sich Punkte nicht verbinden – Punktepaare löschen geht mit Entf."
        if o.kind == "line":
            r = st["rings"][0]
            n = len(r["pts"])
            if not r["closed"] and self._node_sel == {(0, 0), (0, n - 1)}:
                if n < 3:
                    return "Eine Linie aus zwei Punkten lässt sich nicht schließen."
                a, b = r["pts"][0], r["pts"][-1]
                if math.hypot(a[0] - b[0], a[1] - b[1]) < 0.3:   # Enden liegen aufeinander
                    r["pts"].pop()
                r["closed"] = True
                self._node_sel = set()
                self._apply_rings(st)
                return "Linie geschlossen."
        merged = 0
        for ri, r in enumerate(st["rings"]):
            pts, n = r["pts"], len(r["pts"])
            sel = sorted(i for rj, i in self._node_sel if rj == ri)
            if len(sel) < 2:
                continue
            # zusammenhängende Läufe gewählter Punkte (bei geschlossenen Pfaden auch über den Start)
            runs, cur = [], [sel[0]]
            for i in sel[1:]:
                if i == cur[-1] + 1:
                    cur.append(i)
                else:
                    runs.append(cur)
                    cur = [i]
            runs.append(cur)
            if r["closed"] and len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == n - 1:
                runs[0] = runs.pop() + runs[0]
            runs = [run for run in runs if len(run) >= 2]
            minimum = 3 if r["closed"] else 2
            if not runs or n - sum(len(run) - 1 for run in runs) < minimum:
                continue
            drop = set()
            for run in runs:
                x = sum(pts[i][0] for i in run) / len(run)
                y = sum(pts[i][1] for i in run) / len(run)
                kind = CORNER if any(pts[i][2] == CORNER for i in run) else CURVE
                keep = run[0]
                pts[keep] = [x, y, kind]
                drop.update(run[1:])
                merged += len(run) - 1
            r["pts"] = [q for i, q in enumerate(pts) if i not in drop]
        if not merged:
            if o.kind == "line":
                return ("Zum Verbinden die beiden Endpunkte der Linie wählen (Linie schließen) "
                        "oder benachbarte Punkte (zusammenfassen).")
            return "Zum Verbinden benachbarte Punkte wählen – sie werden zu einem Punkt zusammengefasst."
        self._node_sel = set()
        self._apply_rings(st)
        return "Punkte zusammengefasst." if merged > 1 else "2 Punkte zu einem zusammengefasst."

    def selected_node_targets(self):
        """Gewählte Punkte als Ziele für »Mit Linie verbinden«: [{pt, obj, end}]."""
        st = self._node_state()
        if not st:
            return []
        o = st["obj"]
        out = []
        for ri, i in sorted(self._node_sel):
            r = st["rings"][ri]
            end = None
            if o.kind == "line" and not r["closed"]:
                end = "start" if i == 0 else "end" if i == len(r["pts"]) - 1 else None
            out.append({"pt": tuple(r["world"][i]), "obj": o.id, "end": end})
        return out

    def _open_end(self, sp):
        """Offene Linie: (ring, am_anfang) des Endes, das `sp` am nächsten liegt."""
        st = self._node_state()
        if not st or st["obj"].kind != "line" or st["rings"][0]["closed"]:
            return None
        w = st["rings"][0]["world"]
        if len(w) < 2:
            return None
        d0 = math.hypot(w[0][0] - sp.x(), w[0][1] - sp.y())
        d1 = math.hypot(w[-1][0] - sp.x(), w[-1][1] - sp.y())
        return (0, d0 < d1)

    def _append_node(self, sp):
        """Offene Linie am näheren Ende bis `sp` verlängern."""
        end = self._open_end(sp)
        if end is None:
            return None
        st = self._node_state()
        o = st["obj"]
        pts = st["rings"][0]["pts"]
        q = [*o.to_local(sp.x(), sp.y()), CORNER]
        if end[1]:
            pts.insert(0, q)
            idx = 0
        else:
            pts.append(q)
            idx = len(pts) - 1
        self._node_sel = {(0, idx)}
        self._apply_rings(st, keep_selection=True)
        return (0, idx)

    def _apply_rings(self, st, keep_selection=False):
        o = st["obj"]
        rings = st["rings"]
        if o.kind == "satin":
            if len(rings) != 2 or len(rings[0]["pts"]) != len(rings[1]["pts"]):
                return
            o.set_satin(rings[0]["pts"], rings[1]["pts"])
        elif o.kind == "line":
            if len(rings[0]["pts"]) < 2:
                return
            o.closed = bool(rings[0]["closed"]) and len(rings[0]["pts"]) >= 3
            o.set_line_nodes(rings[0]["pts"])
        else:
            keep = [r["pts"] for r in rings if len(r["pts"]) >= 3]
            if not keep or curves.rings_geometry(keep).is_empty:
                return
            o.set_curve(keep)
        sel = self._node_sel if keep_selection else set()
        sizes = [len(r["pts"]) for r in rings]
        self._nodes = None
        self.nodesEdited.emit(o)
        st2 = self._node_state()
        # Auswahl nur behalten, wenn sich die Punktstruktur nicht verändert hat
        if st2 and keep_selection and [len(r["pts"]) for r in st2["rings"]] == sizes:
            self._node_sel = sel
        self.viewport().update()

    # ================================================== Mit Linie verbinden
    def _snap_points(self):
        """Alle Punkte sichtbarer Formen/Linien (Weltkoordinaten), auf denen eingerastet wird."""
        if self._snap_cache is None:
            pts = []
            for it in self.scene().items():
                if not isinstance(it, ObjectItem) or not it.isVisible():
                    continue
                o = it.obj
                try:
                    if o.kind == "line":
                        nodes = o.line_nodes()
                        last = len(nodes) - 1
                        for i, q in enumerate(nodes):
                            end = None
                            if not o.closed:
                                end = "start" if i == 0 else "end" if i == last else None
                            pts.append((*o.to_world(q[0], q[1]), o.id, end))
                    elif o.kind in ("shape", "satin"):
                        rings = o.curve or curves.polygon_rings(o.raw_geometry())
                        for r in rings:
                            if len(r) > 400:          # sehr feine Konturen: nur jeden n-ten Punkt
                                r = r[::len(r) // 200]
                            pts.extend((*o.to_world(q[0], q[1]), o.id, None) for q in r)
                except Exception:
                    continue
            self._snap_cache = pts
        return self._snap_cache

    def _connect_target(self, sp, mods=Qt.NoModifier):
        """Eingerasteter Punkt (oder freie Position) für das Verbinden-Werkzeug."""
        tol = 9 / self.zoom()
        best, bd = None, tol
        for x, y, oid, end in self._snap_points():
            d = math.hypot(x - sp.x(), y - sp.y())
            if d < bd:
                best, bd = {"pt": (x, y), "obj": oid, "end": end}, d
        if best:
            return best
        x, y = sp.x(), sp.y()
        if self._conn_a and mods & Qt.ShiftModifier:      # Umschalt: Winkel in 15°-Schritten
            ax, ay = self._conn_a["pt"]
            ang = round(math.atan2(y - ay, x - ax) / math.radians(15)) * math.radians(15)
            ln = math.hypot(x - ax, y - ay)
            x, y = ax + ln * math.cos(ang), ay + ln * math.sin(ang)
        return {"pt": (x, y), "obj": None, "end": None}

    def _connect_press(self, ev, sp):
        if ev.button() == Qt.RightButton:
            self._conn_a = None
            self.preview.setPath(QPainterPath())
            self.viewport().update()
            return
        if ev.button() != Qt.LeftButton:
            return
        t = self._connect_target(sp, ev.modifiers())
        if self._conn_a is None:
            self._conn_a = t
        else:
            a = self._conn_a
            if math.hypot(a["pt"][0] - t["pt"][0], a["pt"][1] - t["pt"][1]) > 0.2:
                self._conn_a = None
                self.preview.setPath(QPainterPath())
                self.objectCreated.emit("connect", {"a": a, "b": t})
                self._snap_cache = None
        self.viewport().update()

    def _connect_move(self, ev, sp):
        t = self._connect_target(sp, ev.modifiers())
        self._conn_hover = t if t["obj"] else None
        if self._conn_a:
            path = QPainterPath(QPointF(*self._conn_a["pt"]))
            path.lineTo(QPointF(*t["pt"]))
            self.preview.setPath(path)
        self.viewport().update()

    def _draw_connect(self, p):
        z = self.zoom()
        p.setRenderHint(QPainter.Antialiasing)
        # alle Einrastpunkte dezent anzeigen (Linienenden etwas kräftiger)
        pts = self._snap_points()
        if len(pts) <= 4000:
            dot = QPen(ACCENT, 1.2)
            dot.setCosmetic(True)
            p.setPen(dot)
            for x, y, _, end in pts:
                p.setBrush(ACCENT if end else QColor(255, 255, 255, 230))
                r = 3.0 / z
                p.drawEllipse(QPointF(x, y), r, r)
        pen = QPen(ACCENT, 1.6)
        pen.setCosmetic(True)
        p.setPen(pen)
        if self._conn_a:
            p.setBrush(ACCENT)
            x, y = self._conn_a["pt"]
            p.drawEllipse(QPointF(x, y), 4 / z, 4 / z)
        if self._conn_hover:
            p.setBrush(QColor(255, 255, 255, 200))
            x, y = self._conn_hover["pt"]
            p.drawEllipse(QPointF(x, y), 7 / z, 7 / z)
            p.drawEllipse(QPointF(x, y), 2 / z, 2 / z)

    # ======================================================= Sprung-Editor
    def hit_jump(self, x, y):
        tol = 7 / self.zoom()
        best, bd = None, tol
        here = Point(x, y)
        for r in self.jump_records:
            d = LineString([r["a"], r["b"]]).distance(here) if r["length"] > 1e-6 else \
                math.hypot(x - r["a"][0], y - r["a"][1])
            if d < bd:
                best, bd = r["index"], d
        return best

    def _draw_jumps(self, p):
        z = self.zoom()
        p.setRenderHint(QPainter.Antialiasing)
        for r in self.jump_records:
            hot = r["index"] == self._jump_hover
            col = QColor("#E53935") if r["trim"] else QColor("#FB8C00")
            pen = QPen(col, 3.2 if hot else 1.6, Qt.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            a, b = QPointF(*r["a"]), QPointF(*r["b"])
            p.drawLine(a, b)
            s = (5 if hot else 3.5) / z
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawEllipse(b, s * 0.7, s * 0.7)
            if r["trim"]:
                p.drawEllipse(a, s * 1.4, s * 1.4)
                xp = QPen(QColor("white"), 1.4)
                xp.setCosmetic(True)
                p.setPen(xp)
                k = s * 0.7
                p.drawLine(QPointF(a.x() - k, a.y() - k), QPointF(a.x() + k, a.y() + k))
                p.drawLine(QPointF(a.x() - k, a.y() + k), QPointF(a.x() + k, a.y() - k))
            else:
                p.drawEllipse(a, s, s)
