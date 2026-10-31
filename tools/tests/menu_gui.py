"""Test (1.15): Menüband nach Arbeitsschritten, Vorlagen, Karo-Raster, Farbschema."""
import os
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
from stichwizard import render, style, templates
from stichwizard.mainwindow import MainWindow, RibbonButton
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
r = w.ribbon

# ---- Reiter in Arbeitsschritt-Reihenfolge
names = [r.tabText(i) for i in range(r.count())]
want = ["Start", "Erstellen", "Verzieren", "Schrift", "Nachzeichnen", "Form bearbeiten",
        "Anordnen", "Sticken", "Optimieren", "Ansicht", "Export", "Hilfe"]
check(f"Reiter in Arbeitsschritt-Reihenfolge {names}", names == want)

def where(act):
    """Reiter, in denen eine Aktion als Knopf liegt."""
    out = []
    for i in range(r.count()):
        if any(b.defaultAction() is act for b in r.widget(i).findChildren(RibbonButton)):
            out.append(r.tabText(i))
    return out

for act, tab in ((w.a_templates, "Erstellen"), (w.a_library, "Erstellen"),
                 (w.tool_actions["pen"], "Erstellen"), (w.a_digit, "Erstellen"),
                 (w.tool_actions["text"], "Schrift"), (w.a_textpath, "Schrift"),
                 (w.a_fontshop, "Schrift"), (w.a_centerline, "Schrift"), (w.a_convert, "Schrift"),
                 (w.a_copygrid, "Form bearbeiten"), (w.a_grow, "Form bearbeiten"),
                 (w.a_layers, "Anordnen"), (w.a_lock, "Anordnen"), (w.a_intersect, "Anordnen"),
                 (w.a_tosatin, "Sticken"), (w.a_puff, "Sticken"), (w.a_knockdown, "Sticken"),
                 (w.a_guided, "Sticken"), (w.a_startpt, "Sticken"),
                 (w.a_overlap, "Optimieren"), (w.a_optjumps, "Optimieren"),
                 (w.a_import, "Start"), (w.a_ith, "Erstellen"), (w.a_encore, "Verzieren"),
                 (w.a_ornaments, "Verzieren"), (w.a_spiro, "Verzieren"),
                 (w.a_stones, "Verzieren"), (w.a_ith_pdf, "Export"), (w.a_cross, "Verzieren"),
                 (w.a_quilt, "Verzieren"), (w.a_family, "Verzieren"),
                 (w.a_paint, "Verzieren"), (w.a_stitchedit, "Optimieren"),
                 (w.tool_actions["sketch"], "Verzieren"), (w.a_send, "Export"),
                 (w.a_video, "Export")):
    check(f"{act.iconText().replace(chr(10), ' ')} genau in »{tab}«", where(act) == [tab])
check("Simulator im Reiter Optimieren", where(w.a_sim) == ["Optimieren"])
check("Produktvorschau in Ansicht und Export", where(w.a_mockup) == ["Ansicht", "Export"])
check("Text in Form in Verzieren und Schrift", where(w.a_wordsculpt) == ["Verzieren", "Schrift"])
check("Druckvorlage in Verzieren und Export", where(w.a_printsheet) == ["Verzieren", "Export"])
check("Strass-Schablone in Verzieren und Export",
      where(w.a_stones_export) == ["Verzieren", "Export"])

over = []
for i in range(r.count()):
    r.setCurrentIndex(i); QTest.qWait(10)
    sa = r.currentWidget(); sa = sa if isinstance(sa, QScrollArea) else sa.findChild(QScrollArea)
    if sa.widget().sizeHint().width() > 1440:
        over.append((r.tabText(i), sa.widget().sizeHint().width()))
check(f"Alle Reiter passen in 1440 Pixel {over}", not over)
r.setCurrentIndex(0)

# ---- Design-Vorlagen
keys = [t[0] for t in templates.TEMPLATES]
check(f"12 Vorlagen ({len(keys)})", len(keys) == 12 and len(set(keys)) == 12)
bad = []
for k in keys:
    objs = templates.build(k)
    if not objs:
        bad.append(k)
check(f"Jede Vorlage erzeugt Objekte {bad}", not bad)

# ---- Raster im Rahmen: Karos statt Gewebe
w.opts.show_grid = True
w.hoop_item.update(); QTest.qWait(30)
img = w.canvas.viewport().grab().toImage()
check("Rahmen mit Raster wird gezeichnet", not img.isNull())

# ---- Farbschema / Akzentfarbe
check("Mehrere Akzentfarben", len(style.ACCENTS) >= 5 and "violett" in style.ACCENTS)
w.set_theme("dark", "violett")
check("Akzent violett aktiv", style.CURRENT_ACCENT == "violett")
check("Akzent wirkt im Stylesheet", style.ACCENTS["violett"][1].lower() in w.styleSheet().lower())
check("Dunkles Schema gespeichert", w.prefs.get("ui_theme") == "dark" and w.prefs.get("ui_accent") == "violett")
w.set_theme("light", "tuerkis")
check("Zurück zu Hell/Türkis", style.CURRENT_ACCENT == "tuerkis" and w.prefs.get("ui_theme") == "light")
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
