"""Eigene Bibliothek: Elemente und ganze Designs speichern und wiederverwenden.

Jedes Element ist eine Datei <kategorie>/<name>.stichlib (JSON) im Benutzerordner:
{"name", "category", "objects": [objekt-dicts, Mitte bei (0, 0)], "thumb": PNG als base64}.
"""
import base64
import json
import os
import re

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QStandardPaths

EXT = ".stichlib"


def root():
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or \
        os.path.expanduser("~/.local/share/StickStudio")
    d = os.path.join(base, "bibliothek")
    os.makedirs(d, exist_ok=True)
    return d


def safe(name):
    s = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", str(name)).strip().strip(".")
    return re.sub(r"\s+", " ", s)[:60] or "Element"


def categories():
    r = root()
    return sorted(d for d in os.listdir(r) if os.path.isdir(os.path.join(r, d)))


def items(category=None, query=""):
    """[(pfad, name, kategorie)] sortiert; optional nach Kategorie und Suchtext gefiltert."""
    out = []
    q = query.lower().strip()
    for cat in categories():
        if category and cat != category:
            continue
        d = os.path.join(root(), cat)
        for fn in sorted(os.listdir(d)):
            if fn.endswith(EXT):
                name = fn[:-len(EXT)]
                if not q or q in name.lower() or q in cat.lower():
                    out.append((os.path.join(d, fn), name, cat))
    return out


def _thumb_png(objs, size=160):
    from .model import Document
    from .render import render_document
    d = Document()
    d.objects = objs
    d.apply_layer_flags()
    st = d.stats()
    scale = max(1.0, min(20.0, size / max(st["width"], st["height"], 1)))
    img = render_document(d, scale, margin=1, transparent=True)
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return base64.b64encode(bytes(buf.data())).decode("ascii")


def save(name, category, objs):
    """Objekte als Bibliothekselement speichern (Mitte der Auswahl wird (0, 0)).
    Liefert den Dateipfad. Gleichnamige Elemente werden überschrieben."""
    from .model import EmbObject
    copies = [EmbObject.from_dict(o.to_dict()) for o in objs]
    xs, ys = [], []
    for o in copies:
        for _, b in o.world_blocks():
            xs.extend(p[0] for p in b)
            ys.extend(p[1] for p in b)
    cx = (min(xs) + max(xs)) / 2 if xs else 0.0
    cy = (min(ys) + max(ys)) / 2 if ys else 0.0
    for o in copies:
        o.x -= cx
        o.y -= cy
        o.layer = None
        o.locked = False
    data = {"name": name, "category": category,
            "objects": [o.to_dict() for o in copies], "thumb": _thumb_png(copies)}
    d = os.path.join(root(), safe(category))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, safe(name) + EXT)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_objects(path, x=0.0, y=0.0):
    """Element als neue Objekte (neue IDs, eigene Gruppen) um (x, y)."""
    import uuid
    from .model import EmbObject
    data = load(path)
    objs = [EmbObject.from_dict(d).clone() for d in data.get("objects", [])]
    groups = {}
    for o in objs:
        o.x += x
        o.y += y
        if o.group:
            o.group = groups.setdefault(o.group, uuid.uuid4().hex[:8])
    return objs


def thumbnail(path):
    from PySide6.QtGui import QImage
    try:
        b = load(path).get("thumb", "")
        img = QImage()
        img.loadFromData(QByteArray.fromBase64(b.encode("ascii")), "PNG")
        return img
    except (OSError, ValueError):
        return QImage()


def delete(path):
    os.remove(path)
    d = os.path.dirname(path)
    if not os.listdir(d):
        os.rmdir(d)


def rename(path, new_name=None, new_category=None):
    data = load(path)
    name = new_name or data.get("name") or os.path.basename(path)[:-len(EXT)]
    cat = new_category or data.get("category") or os.path.basename(os.path.dirname(path))
    data["name"], data["category"] = name, cat
    d = os.path.join(root(), safe(cat))
    os.makedirs(d, exist_ok=True)
    target = os.path.join(d, safe(name) + EXT)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f)
    if os.path.abspath(target) != os.path.abspath(path):
        delete(path)
    return target
