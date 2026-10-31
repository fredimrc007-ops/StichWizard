"""An Maschine senden: Design im Format der eingestellten Stickmaschine direkt auf einen
USB-Stick (wird automatisch erkannt) oder in einen gemerkten Ordner (z. B. Netzlaufwerk der
Maschine) speichern – auf Wunsch mit Arbeitsblatt und anschließendem Auswerfen (Linux)."""
import os
import re
import shutil
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout)

from . import fileio, icons


# --------------------------------------------------------------- Laufwerke
def _free(path):
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def is_removable(dev, sys_root="/sys"):
    """Ist die Gerätedatei (z. B. /dev/sdb1) ein Wechseldatenträger? Linux: laut /sys –
    »removable« gesetzt, am USB angeschlossen oder SD-Karte (mmcblk). Interne Platten nie."""
    name = os.path.basename(dev or "")
    if not name:
        return False
    part = os.path.join(sys_root, "class", "block", name)
    disk = name
    if os.path.exists(os.path.join(part, "partition")):
        disk = os.path.basename(os.path.dirname(os.path.realpath(part)))
    base = os.path.join(sys_root, "block", disk)
    try:
        with open(os.path.join(base, "removable"), encoding="ascii") as f:
            if f.read().strip() == "1":
                return True
    except OSError:
        return False
    real = os.path.realpath(base)
    return "/usb" in real or disk.startswith("mmcblk")


