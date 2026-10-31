"""Stick-Simulator: zeigt Stich für Stich, wie die Maschine das Design stickt."""
import math

from PySide6.QtCore import QElapsedTimer, QRectF, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QGraphicsItem, QGraphicsScene,
                               QGraphicsView, QHBoxLayout, QLabel, QSlider, QToolButton,
                               QVBoxLayout, QWidget)

from . import icons
from .render import HoopItem, paint_thread, stitch_lines
from .style import canvas_bg
from .threads import thread_name


class SpeedSlider(QWidget):
    """Stufenloser Tempo-Regler für die Simulation (logarithmisch, 1 bis 5000 Stiche/s).
    Merkt sich die Einstellung; »wie die Maschine« = eingestellte Stickgeschwindigkeit."""
    LO, HI = 1.0, 5000.0

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addSpacing(8)
        h.addWidget(QLabel("Tempo"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setFixedWidth(120)
        self.slider.setToolTip("Simulationsgeschwindigkeit – ganz links Stich für Stich, "
                               "ganz rechts sehr schnell")
        self.label = QLabel()
        self.label.setMinimumWidth(104)
        h.addWidget(self.slider)
        h.addWidget(self.label)
        h.addSpacing(14)
        self.qs = QSettings("StickStudio", "StickStudio")
        try:
            sps = float(self.qs.value("sim/speed", 60.0))
        except (TypeError, ValueError):
            sps = 60.0
        self.slider.valueChanged.connect(self._changed)
        self.set_speed(sps)
        self._changed()

    @staticmethod
    def machine_sps():
        from . import model
        return max(1.0, model.STITCHES_PER_MINUTE / 60.0)

    def speed(self):
        """Stiche pro Sekunde."""
        t = self.slider.value() / 1000.0
        return self.LO * (self.HI / self.LO) ** t

    def set_speed(self, sps):
        sps = min(self.HI, max(self.LO, sps))
        self.slider.setValue(round(1000 * math.log(sps / self.LO) / math.log(self.HI / self.LO)))

    def _changed(self, *_):
        sps = self.speed()
        real = self.machine_sps()
        txt = f"{sps:,.0f} Stiche/s".replace(",", ".") if sps >= 10 else f"{sps:.1f} Stiche/s".replace(".", ",")
        ratio = sps / real
        if abs(math.log(ratio)) < 0.12:
            txt += " · wie Maschine"
        else:
            txt += (f" · {ratio:.0f}×" if ratio >= 10 else f" · {ratio:.1f}×").replace(".", ",")
        self.label.setToolTip(f"Die Maschine stickt etwa {real:.0f} Stiche pro Sekunde "
                              "(Einstellungen › Stickgeschwindigkeit)")
        self.label.setText(txt)
        self.qs.setValue("sim/speed", sps)


class SimClock:
    """Liefert je Timer-Takt die Anzahl weiterer Stiche – auch bei sehr langsamen Tempi
    (Bruchteile werden angesammelt) und unabhängig von ruckelnden Takten."""

    def __init__(self):
        self.timer = QElapsedTimer()
        self.acc = 0.0

    def start(self):
        self.timer.start()
        self.acc = 0.0

    def step(self, sps):
        dt = min(0.25, self.timer.restart() / 1000.0) if self.timer.isValid() else 0.016
        self.acc += sps * dt
        n = int(self.acc)
        self.acc -= n
        return n


class SimItem(QGraphicsItem):
    def __init__(self, blocks):
        super().__init__()
        self.blocks = []        # (farbe, lines)
        self.total = 0
        xs, ys = [0], [0]
        for color, sts in blocks:
            lines, _ = stitch_lines(sts)
            self.blocks.append((color, lines))
            self.total += len(lines)
            xs += [s[0] for s in sts]
            ys += [s[1] for s in sts]
        self.rect = QRectF(min(xs) - 3, min(ys) - 3, max(xs) - min(xs) + 6, max(ys) - min(ys) + 6)
        self.n = self.total

    def boundingRect(self):
        return self.rect

    def position(self):
        """(farbindex, aktuelle Linie)"""
        left = self.n
        for i, (c, lines) in enumerate(self.blocks):
            if left <= len(lines):
                return i, (lines[left - 1] if left > 0 else (lines[0] if lines else None))
            left -= len(lines)
        last = self.blocks[-1][1] if self.blocks else []
        return len(self.blocks) - 1, (last[-1] if last else None)

    def paint(self, p, option, widget=None):
        p.setRenderHint(QPainter.Antialiasing)
        left = self.n
        for color, lines in self.blocks:
            if left <= 0:
                break
            part = lines[:left]
            paint_thread(p, part, color, "real", 3.0)
            left -= len(lines)
        _, line = self.position()
        if line is not None and self.n < self.total:
            pt = line.p2()
            p.setPen(QPen(QColor("#E53935"), 0.4))
            p.setBrush(QColor(229, 57, 53, 60))
            p.drawEllipse(pt, 2.2, 2.2)
            p.drawLine(pt.x() - 4, pt.y(), pt.x() + 4, pt.y())
            p.drawLine(pt.x(), pt.y() - 4, pt.x(), pt.y() + 4)


class SimulatorDialog(QDialog):
    def __init__(self, doc, opts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stick-Simulator")
        self.resize(900, 760)
        self.blocks = doc.machine_blocks()
        scene = QGraphicsScene(self)
        hoop = HoopItem(opts)
        w, h = doc.hoop_size
        hoop.set_hoop(w, h, doc.fabric)
        scene.addItem(hoop)
        self.item = SimItem(self.blocks)
        scene.addItem(self.item)
        self.view = QGraphicsView(scene)
        self.view.setRenderHints(QPainter.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor(canvas_bg())))
        self.view.setFrameShape(QGraphicsView.NoFrame)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self._hoop_rect = hoop.boundingRect()

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.view, 1)
        bar = QHBoxLayout()
        bar.setContentsMargins(14, 10, 14, 12)
        self.play = QToolButton()
        self.play.setIcon(icons.icon("play"))
        self.play.setIconSize(QSize(34, 34))
        self.play.setAutoRaise(True)
        self.play.clicked.connect(self.toggle)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, self.item.total)
        self.slider.setValue(self.item.total)
        self.slider.valueChanged.connect(self.seek)
        self.speed = SpeedSlider()
        self.clock = SimClock()
        self.label = QLabel()
        self.label.setMinimumWidth(260)
        bar.addWidget(self.play)
        bar.addWidget(self.slider, 1)
        bar.addWidget(self.speed)
        bar.addWidget(self.label)
        v.addLayout(bar)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.seek(self.item.total)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.view.fitInView(self._hoop_rect, Qt.KeepAspectRatio)

    def toggle(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play.setIcon(icons.icon("play"))
        else:
            if self.slider.value() >= self.item.total:
                self.slider.setValue(0)
            self.clock.start()
            self.timer.start()
            self.play.setIcon(icons.icon("pause"))

    def tick(self):
        step = self.clock.step(self.speed.speed())
        if step <= 0:
            return
        n = self.slider.value() + step
        if n >= self.item.total:
            n = self.item.total
            self.toggle()
        self.slider.setValue(n)

    def seek(self, n):
        self.item.n = n
        self.item.update()
        if self.blocks:
            ci, _ = self.item.position()
            col = self.blocks[max(0, ci)][0]
            self.label.setText(f"Stich {n:,} / {self.item.total:,}   ·   Farbe {ci + 1}/{len(self.blocks)}: "
                               f"{thread_name(col)}".replace(",", "."))

    def closeEvent(self, ev):
        self.timer.stop()
        super().closeEvent(ev)
