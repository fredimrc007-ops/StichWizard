"""Kreuzstich-Atelier: Raster-Editor für Kreuzstich-Objekte (volle, halbe und Viertelkreuze,
Rückstich, Füllen, Pipette, Radierer), Farbpalette, Bild → Kreuzstich und Einstellungen."""
import copy

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QScrollArea, QSpinBox, QDoubleSpinBox, QToolButton,
                               QVBoxLayout, QWidget)

from . import crossstitch as cs
from . import icons

TOOLS = [("x", "Volles Kreuz", "X"), ("/", "Halbes Kreuz /", "/"), ("\\", "Halbes Kreuz \\", "\\"),
         ("q", "Viertelkreuz (Ecke anklicken)", "¼"), ("back", "Rückstich (ziehen)", "—"),
         ("fill", "Fläche füllen", "◧"), ("pick", "Farbe aufnehmen", "⌖"), ("erase", "Radierer", "⌫")]


def _swatch(color, size=22, checked=False):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(QPen(QColor("#00000060"), 1))
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), 4, 4)
    p.end()
    return QIcon(pm)


class Grid(QWidget):
    """Das Raster selbst: Zeichnen mit der Maus, Rückstich durch Ziehen zwischen Rasterpunkten."""
    edited = Signal()
    picked = Signal(int)

    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self.zoom = 14
        self.setMouseTracking(True)
        self._back_start = None
        self._hover = None
        self._stroke = False

    # ------------------------------------------------------------- Größe
    def sizeHint(self):
        d = self.dlg.data
        return QSize(d["cols"] * self.zoom + 1, d["rows"] * self.zoom + 1)

    def relayout(self):
        self.setFixedSize(self.sizeHint())
        self.update()

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            self.zoom = max(4, min(40, self.zoom + (2 if ev.angleDelta().y() > 0 else -2)))
            self.relayout()
            ev.accept()
        else:
            super().wheelEvent(ev)

    # ------------------------------------------------------------ Zeichnen
    def paintEvent(self, _ev):
        d = self.dlg.data
        z = self.zoom
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.dlg.fabric))
        p.setRenderHint(QPainter.Antialiasing)
        pal = d["palette"]
        w = max(1.5, z * 0.2)
        for (x, y, slot), (ci, kind) in self.dlg.cells.items():
            pen = QPen(QColor(pal[ci] if ci < len(pal) else "#000000"), w, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            m = z * 0.12
            x0, y0, x1, y1 = x * z + m, y * z + m, (x + 1) * z - m, (y + 1) * z - m
            if kind in ("x", "/"):
                p.drawLine(QPointF(x0, y1), QPointF(x1, y0))
            if kind in ("x", "\\"):
                p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
            if kind.startswith("q"):
                cx, cy = cs.CORNERS[int(kind[1:])]
                p.drawLine(QPointF(x0 + (x1 - x0) * cx, y0 + (y1 - y0) * cy),
                           QPointF((x + 0.5) * z, (y + 0.5) * z))
        # Raster: jede 10. Linie kräftiger (wie auf Zählmustern)
        for i in range(d["cols"] + 1):
            p.setPen(QPen(QColor(0, 0, 0, 90 if i % 10 == 0 else 28), 1.2 if i % 10 == 0 else 1))
            p.drawLine(i * z, 0, i * z, d["rows"] * z)
        for j in range(d["rows"] + 1):
            p.setPen(QPen(QColor(0, 0, 0, 90 if j % 10 == 0 else 28), 1.2 if j % 10 == 0 else 1))
            p.drawLine(0, j * z, d["cols"] * z, j * z)
        bw = max(2.0, z * 0.22)
        for x0, y0, x1, y1, ci in self.dlg.back:
            p.setPen(QPen(QColor(pal[ci] if ci < len(pal) else "#000"), bw, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x0 * z, y0 * z), QPointF(x1 * z, y1 * z))
        if self._back_start and self._hover:
            p.setPen(QPen(QColor(pal[self.dlg.color]), bw, Qt.DashLine, Qt.RoundCap))
            p.drawLine(QPointF(self._back_start[0] * z, self._back_start[1] * z),
                       QPointF(self._hover[0] * z, self._hover[1] * z))
        p.end()

    # -------------------------------------------------------------- Maus
    def _cell(self, pos):
        z = self.zoom
        x, y = int(pos.x() // z), int(pos.y() // z)
        d = self.dlg.data
        if 0 <= x < d["cols"] and 0 <= y < d["rows"]:
            fx, fy = pos.x() / z - x, pos.y() / z - y
            return x, y, (0 if fy < 0.5 else 3) if fx < 0.5 else (1 if fy < 0.5 else 2)
        return None

    def _point(self, pos):
        d = self.dlg.data
        return (max(0, min(d["cols"], round(pos.x() / self.zoom))),
                max(0, min(d["rows"], round(pos.y() / self.zoom))))

    def mousePressEvent(self, ev):
        tool = "erase" if ev.button() == Qt.RightButton else self.dlg.tool
        if tool == "back":
            self.dlg.snapshot()
            self._back_start = self._point(ev.position())
            return
        c = self._cell(ev.position())
        if c is None:
            return
        if tool == "pick":
            ci = self.dlg.color_at(*c)
            if ci is not None:
                self.picked.emit(ci)
            return
        self.dlg.snapshot()
        if tool == "fill":
            self.dlg.flood(c[0], c[1])
        else:
            self.dlg.apply(tool, *c)
        self._stroke = tool not in ("fill",)
        self.update()
        self.edited.emit()

    def mouseMoveEvent(self, ev):
        if self._back_start:
            self._hover = self._point(ev.position())
            self.update()
            return
        if self._stroke and ev.buttons():
            c = self._cell(ev.position())
            if c is not None:
                tool = "erase" if ev.buttons() & Qt.RightButton else self.dlg.tool
                self.dlg.apply(tool, *c)
                self.update()
                self.edited.emit()

    def mouseReleaseEvent(self, ev):
        if self._back_start:
            end = self._point(ev.position())
            if end != self._back_start:
                self.dlg.back.append([*self._back_start, *end, self.dlg.color])
                self.edited.emit()
            self._back_start = self._hover = None
            self.update()
        self._stroke = False


class CrossDialog(QDialog):
    """Kreuzstich-Atelier. data: vorhandene Kreuzstich-Daten oder None (neues Muster)."""

    def __init__(self, parent=None, data=None, fabric="#FFFFFF", hoop=(130.0, 180.0)):
        super().__init__(parent)
        self.setWindowTitle("Kreuzstich-Atelier")
        self.setWindowIcon(icons.icon("cross"))
        self.resize(1260, 820)
        self.fabric = fabric
        self.hoop = hoop
        self.data = copy.deepcopy(data) if data else cs.new()
        self.cells = {}
        for x, y, ci, kind in self.data["cells"]:
            self.cells[(x, y, kind if kind.startswith("q") else "c")] = (ci, kind)
        self.back = [list(b) for b in self.data["back"]]
        self.tool = "x"
        self.color = 0
        self.history, self.future = [], []
        self.result_data = None

        root = QHBoxLayout(self)
        # ---- links: Werkzeuge und Farben
        left = QVBoxLayout()
        tl = QLabel("Werkzeug")
        tl.setObjectName("cardTitle")
        left.addWidget(tl)
        grid = QGridLayout()
        self.tool_group = QButtonGroup(self)
        for i, (key, tip, sym) in enumerate(TOOLS):
            b = QToolButton()
            b.setText(sym)
            b.setToolTip(tip + ("  (Rechtsklick radiert immer)" if key != "erase" else ""))
            b.setCheckable(True)
            b.setFixedSize(46, 40)
            b.setStyleSheet("font-size: 17px; font-weight: bold;")
            b.setChecked(key == "x")
            b.clicked.connect(lambda _c=False, k=key: self.set_tool(k))
            self.tool_group.addButton(b)
            grid.addWidget(b, i // 4, i % 4)
        left.addLayout(grid)
        self.tool_label = QLabel()
        self.tool_label.setObjectName("muted")
        self.tool_label.setWordWrap(True)
        left.addWidget(self.tool_label)
        cl = QLabel("Garnfarben")
        cl.setObjectName("cardTitle")
        left.addWidget(cl)
        self.pal_box = QGridLayout()
        self.pal_box.setSpacing(4)
        pw = QWidget()
        pw.setLayout(self.pal_box)
        left.addWidget(pw)
        from .widgets import ColorButton
        self.color_btn = ColorButton(self.data["palette"][0])
        self.color_btn.setToolTip("Garnfarbe der gewählten Palettenfarbe ändern")
        self.color_btn.colorChanged.connect(self._color_changed)
        left.addWidget(self.color_btn)
        row = QHBoxLayout()
        add = QPushButton("+ Farbe")
        add.clicked.connect(self.add_color)
        tidy = QPushButton("Unbenutzte entfernen")
        tidy.clicked.connect(self.remove_unused)
        row.addWidget(add)
        row.addWidget(tidy)
        left.addLayout(row)
        sl = QLabel("Muster")
        sl.setObjectName("cardTitle")
        left.addWidget(sl)
        form = QFormLayout()
        self.cols = QSpinBox()
        self.cols.setRange(4, 400)
        self.cols.setValue(self.data["cols"])
        self.rows = QSpinBox()
        self.rows.setRange(4, 400)
        self.rows.setValue(self.data["rows"])
        self.cell = QDoubleSpinBox()
        self.cell.setRange(1.5, 6.0)
        self.cell.setSingleStep(0.1)
        self.cell.setDecimals(1)
        self.cell.setSuffix(" mm")
        self.cell.setValue(self.data["cell"])
        self.cell.setToolTip("Größe eines Kästchens (= eines Kreuzes) auf dem Stoff. "
                             "2,0–3,0 mm sehen aus wie Handstickerei auf Aida.")
        self.passes = QComboBox()
        self.passes.addItem("Einfach (zart)", 1)
        self.passes.addItem("Kräftig (jeder Schenkel 3×)", 3)
        self.passes.setCurrentIndex(max(0, self.passes.findData(self.data.get("passes", 1))))
        form.addRow("Kästchen quer", self.cols)
        form.addRow("Kästchen hoch", self.rows)
        form.addRow("Kästchengröße", self.cell)
        form.addRow("Fadenstärke", self.passes)
        left.addLayout(form)
        for w in (self.cols, self.rows):
            w.valueChanged.connect(self._resize)
        self.cell.valueChanged.connect(self._settings)
        self.passes.currentIndexChanged.connect(self._settings)
        img = QPushButton("Bild laden → Kreuzstich …")
        img.clicked.connect(self.load_image)
        left.addWidget(img)
        clear = QPushButton("Alles löschen")
        clear.clicked.connect(self.clear_all)
        left.addWidget(clear)
        left.addStretch()
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setObjectName("muted")
        left.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        left.addWidget(bb)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(300)
        root.addWidget(lw)
        # ---- rechts: Raster
        self.grid = Grid(self)
        self.grid.edited.connect(self.update_info)
        self.grid.picked.connect(self.select_color)
        sa = QScrollArea()
        sa.setWidget(self.grid)
        sa.setAlignment(Qt.AlignCenter)
        root.addWidget(sa, 1)
        hint = "Strg+Mausrad: zoomen · Rechtsklick: radieren · Strg+Z / Strg+Y"
        sa.setToolTip(hint)
        QShortcut(QKeySequence.Undo, self, self.undo)
        QShortcut(QKeySequence.Redo, self, self.redo)
        self.grid.relayout()
        self.rebuild_palette()
        self.set_tool("x")
        self.update_info()

    # ----------------------------------------------------------- Bearbeiten
    def snapshot(self):
        self.history.append((dict(self.cells), [list(b) for b in self.back],
                             list(self.data["palette"])))
        self.history = self.history[-200:]
        self.future.clear()

    def _restore(self, state):
        self.cells, self.back, self.data["palette"] = dict(state[0]), [list(b) for b in state[1]], \
            list(state[2])
        self.rebuild_palette()
        self.grid.update()
        self.update_info()

    def undo(self):
        if self.history:
            self.future.append((dict(self.cells), [list(b) for b in self.back],
                                list(self.data["palette"])))
            self._restore(self.history.pop())

    def redo(self):
        if self.future:
            self.history.append((dict(self.cells), [list(b) for b in self.back],
                                 list(self.data["palette"])))
            self._restore(self.future.pop())

    def apply(self, tool, x, y, q):
        c = self.color
        if tool == "erase":
            for k in [k for k in self.cells if k[0] == x and k[1] == y]:
                del self.cells[k]
            return
        if tool in ("x", "/", "\\"):
            if tool == "x":                     # volles Kreuz ersetzt Viertel in diesem Kästchen
                for k in [k for k in self.cells if k[:2] == (x, y) and k[2] != "c"]:
                    del self.cells[k]
            self.cells[(x, y, "c")] = (c, tool)
        elif tool == "q":
            full = self.cells.get((x, y, "c"))
            if full and full[1] == "x":
                del self.cells[(x, y, "c")]
            self.cells[(x, y, f"q{q}")] = (c, f"q{q}")

    def color_at(self, x, y, q):
        for k in ((x, y, "c"), (x, y, f"q{q}")):
            if k in self.cells:
                return self.cells[k][0]
        return None

    def flood(self, x, y):
        """Zusammenhängende Kästchen gleicher Farbe (oder leere) mit vollen Kreuzen füllen."""
        start = self.cells.get((x, y, "c"))
        target = start[0] if start else None
        if target == self.color and start and start[1] == "x":
            return
        d = self.data
        seen, todo = set(), [(x, y)]
        while todo and len(seen) < d["cols"] * d["rows"]:
            cx, cy = todo.pop()
            if (cx, cy) in seen or not (0 <= cx < d["cols"] and 0 <= cy < d["rows"]):
                continue
            cur = self.cells.get((cx, cy, "c"))
            if (cur[0] if cur else None) != target:
                continue
            seen.add((cx, cy))
            todo += [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]
        for cx, cy in seen:
            self.apply("x", cx, cy, 0)

    def clear_all(self):
        self.snapshot()
        self.cells.clear()
        self.back.clear()
        self.grid.update()
        self.update_info()

    # -------------------------------------------------------------- Farben
    def rebuild_palette(self):
        while self.pal_box.count():
            it = self.pal_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.pal_buttons = []
        for i, col in enumerate(self.data["palette"]):
            b = QToolButton()
            b.setIcon(_swatch(col))
            b.setIconSize(QSize(22, 22))
            b.setCheckable(True)
            b.setChecked(i == self.color)
            b.setToolTip(f"Farbe {i + 1}: {col}")
            b.clicked.connect(lambda _c=False, k=i: self.select_color(k))
            self.pal_box.addWidget(b, i // 8, i % 8)
            self.pal_buttons.append(b)
        self.color = min(self.color, len(self.data["palette"]) - 1)

    def select_color(self, i):
        self.color = i
        for k, b in enumerate(self.pal_buttons):
            b.setChecked(k == i)
        self.color_btn.set_color(self.data["palette"][i])

    def _color_changed(self, col):
        if self.data["palette"][self.color].upper() != col.upper():
            self.snapshot()
            self.data["palette"][self.color] = col
            self.pal_buttons[self.color].setIcon(_swatch(col))
            self.grid.update()
            self.update_info()

    def add_color(self):
        if len(self.data["palette"]) >= 40:
            return
        self.snapshot()
        self.data["palette"].append("#FFB300")
        self.color = len(self.data["palette"]) - 1
        self.rebuild_palette()
        self.select_color(self.color)

    def remove_unused(self):
        used = {ci for ci, _ in self.cells.values()} | {b[4] for b in self.back}
        if len(used) == len(self.data["palette"]) or not used:
            return
        self.snapshot()
        keep = sorted(used)
        remap = {old: new for new, old in enumerate(keep)}
        self.data["palette"] = [self.data["palette"][i] for i in keep]
        self.cells = {k: (remap[ci], kind) for k, (ci, kind) in self.cells.items()}
        self.back = [[*b[:4], remap[b[4]]] for b in self.back]
        self.color = 0
        self.rebuild_palette()
        self.select_color(0)
        self.grid.update()

    # ------------------------------------------------------------ Werkzeug
    def set_tool(self, key):
        self.tool = key
        for b, (k, tip, _) in zip(self.tool_group.buttons(), TOOLS):
            b.setChecked(k == key)
            if k == key:
                self.tool_label.setText(tip + ". Ziehen mit gedrückter Maustaste zeichnet "
                                        "mehrere Kästchen; Rechtsklick radiert.")

    # ---------------------------------------------------------- Einstellungen
    def _resize(self):
        self.snapshot()
        self.data["cols"], self.data["rows"] = self.cols.value(), self.rows.value()
        self.cells = {k: v for k, v in self.cells.items()
                      if k[0] < self.data["cols"] and k[1] < self.data["rows"]}
        self.back = [b for b in self.back if max(b[0], b[2]) <= self.data["cols"]
                     and max(b[1], b[3]) <= self.data["rows"]]
        self.grid.relayout()
        self.update_info()

    def _settings(self):
        self.data["cell"] = self.cell.value()
        self.data["passes"] = self.passes.currentData()
        self.update_info()

    def load_image(self):
        from .controls import ask_values
        path, _ = QFileDialog.getOpenFileName(self, "Bild für Kreuzstich", "",
                                              "Bilder (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, "Kreuzstich", "Das Bild ließ sich nicht öffnen.")
            return
        hw = int(self.hoop[0] / self.data["cell"])
        v = ask_values(self, "Bild → Kreuzstich", [
            ("cols", "Breite in Kästchen", "int", 8, 300, min(60, hw)),
            ("colors", "Garnfarben", "int", 2, 30, 8),
            ("light", "Helle Bereiche frei lassen (Stoff)", "check", True),
            ("kind", "Stichart", "choice", [("Volle Kreuze", "x"), ("Halbe Kreuze /", "/")], "x")],
            f"Das Bild wird auf ein Raster verkleinert und auf wenige Garnfarben reduziert. "
            f"Bei {self.data['cell']:.1f} mm Kästchen passen {hw} Kästchen in die Rahmenbreite.")
        if not v:
            return
        cells, palette, rows = cs.from_image(img, v["cols"], v["colors"], v["light"],
                                             kind=v["kind"])
        if not cells:
            QMessageBox.information(self, "Kreuzstich", "Im Bild wurde nichts zum Sticken gefunden.")
            return
        self.snapshot()
        self.data.update(cols=int(v["cols"]), rows=int(rows), palette=palette)
        self.cols.blockSignals(True)
        self.rows.blockSignals(True)
        self.cols.setValue(self.data["cols"])
        self.rows.setValue(self.data["rows"])
        self.cols.blockSignals(False)
        self.rows.blockSignals(False)
        self.cells = {(x, y, "c"): (ci, kind) for x, y, ci, kind in cells}
        self.back = []
        self.color = 0
        self.rebuild_palette()
        self.select_color(0)
        self.grid.relayout()
        self.update_info()

    # ------------------------------------------------------------- Ergebnis
    def current(self):
        d = dict(self.data)
        d["palette"] = list(self.data["palette"])
        d["cells"] = [[x, y, ci, kind] for (x, y, _), (ci, kind) in sorted(
            self.cells.items(), key=lambda t: (t[0][1], t[0][0], t[0][2]))]
        d["back"] = [list(b) for b in self.back]
        return d

    def update_info(self):
        st = cs.stats(self.current())
        warn = ""
        if st["width"] > self.hoop[0] or st["height"] > self.hoop[1]:
            warn = (f"\n⚠ Größer als der Rahmen ({self.hoop[0]:.0f} × {self.hoop[1]:.0f} mm) – "
                    "Kästchen kleiner oder weniger Kästchen.")
        self.info.setText(f"Raster {st['width']:.0f} × {st['height']:.0f} mm · {st['full']} volle, "
                          f"{st['half']} halbe, {st['quarter']} Viertelkreuze · {st['back']} "
                          f"Rückstiche · {st['colors']} Farben{warn}")

    def accept(self):
        d = self.current()
        if not d["cells"] and not d["back"]:
            QMessageBox.information(self, "Kreuzstich", "Das Muster ist noch leer.")
            return
        self.result_data = d
        super().accept()
