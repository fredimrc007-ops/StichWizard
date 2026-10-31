"""Beispieldateien für die Tests (nur lesend). Ordner per Umgebungsvariable STICK_TESTDATA
änderbar; Standard ist der Sticken-Ordner in der Nextcloud."""
import os

STICK_DIR = os.environ.get("STICK_TESTDATA",
                           "/home/weidi/Nextcloud/04 Hobby & Werkstatt/Sticken")
HAFNEREI_DST = os.path.join(STICK_DIR, "Stickdateien", "Die Hafnerei 6cm.dst")
_PROJ = os.path.join(STICK_DIR, "Stickstudio Entwürfe", "Die Hafnerei 6cm.stickproj")


def hafnerei_project(out_dir):
    """Pfad zum Hafnerei-Projekt. Gibt es das Original nicht mehr, wird im Testordner eines
    aus der DST-Datei angelegt (das Original wird nie verändert)."""
    if os.path.exists(_PROJ):
        return _PROJ
    path = os.path.join(out_dir, "Die Hafnerei 6cm.stickproj")
    if not os.path.exists(path):
        from stichwizard import fileio
        from stichwizard.model import Document
        doc = Document()
        doc.objects = [fileio.import_file(HAFNEREI_DST)]
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc.to_json(True))
    return path


def jumpy_dst(out_dir):
    """Eigene Test-Stickdatei mit vielen Sprüngen und Fadenschnitten, wie eine schlecht
    digitalisierte Datei: aneinanderstoßende Kacheln, kreuz und quer gestickt (dazu eine
    zweite Farbe). Der Sprung-Optimierer kann die Teile neu ordnen und Verbindungen unter
    später gestickten Kacheln führen. Wird im Testordner angelegt."""
    import random
    path = os.path.join(out_dir, "sprungtest.dst")
    if os.path.exists(path):
        return path
    from shapely.geometry import Point, box
    from stichwizard import fileio
    from stichwizard.model import Document, EmbObject
    doc = Document()
    doc.color_sort = False
    rnd = random.Random(4)
    for color, y0 in (("#1565C0", -30), ("#C62828", 12)):
        cells = [(x, y) for x in range(8) for y in range(3)]
        rnd.shuffle(cells)
        for x, y in cells:
            o = EmbObject("shape", f"Kachel {x}/{y}")
            cx, cy = -28 + x * 8, y0 + y * 8
            o.set_geometry(box(cx - 4.3, cy - 4.3, cx + 4.3, cy + 4.3) if (x + y) % 3
                           else Point(cx, cy).buffer(4.6))
            o.fill.update(type="tatami", color=color, underlay=False)
            o.trim_after = "always"
            doc.objects.append(o)
    fileio.export_file(doc, path)
    return path
