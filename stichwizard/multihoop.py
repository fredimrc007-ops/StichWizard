"""Mehrfach-Rahmung (Multi-Hooping): ein Design, das größer als der Rahmen ist, in Teile zerlegen.

Wie in Profi-Programmen: Das Design wird in ein Raster aus Rahmungen geteilt, die sich um
`overlap` mm überlappen. Objekte bleiben möglichst ganz (sie kommen in den Teil, in dem ihre Mitte
liegt, wenn sie dort hineinpassen); nur Flächen und Linien, die nicht in einen Rahmen passen,
werden an der Teilung zerschnitten. In jedem Überlappungsstreifen sitzen Passmarken (Kreuze), die
in beiden Nachbarteilen an derselben Stelle gestickt werden – daran richtest du die nächste
Rahmung aus.
"""
import math

from shapely.geometry import LineString, MultiLineString, box

from .model import Document, EmbObject

MARK_COLOR = "#E53935"
MARK_SIZE = 6.0        # Kreuz, Armlänge gesamt in mm


def _world_bounds(o):
    pts = [(x + o.x, y + o.y) for _, sts in o.stitch_blocks() for x, y, _ in sts]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _fits(b, r, tol=0.01):
    return b[0] >= r[0] - tol and b[1] >= r[1] - tol and b[2] <= r[2] + tol and b[3] <= r[3] + tol


def plan(doc, hoop_w, hoop_h, overlap=10.0, margin=2.0):
    """Raster der Rahmungen. Liefert (teile, design_rahmen) – teile: [{"row", "col", "rect"}]
    mit rect = (minx, miny, maxx, maxy) in Weltkoordinaten (Stickfeld der Rahmung)."""
    bounds = [b for b in (_world_bounds(o) for o in doc.objects if o.visible) if b]
    if not bounds:
        return [], None
    dx0, dy0 = min(b[0] for b in bounds), min(b[1] for b in bounds)
    dx1, dy1 = max(b[2] for b in bounds), max(b[3] for b in bounds)
    W, H = dx1 - dx0, dy1 - dy0
    uw, uh = hoop_w - 2 * margin, hoop_h - 2 * margin       # nutzbares Feld je Rahmung
    step_x, step_y = max(5.0, uw - overlap), max(5.0, uh - overlap)
    nx = 1 if W <= uw else 1 + math.ceil((W - uw) / step_x)
    ny = 1 if H <= uh else 1 + math.ceil((H - uh) / step_y)
    # Raster mittig über dem Design
    tw = uw + (nx - 1) * step_x
    th = uh + (ny - 1) * step_y
    ox = (dx0 + dx1) / 2 - tw / 2
    oy = (dy0 + dy1) / 2 - th / 2
    parts = []
    for r in range(ny):
        for c in range(nx):
            x0, y0 = ox + c * step_x, oy + r * step_y
            # Kern: der Bereich, für den diese Rahmung zuständig ist (Teilung in Streifenmitte)
            core = (x0 + (overlap / 2 if c > 0 else -1e6), y0 + (overlap / 2 if r > 0 else -1e6),
                    x0 + uw - (overlap / 2 if c < nx - 1 else -1e6),
                    y0 + uh - (overlap / 2 if r < ny - 1 else -1e6))
            parts.append({"row": r, "col": c, "rect": (x0, y0, x0 + uw, y0 + uh), "core": core})
    return parts, (dx0, dy0, dx1, dy1)


def _shape_from(geom, template, name):
    o = EmbObject("shape", name)
    o.layer = template.layer
    o.set_geometry(geom)
    fill = dict(template.fill)
    if template.kind == "text":            # Schrift wird hier zur Fläche
        fill.setdefault("type", "tatami")
    o.fill = dict(fill, angle=fill.get("angle", 0.0) + template.rot, start=None, end=None, guide=None)
    o.border = dict(template.border)
    o.trim_after = template.trim_after
    return o


def _cut(o, rect):
    """Objekt auf den Rahmen zuschneiden. Liefert (neue Objekte, Warnung oder None)."""
    clip = box(*rect)
    if o.kind in ("shape", "text"):
        g = o.world_geometry()
        if g is None:
            return [], None
        part = g.intersection(clip).buffer(0)
        if part.is_empty or part.area < 0.5:
            return [], None
        warn = (f"»{o.name}« (Schriftzug) wurde an der Teilung zerschnitten und als Fläche "
                "gestickt – besser die Schrift so platzieren, dass sie in eine Rahmung passt."
                if o.kind == "text" else None)
        return [_shape_from(part, o, o.name + " (Teil)")], warn
    if o.kind == "line":
        pts = [o.to_world(p[0], p[1]) for p in o.points]
        if o.closed and pts:
            pts.append(pts[0])
        if len(pts) < 2:
            return [], None
        inter = LineString(pts).intersection(clip)
        lines = list(inter.geoms) if isinstance(inter, MultiLineString) else \
            [inter] if isinstance(inter, LineString) else []
        out = []
        for ln in lines:
            if ln.length < 0.5:
                continue
            n = EmbObject("line", o.name + " (Teil)")
            n.layer = o.layer
            n.set_points(list(ln.coords))
            n.border = dict(o.border)
            n.trim_after = o.trim_after
            out.append(n)
        return out, None
    return [], (f"»{o.name}« ({'Satinsäule' if o.kind == 'satin' else 'Stickdatei'}) passt in "
                "keine Rahmung und lässt sich nicht zerschneiden – größeren Rahmen oder mehr "
                "Überlappung wählen.")


