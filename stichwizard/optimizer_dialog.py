"""Stick-Simulator & Optimierer: realistische Sticksimulation mit direkter Bearbeitung von
Sprüngen, Fadenschnitten und Stickreihenfolge."""
import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame,
                               QGraphicsScene, QGraphicsView, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QMenu, QMessageBox, QPushButton, QSlider,
                               QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import icons, jumps
from .engine import STITCH
from .render import HoopItem
from .style import canvas_bg
from .simulator import SimClock, SimItem, SpeedSlider
from .threads import thread_name

FILTERS = [("Alle Sprünge", "all"), ("Ohne Fadenschnitt", "notrim"), ("Mit Fadenschnitt", "trim"),
           ("Verdeckt verbindbar", "hidden"), ("Länger als 10 mm", "long")]


def _lines_before(blocks, mblock, mpos):
    """Anzahl der Stichlinien bis zu einer Stelle (= Position des Simulationsreglers)."""
    n = 0
    for bi, (_, sts) in enumerate(blocks):
        if bi < mblock:
            n += sum(1 for k in range(1, len(sts)) if sts[k][2] == STITCH)
        elif bi == mblock:
            n += sum(1 for k in range(1, min(mpos, len(sts))) if sts[k][2] == STITCH)
            break
    return n


class SimView(QGraphicsView):
    """Simulationsansicht mit Zoom (Mausrad), Verschieben (mittlere Taste) und Sprung-Overlay."""

    def __init__(self, scene, dialog):
        super().__init__(scene)
        self.dlg = dialog
        self.setRenderHints(QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor(canvas_bg())))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMouseTracking(True)
        self._pan = None
        self.hover = None

    def zoom(self):
        return self.transform().m11()

    def wheelEvent(self, ev):
        d = ev.angleDelta().y()
        if not d:
            return
        z = max(0.5, min(80.0, self.zoom() * 1.15 ** (d / 120)))
        p = ev.position()
        s = self.viewportTransform().inverted()[0].map(p)
        f = z / self.zoom()
        self.scale(f, f)
        m = self.viewportTransform().map(s) - p
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + round(m.x()))
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + round(m.y()))

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MiddleButton:
            self._pan = ev.position()
            return
        sp = self.mapToScene(ev.position().toPoint())
        self.dlg.view_clicked(sp.x(), sp.y(), ev.button(), ev.globalPosition().toPoint())

    def mouseMoveEvent(self, ev):
        if self._pan is not None:
            d = ev.position() - self._pan
            self._pan = ev.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(d.y()))
            return
        sp = self.mapToScene(ev.position().toPoint())
        h = self.dlg.hit_jump(sp.x(), sp.y(), 7 / self.zoom())
        if h != self.hover:
            self.hover = h
            self.viewport().update()
        self.viewport().setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)

    def mouseReleaseEvent(self, ev):
        self._pan = None

    def drawForeground(self, p, rect):
        if not self.dlg.show_jumps:
            return
        z = self.zoom()
        p.setRenderHint(QPainter.Antialiasing)
        sel = self.dlg.selected_index()
        now = self.dlg.slider.value()
        recs = self.dlg.records
        labels = []
        for r in recs:
            hot = r["index"] in (sel, self.hover)
            col = QColor("#E53935") if r["trim"] else QColor("#FB8C00")
            upcoming = r["line"] > now            # noch nicht gestickt
            if not hot and (sel is not None or upcoming):
                col.setAlpha(70 if upcoming else 110)
            pen = QPen(col, 3.4 if hot else 1.5, Qt.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            a, b = QPointF(*r["a"]), QPointF(*r["b"])
            p.drawLine(a, b)
            s = (5.5 if hot else 3.5) / z
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
            # Pfeilspitze in Stickrichtung
            dx, dy = b.x() - a.x(), b.y() - a.y()
            ln = math.hypot(dx, dy)
            if ln * z > 18:
                ux, uy = dx / ln, dy / ln
                tip = QPointF(b.x() - ux * s * 0.8, b.y() - uy * s * 0.8)
                k = (9 if hot else 6.5) / z
                p.setBrush(col)
                p.setPen(Qt.NoPen)
                p.drawPolygon([tip, QPointF(tip.x() - ux * k - uy * k * 0.55, tip.y() - uy * k + ux * k * 0.55),
                               QPointF(tip.x() - ux * k + uy * k * 0.55, tip.y() - uy * k - ux * k * 0.55)])
            labels.append((r, hot, upcoming, col))
        # Nummern (Reihenfolge) – bei sehr vielen Sprüngen nur in der Nähe der aktuellen Stelle
        if len(recs) > 150:
            cur = sum(1 for r in recs if r["line"] <= now)
            labels = [x for x in labels if x[1] or abs(x[0]["index"] - cur) <= 6]
        f = p.font()
        f.setPixelSize(10)
        f.setBold(True)
        p.setFont(f)
        p.save()
        for r, hot, upcoming, col in labels:
            mid = self.mapFromScene(QPointF((r["a"][0] + r["b"][0]) / 2, (r["a"][1] + r["b"][1]) / 2))
            p.save()
            p.resetTransform()
            txt = str(r["index"] + 1)
            w = 8 + 6 * len(txt)
            box = QRectF(mid.x() - w / 2, mid.y() - 8, w, 16)
            bg = QColor(col)
            bg.setAlpha(255 if (hot or not upcoming) else 120)
            p.setPen(QPen(QColor("white"), 1.2))
            p.setBrush(bg)
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor("white"))
            p.drawText(box, Qt.AlignCenter, txt)
            p.restore()
        p.restore()


