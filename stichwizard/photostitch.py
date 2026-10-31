"""Fotostich: Fotos als Stickerei.

Zwei Arten wie in gängiger Sticksoftware:
- Farbig: das Foto wird auf wenige Garnfarben reduziert; jede Farbe wird als feine Fläche gestickt,
  helle Farben zuerst, dunkle Details obendrauf, jede Lage mit eigener Stichrichtung.
- Einfarbig (Linienschraffur): parallele Zickzacklinien, deren Ausschlag mit der Bildhelligkeit
  wächst – dunkle Stellen werden dicht, helle bleiben fast frei.
"""
import math

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)
from shapely.ops import unary_union

from . import icons
from .autodigitize import IMAGE_EXTS, load_image, load_rgba, mask_to_geom, quantize
from .engine import JUMP, STITCH, TRIM, polygons_of
from .model import EmbObject
from .threads import nearest_thread

PHOTO_RES = 0.25    # mm pro Pixel beim Abtasten


def _hex(c):
    return "#%02X%02X%02X" % tuple(int(max(0, min(255, v))) for v in c[:3])


def _luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _snap(col):
    """Auf die gewählte Garnkarte setzen (falls eine gewählt ist)."""
    from . import threads
    if threads.CURRENT_CHART:
        return threads.chart_match(col)[2].upper()
    return col


def color_photo(img, width_mm, n_colors=8, detail=0.4, remove_bg=False):
    """Farbiger Fotostich -> Formen (hell zuerst, dunkel obendrauf)."""
    arr = load_rgba(img, width_mm / PHOTO_RES)
    h, w = arr.shape[:2]
    px = width_mm / w
    labels, centers = quantize(arr, n_colors)
    bg = -2
    if remove_bg:
        border = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
        border = border[border >= 0]
        if len(border):
            vals, counts = np.unique(border, return_counts=True)
            if counts.max() > len(border) * 0.35:
                bg = int(vals[np.argmax(counts)])
    tolerance = max(0.05, detail * 0.25)
    min_area = max(0.25, detail * detail)
    layers = []
    for i, c in enumerate(centers):
        if i == bg:
            continue
        geom = mask_to_geom(labels == i, px, tolerance)
        if geom is None:
            continue
        polys = [p for p in polygons_of(geom) if p.area >= min_area]
        if polys:
            layers.append((_luma(c), c, unary_union(polys)))
    layers.sort(key=lambda t: -t[0])          # hell zuerst, dunkle Details obendrauf
    angles = [45, 135, 0, 90, 22, 112, 67, 157]
    objs = []
    for k, (_, c, g) in enumerate(layers):
        col = _snap(_hex(c))
        name, _ = nearest_thread(col)
        o = EmbObject("shape", f"Fotostich {k + 1} ({name})")
        # leicht überlappen, damit zwischen den Farben keine Lücken bleiben
        o.set_geometry(g.buffer(0.25, join_style=2) if k else g)
        o.fill.update(type="tatami", color=col, angle=angles[k % len(angles)], density=0.42,
                      stitch_len=2.2, underlay=k == 0, pull=0.0, pattern="standard")
        o.border["type"] = "none"
        objs.append(o)
    return objs