def _mark(x, y, k):
    o = EmbObject("line", f"Passmarke {k}")
    a = MARK_SIZE / 2
    o.set_points([(x - a, y), (x + a, y), (x, y), (x, y - a), (x, y + a)])
    o.border.update(type="run", stitch_len=1.5, color=MARK_COLOR)
    o.trim_after = "always"
    return o


def split(doc, hoop_index, hoop_w, hoop_h, overlap=10.0, marks=True):
    """Design in Teile zerlegen. Liefert [{"row", "col", "rect", "doc", "warnings"}] – jedes doc
    ist auf seine Rahmenmitte verschoben und kann direkt exportiert werden."""
    parts, dbounds = plan(doc, hoop_w, hoop_h, overlap)
    if not parts:
        return []
    for p in parts:
        p["objs"], p["warnings"] = [], []
    # Objekte zuordnen: ganz in den Teil ihrer Mitte, wenn sie hineinpassen
    for o in doc.objects:
        if not o.visible:
            continue
        b = _world_bounds(o)
        if b is None:
            continue
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        home = min(parts, key=lambda p: (0 if (p["core"][0] <= cx <= p["core"][2] and
                                                p["core"][1] <= cy <= p["core"][3]) else 1,
                                          math.hypot(cx - (p["rect"][0] + p["rect"][2]) / 2,
                                                     cy - (p["rect"][1] + p["rect"][3]) / 2)))
        if _fits(b, home["rect"]):
            home["objs"].append(o.clone())
            continue
        fitting = [p for p in parts if _fits(b, p["rect"])]
        if fitting:
            fitting[0]["objs"].append(o.clone())
            continue
        # zu groß: an den Teilungen zerschneiden (0,5 mm Überlappung gegen Lücken)
        done = False
        for p in parts:
            r, w = p["core"], p["rect"]
            pieces, warn = _cut(o, (max(w[0], r[0] - 0.5), max(w[1], r[1] - 0.5),
                                    min(w[2], r[2] + 0.5), min(w[3], r[3] + 0.5)))
            p["objs"].extend(pieces)
            if warn and warn not in p["warnings"]:
                p["warnings"].append(warn)
            done = done or bool(pieces) or warn is not None
        if not done:
            home["objs"].append(o.clone())
    # Passmarken in den Überlappungsstreifen: im vorderen Teil zuletzt gestickt (Bezug), im
    # folgenden Teil zuerst (zum Prüfen der Lage, bevor das Design weitergeht). Wenn Platz ist,
    # liegen sie außerhalb des Designs.
    if marks and len(parts) > 1:
        dx0, dy0, dx1, dy1 = dbounds
        a = MARK_SIZE / 2 + 1.0
        grid = {(p["row"], p["col"]): p for p in parts}
        k = 0

        def place(p, q, pos):
            nonlocal k
            k += 1
            p["objs"].append(_mark(*pos, k))
            q["objs"].insert(0, _mark(*pos, k))
        for (r, c), p in sorted(grid.items()):
            right, below = grid.get((r, c + 1)), grid.get((r + 1, c))
            if right:
                x = (right["rect"][0] + p["rect"][2]) / 2
                top = max(p["rect"][1], right["rect"][1])
                bot = min(p["rect"][3], right["rect"][3])
                place(p, right, (x, max(top + a, min(dy0 - 4, bot - a))))
                place(p, right, (x, min(bot - a, max(dy1 + 4, top + a))))
            if below:
                y = (below["rect"][1] + p["rect"][3]) / 2
                left = max(p["rect"][0], below["rect"][0])
                rgt = min(p["rect"][2], below["rect"][2])
                place(p, below, (max(left + a, min(dx0 - 4, rgt - a)), y))
                place(p, below, (min(rgt - a, max(dx1 + 4, left + a)), y))
    out = []
    for i, p in enumerate(parts):
        r = p["rect"]
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        d = Document()
        d.hoop = hoop_index
        d.fabric, d.fabric_type = doc.fabric, doc.fabric_type
        d.color_sort, d.order_mode = doc.color_sort, doc.order_mode
        d.layers = [dict(L) for L in doc.layers]
        d.active_layer = doc.active_layer
        for o in p["objs"]:
            o.x -= cx
            o.y -= cy
        d.objects = p["objs"]
        d.apply_layer_flags()
        n_real = sum(1 for o in d.objects if not o.name.startswith("Passmarke"))
        out.append({"index": i + 1, "row": p["row"], "col": p["col"], "rect": r, "doc": d,
                    "warnings": p["warnings"], "objects": n_real})
    return [p for p in out if p["objects"] > 0]


