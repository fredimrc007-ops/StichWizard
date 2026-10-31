"""Sammelt die Lizenztexte aller mitgelieferten Bestandteile nach stichwizard/licenses/.

Aufruf (die Versionen werden aus dem angegebenen site-packages gelesen – beim Bauen also genau
die mitgelieferten Pakete):
  .venv/bin/python tools/collect_licenses.py [site-packages] [zielordner] [python-version]
Ohne Angaben: site-packages der .venv, Ziel stichwizard/licenses.
"""
import glob
import gzip
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPDX = "/usr/share/licenses/spdx"
# Mitgelieferte Volltexte (SPDX-Kennung -> Datei im Ordner licenses)
TEXTS = {"GPL-3.0-only": "GPL-3.0.txt", "LGPL-3.0-only": "LGPL-3.0.txt",
         "LGPL-2.1-only": "LGPL-2.1.txt", "PSF-2.0": "PSF-2.0.txt",
         "CC-BY-SA-4.0": "CC-BY-SA-4.0.txt", "CC-BY-SA-2.5": "CC-BY-SA-2.5.txt",
         "CC-BY-ND-4.0": "CC-BY-ND-4.0.txt", "CC-BY-NC-SA-4.0": "CC-BY-NC-SA-4.0.txt"}


def site_packages():
    cands = glob.glob(os.path.join(ROOT, ".venv/lib/python*/site-packages"))
    return cands[0] if cands else None


def dist_version(sp, name):
    """Version und dist-info-Ordner – erst im angegebenen site-packages (Paket beim Bauen),
    sonst über das laufende Python (System-Pakete der .venv)."""
    for d in glob.glob(os.path.join(sp or "", "*.dist-info")):
        base = os.path.basename(d)[:-len(".dist-info")]
        pkg, _, ver = base.rpartition("-")
        if pkg.lower().replace("_", "-") == name.lower():
            return ver, d
    try:
        import importlib.metadata as md
        dist = md.distribution(name)
        path = getattr(dist, "_path", None)
        return dist.version, str(path) if path else None
    except Exception:
        return None, None


def copy_dist_licenses(dist, dest, prefix):
    out = []
    if not dist:
        return out
    files = [f for f in glob.glob(os.path.join(dist, "**", "*"), recursive=True)
             if os.path.isfile(f) and re.search(r"LICEN[CS]E|COPYING", os.path.basename(f), re.I)
             and "Qt-Commercial" not in f]          # Qt wird unter LGPL genutzt, nicht kommerziell
    for f in sorted(files):
        rel = os.path.relpath(f, dist)
        for skip in ("licenses" + os.sep, "LICENSES" + os.sep):
            rel = rel[len(skip):] if rel.startswith(skip) else rel
        name = f"{prefix}-" + rel.replace(os.sep, "_")
        if not name.endswith(".txt"):
            name += ".txt"
        shutil.copyfile(f, os.path.join(dest, name))
        if name not in out:
            out.append(name)
    return out


def fonts_file(dest):
    """Alle Stickschriften mit Lizenz und Lizenztext (Namensnennung der Urheber)."""
    rows, nc = [], []
    for f in sorted(glob.glob(os.path.join(ROOT, "stichwizard/fonts/*.json.gz"))):
        try:
            d = json.load(gzip.open(f, "rt", encoding="utf-8"))
        except (OSError, ValueError):
            continue
        lic = str(d.get("license") or "?").replace("SCC-", "CC-")
        if "NC" in lic:
            nc.append(d.get("name", os.path.basename(f)))
        rows.append((d.get("name", os.path.basename(f)), lic, (d.get("license_text") or "").strip()))
    with open(os.path.join(dest, "Stickschriften.txt"), "w", encoding="utf-8") as out:
        out.write("Stickschriften in StichWizard\n=============================\n\n"
                  "Alle Schriften stammen aus der Ink/Stitch-Schriftensammlung\n"
                  "(https://github.com/inkstitch/embroidery-fonts) und wurden in das StichWizard-\n"
                  "Format umgewandelt (technische Formatänderung, Glyphen unverändert).\n\n")
        if nc:
            out.write("NUR NICHT-KOMMERZIELL nutzbar (CC BY-NC-SA 4.0): " + ", ".join(nc) + "\n\n")
        for name, lic, text in rows:
            out.write(f"--- {name}  ({lic})\n{text}\n\n")
    return len(rows), nc


