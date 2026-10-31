"""Design-Browser: Vorschaubilder aller Stickdateien eines Ordners."""
import hashlib
import os

from PySide6.QtCore import QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)

from . import fileio, icons
from .model import Document

THUMB = 150
EXTS = set(fileio.IMPORT_EXTS) | {"stickproj"}


def _cache_path(path):
    st = os.stat(path)
    key = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
    d = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation) or ".",
                     "stickstudio", "thumbs_v1")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, key)


def load_design(path):
    """Datei -> Dokument (Projekt oder Stickdatei)."""
    doc = Document()
    if path.lower().endswith(".stickproj"):
        with open(path, encoding="utf-8") as f:
            doc.load_json(f.read())
    else:
        doc.objects = [fileio.import_file(path)]
    return doc


def thumbnail(path):
    """(QImage, info) – zwischengespeichert, solange sich die Datei nicht ändert."""
    from .render import render_document
    cp = _cache_path(path)
    if os.path.exists(cp + ".png") and os.path.exists(cp + ".txt"):
        img = QImage(cp + ".png")
        if not img.isNull():
            return img, open(cp + ".txt", encoding="utf-8").read()
    doc = load_design(path)
    st = doc.stats()
    full = render_document(doc, 3, margin=1, transparent=True)
    img = QImage(THUMB, THUMB, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    from PySide6.QtGui import QPainter
    p = QPainter(img)
    sc = full.scaled(THUMB - 8, THUMB - 8, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawImage((THUMB - sc.width()) // 2, (THUMB - sc.height()) // 2, sc)
    p.end()
    info = (f"{st['width']:.0f} × {st['height']:.0f} mm · {st['stitches']:,} Stiche · "
            f"{st['colors']} Farben").replace(",", ".")
    img.save(cp + ".png")
    with open(cp + ".txt", "w", encoding="utf-8") as f:
        f.write(info)
    return img, info


class DesignBrowser(QDialog):
    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Design-Browser")
        self.setWindowIcon(icons.icon("browse"))
        self.resize(1100, 760)
        self.folder = folder
        self.action = None          # "open" | "insert"
        self.selected_path = None
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.folder_btn = QPushButton()
        self.folder_btn.setIcon(icons.icon("open"))
        self.folder_btn.clicked.connect(self.choose_folder)
        self.sub = QCheckBox("mit Unterordnern")
        self.sub.setChecked(True)
        self.sub.toggled.connect(self.scan)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Dateiname suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        self.sort = QComboBox()
        for label, key in (("Name", "name"), ("Neueste zuerst", "date"), ("Format", "ext")):
            self.sort.addItem(label, key)
        self.sort.currentIndexChanged.connect(self.scan)
        top.addWidget(self.folder_btn)
        top.addWidget(self.sub)
        top.addWidget(self.search, 1)
        top.addWidget(QLabel("Sortieren"))
        top.addWidget(self.sort)
        v.addLayout(top)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(THUMB, THUMB))
        self.list.setGridSize(QSize(THUMB + 40, THUMB + 56))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setWordWrap(True)
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self.on_select)
        self.list.itemDoubleClicked.connect(lambda _: self.finish("open"))
        v.addWidget(self.list, 1)
        self.info = QLabel()
        self.info.setObjectName("muted")
        v.addWidget(self.info)
        bot = QHBoxLayout()
        self.count = QLabel()
        bot.addWidget(self.count, 1)
        b_ins = QPushButton("Ins aktuelle Design einfügen")
        b_ins.clicked.connect(lambda: self.finish("insert"))
        b_open = QPushButton("Öffnen")
        b_open.setObjectName("primary")
        b_open.clicked.connect(lambda: self.finish("open"))
        b_close = QPushButton("Schließen")
        b_close.clicked.connect(self.reject)
        for b in (b_ins, b_open, b_close):
            bot.addWidget(b)
        v.addLayout(bot)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._load_some)
        self.scan()

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Ordner mit Stickdateien", self.folder)
        if d:
            self.folder = d
            self.scan()

    def scan(self):
        self.timer.stop()
        self.list.clear()
        self.items = []
        self.folder_btn.setText("  " + (self.folder or "Ordner wählen …"))
        files = []
        if self.folder and os.path.isdir(self.folder):
            walker = os.walk(self.folder) if self.sub.isChecked() else \
                [(self.folder, [], os.listdir(self.folder))]
            for root, _dirs, names in walker:
                for n in names:
                    if n.rsplit(".", 1)[-1].lower() in EXTS:
                        files.append(os.path.join(root, n))
                if len(files) > 3000:
                    break
        key = self.sort.currentData()
        if key == "date":
            files.sort(key=lambda f: -os.path.getmtime(f))
        elif key == "ext":
            files.sort(key=lambda f: (f.rsplit(".", 1)[-1].lower(), os.path.basename(f).lower()))
        else:
            files.sort(key=lambda f: os.path.basename(f).lower())
        blank = QPixmap(THUMB, THUMB)
        blank.fill(QColor("#F3F5F8"))
        for f in files:
            it = QListWidgetItem(QIcon(blank), os.path.basename(f))
            it.setData(Qt.UserRole, f)
            it.setToolTip(os.path.relpath(f, self.folder))
            self.list.addItem(it)
            self.items.append(it)
        self.count.setText(f"{len(files)} Dateien")
        self._todo = list(self.items)
        self.apply_filter()
        self.timer.start(0)

    def _load_some(self):
        for _ in range(4):
            if not self._todo:
                self.timer.stop()
                return
            it = self._todo.pop(0)
            try:
                img, info = thumbnail(it.data(Qt.UserRole))
                it.setIcon(QIcon(QPixmap.fromImage(img)))
                it.setData(Qt.UserRole + 1, info)
            except Exception as e:
                it.setData(Qt.UserRole + 1, f"Nicht lesbar: {e}")

    def apply_filter(self):
        q = self.search.text().strip().lower()
        for it in self.items:
            it.setHidden(bool(q) and q not in it.text().lower())

    def on_select(self, it, _prev=None):
        if it is None:
            return
        self.selected_path = it.data(Qt.UserRole)
        self.info.setText(f"{self.selected_path}   ·   {it.data(Qt.UserRole + 1) or '…'}")

    def finish(self, action):
        if self.selected_path:
            self.action = action
            self.accept()
