"""Mal-Atelier: ein kleines Malprogramm (Pinsel, Radierer, Linie, Rechteck, Ellipse, Füllen,
Pipette, Text, Bild laden, Rückgängig). Das Ergebnis wird als Druck-Applikation eingefügt,
als Vorlage zum Nachzeichnen benutzt oder vom Bild-Assistenten gestickt."""
import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QKeySequence, QPainter, QPen,
                           QShortcut)
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGridLayout, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPushButton, QScrollArea, QSlider, QToolButton, QVBoxLayout,
                               QWidget)

from . import icons
from .printapp import OUTLINES, flood_mask

PPM = 8.0            # Bildpunkte je Millimeter (≈ 200 dpi)
TOOLS = [("brush", "Pinsel", "✎"), ("erase", "Radierer", "⌫"), ("line", "Linie", "╱"),
         ("rect", "Rechteck", "▭"), ("ellipse", "Ellipse", "◯"), ("fill", "Füllen", "◧"),
         ("pick", "Farbe aufnehmen", "⌖"), ("text", "Text", "T")]
USES = [("Als Druck-Applikation einfügen", "print"), ("Als Vorlage zum Nachzeichnen", "template"),
        ("Mit dem Bild-Assistenten sticken", "digitize")]
PALETTE = ["#000000", "#FFFFFF", "#E53935", "#FB8C00", "#FDD835", "#43A047", "#1E88E5",
           "#8E24AA", "#6D4C41", "#F48FB1", "#80DEEA", "#9E9E9E"]


def _swatch_style(c):
    return f"background:{c}; border:1px solid #00000055; border-radius:4px;"