def main():
    sp = sys.argv[1] if len(sys.argv) > 1 else site_packages()
    dest = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "stichwizard", "licenses")
    os.makedirs(dest, exist_ok=True)
    for f in glob.glob(os.path.join(dest, "*")):
        os.remove(f)
    for spdx, name in TEXTS.items():
        src = os.path.join(SPDX, spdx + ".txt")
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dest, name))
        else:
            print("fehlt:", src)
    comps = []
    for pkg, label, lic, home, src in (
            ("PySide6-Essentials", "Qt for Python (PySide6) mit Qt", "LGPL-3.0-only (Qt, PySide6)",
             "https://www.qt.io", "https://download.qt.io/official_releases/QtForPython/ und "
             "https://download.qt.io/official_releases/qt/"),
            ("shiboken6", "Shiboken6", "LGPL-3.0-only", "https://www.qt.io",
             "https://download.qt.io/official_releases/QtForPython/"),
            ("shapely", "Shapely (mit GEOS)", "BSD-3-Clause; GEOS: LGPL-2.1",
             "https://shapely.readthedocs.io", "https://github.com/shapely/shapely, https://libgeos.org"),
            ("numpy", "NumPy", "BSD-3-Clause (mitgelieferte Teile siehe numpy-Lizenzdateien)",
             "https://numpy.org", "https://github.com/numpy/numpy"),
            ("pyembroidery", "pyembroidery", "MIT", "https://github.com/EmbroidePy/pyembroidery",
             "https://github.com/EmbroidePy/pyembroidery"),
            ("pypdf", "pypdf (Illustrator-/PDF-Import)", "BSD-3-Clause", "https://pypdf.readthedocs.io",
             "https://github.com/py-pdf/pypdf")):
        ver, dist = dist_version(sp, pkg)
        if pkg == "PySide6-Essentials" and not ver:
            ver, dist = dist_version(sp, "PySide6")
        files = copy_dist_licenses(dist, dest, pkg.lower())
        comps.append((label, ver or "?", lic, home, src, files))
    n_fonts, nc = fonts_file(dest)
    py = sys.argv[3] if len(sys.argv) > 3 else ".".join(map(str, sys.version_info[:3]))
    with open(os.path.join(dest, "LIZENZEN-DRITTER.txt"), "w", encoding="utf-8") as out:
        out.write("StichWizard – Lizenzen der mitgelieferten Bestandteile\n"
                  "======================================================\n\n"
                  "StichWizard selbst ist für die private Nutzung gedacht. Es verwendet die folgenden\n"
                  "Bestandteile Dritter; deren Lizenzen gelten unverändert. Die Volltexte liegen in\n"
                  "diesem Ordner.\n\n")
        out.write(f"Python {py}\n  Lizenz: PSF-2.0 (PSF-2.0.txt)\n  https://www.python.org\n\n")
        for label, ver, lic, home, src, files in comps:
            out.write(f"{label} {ver}\n  Lizenz: {lic}\n  {home}\n  Quellcode: {src}\n")
            if files:
                out.write("  Lizenzdateien: " + ", ".join(files) + "\n")
            out.write("\n")
        out.write(
            "Hinweis zu Qt/PySide6 und GEOS (LGPL):\n"
            "  Diese Bibliotheken werden unverändert als eigene Dateien mitgeliefert und dynamisch\n"
            "  geladen. Du darfst sie durch eigene, kompatible Versionen ersetzen. Den Quellcode\n"
            "  der verwendeten Versionen gibt es unter den oben genannten Adressen; auf Anfrage\n"
            "  wird er auch direkt zur Verfügung gestellt. Volltexte: LGPL-3.0.txt, LGPL-2.1.txt,\n"
            "  GPL-3.0.txt.\n\n")
        out.write(
            f"Stickschriften ({n_fonts})\n"
            "  Aus der Ink/Stitch-Schriftensammlung, je Schrift eigene Lizenz: SIL Open Font\n"
            "  License 1.1, CC BY-SA 2.5/4.0, CC BY-ND 4.0, CC BY-NC-SA 4.0 oder gemeinfrei.\n"
            "  Urheber und Lizenz jeder Schrift: Stickschriften.txt (und im Auswahlfenster).\n"
            "  https://github.com/inkstitch/embroidery-fonts\n")
        if nc:
            out.write("  Nur nicht-kommerziell nutzbar: " + ", ".join(nc) + "\n")
        out.write("\n")
        out.write(
            "Garnkarten (Farbtabellen der Garnhersteller)\n"
            "  Aus den Paletten des Ink/Stitch-Projekts, GPL-3.0-or-later (GPL-3.0.txt).\n"
            "  https://github.com/inkstitch/inkstitch (Ordner palettes)\n"
            "  Garn- und Herstellernamen sind Marken ihrer Inhaber; sie dienen nur zur Zuordnung.\n\n"
            "Ideen und Arbeitsweisen vieler Stichfunktionen orientieren sich am Open-Source-Projekt\n"
            "Ink/Stitch (https://inkstitch.org) – vielen Dank an alle Beteiligten.\n")
    print(f"Lizenzen nach {dest}: {len(os.listdir(dest))} Dateien, {n_fonts} Schriften")


if __name__ == "__main__":
    main()
