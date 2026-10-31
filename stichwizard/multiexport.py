"""Mehrfach-Export: mehrere Maschinenformate auf einmal, optional als Namensliste
(eine Datei je Name – wie Ink/Stitch »Batch Lettering«)."""
import os
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QProgressDialog,
                               QPushButton, QVBoxLayout, QWidget)

from . import fileio, icons

MACHINE = [(label, ext) for label, ext in fileio.EXPORT_FORMATS if ext not in ("svg", "png", "zip")]


def safe_name(text):
    """Dateinamentauglich machen (Umlaute bleiben, verbotene Zeichen fallen weg)."""
    s = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", text).strip().strip(".")
    return re.sub(r"\s+", " ", s)[:60] or "Name"


class MultiExportDialog(QDialog):
    def __init__(self, doc, folder, base, chosen=("pes", "dst"), parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Mehrfach-Export")
        self.setWindowIcon(icons.icon("multiexport"))
        self.resize(560, 560)
        v = QVBoxLayout(self)
        intro = QLabel("Exportiert das Design in mehrere Maschinenformate auf einmal. Mit einer "
                       "<b>Namensliste</b> entsteht für jeden Namen eine eigene Datei – der "
                       "gewählte Schriftzug wird dabei jeweils ersetzt.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        grid = QGridLayout()
        self.checks = {}
        for i, (label, ext) in enumerate(MACHINE):
            cb = QCheckBox(label)
            cb.setChecked(ext in chosen)
            self.checks[ext] = cb
            grid.addWidget(cb, i // 2, i % 2)
        box = QWidget()
        box.setLayout(grid)
        v.addWidget(box)
        self.as_zip = QCheckBox("Alles in ein ZIP-Archiv packen (eine Datei je Name)")
        self.as_zip.setToolTip("Statt einzelner Dateien entsteht ein ZIP mit allen gewählten "
                               "Formaten – praktisch zum Weitergeben")
        v.addWidget(self.as_zip)
        f = QFormLayout()
        row = QHBoxLayout()
        self.folder = QLineEdit(folder)
        pick = QPushButton("…")
        pick.setFixedWidth(36)
        pick.clicked.connect(self._pick)
        row.addWidget(self.folder, 1)
        row.addWidget(pick)
        rw = QWidget()
        rw.setLayout(row)
        f.addRow("Ordner", rw)
        self.base = QLineEdit(base)
        f.addRow("Dateiname", self.base)
        self.texts = [o for o in doc.objects if o.kind == "text"]
        self.target = QComboBox()
        self.target.addItem("– keine Namensliste –", None)
        for o in self.texts:
            self.target.addItem(f"{o.name}: »{o.text['text'][:30]}«", o.id)
        f.addRow("Schriftzug ersetzen", self.target)
        v.addLayout(f)
        self.names = QPlainTextEdit()
        self.names.setPlaceholderText("Ein Name pro Zeile, z. B.\nAnna\nBen\nClara")
        self.names.setEnabled(False)
        v.addWidget(self.names, 1)
        self.target.currentIndexChanged.connect(
            lambda _: self.names.setEnabled(self.target.currentData() is not None))
        if len(self.texts) == 1:
            self.target.setCurrentIndex(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Exportieren")
        bb.accepted.connect(self.run)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.written = []

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "Zielordner", self.folder.text())
        if d:
            self.folder.setText(d)

    def jobs(self):
        exts = [e for e, cb in self.checks.items() if cb.isChecked()]
        names = [n.strip() for n in self.names.toPlainText().splitlines() if n.strip()]
        tid = self.target.currentData()
        if tid is None or not names:
            names = [None]
        return exts, names, tid

    def run(self, optimize=True):
        exts, names, tid = self.jobs()
        folder = self.folder.text().strip()
        if not exts:
            QMessageBox.information(self, "Mehrfach-Export", "Bitte mindestens ein Format wählen.")
            return
        if not folder or not os.path.isdir(folder):
            QMessageBox.information(self, "Mehrfach-Export", "Bitte einen vorhandenen Ordner wählen.")
            return
        base = safe_name(self.base.text() or "Design")
        target = next((o for o in self.doc.objects if o.id == tid), None)
        original = dict(target.text) if target is not None else None
        total = len(exts) * len(names)
        prog = QProgressDialog("Exportiere …", "Abbrechen", 0, total, self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(300)
        self.written = []
        try:
            k = 0
            for name in names:
                if target is not None and name is not None:
                    target.text = dict(original, text=name)
                stem = base if name is None else f"{base}_{safe_name(name)}"
                if self.as_zip.isChecked():
                    if prog.wasCanceled():
                        raise KeyboardInterrupt
                    path = os.path.join(folder, f"{stem}.zip")
                    pattern = fileio.build_pattern(self.doc, self.doc.machine_blocks(optimize))
                    pattern.metadata("name", stem[:16])
                    fileio.write_zip(pattern, path, stem, exts)
                    self.written.append(path)
                    k += len(exts)
                    prog.setValue(k)
                    QApplication.processEvents()
                    continue
                for ext in exts:
                    if prog.wasCanceled():
                        raise KeyboardInterrupt
                    path = os.path.join(folder, f"{stem}.{ext}")
                    fileio.export_file(self.doc, path, optimize)
                    self.written.append(path)
                    k += 1
                    prog.setValue(k)
                    QApplication.processEvents()
        except KeyboardInterrupt:
            pass
        finally:
            if target is not None:
                target.text = original
            prog.close()
        self.accept()