def removable_drives():
    """[(pfad, name)] eingesteckter Wechseldatenträger (USB-Sticks, SD-Karten)."""
    out = []
    if sys.platform == "win32":
        import ctypes
        import string
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                root = f"{letter}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 2:      # DRIVE_REMOVABLE
                    buf = ctypes.create_unicode_buffer(261)
                    ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 261, None, None,
                                                                 None, None, 0)
                    out.append((root, f"{buf.value or 'USB-Stick'} ({letter}:)"))
        return out
    if sys.platform == "darwin":
        for name in sorted(os.listdir("/Volumes")) if os.path.isdir("/Volumes") else []:
            p = os.path.join("/Volumes", name)
            if os.path.ismount(p) and os.path.realpath(p) != "/":
                out.append((p, name))
        return out
    # Linux: per udisks eingehängte Datenträger unter /run/media/<nutzer> bzw. /media
    seen = set()
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            mounts = [line.split() for line in f]
    except OSError:
        mounts = []
    for dev, mnt, fs, *_ in mounts:
        mnt = mnt.encode().decode("unicode_escape")
        if (mnt.startswith("/run/media/") or mnt.startswith("/media/")) and \
                fs in ("vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "ext4", "msdos") and \
                is_removable(dev):
            if mnt not in seen:
                seen.add(mnt)
                out.append((mnt, os.path.basename(mnt) or mnt))
    return out


def device_of(path):
    """Gerätedatei (z. B. /dev/sdb1) zu einem Einhängepunkt (Linux) oder None."""
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for line in f:
                dev, mnt = line.split()[:2]
                if mnt.encode().decode("unicode_escape") == os.path.realpath(path):
                    return dev
    except OSError:
        pass
    return None


def eject(path):
    """Datenträger aushängen und ausschalten (Linux, udisksctl). (ok, meldung)"""
    dev = device_of(path)
    exe = shutil.which("udisksctl")
    if not dev or not exe or not is_removable(dev):     # interne Platten nie aushängen
        return False, "Bitte den Stick über die Dateiverwaltung auswerfen."
    try:
        r = subprocess.run([exe, "unmount", "-b", dev], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip() or "Aushängen fehlgeschlagen."
        disk = re.sub(r"p?\d+$", "", dev)
        subprocess.run([exe, "power-off", "-b", disk], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return True, "Der Stick kann jetzt abgezogen werden."


def safe_name(name, short=False):
    """Dateiname ohne Zeichen, die Stickmaschinen nicht mögen (Umlaute, Leerzeichen …)."""
    tr = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
                        "ß": "ss", " ": "_"})
    s = re.sub(r"[^A-Za-z0-9_\-]", "", (name or "Design").translate(tr)) or "Design"
    return s[:8].upper() if short else s[:40]


def send(doc, folder, name, fmt, optimize=False, worksheet=None):
    """Design als <name>.<fmt> nach folder schreiben (vorhandene Datei wird ersetzt).
    worksheet: Funktion(pfad), die zusätzlich das Arbeitsblatt (PDF) schreibt. Liefert den Pfad."""
    path = os.path.join(folder, f"{name}.{fmt}")
    fileio.export_file(doc, path, optimize)
    if worksheet:
        worksheet(os.path.join(folder, f"{name}.pdf"))
    if hasattr(os, "sync"):
        os.sync()                    # alles auf den Stick schreiben, bevor er abgezogen wird
    return path


# ------------------------------------------------------------------ Fenster
class SendDialog(QDialog):
    def __init__(self, parent, machine, design_name, folders=(), stats=None):
        super().__init__(parent)
        self.setWindowTitle("An Maschine senden")
        self.setWindowIcon(icons.icon("usb"))
        self.setMinimumWidth(560)
        self.extra = [f for f in folders if os.path.isdir(f)]
        v = QVBoxLayout(self)
        intro = QLabel(f"Maschine: <b>{machine['name']}</b> · Format <b>{machine['format'].upper()}"
                       f"</b>" + (f"<br>{stats}" if stats else ""))
        intro.setWordWrap(True)
        v.addWidget(intro)
        v.addWidget(QLabel("Ziel (USB-Stick wird automatisch erkannt):"))
        self.list = QListWidget()
        self.list.setMinimumHeight(140)
        v.addWidget(self.list)
        row = QHBoxLayout()
        ref = QPushButton("Neu suchen")
        ref.clicked.connect(self.refresh)
        add = QPushButton("Anderer Ordner …")
        add.setToolTip("z. B. Netzwerkordner der Stickmaschine – wird gemerkt")
        add.clicked.connect(self.add_folder)
        row.addWidget(ref)
        row.addWidget(add)
        row.addStretch()
        v.addLayout(row)
        form = QFormLayout()
        self.name = QLineEdit(safe_name(design_name))
        self.short = QCheckBox("Kurzer Dateiname (8 Zeichen, für ältere Maschinen)")
        self.short.toggled.connect(lambda on: self.name.setText(safe_name(self.name.text(), on)))
        self.fmt = QComboBox()
        for label, ext in fileio.EXPORT_FORMATS:
            if ext in ("pes", "dst", "jef", "exp", "vp3", "xxx", "u01", "pec", "tbf"):
                self.fmt.addItem(f"{label} (.{ext})", ext)
        self.fmt.setCurrentIndex(max(0, self.fmt.findData(machine["format"])))
        self.sheet = QCheckBox("Arbeitsblatt (PDF) mitkopieren")
        self.eject = QCheckBox("Danach Stick auswerfen")
        self.eject.setChecked(sys.platform.startswith("linux") and bool(shutil.which("udisksctl")))
        self.eject.setEnabled(sys.platform.startswith("linux") and bool(shutil.which("udisksctl")))
        form.addRow("Dateiname", self.name)
        form.addRow("", self.short)
        form.addRow("Format", self.fmt)
        form.addRow("", self.sheet)
        form.addRow("", self.eject)
        v.addLayout(form)
        self.hint = QLabel()
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        v.addWidget(self.hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Senden")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.ok_btn = bb.button(QDialogButtonBox.Ok)
        v.addWidget(bb)
        self.list.currentRowChanged.connect(self._update)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for path, label in removable_drives():
            self._add(path, f"USB-Stick:  {label}", True)
        for f in self.extra:
            self._add(f, f"Ordner:  {f}", False)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._update()

    def _add(self, path, label, removable):
        free = _free(path)
        it = QListWidgetItem(label + (f"   –   {free / 1e9:.1f} GB frei" if free is not None else ""))
        it.setData(Qt.UserRole, (path, removable))
        self.list.addItem(it)

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Zielordner wählen")
        if d:
            self.add_path(d)

    def add_path(self, d):
        if d not in self.extra:
            self.extra.append(d)
        self.refresh()
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole)[0] == d:
                self.list.setCurrentRow(i)

    def target(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else (None, False)

    def _update(self):
        path, removable = self.target()
        self.ok_btn.setEnabled(bool(path))
        self.eject.setVisible(bool(removable))
        if not self.list.count():
            self.hint.setText("Kein USB-Stick gefunden – Stick einstecken und »Neu suchen« "
                              "drücken, oder einen anderen Ordner wählen.")
        else:
            self.hint.setText("")
