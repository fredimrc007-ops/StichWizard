"""Arbeitsblatt (PDF): Vorschau, Daten, Farbfolge und 1:1-Schablone zum Positionieren."""
import datetime
import math

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPageSize, QPainter, QPdfWriter, QPen

from .engine import STITCH, STOP
from .render import render_document, stitch_lines
from .threads import HOOPS, thread_name

DPI = 600
MM = DPI / 25.4           # Gerätepixel pro mm


def _font(size, bold=False):
    f = QFont("DejaVu Sans")
    f.setPointSizeF(size)
    f.setBold(bold)
    return f


def _text(p, x, y, s, size=10, bold=False, color="#232634"):
    p.setFont(_font(size, bold))
    p.setPen(QColor(color))
    p.drawText(QPointF(x * MM, y * MM), s)


def write_pdf(doc, path, title="Design", chart=None, machine=None):
    """chart: optionale Funktion farbe -> (Garnname, Nummer) für die gewählte Garnkarte.
    machine: Maschinenprofil (machines.py) – dann mit Nadelempfehlung und Nadelplan."""
    blocks = doc.machine_blocks()
    st = doc.stats()
    pdf = QPdfWriter(path)
    pdf.setResolution(DPI)
    pdf.setPageSize(QPageSize(QPageSize.A4))
    pdf.setPageMargins(QMarginsF(0, 0, 0, 0))
    pdf.setTitle(f"StichWizard – {title}")
    pdf.setCreator("StichWizard")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    W, H = 210, 297

    # ------------------------------------------------------- Seite 1: Übersicht
    p.fillRect(QRectF(0, 0, W * MM, 24 * MM), QColor("#232634"))
    _text(p, 12, 11, "StichWizard · Arbeitsblatt", 9, color="#AEB4C4")
    _text(p, 12, 19, title, 16, True, "#FFFFFF")
    _text(p, 150, 11, datetime.date.today().strftime("%d.%m.%Y"), 9, color="#AEB4C4")
    img = render_document(doc, 10, margin=2)
    box = QRectF(12 * MM, 32 * MM, 186 * MM, 120 * MM)
    p.setPen(QPen(QColor("#DDE1E8"), 2))
    p.setBrush(QColor(doc.fabric))
    p.drawRoundedRect(box, 3 * MM, 3 * MM)
    sc = img.scaled(int(box.width() - 8 * MM), int(box.height() - 8 * MM), Qt.KeepAspectRatio,
                    Qt.SmoothTransformation)
    p.drawImage(QPointF(box.center().x() - sc.width() / 2, box.center().y() - sc.height() / 2), sc)
    hrs = int(st["minutes"] // 60)
    mins = int(round(st["minutes"] % 60))
    rows = [("Größe", f"{st['width']:.1f} × {st['height']:.1f} mm"),
            ("Stiche", f"{st['stitches']:,}".replace(",", ".")),
            ("Farben / Farbwechsel", f"{st['colors']} / {max(0, st['colors'] - 1)}"),
            ("Fadenschnitte", str(st["trims"])),
            ("Stopps", str(st.get("stops", 0))),
            ("Stickzeit (ca.)", f"{hrs} h {mins} min" if hrs else f"{mins} min"),
            ("Rahmen", HOOPS[doc.hoop][0])]
    from . import machines
    if machine:
        rows.append(("Maschine", machine["name"]))
    rows.append(("Nadel", machines.needle_for(machine, doc.fabric_type)))
    y = 164
    _text(p, 12, y, "Daten", 12, True)
    for k, v in rows:
        y += 7
        _text(p, 12, y, k, 10, color="#5B6070")
        _text(p, 60, y, v, 10, True)
    y = 164
    multi = bool(machine and machine.get("needles", 1) > 1)
    stops = {i for i, (_, sts) in enumerate(blocks) if any(s[2] == STOP for s in sts)}
    steps, needles, too_many = machines.needle_plan(blocks, machine, stops)
    _text(p, 108, y, "Nadelplan" if multi else "Farbfolge", 12, True)
    # DST, EXP, XXX kennen keinen Stopp-Befehl: dort wird er ein eigener Farbschritt ohne Stiche –
    # der Plan zählt die Schritte dann genau wie das Maschinen-Display
    stop_step = multi and machine.get("format", "") in ("dst", "exp", "xxx", "tbf")
    nr = 0
    for (i, needle, c, stop_after), (_, sts) in zip(steps, blocks):
        y += 7
        if y > 278:
            _text(p, 108, y, "…", 10)
            break
        nr += 1
        p.setPen(QPen(QColor("#00000040"), 1))
        p.setBrush(QColor(c))
        p.drawRoundedRect(QRectF(108 * MM, (y - 4.2) * MM, 5 * MM, 5 * MM), 0.8 * MM, 0.8 * MM)
        n = sum(1 for s in sts if s[2] == STITCH)
        name, number = chart(c) if chart else (thread_name(c), "")
        label = f"{nr}. " + (f"Nadel {needle} – " if multi else "") + name + \
            (f"  ({number})" if number else "")
        _text(p, 116, y, label, 10)
        _text(p, 182, y, f"{n:,}".replace(",", "."), 9, color="#8A90A0")
        if stop_after:
            y += 6
            if stop_step:
                nr += 1
                nxt = steps[i][1] if i < len(steps) else needle
                _text(p, 116, y, f"{nr}. STOPP-Schritt (0 Stiche): Nadel {nxt}, Pause setzen",
                      9, True, "#C62828")
            else:
                _text(p, 116, y, "■ STOPP – Schaum/Stoff auflegen", 9, True, "#C62828")
    if multi:
        y += 8
        lines = (["Mehr Farben als Nadeln –", "Nadeln zwischendurch neu einfädeln!"] if too_many else
                 ["An der Maschine jedem Schritt die Nadel zuordnen"] +
                 (["und beim Stopp-Schritt »Pause/Stopp« setzen."] if stops else []))
        for k, line in enumerate(lines):
            _text(p, 108, min(y, 282) + k * 4.5, line, 8, too_many,
                  "#C62828" if too_many else "#5B6070")
    _text(p, 12, 290, "Die 1:1-Schablone auf den folgenden Seiten in »Tatsächlicher Größe« "
                      "(100 %) drucken.", 8, color="#8A90A0")

    # --------------------------------------------- 1:1-Schablone (ggf. gekachelt)
    xs = [s[0] for _, sts in blocks for s in sts if s[2] == STITCH]
    ys = [s[1] for _, sts in blocks for s in sts if s[2] == STITCH]
    if xs:
        minx, maxx, miny, maxy = min(xs) - 8, max(xs) + 8, min(ys) - 8, max(ys) + 8
        cw, ch = 186, 255                      # nutzbare Fläche pro Seite in mm
        nx = max(1, math.ceil((maxx - minx) / cw))
        ny = max(1, math.ceil((maxy - miny) / ch))
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        for ty in range(ny):
            for tx in range(nx):
                pdf.newPage()
                ox, oy = minx + tx * cw, miny + ty * ch     # Designkoordinate oben links
                if nx == 1:
                    ox = cx - cw / 2                        # auf der Seite mittig
                if ny == 1:
                    oy = cy - ch / 2
                tag = f" – Teil {ty * nx + tx + 1}/{nx * ny}" if nx * ny > 1 else ""
                _text(p, 12, 12, f"1:1-Schablone{tag}", 13, True)
                _text(p, 12, 18, f"{title} · {st['width']:.1f} × {st['height']:.1f} mm · "
                                 "Mitte = Kreuz · zum Kontrollieren: Maßstab unten muss 50 mm messen",
                      8, color="#5B6070")
                p.save()
                p.setClipRect(QRectF(12 * MM, 24 * MM, cw * MM, ch * MM))
                p.translate(12 * MM, 24 * MM)
                p.scale(MM, MM)
                p.translate(-ox, -oy)
                for c, sts in blocks:
                    col = QColor(c)
                    col.setAlpha(150)
                    lines, _ = stitch_lines(sts)
                    pen = QPen(col, 0.25)
                    p.setPen(pen)
                    p.drawLines(lines)
                cross = QPen(QColor("#E53935"), 0.3)
                p.setPen(cross)
                p.drawLine(QPointF(cx - 15, cy), QPointF(cx + 15, cy))
                p.drawLine(QPointF(cx, cy - 15), QPointF(cx, cy + 15))
                dash = QPen(QColor("#E53935"), 0.15, Qt.DashLine)
                p.setPen(dash)
                p.drawLine(QPointF(ox, cy), QPointF(ox + cw, cy))
                p.drawLine(QPointF(cx, oy), QPointF(cx, oy + ch))
                p.restore()
                p.setPen(QPen(QColor("#C9CFD9"), 2, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRect(QRectF(12 * MM, 24 * MM, cw * MM, ch * MM))
                # Kontrollmaßstab 50 mm
                y0 = 285
                p.setPen(QPen(QColor("#232634"), 3))
                p.drawLine(QPointF(12 * MM, y0 * MM), QPointF(62 * MM, y0 * MM))
                for k in range(0, 51, 10):
                    p.drawLine(QPointF((12 + k) * MM, (y0 - 1.5) * MM), QPointF((12 + k) * MM, y0 * MM))
                _text(p, 66, y0 + 1, "50 mm", 8, color="#5B6070")
    p.end()
    return path