# ---------------------------------------------------------------- Fenster
from PySide6.QtCore import QPointF, QRectF, Qt                                   # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap         # noqa: E402
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,       # noqa: E402
                               QFormLayout, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout)

PART_COLORS = ["#1E88E5", "#E53935", "#43A047", "#FB8C00", "#8E24AA", "#00897B", "#6D4C41",
               "#3949AB"]


def overview_image(doc, parts, px=900):
    """Vorschau: ganzes Design mit den Rahmungen (farbige Rechtecke, Nummern, Passmarken)."""
    from .render import render_document
    blocks = doc.machine_blocks()
    pts = [s for _, sts in blocks for s in sts]
    if not pts:
        return QImage()
    rects = [p["rect"] for p in parts] or [(0, 0, 1, 1)]
    minx = min([min(s[0] for s in pts)] + [r[0] for r in rects]) - 6
    miny = min([min(s[1] for s in pts)] + [r[1] for r in rects]) - 6
    maxx = max([max(s[0] for s in pts)] + [r[2] for r in rects]) + 6
    maxy = max([max(s[1] for s in pts)] + [r[3] for r in rects]) + 6
    ppm = px / max(maxx - minx, maxy - miny)
    img = QImage(int((maxx - minx) * ppm), int((maxy - miny) * ppm), QImage.Format_ARGB32)
    img.fill(QColor(doc.fabric))
    design = render_document(doc, ppm, margin=0, transparent=True)
    dminx, dminy = min(s[0] for s in pts), min(s[1] for s in pts)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.drawImage(QPointF((dminx - minx) * ppm, (dminy - miny) * ppm), design)
    f = QFont("DejaVu Sans")
    f.setPixelSize(max(14, int(px / 28)))
    f.setBold(True)
    p.setFont(f)
    for k, part in enumerate(parts):
        col = QColor(PART_COLORS[k % len(PART_COLORS)])
        r = part["rect"]
        rr = QRectF((r[0] - minx) * ppm, (r[1] - miny) * ppm, (r[2] - r[0]) * ppm, (r[3] - r[1]) * ppm)
        fill = QColor(col)
        fill.setAlpha(28)
        p.setBrush(fill)
        p.setPen(QPen(col, 2.5, Qt.DashLine))
        p.drawRect(rr)
        p.setPen(col)
        p.drawText(rr.adjusted(8, 4, 0, 0), Qt.AlignLeft | Qt.AlignTop, str(part["index"]))
        for o in part["doc"].objects:
            if o.name.startswith("Passmarke"):
                cx = (r[0] + r[2]) / 2 + o.x
                cy = (r[1] + r[3]) / 2 + o.y
                p.setPen(QPen(QColor(MARK_COLOR), 2))
                a = MARK_SIZE / 2 * ppm
                q = QPointF((cx - minx) * ppm, (cy - miny) * ppm)
                p.drawLine(q - QPointF(a, 0), q + QPointF(a, 0))
                p.drawLine(q - QPointF(0, a), q + QPointF(0, a))
    p.end()
    return img


class MultiHoopDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        from .controls import SliderSpin
        from .threads import HOOPS, is_cap_hoop
        self.window = window
        self.parts = []
        self.setWindowTitle("Mehrfach-Rahmung")
        self.resize(1080, 700)
        lay = QHBoxLayout(self)
        side = QVBoxLayout()
        intro = QLabel("Das Design ist größer als der Rahmen? Es wird in Rahmungen geteilt, die "
                       "sich überlappen. Objekte bleiben möglichst ganz; rote Kreuze (Passmarken) "
                       "werden in beiden Nachbarteilen an derselben Stelle gestickt – daran legst "
                       "du die nächste Rahmung an.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        side.addWidget(intro)
        form = QFormLayout()
        self.hoop = QComboBox()
        w, h = window.doc.hoop_size
        mc = window.machine()
        best = None
        for i, (name, hw, hh) in enumerate(HOOPS):
            if is_cap_hoop(i):
                continue
            if mc:
                fw, fh = mc["field"]
                if not ((hw <= fw and hh <= fh) or (hw <= fh and hh <= fw)):
                    continue
            self.hoop.addItem(name, i)
            if best is None or hw * hh > HOOPS[best][1] * HOOPS[best][2]:
                best = i
        cur = self.hoop.findData(window.doc.hoop)
        self.hoop.setCurrentIndex(cur if cur >= 0 else max(0, self.hoop.findData(best)))
        self.overlap = SliderSpin(4, 40, 1, 0, " mm")
        self.overlap.setValue(12)
        self.overlap.setToolTip("Wie weit sich zwei Rahmungen überlappen – dort liegen die "
                                "Passmarken. Mehr Überlappung = Objekte bleiben eher ganz.")
        self.marks = QCheckBox("Passmarken sticken")
        self.marks.setChecked(True)
        form.addRow("Rahmen", self.hoop)
        form.addRow("Überlappung", self.overlap)
        form.addRow("", self.marks)
        side.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.RichText)
        side.addWidget(self.info, 1)
        self.export_btn = QPushButton("Teile exportieren …")
        self.export_btn.clicked.connect(lambda: self.export_parts())
        close = QPushButton("Schließen")
        close.clicked.connect(self.reject)
        side.addWidget(self.export_btn)
        side.addWidget(close)
        lay.addLayout(side, 0)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(560, 420)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setStyleSheet("background:#EEF0F4; border-radius:8px;")
        lay.addWidget(self.preview, 1)
        side_w = 320
        for i in range(side.count()):
            it = side.itemAt(i).widget()
            if it is not None:
                it.setMaximumWidth(side_w)
        self.hoop.currentIndexChanged.connect(self.update_plan)
        self.overlap.valueChanged.connect(self.update_plan)
        self.marks.toggled.connect(self.update_plan)
        self.update_plan()

    def hoop_size(self):
        from .threads import HOOPS
        i = self.hoop.currentData()
        return i, HOOPS[i][1], HOOPS[i][2]

    def update_plan(self, *_):
        i, hw, hh = self.hoop_size()
        self.parts = split(self.window.doc, i, hw, hh, self.overlap.value(), self.marks.isChecked())
        n = len(self.parts)
        if not n:
            self.info.setText("Das Design ist leer.")
            self.export_btn.setEnabled(False)
            self.preview.clear()
            return
        self.export_btn.setEnabled(True)
        rows = 1 + max(p["row"] for p in self.parts)
        cols = 1 + max(p["col"] for p in self.parts)
        lines = [f"<b>{n} Rahmung{'en' if n > 1 else ''}</b> ({rows} × {cols}) im Rahmen "
                 f"{hw:g} × {hh:g} mm."]
        if n == 1:
            lines.append("Das Design passt in eine Rahmung – keine Teilung nötig.")
        for p in self.parts:
            st = p["doc"].stats()
            lines.append(f"Teil {p['index']}: {p['objects']} Objekt(e), "
                         f"{st['stitches']:,} Stiche".replace(",", "."))
        warns = [w for p in self.parts for w in p["warnings"]]
        for w in dict.fromkeys(warns):
            lines.append(f"<span style='color:#C62828'>⚠ {w}</span>")
        lines.append("<br>Reihenfolge: Teil 1 sticken, Stoff neu einspannen, Teil 2 an den "
                     "Passmarken ausrichten (Nadel über die Kreuzmitte fahren) usw.")
        self.info.setText("<br>".join(lines))
        img = overview_image(self.window.doc, self.parts)
        if not img.isNull():
            pm = QPixmap.fromImage(img).scaled(self.preview.size() * 0.96, Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation)
            self.preview.setPixmap(pm)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.parts:
            img = overview_image(self.window.doc, self.parts)
            if not img.isNull():
                self.preview.setPixmap(QPixmap.fromImage(img).scaled(
                    self.preview.size() * 0.96, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def export_parts(self, folder=None, fmt=None):
        """Jeden Teil als Stickdatei, dazu ein Übersichtsbild. Liefert die Dateiliste."""
        import os
        from .fileio import export_file
        w = self.window
        if folder is None:
            folder = QFileDialog.getExistingDirectory(self, "Ordner für die Teile", w._dir())
            if not folder:
                return []
        if fmt is None:
            fmt = w.prefs.get("export_format")
            if fmt in (None, "", "last", "zip", "svg"):
                fmt = w.settings.value("lastFormat", "pes") or "pes"
        base = os.path.splitext(os.path.basename(w.path))[0] if w.path else "Design"
        files = []
        for p in self.parts:
            path = os.path.join(folder, f"{base} – Teil {p['index']}.{fmt}")
            export_file(p["doc"], path, optimize=w.prefs.get("optimize_export"))
            files.append(path)
        ov = os.path.join(folder, f"{base} – Übersicht Rahmungen.png")
        overview_image(w.doc, self.parts, 1600).save(ov)
        files.append(ov)
        w.lbl_tip.setText(f"{len(self.parts)} Teile exportiert nach {folder} (Format "
                          f"{fmt.upper()}) – dazu ein Übersichtsbild der Rahmungen.")
        return files
