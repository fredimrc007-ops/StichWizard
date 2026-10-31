"""Simulationsvideo: das Design entsteht Stich für Stich als MP4 (über ffmpeg), mit Nadel-
markierung und Infoleiste (Farbe, Stich, Fortschritt). Ohne ffmpeg: Einzelbilder als PNG."""
import os
import shutil
import subprocess

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from .engine import STITCH
from .render import paint_thread, stitch_lines

SIZES = [("HD 1280 × 720", (1280, 720)), ("Full HD 1920 × 1080", (1920, 1080)),
         ("Quadratisch 1080 × 1080 (Instagram)", (1080, 1080)),
         ("Hochformat 1080 × 1920 (Reels/Stories)", (1080, 1920)), ("Klein 640 × 360", (640, 360))]


def ffmpeg():
    return shutil.which("ffmpeg")


def _codec(exe):
    try:
        out = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True,
                             timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    if " libx264 " in out:
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"]
    return ["-c:v", "mpeg4", "-q:v", "3", "-pix_fmt", "yuv420p"]


class _Frames:
    """Erzeugt die Bilder nacheinander: der Stoff bleibt stehen, neue Stiche kommen dazu."""

    def __init__(self, doc, size, show_hoop=True, info=True, thread_name=None):
        self.doc = doc
        self.W, self.H = size
        self.info = info
        self.thread_name = thread_name or (lambda c: c)
        self.blocks = [(c, s) for c, s in doc.machine_blocks() if s]
        self.total = sum(len(s) for _, s in self.blocks)
        self.stitches = sum(1 for _, s in self.blocks for p in s if p[2] == STITCH)
        bar = int(self.H * 0.09) if info else 0
        self.bar = bar
        xs = [p[0] for _, s in self.blocks for p in s] or [0.0]
        ys = [p[1] for _, s in self.blocks for p in s] or [0.0]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        if show_hoop:
            hw, hh = doc.hoop_size
            x0, y0, x1, y1 = min(x0, -hw / 2), min(y0, -hh / 2), max(x1, hw / 2), max(y1, hh / 2)
        aw, ah = self.W * 0.9, (self.H - bar) * 0.9
        self.scale = min(aw / max(1.0, x1 - x0), ah / max(1.0, y1 - y0))
        self.ox = self.W / 2 - (x0 + x1) / 2 * self.scale
        self.oy = (self.H - bar) / 2 - (y0 + y1) / 2 * self.scale
        self.base = QImage(self.W, self.H, QImage.Format_ARGB32)
        self.base.fill(QColor(doc.fabric))
        if show_hoop:
            p = QPainter(self.base)
            p.setRenderHint(QPainter.Antialiasing)
            hw, hh = doc.hoop_size
            p.setPen(QPen(QColor(0, 0, 0, 60), max(1.0, self.scale * 0.6), Qt.DashLine))
            p.drawRoundedRect(QRectF(self.ox - hw / 2 * self.scale, self.oy - hh / 2 * self.scale,
                                     hw * self.scale, hh * self.scale), 8, 8)
            p.end()
        self.done = 0               # so viele Punkte sind schon gezeichnet
        self.needle = None
        self.cur_block = 0
        self.stitched = 0

    def advance(self, target):
        """Punkte bis `target` (über alle Farbblöcke gezählt) auf das Grundbild zeichnen."""
        target = min(self.total, target)
        if target <= self.done:
            return
        p = QPainter(self.base)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.ox, self.oy)
        p.scale(self.scale, self.scale)
        start = 0
        for bi, (col, sts) in enumerate(self.blocks):
            end = start + len(sts)
            a, b = max(self.done, start), min(target, end)
            if a < b:
                part = sts[max(0, a - start - 1):b - start]
                lines, _ = stitch_lines(part)
                if lines:
                    paint_thread(p, lines, col, "real", self.scale)
                self.needle = part[-1][:2]
                self.cur_block = bi
                self.stitched += sum(1 for q in sts[a - start:b - start] if q[2] == STITCH)
            start = end
        p.end()
        self.done = target

    def frame(self, final=False):
        img = self.base.copy()
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        if self.needle and not final:
            x, y = self.ox + self.needle[0] * self.scale, self.oy + self.needle[1] * self.scale
            r = max(4.0, self.W / 160)
            p.setPen(QPen(QColor("#FFFFFF"), r * 0.4))
            p.setBrush(QColor("#E53935"))
            p.drawEllipse(QPointF(x, y), r, r)
        if self.bar:
            top = self.H - self.bar
            p.fillRect(QRectF(0, top, self.W, self.bar), QColor(30, 32, 40, 235))
            frac = self.done / max(1, self.total)
            p.fillRect(QRectF(0, top, self.W * frac, self.bar * 0.08), QColor("#26C6DA"))
            col = self.blocks[self.cur_block][0] if self.blocks else "#000000"
            sw = self.bar * 0.45
            p.setPen(QPen(QColor("#FFFFFF"), 1))
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(self.bar * 0.3, top + (self.bar - sw) / 2 + 2, sw, sw), 4, 4)
            f = QFont("DejaVu Sans")
            f.setPixelSize(max(10, int(self.bar * 0.3)))
            p.setFont(f)
            p.setPen(QColor("#FFFFFF"))
            txt = (f"Farbe {self.cur_block + 1}/{len(self.blocks)} · {self.thread_name(col)}"
                   f"   ·   Stich {self.stitched:,}/{self.stitches:,}".replace(",", "."))
            p.drawText(QRectF(self.bar * 0.45 + sw, top + 2, self.W, self.bar), Qt.AlignVCenter, txt)
        p.end()
        return img


