"""Bild-Assistent: wandelt ein Rasterbild automatisch in Stickflächen um."""
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QVBoxLayout)
from shapely.geometry import box
from shapely.ops import unary_union

from .engine import polygons_of
from .model import EmbObject
from .threads import nearest_thread, rgb_to_hex


IMAGE_EXTS = ["svg", "svgz", "png", "jpg", "jpeg", "bmp", "gif", "webp", "ai", "pdf"]


def load_image(path, size=1600):
    """Lädt Rasterbilder direkt; SVG-Vektorgrafiken werden mit transparentem
    Hintergrund in ein hochaufgelöstes Bild gerendert, ebenso AI- und PDF-Dateien."""
    if path.lower().endswith((".ai", ".pdf")):
        from .vectorimport import VectorError, load_as_image
        try:
            return load_as_image(path, size)
        except VectorError:
            return None
    if path.lower().endswith((".svg", ".svgz")):
        from PySide6.QtGui import QPainter
        from PySide6.QtSvg import QSvgRenderer
        r = QSvgRenderer(path)
        if not r.isValid():
            return None
        vb = r.viewBoxF()
        w, h = (vb.width(), vb.height()) if vb.width() > 0 else (r.defaultSize().width(),
                                                                  r.defaultSize().height())
        if w <= 0 or h <= 0:
            w = h = 1
        f = size / max(w, h)
        img = QImage(max(1, int(w * f)), max(1, int(h * f)), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        r.render(p)
        p.end()
        return img
    img = QImage(path)
    return None if img.isNull() else img


TRACE_RES = 0.2   # mm pro Pixel beim Abtasten (feiner als jede Stichbreite)


def load_rgba(img, width_px):
    """Skaliert das Bild auf die Abtastbreite – auch hoch, damit Kanten glatt werden."""
    width_px = max(8, min(2400, int(width_px)))
    h_px = max(1, round(img.height() * width_px / img.width()))
    if h_px > 2400:
        width_px, h_px = max(1, round(width_px * 2400 / h_px)), 2400
    img = img.convertToFormat(QImage.Format_RGBA8888)
    img = img.scaled(width_px, h_px, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine())
    arr = arr[:, :w * 4].reshape(h, w, 4).copy()
    return arr


def kmeans(pixels, k, iters=14, seed=1, drop=True):
    rng = np.random.default_rng(seed)
    sample = pixels if len(pixels) <= 30000 else pixels[rng.choice(len(pixels), 30000, replace=False)]
    # Start: häufige Farben (Kantenrauschen ignorieren), dann jeweils die entfernteste
    q = (sample // 16).astype(np.int32)
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    uniq, inv, counts = np.unique(keys, return_inverse=True, return_counts=True)
    keep = counts >= max(5, len(sample) * 0.003)
    cand = np.array([sample[inv == i].mean(0) for i in np.where(keep)[0]], np.float32)
    cnt = counts[keep]
    if len(cand) == 0:
        cand, cnt = sample[:1], np.array([1])
    centers = [cand[np.argmax(cnt)]]
    while len(centers) < min(k, len(cand)):
        d = np.min([((cand - c) ** 2).sum(1) for c in centers], axis=0)
        centers.append(cand[np.argmax(d * np.sqrt(cnt))])
    centers = np.array(centers, dtype=np.float32)
    for _ in range(iters):
        lab = np.argmin(((sample[:, None, :] - centers[None]) ** 2).sum(2), axis=1)
        for i in range(len(centers)):
            m = sample[lab == i]
            if len(m):
                centers[i] = m.mean(0)
    lab = np.argmin(((sample[:, None, :] - centers[None]) ** 2).sum(2), axis=1)
    share = np.bincount(lab, minlength=len(centers)) / max(1, len(sample))
    return _drop_mixtures(centers, share) if drop else centers[share > 0]


def _drop_mixtures(centers, share):
    """Entfernt Farben, die nur Kantenpixel sind (Mischung zweier echter Farben, z. B. das
    Grau an den Rändern schwarzer Schrift) oder fast gleich wie eine andere Farbe."""
    keep = list(range(len(centers)))
    changed = True
    while changed and len(keep) > 1:
        changed = False
        for i in sorted(keep, key=lambda i: share[i]):
            others = [j for j in keep if j != i]
            c = centers[i]
            # nahezu doppelte Farbe
            if any(np.linalg.norm(c - centers[j]) < 28 and share[j] >= share[i] for j in others):
                keep.remove(i)
                changed = True
                break
            if share[i] > 0.12 or len(others) < 2:
                continue
            # liegt die Farbe auf der Verbindung zweier anderer Farben?
            for a in others:
                for b in others:
                    if a >= b:
                        continue
                    ab = centers[b] - centers[a]
                    L = float(ab @ ab)
                    if L < 1:
                        continue
                    t = float((c - centers[a]) @ ab) / L
                    if 0.08 < t < 0.92 and np.linalg.norm(centers[a] + t * ab - c) < 22:
                        keep.remove(i)
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    return centers[keep]


def quantize(arr, k, drop=True):
    rgb = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3]
    opaque = alpha > 128
    centers = kmeans(rgb[opaque], k, drop=drop)
    labels = np.full(alpha.shape, -1, np.int32)
    flat = rgb[opaque]
    lab = np.empty(len(flat), np.int32)
    for s in range(0, len(flat), 50000):
        part = flat[s:s + 50000]
        lab[s:s + 50000] = np.argmin(((part[:, None, :] - centers[None]) ** 2).sum(2), axis=1)
    labels[opaque] = lab
    return labels, centers


def mask_to_geom(mask, px, tolerance):
    """Pixelmaske -> Polygone. Nur sanftes Schließen kleiner Lücken; dünne Linien
    (z. B. Schriftstriche) bleiben erhalten."""
    h, w = mask.shape
    pad = np.zeros((h, w + 2), np.int8)
    pad[:, 1:-1] = mask
    d = np.diff(pad, axis=1)
    ys, starts = np.nonzero(d == 1)
    _, ends = np.nonzero(d == -1)
    if len(starts) == 0:
        return None
    boxes = [box(s * px, y * px, e * px, (y + 1) * px) for y, s, e in zip(ys, starts, ends)]
    g = unary_union(boxes)
    r = px * 0.5
    g = g.buffer(r, join_style=1).buffer(-r, join_style=1)
    return g.simplify(tolerance)


def _mean_width(poly):
    return 2 * poly.area / max(poly.length, 1e-6)


def digitize(img, n_colors, width_mm, remove_bg=True, detail=0.5):
    """Liefert (objekte, vorschau-QImage). detail = Glättung/Mindestgröße in mm."""
    # feinere Detailgenauigkeit = feiner abtasten (0,08–0,2 mm pro Bildpunkt)
    res = min(TRACE_RES, max(0.08, detail / 2))
    arr = load_rgba(img, width_mm / res)
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
    # Vorschau
    prev = np.zeros((h, w, 4), np.uint8)
    for i, c in enumerate(centers):
        if i == bg:
            continue
        prev[labels == i, :3] = c.astype(np.uint8)
        prev[labels == i, 3] = 255
    qimg = QImage(prev.data, w, h, w * 4, QImage.Format_RGBA8888).copy()

    tolerance = max(0.05, detail * 0.3)
    min_area = max(0.2, detail * detail * 1.5)
    regions = []
    for i, c in enumerate(centers):
        if i == bg:
            continue
        geom = mask_to_geom(labels == i, px, tolerance)
        if geom is None:
            continue
        polys = [p for p in polygons_of(geom) if p.area >= min_area]
        if not polys:
            continue
        regions.append((sum(p.area for p in polys), c, polys))
    regions.sort(key=lambda r: -r[0])
    objs = []
    angles = [45, 135, 0, 90, 30, 120, 60, 150]
    for idx, (_, c, polys) in enumerate(regions):
        name, _ = nearest_thread(rgb_to_hex(*c))
        # Schmale Teile (Schrift, Linien) in Satin, breite Flächen in Tatami
        thin = [p for p in polys if _mean_width(p) < 3.0]
        wide = [p for p in polys if _mean_width(p) >= 3.0]
        for part, kind in ((wide, "tatami"), (thin, "satin")):
            if not part:
                continue
            label = f"Bildfläche {idx + 1} ({name})" + (" – fein" if kind == "satin" and wide else "")
            o = EmbObject("shape", label)
            o.set_geometry(unary_union(part))
            o.fill.update(color=rgb_to_hex(*c), type=kind, pull=0.2,
                          angle=0 if kind == "satin" else angles[idx % len(angles)])
            objs.append(o)
    return objs, qimg


def render_frame(objs, w_mm, h_mm, max_px=3200, bg="#FFFFFF"):
    """Stiche im Bildrahmen (0,0)–(w_mm,h_mm) zeichnen – deckungsgleich mit dem Original,
    so groß, dass beim Hineinzoomen einzelne Stiche erkennbar sind."""
    from PySide6.QtGui import QColor, QPainter
    from .render import paint_thread, stitch_lines
    scale = max(3.0, min(16.0, max_px / max(w_mm, h_mm, 1)))
    img = QImage(max(1, int(w_mm * scale)), max(1, int(h_mm * scale)), QImage.Format_ARGB32)
    img.fill(QColor(bg))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(scale, scale)
    for o in objs:                       # Druckbilder unter den Stichen
        if o.kind == "print":
            from .printapp import paint as paint_print
            paint_print(p, o, world=True)
    for o in objs:
        for color, sts in o.world_blocks():
            lines, _ = stitch_lines(sts)
            paint_thread(p, lines, color, "real", 3.0)
    for o in objs:                       # Strass-Steine obenauf
        if o.kind == "stones":
            from .stones import paint as paint_stones
            paint_stones(p, o, world=True)
    p.end()
    return img


class DigitizeDialog(QDialog):
    """Bild-Assistent: Original und Ergebnis nebeneinander, beide zoombar (gekoppelt)."""

    def __init__(self, parent=None, hoop_w=130):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton
        from .controls import SliderSpin, ZoomPanel
        super().__init__(parent)
        self.setWindowTitle("Bild-Assistent – Automatisch digitalisieren")
        self.resize(1180, 760)
        self.img = None
        self.objects = []
        self._q = None
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.pick = QPushButton("Bild wählen …")
        self.pick.setObjectName("primary")
        self.pick.clicked.connect(self.choose)
        self.file_label = QLabel("Noch kein Bild gewählt (SVG, PNG, JPG, BMP, GIF)")
        self.file_label.setObjectName("muted")
        top.addWidget(self.pick)
        top.addWidget(self.file_label, 1)
        self.linked = QCheckBox("Ansichten koppeln")
        self.linked.setChecked(True)
        self.linked.setToolTip("Original und Ergebnis zeigen beim Zoomen denselben Ausschnitt")
        self.linked.toggled.connect(self._link)
        top.addWidget(self.linked)
        v.addLayout(top)
        mid = QHBoxLayout()
        self.orig_panel = ZoomPanel("Original", "Bild wählen …")
        self.prev_panel = ZoomPanel("Ergebnis", "Hier erscheint das digitalisierte Motiv.\n"
                                    "Mausrad = zoomen, Ziehen = verschieben,\nDoppelklick = einpassen")
        self.orig = self.orig_panel.view
        self.prev = self.prev_panel.view
        self.show_mode = QComboBox()
        self.show_mode.addItem("Flächen", "areas")
        self.show_mode.addItem("Stiche", "stitches")
        self.show_mode.setToolTip("Ergebnis als Farbflächen oder als echte Stiche anzeigen")
        self.show_mode.currentIndexChanged.connect(self._show_result)
        self.prev_panel.layout().itemAt(0).layout().insertWidget(1, self.show_mode)
        mid.addWidget(self.orig_panel, 1)
        mid.addWidget(self.prev_panel, 1)
        v.addLayout(mid, 1)
        form = QFormLayout()
        self.colors = SliderSpin(1, 16, 1, integer=True, value=5)
        self.colors.setToolTip("Anzahl der Garnfarben – jede Farbe wird eine eigene Fläche")
        self.width = SliderSpin(10, 400, 1, 0, " mm", value=min(100, hoop_w - 10))
        self.width.setToolTip("Breite des Motivs im Stickrahmen")
        self.detail = SliderSpin(0.1, 2.0, 0.05, 2, " mm", value=0.4, invert=True,
                                 ends=("glatter", "feiner"))
        self.detail.setToolTip("Detailgenauigkeit: nach rechts = feinere Details und kleinere "
                               "Teile bleiben erhalten (mehr Stiche), nach links = glattere "
                               "Konturen. Der Wert ist die kleinste Strukturgröße in mm.")
        self.bg = QCheckBox("Hintergrund entfernen (häufigste Randfarbe)")
        self.bg.setChecked(True)
        form.addRow("Garnfarben", self.colors)
        form.addRow("Breite im Rahmen", self.width)
        form.addRow("Detailgenauigkeit", self.detail)
        form.addRow("", self.bg)
        self.info = QLabel()
        self.info.setObjectName("muted")
        form.addRow("", self.info)
        v.addLayout(form)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)            # erst rechnen, wenn der Regler ruht
        self.timer.timeout.connect(self.update_preview)
        for w in (self.colors, self.width, self.detail):
            w.valueChanged.connect(self.timer.start)
        self.bg.toggled.connect(self.timer.start)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Digitalisieren")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._link(True)

    def _link(self, on):
        if on:
            self.orig.link(self.prev)
        else:
            self.orig.unlink()

    def choose(self):
        exts = " ".join(f"*.{e} *.{e.upper()}" for e in IMAGE_EXTS)
        path, _ = QFileDialog.getOpenFileName(self, "Bild öffnen", "",
                                              f"Bilder und Vektorgrafiken ({exts})")
        if path:
            self.load(path)

    def load(self, path):
        img = load_image(path)
        if img is None or img.isNull():
            self.file_label.setText("Bild konnte nicht geladen werden.")
            return
        self.img = img
        self.file_label.setText(path)
        self.orig.set_image(img, keep_view=False)
        self.update_preview()

    def update_preview(self):
        if self.img is None:
            return
        self.setCursor(Qt.WaitCursor)
        try:
            self.objects, self._q = digitize(self.img, int(self.colors.value()), self.width.value(),
                                             self.bg.isChecked(), self.detail.value())
            self._show_result()
        finally:
            self.unsetCursor()

    def _show_result(self, *_):
        if self._q is None:
            return
        if self.show_mode.currentData() == "stitches" and self.objects:
            self.prev.set_image(render_frame(self.objects, self.width.value(),
                                             self.width.value() * self._q.height() / self._q.width()))
        else:
            self.prev.set_image(self._q)
        n = sum(1 for o in self.objects for _, b in o.stitch_blocks() for p in b if p[2] == 0) \
            if self.objects else 0
        self.info.setText(f"{len(self.objects)} Fläche(n) · ca. {n:,} Stiche".replace(",", "."))
