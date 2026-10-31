"""Import/Export von Maschinenformaten über pyembroidery."""
import os

import pyembroidery as pe

from .engine import JUMP, STITCH, STOP, TRIM, bounds_of
from .model import EmbObject
from .threads import hex_to_rgb, rgb_to_hex, thread_name

EXPORT_FORMATS = [
    ("PES – Brother / Babylock / Deco", "pes"),
    ("DST – Tajima (universell)", "dst"),
    ("JEF – Janome / Elna", "jef"),
    ("EXP – Melco / Bernina", "exp"),
    ("VP3 – Pfaff / Husqvarna Viking", "vp3"),
    ("XXX – Singer / Compucon", "xxx"),
    ("U01 – Barudan", "u01"),
    ("PEC – Brother", "pec"),
    ("TBF – Tajima (mit Farben)", "tbf"),
    ("PMV – Brother Strick-/Stickmaschine", "pmv"),
    ("ZIP – mehrere Formate in einem Archiv", "zip"),
    ("SVG – Vektorgrafik", "svg"),
    ("CSV – Stichliste als Tabelle", "csv"),
    ("TXT – Stichliste als Text", "txt"),
    ("JSON – Stichdaten", "json"),
    ("G-Code – CNC/Plotter", "gcode"),
    ("COL – Farbliste", "col"),
    ("EDR – Farbliste (Embird)", "edr"),
    ("INF – Farbliste (Husqvarna)", "inf"),
]
# Inhalt einer ZIP-Datei (wie Ink/Stitch »ZIP-Export«): die gängigen Maschinenformate und eine
# Farbliste – für Weitergabe an andere oder unbekannte Maschinen
ZIP_FORMATS = ["pes", "dst", "jef", "exp", "vp3", "xxx", "u01", "txt"]

IMPORT_EXTS = ["pes", "dst", "jef", "exp", "vp3", "xxx", "hus", "vip", "sew", "pec",
               "u01", "shv", "10o", "dsb", "dsz", "emd", "exy", "jpx", "ksm", "max",
               "pcs", "pcm", "phb", "phc", "stc", "tap", "zhs", "inb", "tbf", "pmv", "csv",
               "json", "gcode", "100", "bro", "dat", "fxy", "gt", "spx", "stx", "new", "mit",
               "pcd", "pcq", "zxy"]


def build_pattern(doc, blocks=None):
    pattern = pe.EmbPattern()
    first = True
    for color, sts in (blocks if blocks is not None else doc.machine_blocks()):
        r, g, b = hex_to_rgb(color)
        t = pe.EmbThread()
        t.set_color(r, g, b)
        t.description = thread_name(color)
        t.chart = "StichWizard"
        from . import threads
        m = threads.chart_match(color) if threads.CURRENT_CHART else None
        if m:
            t.description, t.catalog_number = m[0], m[1]
            t.brand = t.chart = threads.CURRENT_CHART
        pattern.add_thread(t)
        if not first:
            x, y = sts[0][0], sts[0][1]
            pattern.add_stitch_absolute(pe.COLOR_CHANGE, x * 10, y * 10)
        first = False
        for x, y, f in sts:
            cmd = {STITCH: pe.STITCH, JUMP: pe.JUMP, TRIM: pe.TRIM, STOP: pe.STOP}[f]
            pattern.add_stitch_absolute(cmd, x * 10, y * 10)
    pattern.end()
    return pattern


def export_file(doc, path, optimize=False, progress=None):
    """Exportiert das Design. optimize=True: Sprungstiche vorher optimieren.
    Liefert die Optimierungs-Statistik (oder None)."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    # Optimiert wird nur innerhalb berechneter Formen – Stickdateien und von Hand gesetzte
    # Sprünge/Fadenschnitte bleiben unverändert.
    from .optimize import count_jumps
    blocks, stats = doc.machine_blocks(optimize), None
    if optimize and blocks:
        stats = {"jumps_before": count_jumps(doc.machine_blocks(False)),
                 "jumps_after": count_jumps(blocks)}
    pattern = build_pattern(doc, blocks)
    name = os.path.splitext(os.path.basename(path))[0]
    pattern.metadata("name", name[:16])
    if ext == "zip":
        write_zip(pattern, path, name, ZIP_FORMATS)
        return stats
    _write(pattern, path, ext)
    return stats


# Längster Stich, den alle Exportformate und Maschinen sicher kennen: 12,1 mm (Tajima DST;
# PES, JEF, EXP, VP3, XXX und U01 erlauben 12,7 mm). Kürzer darf die Grenze nicht sein, sonst
# teilt pyembroidery breite Satinstiche (bis »split_len«, Standard 8 mm) beim Export ungefragt.
MAX_STITCH_MM = 12.1


def _write(pattern, path, ext):
    settings = {"max_stitch": round(MAX_STITCH_MM * 10), "max_jump": 120} \
        if ext not in ("svg",) else {}
    if ext == "pes":
        settings["version"] = "6"      # PES 6 speichert Garnname, Nummer und Hersteller
    pe.write(pattern, path, settings)


def write_zip(pattern, path, name, formats):
    """Mehrere Formate in ein ZIP-Archiv schreiben (Dateien heißen wie das Archiv)."""
    import tempfile
    import zipfile
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(path, "w",
                                                               zipfile.ZIP_DEFLATED) as z:
        for ext in formats:
            p = os.path.join(tmp, f"{name}.{ext}")
            _write(pattern, p, ext)
            z.write(p, os.path.basename(p))


# Formate ohne Garnfarben (DST, EXP …): feste, gut unterscheidbare Standardfarben statt Zufall
DEFAULT_COLORS = ["#1A237E", "#C62828", "#2E7D32", "#F9A825", "#6A1B9A", "#00838F", "#EF6C00",
                  "#AD1457", "#4E342E", "#546E7A", "#1565C0", "#9E9D24"]


def import_file(path):
    pattern = pe.read(path)
    if pattern is None:
        raise ValueError("Datei konnte nicht gelesen werden")
    if not pattern.threadlist:
        n = sum(1 for s in pattern.stitches if s[2] & pe.COMMAND_MASK == pe.COLOR_CHANGE) + 1
        for i in range(n):
            t = pe.EmbThread()
            t.set_hex_color(DEFAULT_COLORS[i % len(DEFAULT_COLORS)])
            pattern.add_thread(t)
    blocks = []
    for stitches, thread in pattern.get_as_colorblocks():
        pts = []
        for x, y, cmd in stitches:
            cmd = cmd & pe.COMMAND_MASK
            if cmd == pe.STITCH:
                pts.append([x / 10.0, y / 10.0, STITCH])
            elif cmd == pe.JUMP:
                pts.append([x / 10.0, y / 10.0, JUMP])
            elif cmd == pe.TRIM:
                if pts:
                    pts.append([pts[-1][0], pts[-1][1], TRIM])
            elif cmd == pe.STOP:
                if pts:
                    pts.append([pts[-1][0], pts[-1][1], STOP])
        if not any(p[2] == STITCH for p in pts):
            continue
        if pts:
            pts[0][2] = JUMP
        try:
            col = rgb_to_hex(thread.get_red(), thread.get_green(), thread.get_blue())
        except Exception:
            col = "#333333"
        blocks.append({"color": col, "stitches": pts})
    allpts = [p for b in blocks for p in b["stitches"]]
    minx, miny, maxx, maxy = bounds_of(allpts)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    for b in blocks:
        b["stitches"] = [[x - cx, y - cy, f] for x, y, f in b["stitches"]]
    obj = EmbObject("stitches", os.path.basename(path))
    obj.blocks = blocks
    return obj