def export_video(doc, path, seconds=20.0, size=(1280, 720), fps=30, show_hoop=True, info=True,
                 hold=2.0, progress=None, thread_name=None):
    """Video schreiben. progress(f) → False bricht ab. Liefert die Zahl der Bilder.
    Ohne ffmpeg: Fehler RuntimeError (dann export_frames benutzen)."""
    exe = ffmpeg()
    if not exe:
        raise RuntimeError("ffmpeg wurde nicht gefunden.")
    W, H = (int(size[0]) // 2) * 2, (int(size[1]) // 2) * 2
    fr = _Frames(doc, (W, H), show_hoop, info, thread_name)
    if not fr.total:
        raise ValueError("Das Design hat keine Stiche.")
    n_draw = max(1, int(seconds * fps))
    n_hold = int(hold * fps)
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", *_codec(exe), path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    count = 0
    try:
        for k in range(1, n_draw + n_hold + 1):
            fr.advance(round(fr.total * min(1.0, k / n_draw)))
            img = fr.frame(final=k > n_draw)
            proc.stdin.write(bytes(img.constBits())[:W * H * 4] if img.bytesPerLine() == W * 4
                             else _packed(img))
            count += 1
            if progress and progress(k / (n_draw + n_hold)) is False:
                raise InterruptedError("abgebrochen")
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait(timeout=600) != 0:
            raise RuntimeError(f"ffmpeg meldet einen Fehler:\n{err[-800:]}")
    except BaseException:
        proc.kill()
        proc.wait()
        if os.path.exists(path):
            os.remove(path)
        raise
    return count


def _packed(img):
    bpl, w = img.bytesPerLine(), img.width() * 4
    raw = bytes(img.constBits())
    return b"".join(raw[y * bpl:y * bpl + w] for y in range(img.height()))


def export_frames(doc, folder, seconds=10.0, size=(1280, 720), fps=10, show_hoop=True, info=True,
                  progress=None, thread_name=None):
    """Ersatz ohne ffmpeg: Einzelbilder bild_0001.png … in einen Ordner."""
    os.makedirs(folder, exist_ok=True)
    fr = _Frames(doc, size, show_hoop, info, thread_name)
    if not fr.total:
        raise ValueError("Das Design hat keine Stiche.")
    n = max(1, int(seconds * fps))
    for k in range(1, n + 1):
        fr.advance(round(fr.total * k / n))
        fr.frame(final=k == n).save(os.path.join(folder, f"bild_{k:04d}.png"))
        if progress and progress(k / n) is False:
            break
    return n


def final_image(doc, size=(1280, 720), show_hoop=True, info=True):
    """Letztes Bild (für Vorschau/Test)."""
    fr = _Frames(doc, size, show_hoop, info)
    fr.advance(fr.total)
    return fr.frame(final=True)
