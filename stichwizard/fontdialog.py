"""Auswahlfenster für Stickschriften mit gestickten Vorschaubildern."""
import os

from PySide6.QtCore import QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout)

from . import embfont, icons

FILTERS = [("Alle Stickschriften", None), ("Schreibschrift", "script"), ("Satin", "satin"),
           ("Klein (bis 10 mm)", "small"), ("Groß (ab 25 mm)", "large"),
           ("Mehrfarbig", "multi"), ("Kommerziell nutzbar", "commercial")]
PREVIEW_W, PREVIEW_H = 220, 70


def _cache_dir():
    d = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation) or ".",
                     "stickstudio", "fontprev_v1")
    os.makedirs(d, exist_ok=True)
    return d


def render_preview(fid, text, height_px=PREVIEW_H, width_px=PREVIEW_W, color="#1565C0"):
    """Gestickte Vorschau eines Textes als QImage (transparent)."""
    from .model import Document, EmbObject
    from .render import render_document
    info = next((f for f in embfont.font_index() if f["id"] == fid), None)
    size = max(6.0, min(info["max"] if info else 20, 20))
    blocks, outline = embfont.render(fid, text, size)
    img = QImage(width_px, height_px, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    if not blocks:
        return img
    o = EmbObject("stitches")
    o.blocks = [{"color": c or color, "stitches": [list(p) for p in s]} for c, s in blocks]
    d = Document()
    d.objects = [o]
    full = render_document(d, 4, margin=1, transparent=True)
    p = QPainter(img)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    sc = full.scaled(width_px, height_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawImage((width_px - sc.width()) // 2, (height_px - sc.height()) // 2, sc)
    p.end()
    return img


SHIPPED = os.path.join(embfont.FONT_DIR, "previews")


def cached_preview(fid):
    if fid.startswith(embfont.USER_PREFIX):            # eigene Schriften ändern sich – frisch
        return render_preview(fid, "Abc")
    shipped = os.path.join(SHIPPED, fid + ".png")      # mit dem Programm ausgeliefert
    if os.path.exists(shipped):
        img = QImage(shipped)
        if not img.isNull():
            return img
    path = os.path.join(_cache_dir(), fid + ".png")
    if os.path.exists(path):
        img = QImage(path)
        if not img.isNull():
            return img
    img = render_preview(fid, "Abc")
    img.save(path)
    return img


class EmbFontDialog(QDialog):
    def __init__(self, current="", sample="Abc", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stickschrift wählen")
        self.setWindowIcon(icons.icon("text"))
        self.resize(980, 720)
        self.selected = current
        self.sample = sample.strip() or "Abc"
        self.fonts = embfont.font_index()
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Schrift suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        self.filter = QComboBox()
        for label, key in FILTERS:
            self.filter.addItem(label, key)
        self.filter.currentIndexChanged.connect(self.apply_filter)
        self.only_complete = QCheckBox(f"nur Schriften mit allen Zeichen von »{self.sample[:20]}«")
        self.only_complete.setToolTip("Blendet Schriften aus, denen Zeichen deines Textes fehlen "
                                      "(z. B. Umlaute oder Ziffern)")
        self.only_complete.setChecked(self.sample != "Abc")
        self.only_complete.toggled.connect(self.apply_filter)
        top.addWidget(self.search, 1)
        top.addWidget(self.filter)
        top.addWidget(self.only_complete)
        v.addLayout(top)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(PREVIEW_W, PREVIEW_H))
        self.list.setGridSize(QSize(PREVIEW_W + 24, PREVIEW_H + 44))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self.on_select)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        v.addWidget(self.list, 1)
        self.detail_img = QLabel()
        self.detail_img.setMinimumHeight(110)
        self.detail_img.setAlignment(Qt.AlignCenter)
        self.detail_img.setObjectName("imgBox")
        v.addWidget(self.detail_img)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.RichText)
        v.addWidget(self.detail)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        plain = QPushButton("Computerschrift verwenden")
        plain.setToolTip("Normale Schrift des Computers (wird automatisch digitalisiert)")
        plain.clicked.connect(self.use_plain)
        bb.addButton(plain, QDialogButtonBox.ResetRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.items = {}
        placeholder = QPixmap(PREVIEW_W, PREVIEW_H)
        placeholder.fill(QColor(0, 0, 0, 0))
        for f in self.fonts:
            it = QListWidgetItem(QIcon(placeholder),
                                 f"{f['name']}\n{f['min']:.0f}–{f['max']:.0f} mm")
            it.setData(Qt.UserRole, f["id"])
            it.setToolTip(f"{f['name']} – {f['description']}\nLizenz: {f['license']}")
            self.list.addItem(it)
            self.items[f["id"]] = it
        if current in self.items:
            self.list.setCurrentItem(self.items[current])
        self.apply_filter()
        self._todo = [f["id"] for f in self.fonts]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load_some)
        self._timer.start(0)

    def _load_some(self):
        for _ in range(3):
            if not self._todo:
                self._timer.stop()
                return
            fid = self._todo.pop(0)
            try:
                img = cached_preview(fid)
                self.items[fid].setIcon(QIcon(QPixmap.fromImage(img)))
            except Exception:
                self.items[fid].setText(self.items[fid].text() + "\n(Vorschau fehlt)")

    def apply_filter(self):
        q = self.search.text().strip().lower()
        key = self.filter.currentData()
        for f in self.fonts:
            ok = not q or q in f["name"].lower() or q in f["description"].lower() or \
                any(q in k.lower() for k in f["keywords"])
            kws = " ".join(f["keywords"]).lower()
            if key == "script":
                ok &= "script" in kws or "handwriting" in kws
            elif key == "satin":
                ok &= "satin" in kws
            elif key == "small":
                ok &= f["min"] <= 10
            elif key == "large":
                ok &= f["max"] >= 25
            elif key == "multi":
                ok &= f["colors"] > 1
            elif key == "commercial":
                ok &= not f["noncommercial"]
            if self.only_complete.isChecked():
                ok &= not embfont.missing_chars(f, self.sample)
            self.items[f["id"]].setHidden(not ok)

    def on_select(self, it, _prev=None):
        if it is None:
            return
        fid = it.data(Qt.UserRole)
        self.selected = fid
        f = next(x for x in self.fonts if x["id"] == fid)
        try:
            img = render_preview(fid, self.sample[:30], 110, 900)
            self.detail_img.setPixmap(QPixmap.fromImage(img))
        except Exception:
            self.detail_img.setText("Vorschau nicht möglich")
        nc = (" <span style='color:#C62828'>– nur private, nicht-kommerzielle Nutzung</span>"
              if f["noncommercial"] else "")
        miss = embfont.missing_chars(f, self.sample)
        if miss:
            nc += ("<br><span style='color:#C62828'>Fehlende Zeichen: "
                   + " ".join(miss[:20]) + "</span>")
        self.detail.setText(
            f"<b>{f['name']}</b> – {f['description']}<br>"
            f"Empfohlene Höhe: <b>{f['min']:.0f}–{f['max']:.0f} mm</b> (Großbuchstaben)<br>"
            f"Lizenz: {f['license']}{nc} · aus der Ink/Stitch-Schriftensammlung")

    def use_plain(self):
        self.selected = ""
        self.accept()