def hatch_photo(img, width_mm, spacing=1.4, angle=0.0, color="#1A1A1A", invert=False,
                contrast=1.3, threshold=0.10):
    """Einfarbige Linienschraffur -> ein Stichobjekt (Zickzacklinien, Ausschlag = Dunkelheit)."""
    arr = load_rgba(img, width_mm / PHOTO_RES)
    h, w = arr.shape[:2]
    px = width_mm / w
    rgb = arr[..., :3].astype(np.float32) / 255.0
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    dark = 1.0 - lum if not invert else lum
    dark[arr[..., 3] < 128] = 0.0
    dark = np.clip((dark - 0.5) * contrast + 0.5, 0, 1)          # Kontrast um die Mitte
    W, H = w * px, h * px
    cx, cy = W / 2, H / 2
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    R = math.hypot(W, H) / 2 + spacing
    base = max(0.5, min(1.2, spacing * 0.7))          # halbe Zickzack-Wellenlänge (hell)

    def sample(u, v):
        x = cx + u * ca - v * sa
        y = cy + u * sa + v * ca
        i, j = int(y / px), int(x / px)
        if 0 <= i < h and 0 <= j < w:
            return float(dark[i, j]), x, y, True
        return 0.0, x, y, False

    runs = []
    row = 0
    v = -R + spacing / 2
    while v < R:
        sgn = -1 if row % 2 else 1
        u = -R * sgn
        cur = []
        quiet = 0.0
        k = 0
        while (u < R) if sgn > 0 else (u > -R):
            # Dunkelheit über die Reihenbreite mitteln
            d = sum(sample(u, v + dv)[0] for dv in (-spacing * 0.3, 0, spacing * 0.3)) / 3
            _, x0, y0, inside = sample(u, v)
            step = max(0.3, base * (1 - 0.6 * d))       # dunkel: engere Zacken
            if not inside or d < threshold:
                quiet += step
                if cur and quiet > 1.2:
                    runs.append(cur)
                    cur = []
                u += step * sgn
                continue
            quiet = 0.0
            amp = d * spacing * 0.48 * (1 if k % 2 else -1)   # dunkel: weiter Ausschlag
            cur.append((x0 - amp * sa - cx, y0 + amp * ca - cy))
            k += 1
            u += step * sgn
        if len(cur) > 1:
            runs.append(cur)
        v += spacing
        row += 1
    sts, last = [], None
    for run in runs:
        if len(run) < 2:
            continue
        if last is not None:
            d = math.hypot(run[0][0] - last[0], run[0][1] - last[1])
            if d > 3.0:
                sts.append([last[0], last[1], TRIM])
            sts.append([run[0][0], run[0][1], JUMP])
        else:
            sts.append([run[0][0], run[0][1], JUMP])
        sts.extend([x, y, STITCH] for x, y in run)
        last = run[-1]
    if not sts:
        return []
    o = EmbObject("stitches", "Fotostich (Linien)")
    o.blocks = [{"color": color, "stitches": sts}]
    return [o]