class Canvas(QWidget):
    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self.zoom = 1.0
        self.setMouseTracking(True)
        self._start = self._last = self._now = None

    def sizeHint(self):
        img = self.dlg.img
        return QSize(int(img.width() * self.zoom) + 1, int(img.height() * self.zoom) + 1)

    def relayout(self):
        self.setFixedSize(self.sizeHint())
        self.update()

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
            self.zoom = max(0.2, min(6.0, self.zoom * f))
            self.relayout()
            ev.accept()
        else:
            super().wheelEvent(ev)

    def _img_pos(self, pos):
        return QPointF(pos.x() / self.zoom, pos.y() / self.zoom)

    def paintEvent(self, _ev):
        p = QPainter(self)
        # Schachbrett = durchsichtig
        s = 10
        for y in range(0, self.height(), s):
            for x in range(0, self.width(), s):
                p.fillRect(x, y, s, s, QColor("#FFFFFF" if (x // s + y // s) % 2 else "#E6E6E6"))
        p.scale(self.zoom, self.zoom)
        p.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1)
        p.drawImage(0, 0, self.dlg.img)
        if self._start is not None and self.dlg.tool in ("line", "rect", "ellipse"):
            self.dlg.draw_shape(p, self._start, self._now)
        p.end()

    def mousePressEvent(self, ev):
        pos = self._img_pos(ev.position())
        tool = self.dlg.tool
        if tool == "pick":
            x, y = int(pos.x()), int(pos.y())
            if 0 <= x < self.dlg.img.width() and 0 <= y < self.dlg.img.height():
                self.dlg.set_color(self.dlg.img.pixelColor(x, y).name().upper())
            return
        self.dlg.snapshot()
        if tool == "fill":
            self.dlg.fill(int(pos.x()), int(pos.y()))
            self.update()
            return
        if tool == "text":
            self.dlg.place_text(pos)
            self.update()
            return
        self._start = self._last = self._now = pos
        if tool in ("brush", "erase"):
            self.dlg.stroke(pos, pos)
        self.update()

    def mouseMoveEvent(self, ev):
        if self._start is None:
            return
        pos = self._img_pos(ev.position())
        if self.dlg.tool in ("brush", "erase"):
            self.dlg.stroke(self._last, pos)
            self._last = pos
        self._now = pos
        self.update()

    def mouseReleaseEvent(self, ev):
        if self._start is None:
            return
        pos = self._img_pos(ev.position())
        if self.dlg.tool in ("line", "rect", "ellipse"):
            p = QPainter(self.dlg.img)
            self.dlg.draw_shape(p, self._start, pos)
            p.end()
        self._start = self._last = self._now = None
        self.update()


class PaintDialog(QDialog):
    """image: vorhandenes Bild (QImage) oder None; size_mm: (breite, höhe)."""

    def __init__(self, parent=None, image=None, size_mm=(100.0, 100.0), edit=False):
        super().__init__(parent)
        self.setWindowTitle("Mal-Atelier")
        self.setWindowIcon(icons.icon("paint"))
        self.resize(1260, 820)
        self.w_mm, self.h_mm = size_mm
        self.img = self._blank(self.w_mm, self.h_mm, white=True)
        if image is not None and not image.isNull():
            p = QPainter(self.img)
            p.drawImage(QRectF(0, 0, self.img.width(), self.img.height()), image)
            p.end()
        self.tool = "brush"
        self.color = "#E53935"
        self.history, self.future = [], []
        self.edit = edit
        self.use = "print"

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        t = QLabel("Werkzeug")
        t.setObjectName("cardTitle")
        left.addWidget(t)
        grid = QGridLayout()
        self.tool_group = QButtonGroup(self)
        for i, (key, tip, sym) in enumerate(TOOLS):
            b = QToolButton()
            b.setText(sym)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(46, 40)
            b.setStyleSheet("font-size: 17px;")
            b.setChecked(key == "brush")
            b.clicked.connect(lambda _c=False, k=key: self.set_tool(k))
            self.tool_group.addButton(b)
            grid.addWidget(b, i // 4, i % 4)
        left.addLayout(grid)
        form = QFormLayout()
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(1, 120)
        self.size.setValue(16)
        self.size_lbl = QLabel()
        self.size.valueChanged.connect(lambda v: self.size_lbl.setText(f"{v / 4:.1f} mm"))
        self.size.valueChanged.emit(self.size.value())
        row = QHBoxLayout()
        row.addWidget(self.size)
        row.addWidget(self.size_lbl)
        form.addRow("Stärke", row)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(5, 100)
        self.opacity.setValue(100)
        form.addRow("Deckkraft", self.opacity)
        self.filled = QCheckBox("Formen gefüllt")
        form.addRow(self.filled)
        left.addLayout(form)
        c = QLabel("Farbe")
        c.setObjectName("cardTitle")
        left.addWidget(c)
        pal = QGridLayout()
        for i, col in enumerate(PALETTE):
            b = QPushButton()
            b.setFixedSize(28, 24)
            b.setStyleSheet(_swatch_style(col))
            b.setToolTip(col)
            b.clicked.connect(lambda _c=False, k=col: self.set_color(k))
            pal.addWidget(b, i // 6, i % 6)
        left.addLayout(pal)
        self.color_btn = QPushButton("Eigene Farbe …")
        self.color_btn.clicked.connect(self.choose_color)
        left.addWidget(self.color_btn)
        s = QLabel("Bild")
        s.setObjectName("cardTitle")
        left.addWidget(s)
        sz = QFormLayout()
        self.w_spin = QDoubleSpinBox()
        self.h_spin = QDoubleSpinBox()
        for sp, v in ((self.w_spin, self.w_mm), (self.h_spin, self.h_mm)):
            sp.setRange(20, 300)
            sp.setSuffix(" mm")
            sp.setDecimals(0)
            sp.setValue(v)
        sz.addRow("Breite", self.w_spin)
        sz.addRow("Höhe", self.h_spin)
        left.addLayout(sz)
        row = QHBoxLayout()
        res = QPushButton("Größe ändern")
        res.setToolTip("Bild auf die neue Größe skalieren")
        res.clicked.connect(self.resize_image)
        load = QPushButton("Bild laden …")
        load.clicked.connect(self.load_image)
        row.addWidget(res)
        row.addWidget(load)
        left.addLayout(row)
        row = QHBoxLayout()
        clear_w = QPushButton("Weiß leeren")
        clear_w.clicked.connect(lambda: self.clear(True))
        clear_t = QPushButton("Durchsichtig leeren")
        clear_t.clicked.connect(lambda: self.clear(False))
        row.addWidget(clear_w)
        row.addWidget(clear_t)
        left.addLayout(row)
        u = QLabel("Verwenden")
        u.setObjectName("cardTitle")
        left.addWidget(u)
        self.use_combo = QComboBox()
        for label, key in USES:
            self.use_combo.addItem(label, key)
        if edit:
            self.use_combo.setEnabled(False)
        left.addWidget(self.use_combo)
        app = QFormLayout()
        self.outline = QComboBox()
        for label, key in OUTLINES:
            self.outline.addItem(label, key)
        self.edge = QPushButton()
        self.edge_color = "#3E2723"
        self.edge.setStyleSheet(_swatch_style(self.edge_color))
        self.edge.setFixedHeight(24)
        self.edge.clicked.connect(self.choose_edge)
        self.satin = QDoubleSpinBox()
        self.satin.setRange(1.5, 6.0)
        self.satin.setSingleStep(0.5)
        self.satin.setSuffix(" mm")
        self.satin.setValue(3.0)
        app.addRow("Umriss", self.outline)
        app.addRow("Satinrand", self.satin)
        app.addRow("Randfarbe", self.edge)
        self.app_box = QWidget()
        self.app_box.setLayout(app)
        left.addWidget(self.app_box)
        self.use_combo.currentIndexChanged.connect(
            lambda: self.app_box.setVisible(self.use_combo.currentData() == "print"))
        left.addStretch()
        hint = QLabel("Strg+Mausrad: zoomen · Strg+Z / Strg+Y")
        hint.setObjectName("muted")
        left.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        left.addWidget(bb)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(300)
        root.addWidget(lw)
        self.canvas = Canvas(self)
        sa = QScrollArea()
        sa.setWidget(self.canvas)
        sa.setAlignment(Qt.AlignCenter)
        root.addWidget(sa, 1)
        self.canvas.zoom = min(1.0, 760 / max(self.img.width(), self.img.height()))
        self.canvas.relayout()
        QShortcut(QKeySequence.Undo, self, self.undo)
        QShortcut(QKeySequence.Redo, self, self.redo)
        self.set_color(self.color)

    # ------------------------------------------------------------- Bild
    @staticmethod
    def _blank(w_mm, h_mm, white=True):
        img = QImage(max(1, int(w_mm * PPM)), max(1, int(h_mm * PPM)), QImage.Format_ARGB32)
        img.fill(QColor("#FFFFFF") if white else Qt.transparent)
        return img

    def snapshot(self):
        self.history.append((self.img.copy(), self.w_mm, self.h_mm))
        self.history = self.history[-30:]
        self.future.clear()

    def _restore(self, state):
        self.img, self.w_mm, self.h_mm = state[0].copy(), state[1], state[2]
        self.w_spin.setValue(self.w_mm)
        self.h_spin.setValue(self.h_mm)
        self.canvas.relayout()

    def undo(self):
        if self.history:
            self.future.append((self.img.copy(), self.w_mm, self.h_mm))
            self._restore(self.history.pop())

    def redo(self):
        if self.future:
            self.history.append((self.img.copy(), self.w_mm, self.h_mm))
            self._restore(self.future.pop())

    def clear(self, white):
        self.snapshot()
        self.img.fill(QColor("#FFFFFF") if white else Qt.transparent)
        self.canvas.update()

    def resize_image(self):
        self.snapshot()
        self.w_mm, self.h_mm = self.w_spin.value(), self.h_spin.value()
        self.img = self.img.scaled(int(self.w_mm * PPM), int(self.h_mm * PPM),
                                   Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.canvas.relayout()

    def load_image(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Bild laden", "",
                                                  "Bilder (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, "Mal-Atelier", "Das Bild ließ sich nicht öffnen.")
            return
        self.snapshot()
        # Seitenverhältnis des Bilds übernehmen, Breite bleibt
        self.h_mm = round(self.w_mm * img.height() / max(1, img.width()))
        self.h_spin.setValue(self.h_mm)
        self.img = self._blank(self.w_mm, self.h_mm, white=False)
        p = QPainter(self.img)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, self.img.width(), self.img.height()), img)
        p.end()
        self.canvas.relayout()

    # ----------------------------------------------------------- Zeichnen
    def set_tool(self, key):
        self.tool = key
        for b, (k, _, _) in zip(self.tool_group.buttons(), TOOLS):
            b.setChecked(k == key)

    def set_color(self, col):
        self.color = col
        self.color_btn.setStyleSheet(_swatch_style(col) + " color: " +
                                     ("#000" if QColor(col).lightness() > 128 else "#FFF") + ";")

    def choose_color(self):
        c = QColorDialog.getColor(QColor(self.color), self, "Farbe wählen")
        if c.isValid():
            self.set_color(c.name().upper())

    def choose_edge(self):
        c = QColorDialog.getColor(QColor(self.edge_color), self, "Randfarbe")
        if c.isValid():
            self.edge_color = c.name().upper()
            self.edge.setStyleSheet(_swatch_style(self.edge_color))

    def _pen(self):
        col = QColor(self.color)
        col.setAlphaF(self.opacity.value() / 100)
        return QPen(col, self.size.value() / 4 * PPM, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def stroke(self, a, b):
        p = QPainter(self.img)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(Qt.black, self.size.value() / 4 * PPM, Qt.SolidLine, Qt.RoundCap) \
            if self.tool == "erase" else self._pen()
        if self.tool == "erase":
            p.setCompositionMode(QPainter.CompositionMode_Clear)
        if a == b:                            # einzelner Klick: runder Punkt
            r = pen.widthF() / 2
            p.setPen(Qt.NoPen)
            p.setBrush(pen.color())
            p.drawEllipse(a, r, r)
        else:
            p.setPen(pen)
            p.drawLine(a, b)
        p.end()

    def draw_shape(self, p, a, b):
        p.setRenderHint(QPainter.Antialiasing)
        pen = self._pen()
        p.setPen(pen)
        fill = self.filled.isChecked() and self.tool != "line"
        p.setBrush(QBrush(pen.color()) if fill else Qt.NoBrush)
        r = QRectF(a, b).normalized()
        if self.tool == "line":
            p.drawLine(a, b)
        elif self.tool == "rect":
            p.drawRect(r)
        else:
            p.drawEllipse(r)

    def fill(self, x, y, tol=24):
        w, h = self.img.width(), self.img.height()
        if not (0 <= x < w and 0 <= y < h):
            return
        img = self.img.convertToFormat(QImage.Format_RGBA8888)
        arr = np.frombuffer(img.constBits(), np.uint8, img.bytesPerLine() * h).reshape(h, -1)
        arr = arr[:, :w * 4].reshape(h, w, 4).copy()
        mask = flood_mask(arr, x, y, tol)
        col = QColor(self.color)
        arr[mask] = [col.red(), col.green(), col.blue(), int(255 * self.opacity.value() / 100)]
        out = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
        self.img = out.convertToFormat(QImage.Format_ARGB32)

    def place_text(self, pos):
        t, ok = QInputDialog.getText(self, "Text", "Text:")
        if not ok or not t:
            return
        p = QPainter(self.img)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont("DejaVu Sans", 10, QFont.Bold)
        f.setPixelSize(max(6, int(self.size.value() / 4 * PPM * 2.5)))
        p.setFont(f)
        p.setPen(self._pen())
        p.drawText(pos, t)
        p.end()

    # ------------------------------------------------------------- Ergebnis
    def accept(self):
        self.use = self.use_combo.currentData()
        super().accept()