class OptimizerDialog(QDialog):
    def __init__(self, window, title="Stick-Simulator & Optimierer"):
        super().__init__(window)
        self.w = window
        self.setWindowTitle(title)
        self.setWindowIcon(icons.icon("jumps"))
        self.resize(1360, 860)
        self.records, self.blocks = [], []
        self.show_jumps = True
        self.start_stats = self._stats()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------------------------------------------------------- Simulation
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        self.scene = QGraphicsScene(-3000, -3000, 6000, 6000, self)
        self.hoop = HoopItem(window.opts)
        w_, h_ = window.doc.hoop_size
        self.hoop.set_hoop(w_, h_, window.doc.fabric)
        self.scene.addItem(self.hoop)
        self.sim = None
        self.view = SimView(self.scene, self)
        lv.addWidget(self.view, 1)
        bar = QHBoxLayout()
        bar.setContentsMargins(12, 8, 12, 10)
        self.btn_prev = self._tbtn("Vorheriger Sprung", "◀", lambda: self.step_jump(-1))
        self.play = QToolButton()
        self.play.setIcon(icons.icon("play"))
        self.play.setIconSize(QSize(32, 32))
        self.play.setAutoRaise(True)
        self.play.setToolTip("Abspielen / Anhalten (Leertaste)")
        self.play.clicked.connect(self.toggle)
        self.btn_next = self._tbtn("Nächster Sprung", "▶", lambda: self.step_jump(1))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.seek)
        self.speed = SpeedSlider()
        self.clock = SimClock()
        self.pos_label = QLabel()
        self.pos_label.setMinimumWidth(230)
        for wdg in (self.btn_prev, self.play, self.btn_next):
            bar.addWidget(wdg)
        bar.addWidget(self.slider, 1)
        bar.addWidget(self.speed)
        bar.addWidget(self.pos_label)
        self.btn_side = QToolButton()
        self.btn_side.setText("Sprünge ▸")
        self.btn_side.setCheckable(True)
        self.btn_side.setChecked(True)
        self.btn_side.setToolTip("Sprungliste und Bearbeitung ein-/ausblenden")
        bar.addWidget(self.btn_side)
        lv.addLayout(bar)
        root.addWidget(left, 1)

        # ---------------------------------------------------------- Seitenleiste
        side = QFrame()
        side.setObjectName("optSide")
        side.setFixedWidth(400)

        sv = QVBoxLayout(side)
        sv.setContentsMargins(14, 14, 14, 14)
        sv.setSpacing(10)

        t = QLabel("Übersicht")
        t.setObjectName("cardTitle")
        sv.addWidget(t)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.stat_labels = {}
        for c, head in enumerate(("", "beim Öffnen", "jetzt")):
            h = QLabel(head)
            h.setObjectName("muted")
            self.grid.addWidget(h, 0, c)
        for r, (key, label) in enumerate((("stitches", "Stiche"), ("jumps", "Sprünge"),
                                          ("trims", "Fadenschnitte"), ("colors", "Farbwechsel"),
                                          ("minutes", "Stickzeit")), start=1):
            self.grid.addWidget(QLabel(label), r, 0)
            a, b = QLabel(), QLabel()
            b.setTextFormat(Qt.RichText)
            self.grid.addWidget(a, r, 1)
            self.grid.addWidget(b, r, 2)
            self.stat_labels[key] = (a, b)
        sv.addLayout(self.grid)

        self.btn_auto = QPushButton("✦  Automatisch optimieren")
        self.btn_auto.setObjectName("primary")
        self.btn_auto.setToolTip("Stickdateien neu ordnen und Verbindungen verdeckt führen; "
                                 "eigene Formen werden beim Export ohnehin optimiert")
        self.btn_auto.clicked.connect(self.auto_optimize)
        sv.addWidget(self.btn_auto)

        row = QHBoxLayout()
        t2 = QLabel("Sprünge")
        t2.setObjectName("cardTitle")
        row.addWidget(t2)
        row.addStretch()
        self.filter = QComboBox()
        for label, key in FILTERS:
            self.filter.addItem(label, key)
        self.filter.currentIndexChanged.connect(self.fill_list)
        row.addWidget(self.filter)
        sv.addLayout(row)

        self.list = QTreeWidget()
        self.list.setHeaderLabels(["#", "Länge", "Schnitt", "Art", "Verbindbar"])
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.list.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.list.itemSelectionChanged.connect(self.on_select)
        sv.addWidget(self.list, 1)

        self.sel_label = QLabel("Sprung in der Liste oder im Bild anklicken.")
        self.sel_label.setWordWrap(True)
        self.sel_label.setObjectName("muted")
        sv.addWidget(self.sel_label)
        acts = QGridLayout()
        self.btn_trim = QPushButton("✂  Schnitt setzen")
        self.btn_trim.clicked.connect(lambda: self.edit_selected("toggle_trim"))
        self.btn_connect = QPushButton("Verbinden")
        self.btn_connect.clicked.connect(lambda: self.edit_selected("connect"))
        self.mode = QComboBox()
        for label, key in (("Schnitt automatisch (laut Einstellungen)", "auto"), ("Immer schneiden", "always"),
                           ("Nie schneiden", "never")):
            self.mode.addItem(label, key)
        self.mode.activated.connect(lambda _: self.edit_selected("mode"))
        acts.addWidget(self.btn_trim, 0, 0)
        acts.addWidget(self.btn_connect, 0, 1)
        acts.addWidget(self.mode, 1, 0, 1, 2)
        sv.addLayout(acts)

        t4 = QLabel("Reihenfolge")
        t4.setObjectName("cardTitle")
        sv.addWidget(t4)
        self.order_label = QLabel()
        self.order_label.setWordWrap(True)
        self.order_label.setObjectName("muted")
        sv.addWidget(self.order_label)
        ob = QHBoxLayout()
        self.btn_earlier = QPushButton("◀ Früher")
        self.btn_earlier.setToolTip("Das Teil nach diesem Sprung einen Platz früher sticken")
        self.btn_earlier.clicked.connect(lambda: self.edit_order("earlier"))
        self.btn_later = QPushButton("Später ▶")
        self.btn_later.setToolTip("Das Teil nach diesem Sprung einen Platz später sticken")
        self.btn_later.clicked.connect(lambda: self.edit_order("later"))
        self.btn_reverse = QPushButton("⇄ Umdrehen")
        self.btn_reverse.setToolTip("Das Teil nach diesem Sprung von der anderen Seite her sticken "
                                    "(nur innerhalb eines Objekts)")
        self.btn_reverse.clicked.connect(lambda: self.edit_order("reverse"))
        for b in (self.btn_earlier, self.btn_later, self.btn_reverse):
            ob.addWidget(b)
        sv.addLayout(ob)
        self.auto_order = QCheckBox("Gleiche Farben auf kürzestem Weg ordnen")
        self.auto_order.setToolTip("An: Objekte gleicher Farbe automatisch in der Reihenfolge mit den "
                                   "kürzesten Sprüngen sticken.\nAus: Reihenfolge wie in der Objektliste "
                                   "bzw. wie von Hand festgelegt")
        self.auto_order.setChecked(window.doc.order_mode == "auto")
        self.auto_order.toggled.connect(self.set_auto_order)
        sv.addWidget(self.auto_order)

        t3 = QLabel("Alle auf einmal")
        t3.setObjectName("cardTitle")
        sv.addWidget(t3)
        b1 = QHBoxLayout()
        self.short = QDoubleSpinBox()
        self.short.setRange(0.5, 20)
        self.short.setValue(2.0)
        self.short.setSuffix(" mm")
        btn_short = QPushButton("Schnitt entfernen bei Sprüngen unter")
        btn_short.setToolTip("Bei kurzen Sprüngen ist ein Schnitt meist unnötig und kostet Zeit")
        btn_short.clicked.connect(lambda: self.bulk("untrim", self.short.value()))
        b1.addWidget(btn_short, 1)
        b1.addWidget(self.short)
        sv.addLayout(b1)
        b2 = QHBoxLayout()
        self.long = QDoubleSpinBox()
        self.long.setRange(1, 100)
        from .engine import TRIM_DISTANCE
        self.long.setValue(max(1.0, TRIM_DISTANCE))
        self.long.setSuffix(" mm")
        btn_long = QPushButton("Schnitt setzen bei Sprüngen ab")
        btn_long.setToolTip("Sprungfäden ab dieser Länge schneiden lassen – sonst müssen sie von Hand "
                            "abgeschnitten werden")
        btn_long.clicked.connect(lambda: self.bulk("trim", self.long.value()))
        b2.addWidget(btn_long, 1)
        b2.addWidget(self.long)
        sv.addLayout(b2)
        btn_hidden = QPushButton("Alle verdeckt verbindbaren Sprünge verbinden")
        btn_hidden.clicked.connect(lambda: self.bulk("connect", 0))
        sv.addWidget(btn_hidden)

        foot = QHBoxLayout()
        for label, fn in (("↶ Rückgängig", self.undo), ("↷ Wiederholen", self.redo)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            foot.addWidget(b)
        foot.addStretch()
        close = QPushButton("Fertig")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        sv.addLayout(foot)
        root.addWidget(side)
        self.side = side
        self.btn_side.toggled.connect(lambda on: (self.side.setVisible(on),
                                                  self.btn_side.setText("Sprünge ▸" if on else "◂ Sprünge")))

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.refresh(first=True)

    # --------------------------------------------------------------- Helfer
    def _tbtn(self, tip, text, fn):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setStyleSheet("QToolButton { font-size: 15pt; padding: 2px 8px; }")
        b.clicked.connect(fn)
        return b

    def _stats(self):
        st = self.w.doc.stats()
        recs = jumps.jump_list(self.w.doc)
        return {"stitches": st["stitches"], "jumps": len(recs), "trims": st["trims"],
                "colors": max(0, st["colors"] - 1), "minutes": st["minutes"]}

    def selected_index(self):
        items = self.list.selectedItems()
        return items[0].data(0, Qt.UserRole) if items else None

    def selected_record(self):
        i = self.selected_index()
        return self.records[i] if i is not None and i < len(self.records) else None

    def hit_jump(self, x, y, tol):
        from shapely.geometry import LineString, Point
        best, bd = None, tol
        here = Point(x, y)
        for r in self.records:
            d = LineString([r["a"], r["b"]]).distance(here) if r["length"] > 1e-6 else \
                math.hypot(x - r["a"][0], y - r["a"][1])
            if d < bd:
                best, bd = r["index"], d
        return best

    # -------------------------------------------------------------- Aufbau
    def refresh(self, first=False, keep=None):
        frac = self.slider.value() / max(1, self.slider.maximum()) if not first else 1.0
        self.blocks = []
        self.records = jumps.jump_list(self.w.doc, self.blocks)
        self.cover = jumps.CoverageIndex(self.blocks)
        for r in self.records:
            r["hidden"] = r["kind"] == "inside" and self.cover.covered(r)
            r["line"] = _lines_before(self.blocks, r["mblock"], r["mpos"])
        if self.sim is not None:
            self.scene.removeItem(self.sim)
        self.sim = SimItem(self.blocks)
        self.scene.addItem(self.sim)
        self.slider.blockSignals(True)
        self.slider.setRange(0, self.sim.total)
        self.slider.setValue(int(frac * self.sim.total))
        self.slider.blockSignals(False)
        self.seek(self.slider.value())
        self.update_stats()
        self.fill_list(keep=keep)
        if first:
            QTimer.singleShot(0, lambda: self.view.fitInView(self.hoop.boundingRect(),
                                                             Qt.KeepAspectRatio))

    def update_stats(self):
        now = self._stats()
        for key, (a, b) in self.stat_labels.items():
            v0, v1 = self.start_stats[key], now[key]
            fmt = (lambda v: f"{v:.1f} min") if key == "minutes" else (lambda v: f"{v:,}".replace(",", "."))
            a.setText(fmt(v0))
            better = v1 < v0 - 1e-9
            worse = v1 > v0 + 1e-9
            col = "#2E7D32" if better and key != "stitches" else "#C62828" if worse and key != "stitches" else "#2B2D3A"
            b.setText(f"<b style='color:{col}'>{fmt(v1)}</b>")

    def fill_list(self, *_, keep=None):
        keep = keep if keep is not None else self.selected_record()
        flt = self.filter.currentData()
        self.list.blockSignals(True)
        self.list.clear()
        sel_item = None
        for r in self.records:
            if flt == "notrim" and r["trim"] or flt == "trim" and not r["trim"] or \
                    flt == "hidden" and not r["hidden"] or flt == "long" and r["length"] <= 10:
                continue
            kind = ("zwischen Objekten" if r["kind"] == "between" and not r["same"]
                    else "in " + (self.w.doc.find(r["obj"]).name if self.w.doc.find(r["obj"]) else "?"))
            it = QTreeWidgetItem([str(r["index"] + 1), f"{r['length']:.1f} mm",
                                  "✂" if r["trim"] else "–", kind,
                                  "✓ verdeckt" if r["hidden"] else ""])
            it.setData(0, Qt.UserRole, r["index"])
            if r["trim"]:
                it.setForeground(2, QColor("#C62828"))
            if r["hidden"]:
                it.setForeground(4, QColor("#2E7D32"))
            self.list.addTopLevelItem(it)
            if keep and abs(r["a"][0] - keep["a"][0]) < 0.05 and abs(r["a"][1] - keep["a"][1]) < 0.05 \
                    and abs(r["b"][0] - keep["b"][0]) < 0.05 and abs(r["b"][1] - keep["b"][1]) < 0.05:
                sel_item = it
        self.list.blockSignals(False)
        if sel_item:
            self.list.setCurrentItem(sel_item)
        self.on_select()

    # ------------------------------------------------------------ Simulation
    def toggle(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play.setIcon(icons.icon("play"))
        else:
            if self.slider.value() >= self.sim.total:
                self.slider.setValue(0)
            self.clock.start()
            self.timer.start()
            self.play.setIcon(icons.icon("pause"))

    def tick(self):
        step = self.clock.step(self.speed.speed())
        if step <= 0:
            return
        n = self.slider.value() + step
        if n >= self.sim.total:
            n = self.sim.total
            self.toggle()
        self.slider.setValue(n)

    def seek(self, n):
        if self.sim is None:
            return
        self.sim.n = n
        self.sim.update()
        if self.blocks:
            ci, _ = self.sim.position()
            col = self.blocks[max(0, ci)][0]
            passed = sum(1 for r in self.records if r["line"] <= n)
            self.pos_label.setText(
                f"Stich {n:,}/{self.sim.total:,} · Farbe {ci + 1}/{len(self.blocks)} · "
                f"Sprung {passed}/{len(self.records)}".replace(",", "."))
            self.pos_label.setToolTip(f"Aktuelle Garnfarbe: {thread_name(col)}")

    def step_jump(self, d):
        n = self.slider.value()
        lines = sorted({r["line"] for r in self.records})
        target = None
        if not lines:
            return
        if d > 0:
            target = next((x for x in lines if x > n), lines[0])          # am Ende: von vorn
        else:
            target = next((x for x in reversed(lines) if x < n), lines[-1])
        self.slider.setValue(target)
        rec = next(r for r in self.records if r["line"] == target)
        self.select_record(rec["index"])

    def select_record(self, idx):
        for attempt in (1, 2):
            for i in range(self.list.topLevelItemCount()):
                it = self.list.topLevelItem(i)
                if it.data(0, Qt.UserRole) == idx:
                    self.list.setCurrentItem(it)
                    self.list.scrollToItem(it)
                    return
            if self.filter.currentIndex() == 0:
                return
            self.filter.setCurrentIndex(0)      # im aktuellen Filter nicht sichtbar

    def on_select(self):
        rec = self.selected_record()
        between = rec is not None and rec["kind"] == "between" and not rec["same"]
        self.btn_trim.setEnabled(rec is not None and not between)
        self.btn_connect.setEnabled(rec is not None and not between)
        self.mode.setVisible(between)
        for b in (self.btn_earlier, self.btn_later):
            b.setEnabled(rec is not None)
        self.btn_reverse.setEnabled(rec is not None and not between)
        if rec is None:
            self.order_label.setText("Sprung wählen, um das Teil danach früher, später oder umgedreht "
                                     "zu sticken.")
        else:
            nxt = self.w.doc.find(rec["obj_b"] if between else rec["obj"])
            what = f"das Objekt »{nxt.name}«" if between else f"das nächste Teil von »{nxt.name}«"
            self.order_label.setText(f"Nach Sprung {rec['index'] + 1} kommt {what}.")
        if rec is None:
            self.sel_label.setText("Sprung in der Liste oder im Bild anklicken.")
        else:
            o = self.w.doc.find(rec["obj"])
            where = (f"zwischen »{o.name}« und »{self.w.doc.find(rec['obj_b']).name}«"
                     if between else f"in »{o.name}«" + ("" if o.kind == "stitches"
                                                          else " (wird zum Bearbeiten in Stiche umgewandelt)"))
            self.sel_label.setText(f"Sprung {rec['index'] + 1}: {rec['length']:.1f} mm, "
                                   f"{'mit' if rec['trim'] else 'ohne'} Fadenschnitt, {where}.")
            self.btn_trim.setText("Schnitt entfernen" if rec["trim"] else "✂  Schnitt setzen")
            self.btn_connect.setText("Verbinden (verdeckt)" if rec["hidden"] else "Verbinden (⚠ sichtbar)")
            self.btn_connect.setToolTip("Sprung durch Steppstiche ersetzen – " +
                                        ("sie werden später überstickt" if rec["hidden"]
                                         else "der Faden bliebe sichtbar"))
            if between:
                self.mode.setCurrentIndex(max(0, self.mode.findData(o.trim_after)))
            # Simulation an die Stelle des Sprungs setzen
            if not self.timer.isActive():
                self.slider.setValue(rec["line"])
        self.view.viewport().update()

    # ----------------------------------------------------------- Bearbeiten
    def edit_selected(self, action):
        rec = self.selected_record()
        if rec is None:
            return
        if action == "mode":
            jumps.set_trim_mode(self.w.doc, rec, self.mode.currentData())
            o = self.w.doc.find(rec["obj"])
            self.w.rebuild([o])
            self.w.commit()
        elif action == "toggle_trim":
            self.w._edit_inside(rec, "trim_off" if rec["trim"] else "trim_on")
        elif action == "connect":
            if not rec["hidden"] and QMessageBox.question(
                    self, "Simulator & Optimierer", "Dieser Verbindungsfaden würde später nicht "
                    "überstickt und bliebe sichtbar. Trotzdem verbinden?",
                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            self.w._edit_inside(rec, "connect")
        self.refresh(keep=rec)

    def edit_order(self, action):
        """Teil nach dem gewählten Sprung früher/später sticken oder umdrehen."""
        rec = self.selected_record()
        if rec is None:
            return
        between = rec["kind"] == "between" and not rec["same"]
        target_b = rec["b"]
        try:
            if between:
                if action == "reverse":
                    raise ValueError("Umdrehen geht nur für Teile innerhalb eines Objekts")
                msg = jumps.move_object(self.w.doc, rec["obj_b"], -1 if action == "earlier" else 1)
                self.w.sync_items([rec["obj_b"]])
                self.auto_order.blockSignals(True)
                self.auto_order.setChecked(False)
                self.auto_order.blockSignals(False)
            else:
                if not self._convert_needed([rec]):
                    return
                r2 = self.w._refind_jump(rec) or rec
                if action == "reverse":
                    msg = jumps.reverse_run(self.w.doc, r2)
                else:
                    msg = jumps.move_run(self.w.doc, r2, -1 if action == "earlier" else 1)
                self.w.sync_items([r2["obj"]])
        except ValueError as e:
            self.sel_label.setText(str(e))
            return
        self.w.commit()
        self.refresh()
        # den Sprung wählen, der jetzt zu diesem Teil führt
        hit = next((r for r in self.records if abs(r["b"][0] - target_b[0]) < 0.05
                    and abs(r["b"][1] - target_b[1]) < 0.05), None)
        if action == "reverse" or hit is None:
            hit = None
        if hit is not None:
            self.select_record(hit["index"])
        self.sel_label.setText(msg)

    def set_auto_order(self, on):
        self.w.doc.order_mode = "auto" if on else "manual"
        self.w.commit()
        self.refresh()
        self.sel_label.setText("Reihenfolge: automatisch auf kürzestem Weg." if on else
                               "Reihenfolge: wie in der Objektliste bzw. von Hand festgelegt.")

    def view_clicked(self, x, y, button, gpos):
        idx = self.hit_jump(x, y, 7 / self.view.zoom())
        if idx is not None:
            self.select_record(idx)
            if button == Qt.RightButton:
                m = QMenu(self)
                rec = self.records[idx]
                if rec["kind"] == "between" and not rec["same"]:
                    for i in range(self.mode.count()):
                        a = m.addAction(self.mode.itemText(i),
                                        lambda i=i: (self.mode.setCurrentIndex(i), self.edit_selected("mode")))
                        a.setCheckable(True)
                        a.setChecked(self.mode.currentIndex() == i)
                else:
                    m.addAction(self.btn_trim.text(), lambda: self.edit_selected("toggle_trim"))
                    m.addAction(self.btn_connect.text(), lambda: self.edit_selected("connect"))
                m.addSeparator()
                m.addAction("Teil danach früher sticken", lambda: self.edit_order("earlier"))
                m.addAction("Teil danach später sticken", lambda: self.edit_order("later"))
                if not (rec["kind"] == "between" and not rec["same"]):
                    m.addAction("Teil danach umdrehen", lambda: self.edit_order("reverse"))
                m.exec(gpos)
            return
        hit = jumps.find_stitch(self.w.doc, x, y, 6 / self.view.zoom())
        if hit is None:
            return
        m = QMenu(self)
        head = m.addAction(f"Stich {hit['length']:.1f} mm in »{self.w.doc.find(hit['obj']).name}«")
        head.setEnabled(False)
        m.addSeparator()
        for trim, label in ((False, "In Sprung umwandeln"), (True, "In Sprung mit Fadenschnitt umwandeln")):
            m.addAction(label, lambda t=trim: (jumps.split_stitch(self.w.doc, hit, t),
                                               self.w.sync_items([hit["obj"]]), self.w.commit(),
                                               self.refresh()))
        m.exec(gpos)

    def _convert_needed(self, recs):
        objs = {r["obj"] for r in recs if r["kind"] == "inside" or r.get("same")}
        gen = [self.w.doc.find(o) for o in objs if self.w.doc.find(o).kind != "stitches"]
        if not gen:
            return True
        names = ", ".join(f"»{o.name}«" for o in gen[:4]) + (" …" if len(gen) > 4 else "")
        if QMessageBox.question(self, "Simulator & Optimierer",
                                f"Dafür werden {len(gen)} berechnete Form(en) in feste Stiche "
                                f"umgewandelt ({names}). Fortfahren?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return False
        for o in gen:
            jumps.to_stitches(o, self.w.doc.optimize)
        return True

    def bulk(self, kind, limit):
        recs = self.records
        if kind == "untrim":
            target = [r for r in recs if r["trim"] and r["length"] < limit]
        elif kind == "trim":
            target = [r for r in recs if not r["trim"] and r["length"] >= limit]
        else:
            target = [r for r in recs if r["hidden"]]
        if not target:
            self.sel_label.setText("Keine passenden Sprünge gefunden.")
            return
        if not self._convert_needed(target):
            return
        # nach der Umwandlung neu ermitteln und von hinten nach vorn bearbeiten
        fresh = [self.w._refind_jump(r) or r for r in target]
        fresh.sort(key=lambda r: (r["obj"], r.get("block", -1), r.get("gs", -1)), reverse=True)
        changed, skipped = set(), 0
        for r in fresh:
            try:
                if r["kind"] == "between" and not r["same"]:
                    jumps.set_trim_mode(self.w.doc, r, "never" if kind == "untrim" else "always")
                elif kind == "connect":
                    jumps.connect(self.w.doc, r)
                else:
                    jumps.set_trim(self.w.doc, r, kind == "trim")
                changed.add(r["obj"])
            except ValueError:
                skipped += 1
        self.w.sync_items(list(changed))
        self.w.commit()
        self.refresh()
        self.sel_label.setText(f"{len(fresh) - skipped} Sprünge geändert." +
                               (f" {skipped} ließen sich nicht ändern." if skipped else ""))

    def auto_optimize(self):
        before = self._stats()
        if not self.w.doc.optimize:
            self.w.prefs.set("optimize_export", True)
            self.w.doc.optimize = True
        if any(o.kind == "stitches" for o in self.w.doc.objects):
            self.w.optimize_jumps([o for o in self.w.doc.objects if o.kind == "stitches"])
        else:
            self.w.commit()
        self.refresh()
        after = self._stats()
        self.sel_label.setText(f"Automatisch optimiert: Sprünge {before['jumps']} → {after['jumps']}, "
                               f"Schnitte {before['trims']} → {after['trims']}.")

    def undo(self):
        self.w.undo()
        self.refresh()

    def redo(self):
        self.w.redo()
        self.refresh()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            self.toggle()
            return
        if ev.key() in (Qt.Key_Right, Qt.Key_Left) and ev.modifiers() & Qt.ControlModifier:
            self.step_jump(1 if ev.key() == Qt.Key_Right else -1)
            return
        super().keyPressEvent(ev)

    def done(self, r):
        self.timer.stop()
        super().done(r)
