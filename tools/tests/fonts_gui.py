"""Test (1.19): Stickbild der Schriften – Stickschriften (Schienen, Ripple, geführte Füllung,
Kreuzstich, Steppstich-Schriften) und Computerschriften als Satin-Lettering."""
import math
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
from stichwizard import embfont, engine
from stichwizard.model import Document, EmbObject
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)


def doc_for(text, size, **kw):
    o = EmbObject("text", "T")
    o.text.update(text=text, size=size, **kw)
    d = Document()
    d.objects = [o]
    return d, o


def flat(d):
    return [s for _, b in d.machine_blocks() for s in b]


def longest(pts):
    return max((engine.dist(a, b) for a, b in zip(pts, pts[1:])
                if a[2] == engine.STITCH and b[2] == engine.STITCH), default=0)


def jumps(pts):
    return sum(1 for a, b in zip(pts, pts[1:]) if b[2] == engine.JUMP and engine.dist(a, b) > 1.6)


font = lambda fid: embfont.load(fid)

# ---- Satinschienen richtig gewählt (Emilio »B«: Stamm war ein Fächer)
d, _ = doc_for("B", 30, embfont="emilio_20_simple")
check(f"Emilio »B«: Stamm als Satinsäule, kein Fächer (längster Stich {longest(flat(d)):.1f} mm)",
      longest(flat(d)) < 8.6)

# ---- Ripple-Linien (Ondulamarif)
types = {e["t"] for g in font("ondulamarif_S")["glyphs"].values() for e in g["e"]}
check("Ondulamarif: Ripple-Linien erkannt", "ripple" in types)
d, _ = doc_for("Abc", 57, embfont="ondulamarif_S")
check(f"Ondulamarif: fast ohne Sprünge ({jumps(flat(d))})", jumps(flat(d)) <= 10)

# ---- geführte Füllung: Führungslinien werden nicht gestickt
els = [e for g in font("barstitch_cloudy")["glyphs"].values() for e in g["e"]]
check("Barstitch Cloudy: geführte Füllung mit Führungslinie",
      any(e["t"] == "fill" and e.get("m") == "guided" and e.get("g") for e in els))
guides = {tuple(map(tuple, e["g"])) for e in els if e.get("g")}
stroked = {tuple(map(tuple, ln)) for e in els if e["t"] in ("run", "zigzag", "manual") for ln in e["lines"]}
check(f"Barstitch Cloudy: keine Führungslinie als Stichlinie ({len(guides)} Führungslinien)",
      guides and not guides & stroked)

# ---- Kreuzstich-Schriften
els = [e for e in font("abecedaire")["glyphs"]["A"]["e"]]
check("Abécédaire: Kreuzstich-Füllung", all(e.get("m") == "cross" for e in els if e["t"] == "fill"))
d, _ = doc_for("Ab", 45, embfont="jersey_15")
check(f"Jersey: Kreuzstich mit wenigen Sprüngen ({jumps(flat(d))})", jumps(flat(d)) <= 6)

# ---- Steppstich-Schrift bleibt Steppstich (Califragilistic)
d, _ = doc_for("Abc", 75, embfont="califragilistic")
st = d.stats()["stitches"]
check(f"Califragilistic: Steppstich statt Zickzack ({st} Stiche)", st < 80000)

# ---- Kurze Stiche in Kurven (Ink/Stitch-Standard) gelten für Schriften
e = next(e for e in font("amitaclo")["glyphs"]["o"]["e"] if e["t"] == "satin")
check("Satin: kurze Stiche in Kurven eingestellt", e.get("si", 0) > 0 and e.get("sd", 0) > 0)

# ---- keine Schrift erzeugt zu lange Stiche (Maschinen: max. 12,1 mm)
bad = []
for f in embfont.font_index():
    size = max(f["min"], min(f["size"], f["max"]))
    d, _ = doc_for("AgB1" if f.get("case") != "upper" else "AGB1", size, embfont=f["id"])
    if longest(flat(d)) > 12.1:
        bad.append(f["id"])
check(f"Alle {len(embfont.font_index())} Stickschriften ohne Stiche über 12,1 mm {bad}", not bad)

# ---- Computerschrift als Satin-Lettering
d1, o1 = doc_for("Abeg", 15, font="DejaVu Serif", bold=False, embfont="")
d0, o0 = doc_for("Abeg", 15, font="DejaVu Serif", bold=False, embfont="", auto_satin=False)
f1, f0 = flat(d1), flat(d0)
check("Computerschrift: Satin-Lettering ist Standard", o1.text.get("auto_satin", True))


def mean_dir_spread(pts):
    """Wie stark die Stichrichtungen streuen – Tatami: fast alle gleich, Satin: dreht mit."""
    angs = [math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi for a, b in zip(pts, pts[1:])
            if a[2] == engine.STITCH and b[2] == engine.STITCH and engine.dist(a, b) > 0.8]
    bins = [0] * 12
    for a in angs:
        bins[min(11, int(a / math.pi * 12))] += 1
    return sum(1 for b in bins if b > len(angs) * 0.04)


check(f"Satin dreht mit der Buchstabenform (Richtungen: Satin {mean_dir_spread(f1)}, "
      f"Tatami {mean_dir_spread(f0)})", mean_dir_spread(f1) > mean_dir_spread(f0) + 3)
check(f"Satin-Lettering ohne zu lange Stiche ({longest(f1):.1f} mm)", longest(f1) < 8.0)
g = o1.shaped_geometry()
pts = [Point for Point in f1 if Point[2] == engine.STITCH]
from shapely.geometry import Point
outside = sum(1 for p in pts if not g.buffer(0.6).contains(Point(p[0], p[1])))
check(f"Stiche bleiben in der Buchstabenform ({outside} außerhalb)", outside <= len(pts) * 0.01)
d2, _ = doc_for("Abeg", 40, font="DejaVu Sans", bold=True, embfont="")
check("Sehr breite Striche: weiter Tatami (große Schrift)", d2.stats()["stitches"] > 0)
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