class PhotoStitchDialog(QDialog):
    """Fotostich-Assistent mit Live-Vorschau."""

    def __init__(self, parent=None, hoop_w=130):
        super().__init__(parent)
        self.setWindowTitle("Fotostich – Foto als Stickerei")
        self.setWindowIcon(icons.icon("photo"))
        self.resize(1280, 760)
        self.img = None
        self.objects = []
        from .controls import SliderSpin, ZoomPanel
        root = QHBoxLayout(self)
        views = QHBoxLayout()
        self.orig_panel = ZoomPanel("Foto", "Noch kein Foto gewählt.\n\nJPG, PNG, BMP …")
        self.res_panel = ZoomPanel("Stickerei", "Mausrad = zoomen, Ziehen = verschieben,\n"
                                   "Doppelklick = einpassen")
        self.preview = self.res_panel.view
        self.orig_panel.view.link(self.preview)
        views.addWidget(self.orig_panel, 1)
        views.addWidget(self.res_panel, 1)
        root.addLayout(views, 1)
        side = QWidget()
        side.setFixedWidth(360)
        v = QVBoxLayout(side)
        pick = QPushButton("Foto wählen …")
        pick.setObjectName("primary")
        pick.clicked.connect(self.choose)
        v.addWidget(pick)
        self.file_label = QLabel()
        self.file_label.setObjectName("muted")
        self.file_label.setWordWrap(True)
        v.addWidget(self.file_label)
        f = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem("Farbig – Fotostich (mehrere Garne)", "color")
        self.mode.addItem("Einfarbig – Linienschraffur", "hatch")
        f.addRow("Art", self.mode)
        self.width_mm = SliderSpin(20, 400, 1, 0, " mm", value=min(100.0, hoop_w * 0.8))
        f.addRow("Breite", self.width_mm)
        self.colors = SliderSpin(2, 16, 1, integer=True, value=8)
        f.addRow("Garnfarben", self.colors)
        self.detail = SliderSpin(0.2, 2.0, 0.05, 2, " mm", value=0.4, invert=True,
                                 ends=("glatter", "feiner"))
        self.detail.setToolTip("Detailgenauigkeit: nach rechts = feinere Details (mehr Stiche), "
                               "nach links = ruhigere Flächen")
        f.addRow("Detailgenauigkeit", self.detail)
        self.nobg = QCheckBox("Hintergrund weglassen")
        f.addRow("", self.nobg)
        self.spacing = SliderSpin(0.6, 4.0, 0.1, 1, " mm", value=1.4)
        f.addRow("Linienabstand", self.spacing)
        self.angle = QComboBox()
        for label, a in (("Waagerecht", 0.0), ("Diagonal ↗", -45.0), ("Senkrecht", 90.0),
                         ("Diagonal ↘", 45.0)):
            self.angle.addItem(label, a)
        f.addRow("Richtung", self.angle)
        self.contrast = SliderSpin(0.4, 3.0, 0.1, 1, "", value=1.3)
        self.contrast.setToolTip("Über 1: kräftigere Unterschiede zwischen hellen und dunklen Stellen")
        f.addRow("Kontrast", self.contrast)
        from .widgets import ColorButton
        self.thread = ColorButton("#1A1A1A")
        f.addRow("Garnfarbe", self.thread)
        self.invert = QCheckBox("Hell auf dunklem Stoff (umkehren)")
        f.addRow("", self.invert)
        v.addLayout(f)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setObjectName("muted")
        v.addWidget(self.info)
        hint = QLabel("Tipp: Fotos mit klarem Motiv und gutem Kontrast wirken am besten. Für "
                      "Porträts eignet sich die Linienschraffur, für bunte Motive der farbige "
                      "Fotostich. Vor dem Sticken eine Probe auf einem Stoffrest machen.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        v.addWidget(hint)
        v.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        root.addWidget(side)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.update_preview)
        for wdg in (self.width_mm, self.colors, self.detail, self.spacing, self.contrast):
            wdg.valueChanged.connect(self.timer.start)
        for wdg in (self.mode, self.angle):
            wdg.currentIndexChanged.connect(self.timer.start)
        for wdg in (self.nobg, self.invert):
            wdg.toggled.connect(self.timer.start)
        self.thread.colorChanged.connect(lambda _: self.timer.start())
        self.mode.currentIndexChanged.connect(self._rows)
        self._rows()

    def _rows(self):
        color = self.mode.currentData() == "color"
        form = self.findChild(QFormLayout)
        for wdg in (self.colors, self.detail, self.nobg):
            form.setRowVisible(wdg, color)
        for wdg in (self.spacing, self.angle, self.contrast, self.thread, self.invert):
            form.setRowVisible(wdg, not color)

    def choose(self):
        exts = " ".join(f"*.{e}" for e in IMAGE_EXTS if e not in ("svg", "svgz"))
        path, _ = QFileDialog.getOpenFileName(self, "Foto wählen", "", f"Bilder ({exts})")
        if path:
            self.load(path)

    def load(self, path):
        img = load_image(path, 2000)
        if img is None:
            self.file_label.setText("Das Foto ließ sich nicht öffnen.")
            return
        self.img = img
        import os
        self.file_label.setText(os.path.basename(path))
        self.orig_panel.view.set_image(img, keep_view=False)
        self.update_preview()

    def build(self):
        if self.img is None:
            return []
        if self.mode.currentData() == "color":
            return color_photo(self.img, self.width_mm.value(), int(self.colors.value()),
                               self.detail.value(), self.nobg.isChecked())
        return hatch_photo(self.img, self.width_mm.value(), self.spacing.value(),
                           self.angle.currentData(), self.thread.color, self.invert.isChecked(),
                           self.contrast.value())

    def update_preview(self):
        from PySide6.QtWidgets import QApplication
        from .model import Document
        if self.img is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.objects = self.build()
            d = Document()
            d.objects = self.objects
            d.fabric = "#1A1A1A" if self.invert.isChecked() and self.mode.currentData() == "hatch" \
                else "#FFFFFF"
            if not self.objects:
                self.preview.clear("Keine Stiche – Einstellungen anpassen.")
                return
            st = d.stats()
            from .autodigitize import render_frame
            w_mm = self.width_mm.value()
            self.preview.set_image(render_frame(self.objects, w_mm,
                                                w_mm * self.img.height() / self.img.width(),
                                                bg=d.fabric))
            self.info.setText(f"{st['width']:.0f} × {st['height']:.0f} mm · "
                              f"{st['stitches']:,} Stiche · {st['colors']} Farbe(n) · "
                              f"ca. {st['minutes']:.0f} min".replace(",", "."))
        finally:
            QApplication.restoreOverrideCursor()
