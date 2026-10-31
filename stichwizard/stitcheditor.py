"""Stich-Editor: einzelne Stiche einer Stickdatei (Objektart »stitches«) bearbeiten – wählen
(Klick, Umschalt+Klick, Rahmen ziehen), verschieben (ziehen, Pfeiltasten), löschen, einfügen,
Stichart ändern (Stich/Sprung/Schnitt/Stopp), Farbwechsel setzen, Blockfarbe ändern, kurze
Stiche entfernen und lange teilen. Stich für Stich durch das Design blättern."""
import copy
import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget)

from . import icons
from .engine import JUMP, STITCH, STOP, TRIM

FLAGS = [("Stich", STITCH), ("Sprung", JUMP), ("Fadenschnitt", TRIM), ("Stopp", STOP)]


class StitchView(QWidget):
    changed = Signal()          # Stiche verändert (nach dem Ziehen)
    selected = Signal()

    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.scale = 6.0
        self.off = QPointF(0, 0)
        self.setMinimumSize(600, 500)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self._drag = self._band = self._pan = None

    # ---------------------------------------------------------- Umrechnung
    def to_screen(self, x, y):
        return QPointF(x * self.scale + self.off.x(), y * self.scale + self.off.y())

    def to_mm(self, p):
        return ((p.x() - self.off.x()) / self.scale, (p.y() - self.off.y()) / self.scale)

    def fit(self):
        pts = self.ed.points()
        if not len(pts):
            return
        x0, y0 = pts[:, 0].min(), pts[:, 1].min()
        x1, y1 = pts[:, 0].max(), pts[:, 1].max()
        w, h = max(1.0, x1 - x0), max(1.0, y1 - y0)
        self.scale = max(0.5, min((self.width() - 40) / w, (self.height() - 40) / h))
        self.off = QPointF(self.width() / 2 - (x0 + x1) / 2 * self.scale,
                           self.height() / 2 - (y0 + y1) / 2 * self.scale)
        self.update()

    def center_on(self, x, y):
        s = self.to_screen(x, y)
        if not self.rect().adjusted(30, 30, -30, -30).contains(s.toPoint()):
            self.off = QPointF(self.width() / 2 - x * self.scale, self.height() / 2 - y * self.scale)
            self.update()

    # ------------------------------------------------------------- Zeichnen
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        p.setRenderHint(QPainter.Antialiasing)
        ed = self.ed
        cur = ed.current
        dots = self.scale >= 5
        jpen = QPen(QColor(120, 120, 120, 170), 1, Qt.DashLine)
        for bi, b in enumerate(ed.blocks):
            pen = QPen(QColor(b["color"]), max(1.0, min(3.0, self.scale * 0.35)), Qt.SolidLine,
                       Qt.RoundCap)
            st = b["stitches"]
            for i in range(1, len(st)):
                a, c = st[i - 1], st[i]
                p.setPen(pen if c[2] == STITCH else jpen)
                p.drawLine(self.to_screen(a[0], a[1]), self.to_screen(c[0], c[1]))
            if dots:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, 110))
                for x, y, f in st:
                    p.drawEllipse(self.to_screen(x, y), 1.6, 1.6)
        p.setPen(QPen(QColor("#FFFFFF"), 1.2))
        p.setBrush(QColor("#00897B"))
        for bi, si in ed.sel:
            x, y, f = ed.blocks[bi]["stitches"][si]
            p.drawEllipse(self.to_screen(x, y), 4, 4)
        if cur is not None:
            x, y, f = ed.blocks[cur[0]]["stitches"][cur[1]]
            p.setPen(QPen(QColor("#E53935"), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(self.to_screen(x, y), 7, 7)
        if self._band:
            p.setPen(QPen(QColor("#00897B"), 1, Qt.DashLine))
            p.setBrush(QColor(0, 137, 123, 30))
            p.drawRect(QRectF(*self._band).normalized())
        p.end()

    # ---------------------------------------------------------------- Maus
    def wheelEvent(self, ev):
        f = 1.2 if ev.angleDelta().y() > 0 else 1 / 1.2
        pos = ev.position()
        mx, my = self.to_mm(pos)
        self.scale = max(0.3, min(200.0, self.scale * f))
        self.off = QPointF(pos.x() - mx * self.scale, pos.y() - my * self.scale)
        self.update()

    def _hit(self, pos, radius=7):
        pts = self.ed.points()
        if not len(pts):
            return None
        x, y = self.to_mm(pos)
        d = np.hypot(pts[:, 0] - x, pts[:, 1] - y)
        i = int(np.argmin(d))
        return self.ed.index[i] if d[i] * self.scale <= radius else None

    def mousePressEvent(self, ev):
        pos = ev.position()
        if ev.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan = (pos, QPointF(self.off))
            return
        hit = self._hit(pos)
        shift = bool(ev.modifiers() & Qt.ShiftModifier)
        if hit is not None:
            if shift:
                self.ed.sel ^= {hit}
            elif hit not in self.ed.sel:
                self.ed.sel = {hit}
            self.ed.set_current(hit, select=False)
            self.ed.snapshot()
            self._drag = (self.to_mm(pos), False)
        else:
            if not shift:
                self.ed.sel = set()
            self._band = [pos.x(), pos.y(), 0.0, 0.0]
        self.selected.emit()
        self.update()

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        if self._pan:
            start, off = self._pan
            self.off = off + (pos - start)
            self.update()
        elif self._drag:
            (x0, y0), _ = self._drag
            x, y = self.to_mm(pos)
            self.ed.move_selection(x - x0, y - y0)
            self._drag = ((x, y), True)
            self.update()
        elif self._band:
            self._band[2] = pos.x() - self._band[0]
            self._band[3] = pos.y() - self._band[1]
            self.update()

    def mouseReleaseEvent(self, ev):
        if self._pan:
            self._pan = None
            return
        if self._drag:
            moved = self._drag[1]
            self._drag = None
            if moved:
                self.changed.emit()
            else:
                self.ed.history.pop()          # nur geklickt: kein Rückgängig-Schritt
        if self._band:
            r = QRectF(*self._band).normalized()
            if r.width() > 3 or r.height() > 3:
                (ax, ay), (bx, by) = self.to_mm(r.topLeft()), self.to_mm(r.bottomRight())
                pts = self.ed.points()
                inside = np.nonzero((pts[:, 0] >= ax) & (pts[:, 0] <= bx) &
                                    (pts[:, 1] >= ay) & (pts[:, 1] <= by))[0]
                self.ed.sel |= {self.ed.index[i] for i in inside}
            self._band = None
            self.selected.emit()
        self.update()


class StitchEditor(QDialog):
    """blocks: [{"color", "stitches": [[x, y, flag], …]}] (Objektkoordinaten) – wird kopiert."""

    def __init__(self, parent=None, blocks=None):
        super().__init__(parent)
        self.setWindowTitle("Stich-Editor")
        self.setWindowIcon(icons.icon("stitchedit"))
        self.resize(1300, 840)
        self.blocks = [{"color": b["color"], "stitches": [list(s) for s in b["stitches"]]}
                       for b in (blocks or [])]
        self.sel = set()
        self.current = None
        self.history, self.future = [], []
        self._pts = None
        root = QHBoxLayout(self)
        self.view = StitchView(self)
        root.addWidget(self.view, 1)
        side = QVBoxLayout()
        t = QLabel("Stich für Stich")
        t.setObjectName("cardTitle")
        side.addWidget(t)
        nav = QHBoxLayout()
        self.prev = QPushButton("◀")
        self.next = QPushButton("▶")
        self.slider = QSlider(Qt.Horizontal)
        for b in (self.prev, self.next):
            b.setFixedWidth(36)
        nav.addWidget(self.prev)
        nav.addWidget(self.slider, 1)
        nav.addWidget(self.next)
        side.addLayout(nav)
        self.pos_lbl = QLabel()
        self.pos_lbl.setObjectName("muted")
        self.pos_lbl.setWordWrap(True)
        side.addWidget(self.pos_lbl)
        form = QFormLayout()
        self.x = QDoubleSpinBox()
        self.y = QDoubleSpinBox()
        for sp in (self.x, self.y):
            sp.setRange(-2000, 2000)
            sp.setDecimals(2)
            sp.setSingleStep(0.1)
            sp.setSuffix(" mm")
            sp.setKeyboardTracking(False)
        self.flag = QComboBox()
        for label, f in FLAGS:
            self.flag.addItem(label, f)
        from .widgets import ColorButton
        self.block_color = ColorButton("#000000")
        form.addRow("X", self.x)
        form.addRow("Y", self.y)
        form.addRow("Art", self.flag)
        form.addRow("Blockfarbe", self.block_color)
        side.addLayout(form)
        row = QHBoxLayout()
        self.b_del = QPushButton("Löschen (Entf)")
        self.b_ins = QPushButton("Einfügen (Einfg)")
        row.addWidget(self.b_del)
        row.addWidget(self.b_ins)
        side.addLayout(row)
        self.b_split = QPushButton("Farbwechsel ab hier")
        self.b_split.setToolTip("Ab dem aktuellen Stich beginnt ein neuer Farbblock")
        side.addWidget(self.b_split)
        t2 = QLabel("Aufräumen")
        t2.setObjectName("cardTitle")
        side.addWidget(t2)
        f2 = QFormLayout()
        self.short = QDoubleSpinBox()
        self.short.setRange(0.1, 2.0)
        self.short.setSingleStep(0.1)
        self.short.setValue(0.4)
        self.short.setSuffix(" mm")
        self.long = QDoubleSpinBox()
        self.long.setRange(3.0, 12.0)
        self.long.setSingleStep(0.5)
        self.long.setValue(7.0)
        self.long.setSuffix(" mm")
        self.b_short = QPushButton("Entfernen")
        self.b_short.setToolTip("Stiche kürzer als dieser Wert mit dem nächsten zusammenfassen")
        self.b_long = QPushButton("Teilen")
        self.b_long.setToolTip("Stiche länger als dieser Wert in gleich lange Stiche teilen")
        r1 = QHBoxLayout()
        r1.addWidget(self.short)
        r1.addWidget(self.b_short)
        r2 = QHBoxLayout()
        r2.addWidget(self.long)
        r2.addWidget(self.b_long)
        f2.addRow("Kürzer als", r1)
        f2.addRow("Länger als", r2)
        side.addLayout(f2)
        side.addStretch()
        self.info = QLabel()
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        side.addWidget(self.info)
        hint = QLabel("Klick wählt · Umschalt+Klick / Rahmen ziehen: mehrere · Ziehen verschiebt · "
                      "Pfeiltasten: 0,1 mm (Umschalt 1 mm) · Rechte Maustaste: verschieben · "
                      "Mausrad: zoomen")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        side.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        side.addWidget(bb)
        sw = QWidget()
        sw.setLayout(side)
        sw.setFixedWidth(330)
        root.addWidget(sw)
        # Verbindungen
        self.prev.clicked.connect(lambda: self.step(-1))
        self.next.clicked.connect(lambda: self.step(1))
        self.slider.valueChanged.connect(lambda v: self.set_current(self.index[v])
                                         if 0 <= v < len(self.index) else None)
        self.x.valueChanged.connect(self._xy_edited)
        self.y.valueChanged.connect(self._xy_edited)
        self.flag.currentIndexChanged.connect(self._flag_edited)
        self.block_color.colorChanged.connect(self._color_edited)
        self.b_del.clicked.connect(self.delete_selected)
        self.b_ins.clicked.connect(self.insert_after)
        self.b_split.clicked.connect(self.split_here)
        self.b_short.clicked.connect(lambda: self.remove_short(self.short.value()))
        self.b_long.clicked.connect(lambda: self.split_long(self.long.value()))
        self.view.changed.connect(self.refresh)
        self.view.selected.connect(self.refresh)
        for key, fn in ((QKeySequence.Undo, self.undo), (QKeySequence.Redo, self.redo),
                        (QKeySequence.Delete, self.delete_selected),
                        (QKeySequence(Qt.Key_Insert), self.insert_after),
                        (QKeySequence.SelectAll, self.select_all)):
            QShortcut(key, self, fn)
        for key, dx, dy in ((Qt.Key_Left, -1, 0), (Qt.Key_Right, 1, 0), (Qt.Key_Up, 0, -1),
                            (Qt.Key_Down, 0, 1)):
            QShortcut(QKeySequence(key), self, lambda a=dx, b=dy: self.nudge(a * 0.1, b * 0.1))
            QShortcut(QKeySequence(Qt.SHIFT | key), self, lambda a=dx, b=dy: self.nudge(a, b))
        self._rebuild_index()
        if self.index:
            self.set_current(self.index[0])
        self.refresh()

    # ------------------------------------------------------------- Daten
    def _rebuild_index(self):
        self.index = [(bi, si) for bi, b in enumerate(self.blocks) for si in range(len(b["stitches"]))]
        self._pts = None
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, len(self.index) - 1))
        self.slider.blockSignals(False)
        self.sel = {k for k in self.sel if k[0] < len(self.blocks) and
                    k[1] < len(self.blocks[k[0]]["stitches"])}
        if self.current is not None and self.current not in set(self.index):
            self.current = self.index[min(len(self.index) - 1, self.flat(self.current))] \
                if self.index else None

    def points(self):
        if self._pts is None:
            self._pts = np.array([s[:2] for b in self.blocks for s in b["stitches"]] or
                                 np.zeros((0, 2)), float).reshape(-1, 2)
        return self._pts

    def flat(self, key):
        bi, si = key
        return sum(len(b["stitches"]) for b in self.blocks[:bi]) + si

    def stitch(self, key):
        return self.blocks[key[0]]["stitches"][key[1]]

    def snapshot(self):
        self.history.append(copy.deepcopy(self.blocks))
        self.history = self.history[-100:]
        self.future.clear()

    def undo(self):
        if self.history:
            self.future.append(copy.deepcopy(self.blocks))
            self.blocks = self.history.pop()
            self._rebuild_index()
            self.refresh()

    def redo(self):
        if self.future:
            self.history.append(copy.deepcopy(self.blocks))
            self.blocks = self.future.pop()
            self._rebuild_index()
            self.refresh()

    # --------------------------------------------------------- Bearbeiten
    def set_current(self, key, select=True):
        self.current = key
        if select:
            self.sel = {key}
        x, y, _ = self.stitch(key)
        self.view.center_on(x, y)
        self.refresh()

    def step(self, d):
        if not self.index:
            return
        i = self.flat(self.current) if self.current else 0
        self.set_current(self.index[max(0, min(len(self.index) - 1, i + d))])

    def select_all(self):
        self.sel = set(self.index)
        self.refresh()

    def move_selection(self, dx, dy):
        for k in self.sel:
            s = self.stitch(k)
            s[0] += dx
            s[1] += dy
        self._pts = None

    def nudge(self, dx, dy):
        if self.sel:
            self.snapshot()
            self.move_selection(dx, dy)
            self.refresh()

    def _xy_edited(self):
        if self._loading or self.current is None:
            return
        s = self.stitch(self.current)
        if abs(s[0] - self.x.value()) > 1e-6 or abs(s[1] - self.y.value()) > 1e-6:
            self.snapshot()
            s[0], s[1] = self.x.value(), self.y.value()
            self._pts = None
            self.refresh()

    def _flag_edited(self):
        if self._loading or self.current is None:
            return
        f = self.flag.currentData()
        targets = self.sel or {self.current}
        if any(self.stitch(k)[2] != f for k in targets):
            self.snapshot()
            for k in targets:
                self.stitch(k)[2] = f
            self.refresh()

    def _color_edited(self, col):
        if self._loading or self.current is None:
            return
        b = self.blocks[self.current[0]]
        if b["color"].upper() != col.upper():
            self.snapshot()
            b["color"] = col
            self.refresh()

    def delete_selected(self):
        targets = self.sel or ({self.current} if self.current else set())
        if not targets:
            return
        self.snapshot()
        first = min(self.flat(k) for k in targets)
        for bi in sorted({k[0] for k in targets}, reverse=True):
            drop = {k[1] for k in targets if k[0] == bi}
            self.blocks[bi]["stitches"] = [s for i, s in enumerate(self.blocks[bi]["stitches"])
                                           if i not in drop]
        self.blocks = [b for b in self.blocks if b["stitches"]]
        self.sel = set()
        self.current = None
        self._rebuild_index()
        if self.index:
            self.set_current(self.index[min(first, len(self.index) - 1)])
        self.refresh()

    def insert_after(self):
        if self.current is None:
            return
        self.snapshot()
        bi, si = self.current
        st = self.blocks[bi]["stitches"]
        a = st[si]
        b = st[si + 1] if si + 1 < len(st) else [a[0] + 1.0, a[1], STITCH]
        st.insert(si + 1, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, STITCH])
        self._rebuild_index()
        self.set_current((bi, si + 1))

    def split_here(self):
        """Ab dem aktuellen Stich ein neuer Farbblock (Maschine wechselt hier die Farbe)."""
        if self.current is None or self.current[1] == 0:
            return
        self.snapshot()
        bi, si = self.current
        b = self.blocks[bi]
        rest = b["stitches"][si:]
        b["stitches"] = b["stitches"][:si]
        col = QColor(b["color"])
        new = col.lighter(150) if col.lightness() < 128 else col.darker(150)
        self.blocks.insert(bi + 1, {"color": new.name().upper(), "stitches": rest})
        self._rebuild_index()
        self.set_current((bi + 1, 0))

    def remove_short(self, limit):
        """Stiche kürzer als limit mit dem folgenden zusammenfassen (Sprünge bleiben)."""
        self.snapshot()
        n = 0
        for b in self.blocks:
            out = []
            for s in b["stitches"]:
                if out and s[2] == STITCH and out[-1][2] == STITCH and \
                        math.dist(out[-1][:2], s[:2]) < limit and len(out) > 1:
                    out[-1] = list(s)
                    n += 1
                else:
                    out.append(list(s))
            b["stitches"] = out
        self._rebuild_index()
        self.refresh()
        return n

    def split_long(self, limit):
        """Stiche länger als limit in gleich lange Teilstiche teilen."""
        self.snapshot()
        n = 0
        for b in self.blocks:
            out = []
            for s in b["stitches"]:
                if out and s[2] == STITCH:
                    a = out[-1]
                    d = math.dist(a[:2], s[:2])
                    k = math.ceil(d / limit)
                    for j in range(1, k):
                        out.append([a[0] + (s[0] - a[0]) * j / k, a[1] + (s[1] - a[1]) * j / k,
                                    STITCH])
                        n += 1
                out.append(list(s))
            b["stitches"] = out
        self._rebuild_index()
        self.refresh()
        return n

    # --------------------------------------------------------------- Anzeige
    _loading = False

    def refresh(self):
        self._loading = True
        if self.current is not None and self.index:
            i = self.flat(self.current)
            self.slider.blockSignals(True)
            self.slider.setValue(i)
            self.slider.blockSignals(False)
            x, y, f = self.stitch(self.current)
            self.x.setValue(x)
            self.y.setValue(y)
            self.flag.setCurrentIndex(max(0, self.flag.findData(f)))
            self.block_color.set_color(self.blocks[self.current[0]]["color"])
            prev = self.stitch(self.index[i - 1]) if i else None
            ln = f" · Stichlänge {math.dist(prev[:2], (x, y)):.2f} mm" if prev else ""
            self.pos_lbl.setText(f"Stich {i + 1} von {len(self.index)} · Farbblock "
                                 f"{self.current[0] + 1} von {len(self.blocks)}{ln}"
                                 + (f" · {len(self.sel)} gewählt" if len(self.sel) > 1 else ""))
        lens = [math.dist(a[:2], b[:2]) for bl in self.blocks
                for a, b in zip(bl["stitches"], bl["stitches"][1:]) if b[2] == STITCH]
        jumps = sum(1 for bl in self.blocks for s in bl["stitches"] if s[2] == JUMP)
        self.info.setText(f"{len(self.index)} Punkte · {len(self.blocks)} Farbblöcke · "
                          f"{jumps} Sprünge · längster Stich {max(lens or [0]):.1f} mm · "
                          f"{sum(1 for v in lens if v < 0.4)} Stiche unter 0,4 mm")
        self._loading = False
        self._pts = None
        self.view.update()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.view.fit()
