"""Wiederverwendbare Bedienelemente: Zahlenfeld mit Schieberegler und zoombare Bildansicht."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (QDoubleSpinBox, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView,
                               QHBoxLayout, QLabel, QSizePolicy, QSlider, QSpinBox, QToolButton,
                               QVBoxLayout, QWidget)


class _Slider(QSlider):
    """Mausrad nur mit Fokus – sonst scrollt man in Seitenleisten versehentlich Werte weg."""

    def wheelEvent(self, ev):
        if self.hasFocus():
            super().wheelEvent(ev)
        else:
            ev.ignore()


class SliderSpin(QWidget):
    """Schieberegler plus Zahlenfeld (beide synchron). Verhält sich nach außen wie ein
    QDoubleSpinBox bzw. QSpinBox (value, setValue, valueChanged, setRange, setSuffix …).
    invert: Regler rechts = kleiner Wert (z. B. »fein« = kleiner Glättungswert).
    ends: Beschriftung links/rechts unter dem Regler, z. B. ("grob", "fein")."""
    valueChanged = Signal(float)

    def __init__(self, lo, hi, step=1.0, decimals=1, suffix="", value=None, integer=False,
                 invert=False, ends=None, parent=None):
        super().__init__(parent)
        self._int = integer
        self._invert = invert
        self._sync = False
        self.slider = _Slider(Qt.Horizontal)
        self.slider.setFocusPolicy(Qt.StrongFocus)
        self.slider.setMinimumWidth(60)
        self.spin = QSpinBox() if integer else QDoubleSpinBox()
        if not integer:
            self.spin.setDecimals(decimals)
        self.spin.setKeyboardTracking(False)
        self.spin.setSuffix(suffix)
        self.spin.setSingleStep(step)
        self.spin.setFixedWidth(104)
        self._res = 1.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.slider, 1)
        row.addWidget(self.spin)
        lay.addLayout(row)
        if ends:
            er = QHBoxLayout()
            er.setContentsMargins(0, 0, 0, 0)
            for i, t in enumerate(ends):
                lab = QLabel(t)
                lab.setObjectName("muted")
                f = lab.font()
                f.setPointSizeF(max(6.5, f.pointSizeF() * 0.85))
                lab.setFont(f)
                er.addWidget(lab)
                if i == 0:
                    er.addStretch()
            er.addSpacing(80)
            lay.addLayout(er)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setRange(lo, hi)
        self.spin.valueChanged.connect(self._from_spin)
        self.slider.valueChanged.connect(self._from_slider)
        if value is not None:
            self.setValue(value)

    # ------------------------------------------------ wie QDoubleSpinBox
    def setRange(self, lo, hi):
        self.spin.setRange(lo, hi)
        dec = 0 if self._int else self.spin.decimals()
        n = int(round((hi - lo) * 10 ** dec))
        while n > 2000:              # Regler: höchstens ~2000 Stufen
            n //= 10
        n = max(1, n)
        self._res = (hi - lo) / n
        self.slider.setRange(0, n)
        self.slider.setPageStep(max(1, n // 10))
        self._to_slider(self.spin.value())

    def setMinimum(self, v):
        self.setRange(v, self.spin.maximum())

    def setMaximum(self, v):
        self.setRange(self.spin.minimum(), v)

    def minimum(self):
        return self.spin.minimum()

    def maximum(self):
        return self.spin.maximum()

    def setDecimals(self, d):
        if not self._int:
            self.spin.setDecimals(d)
            self.setRange(self.spin.minimum(), self.spin.maximum())

    def setSingleStep(self, s):
        self.spin.setSingleStep(s)

    def setSuffix(self, s):
        self.spin.setSuffix(s)

    def setSpecialValueText(self, t):
        self.spin.setSpecialValueText(t)

    def setKeyboardTracking(self, on):
        self.spin.setKeyboardTracking(on)

    def setToolTip(self, t):
        super().setToolTip(t)
        self.slider.setToolTip(t)
        self.spin.setToolTip(t)

    def value(self):
        return self.spin.value()

    def setValue(self, v):
        self.spin.setValue(int(round(v)) if self._int else v)

    def text(self):
        return self.spin.text()

    # ------------------------------------------------ Abgleich
    def _to_slider(self, v):
        k = int(round((v - self.spin.minimum()) / self._res)) if self._res else 0
        if self._invert:
            k = self.slider.maximum() - k
        self._sync = True
        self.slider.setValue(k)
        self._sync = False

    def _from_spin(self, v):
        if not self._sync:
            self._to_slider(v)
        self.valueChanged.emit(float(v))

    def _from_slider(self, k):
        if self._sync:
            return
        if self._invert:
            k = self.slider.maximum() - k
        v = self.spin.minimum() + k * self._res
        self._sync = True
        self.spin.setValue(int(round(v)) if self._int else v)
        self._sync = False


class ZoomView(QGraphicsView):
    """Bildansicht mit Zoom (Mausrad, +/−), Verschieben per Ziehen und Doppelklick = einpassen.
    Zwei Ansichten lassen sich koppeln (gleicher Ausschnitt, z. B. Original und Ergebnis)."""
    viewChanged = Signal()

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.item = QGraphicsPixmapItem()
        self.item.setTransformationMode(Qt.SmoothTransformation)
        self.scene().addItem(self.item)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#EEF0F4"))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setMinimumSize(260, 240)
        self.placeholder = placeholder
        self._fitted = True
        self._partner = None
        self._linking = False
        self.horizontalScrollBar().valueChanged.connect(self._moved)
        self.verticalScrollBar().valueChanged.connect(self._moved)

    # ------------------------------------------------ Inhalt
    def set_image(self, img, keep_view=True):
        """img: QImage oder QPixmap. keep_view: Ausschnitt (relativ) beibehalten."""
        pm = img if isinstance(img, QPixmap) else QPixmap.fromImage(img)
        state = self.view_state() if keep_view and not self._fitted and not self.item.pixmap().isNull() \
            else None
        self.item.setPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()).adjusted(-pm.width(), -pm.height(),
                                                             pm.width(), pm.height()))
        if state is None:
            self.fit()
        else:
            self.apply_state(state)
        self.viewport().update()

    def clear(self, text=None):
        self.item.setPixmap(QPixmap())
        if text is not None:
            self.placeholder = text
        self.viewport().update()

    def has_image(self):
        return not self.item.pixmap().isNull()

    # ------------------------------------------------ Zoom
    def _fit_scale(self):
        pm = self.item.pixmap()
        if pm.isNull():
            return 1.0
        vw, vh = max(1, self.viewport().width() - 16), max(1, self.viewport().height() - 16)
        return min(vw / pm.width(), vh / pm.height())

    def zoom_factor(self):
        """Zoom relativ zur eingepassten Ansicht (1 = ganzes Bild sichtbar)."""
        return self.transform().m11() / self._fit_scale()

    def fit(self):
        pm = self.item.pixmap()
        if pm.isNull():
            return
        s = self._fit_scale()
        self.setTransform(QTransform.fromScale(s, s))
        self.centerOn(self.item.boundingRect().center())
        self._fitted = True
        self.viewChanged.emit()
        self._push()

    def zoom_by(self, f, anchor=None):
        if not self.has_image():
            return
        cur = self.zoom_factor()
        f = max(0.5 / cur, min(40.0 / cur, f))      # zwischen halber und 40-facher Größe
        if anchor is None:
            self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.scale(f, f)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._fitted = abs(self.zoom_factor() - 1) < 1e-3
        self.viewChanged.emit()
        self._push()

    def actual_size(self):
        """1 Bildpixel = 1 Bildschirmpixel."""
        if not self.has_image():
            return
        self.setTransform(QTransform())
        self._fitted = False
        self.viewChanged.emit()
        self._push()

    def wheelEvent(self, ev):
        steps = ev.angleDelta().y() / 120.0
        if steps:
            self.zoom_by(1.25 ** steps, anchor=ev.position())

    def mouseDoubleClickEvent(self, ev):
        self.fit()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self._fitted:
            self.fit()

    def drawForeground(self, p, rect):
        if self.has_image() or not self.placeholder:
            return
        p.save()
        p.resetTransform()
        p.setPen(QColor("#8A90A0"))
        p.drawText(self.viewport().rect(), Qt.AlignCenter | Qt.TextWordWrap, self.placeholder)
        p.restore()

    # ------------------------------------------------ Koppeln
    def view_state(self):
        """(zoom relativ zum Einpassen, Mitte relativ zur Bildgröße)."""
        pm = self.item.pixmap()
        c = self.mapToScene(self.viewport().rect().center())
        w, h = max(1, pm.width()), max(1, pm.height())
        return self.zoom_factor(), c.x() / w, c.y() / h, self._fitted

    def apply_state(self, st):
        z, cx, cy, fitted = st
        pm = self.item.pixmap()
        if pm.isNull():
            return
        self._linking = True
        if fitted:
            self.fit()
        else:
            s = self._fit_scale() * z
            self.setTransform(QTransform.fromScale(s, s))
            self.centerOn(QPointF(cx * pm.width(), cy * pm.height()))
            self._fitted = False
        self._linking = False
        self.viewChanged.emit()

    def link(self, other):
        self._partner, other._partner = other, self

    def unlink(self):
        if self._partner is not None:
            self._partner._partner = None
        self._partner = None

    def _moved(self, *_):
        self._push()

    def _push(self):
        if self._linking or self._partner is None or not self._partner.has_image():
            return
        self._partner._linking = True
        try:
            self._partner.apply_state(self.view_state())
        finally:
            self._partner._linking = False


class ZoomPanel(QWidget):
    """ZoomView mit Titel und Knöpfen (−, +, Einpassen, 100 %) und Zoomanzeige."""

    def __init__(self, title="", placeholder="", parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        bar.addWidget(self.title)
        bar.addStretch()
        self.view = ZoomView(placeholder)
        self.zoom_label = QLabel("")
        self.zoom_label.setObjectName("muted")
        bar.addWidget(self.zoom_label)
        for text, tip, fn in (("−", "Verkleinern (Mausrad)", lambda: self.view.zoom_by(1 / 1.5)),
                              ("+", "Vergrößern (Mausrad)", lambda: self.view.zoom_by(1.5)),
                              ("⤢", "Einpassen (Doppelklick)", self.view.fit),
                              ("1:1", "Originalpixel", self.view.actual_size)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.clicked.connect(fn)
            bar.addWidget(b)
        v.addLayout(bar)
        v.addWidget(self.view, 1)
        self.view.viewChanged.connect(self._show_zoom)

    def _show_zoom(self):
        self.zoom_label.setText(f"{self.view.zoom_factor() * 100:.0f} %" if self.view.has_image() else "")


def ask_values(parent, title, fields, intro=""):
    """Kleiner Eingabedialog. fields: [(schlüssel, beschriftung, art, …)] mit
    art "num": (lo, hi, schritt, nachkommastellen, einheit, wert[, tooltip]),
    "int": (lo, hi, wert[, tooltip]), "check": (wert[, tooltip]), "choice": ([(text, daten)], wert).
    Liefert ein dict oder None (abgebrochen)."""
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                                   QLabel, QVBoxLayout)
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(440)
    v = QVBoxLayout(dlg)
    if intro:
        lab = QLabel(intro)
        lab.setWordWrap(True)
        lab.setObjectName("muted")
        v.addWidget(lab)
    form = QFormLayout()
    widgets = {}
    for key, label, kind, *args in fields:
        tip = ""
        if kind == "num":
            lo, hi, step, dec, unit, val, *rest = args
            w = SliderSpin(lo, hi, step, dec, unit, value=val)
            tip = rest[0] if rest else ""
        elif kind == "int":
            lo, hi, val, *rest = args
            w = SliderSpin(lo, hi, 1, integer=True, value=val)
            tip = rest[0] if rest else ""
        elif kind == "text":
            from PySide6.QtWidgets import QLineEdit
            val, *rest = args
            w = QLineEdit(str(val))
            tip = rest[0] if rest else ""
        elif kind == "editcombo":
            items, val = args
            w = QComboBox()
            w.setEditable(True)
            w.addItems(items)
            w.setCurrentText(val)
        elif kind == "check":
            val, *rest = args
            w = QCheckBox(label)
            w.setChecked(bool(val))
            tip = rest[0] if rest else ""
        else:
            items, val = args
            w = QComboBox()
            for t, d in items:
                w.addItem(t, d)
            w.setCurrentIndex(max(0, w.findData(val)))
        if tip:
            w.setToolTip(tip)
        widgets[key] = (kind, w)
        form.addRow("" if kind == "check" else label, w)
    v.addLayout(form)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    v.addWidget(bb)
    dlg._widgets = widgets
    if ask_values.auto is not None:          # für Tests: Werte vorgeben statt Dialog
        res = {k: _val(kd, w) for k, (kd, w) in widgets.items()}
        res.update(ask_values.auto)
        return res
    if not dlg.exec():
        return None
    return {k: _val(kd, w) for k, (kd, w) in widgets.items()}


def _val(kind, w):
    if kind in ("num", "int"):
        return w.value()
    if kind == "check":
        return w.isChecked()
    if kind == "text":
        return w.text().strip()
    if kind == "editcombo":
        return w.currentText().strip()
    return w.currentData()


ask_values.auto = None
