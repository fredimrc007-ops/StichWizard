"""Baut die Funktionsanleitung als PDF (docs/StichWizard-Anleitung.pdf).

Vorher die Bilder erzeugen (tools/manual/images.py), dann:
  QT_QPA_PLATFORM=offscreen .venv/bin/python tools/manual/make_manual.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
IMG = os.path.join(ROOT, "build/manual/img")
OUT = os.path.join(ROOT, "docs/StichWizard-Anleitung.pdf")

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QPageLayout, QPageSize, QPainter,
                           QPdfWriter, QPen, QTextDocument)
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from stichwizard import __version__, engine

ACCENT = "#0B8A8A"


def img(name, width=100, caption=""):
    """Bild in voller Breite (Prozent der Textbreite) mit Bildunterschrift."""
    return f'<p align="center" style="margin-bottom:10px">@@IMG|{name}|{width}|{caption}@@</p>'


def tip(text, kind="Tipp"):
    color = {"Tipp": "#E0F2F1", "Achtung": "#FFF3E0", "Beispiel": "#EDE7F6"}[kind]
    label = "▶ Beispiel" if kind == "Beispiel" else kind
    return (f'<table width="100%" cellpadding="8" cellspacing="0" style="background:{color};'
            f' margin-top:4px; margin-bottom:8px"><tr><td><b>{label}:</b> {text}</td></tr></table>')


def table(rows, head=None, widths=None):
    out = ['<table width="100%" cellpadding="5" cellspacing="0" border="0.5" '
           'style="border-color:#C9CED8; margin-bottom:8px">']
    if head:
        out.append("<tr>" + "".join(f'<th bgcolor="#E6F2F2" align="left">{h}</th>' for h in head)
                   + "</tr>")
    for k, r in enumerate(rows):
        bg = ' bgcolor="#F7F8FA"' if k % 2 else ""
        cells = []
        for i, c in enumerate(r):
            wd = f' width="{widths[i]}%"' if widths else ""
            cells.append(f"<td{wd} valign=\"top\">{c}</td>")
        out.append(f"<tr{bg}>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "".join(out)


def ex(title, items, img_name=None):
    """Kleines Beispiel zu einer Funktion: Aufgabe + Schritte."""
    body = f"<b>{title}</b>" + "<ol style=\"margin-top:2px; margin-bottom:0px\">" + \
        "".join(f"<li>{i}</li>" for i in items) + "</ol>"
    return tip(body, "Beispiel")


def with_ex(examples, rows):
    """Tabellenzeilen um eine Spalte »Beispiel« ergänzen."""
    assert len(examples) == len(rows), (len(examples), len(rows))
    return [list(r) + [f"<i>{e}</i>"] for r, e in zip(rows, examples)]


def steps(items):
    return "<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def bullets(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


CH = []          # (nummer, titel, anker)


def h1(title):
    CH.append((len(CH) + 1, title, f"c{len(CH) + 1}"))
    n = len(CH)
    return (f'<h1 style="page-break-before:always"><a name="c{n}"></a>'
            f'<span style="color:{ACCENT}">{n}</span>&nbsp;&nbsp;{title}</h1>')


def h2(t):
    return f"<h2>{t}</h2>"


def h3(t):
    return f"<h3>{t}</h3>"


def p(t):
    return f"<p>{t}</p>"


K = lambda t: f'<span class="key">{t}</span>'       # Taste
M = lambda t: f"<b>{t}</b>"                          # Menüpfad / Knopf

# ===================================================================== Inhalt
parts = []
A = parts.append

# ---------------------------------------------------------------- Titelseite
A(f'''<p align="center" style="margin-top:60px"><img src="img/logo.png" width="{{W38}}"></p>
<p align="center" class="title">StichWizard</p>
<p align="center" class="subtitle">Funktionsanleitung</p>
<p align="center" class="meta">Version {__version__} · Sticksoftware für Linux und Windows</p>
<p align="center" style="margin-top:30px"><img src="img/ex_design.png" width="{{W45}}"></p>
<p align="center" class="meta" style="margin-top:30px">Alle Funktionen mit Beispielen und
Bildern – vom ersten Motiv bis zur fertigen Stickdatei.</p>''')
A('<div style="page-break-before:always"></div><h1>Inhalt</h1>@@TOC@@')

# ---------------------------------------------------------------- 1 Überblick
A(h1("Überblick und erste Schritte"))
A(p("StichWizard ist ein Programm zum Erstellen von Stickmotiven für Stickmaschinen. Du zeichnest "
    "Formen, schreibst Schriftzüge oder wandelst Bilder und Fotos um; das Programm berechnet "
    "daraus die Stiche – mit Unterlage, Zugausgleich, Vernähstichen und einer Stichreihenfolge "
    "mit möglichst wenigen Sprüngen. Am Ende exportierst du eine Datei für deine Maschine "
    "(PES, DST, JEF, EXP, VP3 und viele mehr)."))
A(h2("Starten"))
A(table([
    ["Linux (Flatpak)", "Im Startmenü <b>StichWizard</b> wählen. Installation einer neuen Version: "
     "<tt>flatpak install --user StichWizard-&lt;version&gt;.flatpak</tt>"],
    ["Windows", "<tt>StichWizard-Setup-&lt;version&gt;.exe</tt> ausführen (ohne Administratorrechte). "
     "Danach über Startmenü oder Desktop-Verknüpfung starten."],
    ["Dateien öffnen", "Doppelklick auf eine <tt>.stickproj</tt>-Projektdatei oder "
     f"{M('Start › Öffnen')} ({K('Strg+O')})."],
], widths=[22, 78]))
A(h2("Der Bildschirm"))
A(img("screen_main", 100, "Das Hauptfenster mit einem Beispiel-Design"))
A(table([
    ["<b>Menüband</b> (oben)", "Alle Funktionen, nach Arbeitsschritten in Reiter sortiert wie in Profi-Sticksoftware: Start, "
     "Erstellen, Schrift, Nachzeichnen, Verzieren, Form bearbeiten, Anordnen, Sticken, Optimieren, Export, Ansicht, Hilfe."],
    ["<b>Werkzeugleiste</b> (links)", "Auswahl, Rechteck, Ellipse, Vieleck, Linie, Freihand, "
     "Säulen-Satin, Text, Punkte bearbeiten, Mit Linie verbinden, Radierer, Sprünge bearbeiten, "
     "Bild-Assistent und Simulator."],
    ["<b>Arbeitsfläche</b> (Mitte)", "Der Stickrahmen mit Stoff. Mausrad = zoomen, mittlere Maustaste "
     "oder Leertaste + Ziehen = verschieben."],
    ["<b>Seitenleiste</b> (rechts)", "<i>Eigenschaften</i> des gewählten Objekts, <i>Objekte</i> "
     "(Stickreihenfolge) und <i>Motive</i> (fertige Formen)."],
    ["<b>Garnfarben-Leiste</b> (unten)", "Klick auf eine Farbe färbt die Auswahl. Links die Garnkarte "
     "(z. B. Madeira, Isacord, Brother), rechts »Alle …« für die komplette Karte mit Suche."],
    ["<b>Statuszeile</b>", "Hinweise, Stichzahl, Farben, Größe, Stickzeit, Mausposition, Zoom."],
], widths=[26, 74]))
A(tip("Zu fast jeder Funktion gibt es in dieser Anleitung ein kurzes <b>▶ Beispiel</b> – eine kleine "
      "Aufgabe zum Nachmachen mit konkreten Werten. Probiere sie in einem neuen, leeren Design aus "
      "(Strg+N); mit Strg+Z machst du jeden Schritt wieder rückgängig."))
A(h2("Die Reiter des Menübands"))
for name, title, desc in (
        ("start", "Start", "Datei (auch Stickdatei importieren), Bearbeiten, Rahmen, Stofffarbe und "
         "Stoffart."),
        ("erstellen", "Erstellen", "Formen (auch Stern/Vieleck, Motive), Linien (Bézier-Stift, "
         "Linie, Freihand, Säulen-Satin, Spirale), Automatisch (Bild-Assistent, Fotostich, Umriss aus "
         "Stickdatei), Vorlagen & Bibliothek mit Projekt im Rahmen."),
        ("verzieren", "Verzieren", "Encore (Muster wiederholen), Spirograph, Text in Form, "
         "Kreuzstich-Atelier, Quiltblock, Stammbaum, Sketch, Mal-Atelier, Druckvorlage, Rahmen & "
         "Schnörkel, Strass & Perlen mit Schablone."),
        ("schrift", "Schrift", "Schriftzug, Text an Pfad, Pfad lösen, Hüllform, Schatten, Umwandeln "
         "(in Form, Mittellinie), Schrift-Werkstatt für eigene Stickschriften."),
        ("nachzeichnen", "Nachzeichnen", "Bild als Vorlage einlegen und von Hand nachzeichnen."),
        ("form_bearbeiten", "Form bearbeiten", "Werkzeuge (Punkte, Verbinden, Radierer), Punkte, "
         "Versatz (Erweitern, Schrumpfen, Umriss, Schatten), Kopien im Raster/Kreis."),
        ("anordnen", "Anordnen", "Gruppe, Pfad-Operationen (Kombinieren, Ausschneiden, Schnittmenge, "
         "Exklusion, Teilen, Zerlegen), Ausrichten & Verteilen, Zentrieren, Spiegeln, Ebenen & Sperren."),
        ("sticken", "Sticken", "Satin-Werkzeuge, Linien führen (Redwork, Auto-Route), Füllung "
         "(geführte Füllung), Effekte (3D-Puff, Knockdown), Start & Ende."),
        ("optimieren", "Optimieren", "Verbessern (Überlappung, Kleinteile), Reihenfolge, Sprünge, "
         "Prüfen (Simulator, Dichte), Stich-Editor."),
        ("ansicht", "Ansicht", "Messen (Lineal, Messwerkzeug), Darstellung (Raster-Knopf mit "
         "Einrasten-Menü), Zoom, Produktvorschau, Oberfläche anpassen."),
        ("export", "Export", "Stickmaschine, An Maschine senden, Exportieren, Mehrfach-Export, "
         "Mehrfach-Rahmung, Arbeitsblatt, Bild, Produktvorschau, Schneidedatei, Strass-Schablone, "
         "Projekt-Anleitung, Druckvorlage, Simulationsvideo, Information.")):
    A(f'<p><b>{title}</b> – {desc}</p>')
    A(f'<p align="center"><img src="img/ribbon_{name}.png" width="{{W100}}"></p>')
A(h2("Dein erstes Stickmotiv in 6 Schritten"))
A(steps([
    f"{M('Start › Rahmen')}: Stickrahmen deiner Maschine wählen (z. B. 130 × 180 mm), "
    "dazu Stofffarbe und <b>Stoffart</b> (z. B. T-Shirt).",
    f"Im Reiter {M('Motive')} rechts ein Herz anklicken – es erscheint in der Rahmenmitte.",
    f"In den {M('Eigenschaften')} Garnfarbe, Füllart und Rand einstellen (z. B. roter Tatami, "
    "dunkelroter Satinrand 2,5 mm).",
    f"Mit dem Textwerkzeug ({K('T')}) in das Herz klicken, »Anna« eingeben und eine "
    f"<b>Stickschrift</b> wählen.",
    f"Mit {M('F5')} den <b>Simulator</b> öffnen und prüfen, wie die Maschine stickt.",
    f"{M('Export › Für Maschine exportieren')} ({K('Strg+E')}) und das Format deiner Maschine "
    "wählen, z. B. PES für Brother.",
]))
A(img("ex_design", 55, "Ergebnis: Herz mit Stickschrift, Sternen und Bohnenstich-Linie"))

# ---------------------------------------------------------------- 2 Rahmen & Stoff
A(h1("Rahmen, Stoff und Stoffart"))
A(p(f"Rechts im Reiter {M('Start')} stellst du drei Dinge ein, die für das ganze Design gelten:"))
A(table([
    ["<b>Rahmen</b>", "Größe des Stickfelds: 100 × 100, 130 × 180, 150 × 150, 160 × 260, 200 × 200, "
     "240 × 150, 260 × 200 oder 360 × 200 mm – oder ganz unten <b>Eigener Rahmen …</b> mit "
     "beliebiger Größe (20–1500 mm, optional mit Namen; wird gespeichert und reist in der "
     "Projektdatei mit). Objekte außerhalb werden gewarnt."],
    ["<b>Farbe</b>", "Stofffarbe für die realistische Vorschau (Weiß, Leinen, Jeans, Schwarz …). "
     "Der Knockdown-Stich übernimmt diese Farbe."],
    ["<b>Stoffart</b>", "Passt Dichte, Zugausgleich und Unterlage beim Berechnen an den Stoff an – "
     "wie in Profi-Programmen. Deine eingestellten Werte der Objekte bleiben dabei unverändert."],
], widths=[18, 82]))
rows = []
for key, pr in engine.FABRIC_PROFILES.items():
    d = pr.get("density", 1.0)
    dens = "unverändert" if d == 1.0 else (f"{round((1 / d - 1) * 100):+d} % dichter"
                                           if d < 1 else f"{round((1 - 1 / d) * 100)} % lockerer")
    rows.append([f"<b>{pr['name']}</b>", dens,
                 f"{pr.get('pull', 0):+.2f} mm".replace(".", ","), pr["hint"]])
A(table(rows, ["Stoffart", "Dichte", "Zugausgleich", "Hinweis (Vlies, Topping)"], [24, 14, 13, 49]))
A(img("fabrics", 92, "Dieselbe Fläche (24 × 16 mm) auf drei Stoffarten"))
A(tip("Die Statuszeile zeigt nach dem Umschalten passendes Vlies und Topping an. Bei Frottee "
      "und Fleece zusätzlich einen <b>Knockdown-Stich</b> (Sticken › Effekte) verwenden."))
A(ex("Eigener Rahmen 180 × 300 mm", [
    f"{M('Start › Rahmen')} aufklappen und ganz unten <b>Eigener Rahmen …</b> wählen.",
    "Breite 180 mm, Höhe 300 mm und als Namen z. B. »Brother XL« eintragen, OK.",
    "Der Rahmen ist sofort aktiv und steht ab jetzt immer in der Liste – auch nach einem Neustart.",
    "Nicht mehr gebraucht? »Eigenen Rahmen löschen …« in derselben Liste.",
]))
A(h2("Kappenrahmen"))
A(p("Für Kappen gibt es zwei Kappenrahmen: <b>Kappe 130 × 60 mm</b> (z. B. Brother PR, Janome) und "
    "<b>Kappe breit 360 × 75 mm</b> (270°-Rahmen, z. B. Tajima). Beim Wählen wird die Stoffart "
    "automatisch auf »Kappe« gestellt (festere Unterlage, mehr Zugausgleich); zurück auf einem flachen "
    "Rahmen kommt die vorige Stoffart wieder. Ein eigener Rahmen mit »Kappe« oder »Cap« im Namen gilt "
    "ebenfalls als Kappenrahmen."))
A(img("cap_hoop", 42, "Kappenrahmen mit angedeutetem Schirm"))
A(tip("Auf Kappen von der Mitte nach außen und von unten nach oben sticken, Schrift ab 6 mm Höhe, "
      "keine großen Flächen über die Mittelnaht. Für 3D-Puff siehe Kapitel 7."))
A(ex("Name auf ein Kinder-T-Shirt", [
    f"{M('Start › Rahmen')} 130 × 180 mm, {M('Farbe')} »Weiß«, {M('Stoffart')} »T-Shirt / Jersey«.",
    "Die Statuszeile empfiehlt jetzt Schneidvlies – das legst du beim Einspannen unter.",
    "Schriftzug anlegen wie gewohnt: Dichte und Zugausgleich werden beim Sticken automatisch an den "
    "dehnbaren Stoff angepasst, deine Werte in den Eigenschaften bleiben unverändert.",
    "Wechselst du später auf »Jeans«, wird dasselbe Design lockerer gestickt – ohne dass du etwas "
    "nachstellen musst.",
]))

# ---------------------------------------------------------------- 3 Erstellen
A(h1("Objekte erstellen"))
A(h2("Formen und Motive"))
A(p(f"Rechteck ({K('R')}) und Ellipse ({K('E')}): auf der Arbeitsfläche aufziehen, "
    f"{K('Umschalt')} hält Quadrat bzw. Kreis. Vieleck ({K('P')}): Punkt für Punkt klicken – "
    "<b>Linksklick setzt einen Eckpunkt, Rechtsklick einen Rundungspunkt</b>; Klick auf den Startpunkt "
    f"oder Doppelklick schließt die Form. Im Reiter {M('Motive')} gibt es 20 fertige Formen: Herz, "
    "Stern, Kreis, Quadrat, Abgerundet, Dreieck, Sechseck, Raute, Blume, Wolke, Mond, Blitz, Pfote, "
    "Blatt, Ring, Tropfen, Haus, Schmetterling, Anker und Stern 8."))
A(img("panel_motifs", 38, "Der Reiter »Motive«"))
A(ex("Kreis mit genau 30 mm und ein Herz", [
    f"Ellipse ({K('E')}) wählen und mit gedrückter {K('Umschalt')}-Taste einen Kreis aufziehen.",
    "Rechts in den Eigenschaften bei <i>Proportional</i> den Haken lassen und die Breite auf 30 mm "
    "stellen – die Höhe folgt automatisch.",
    f"Im Reiter {M('Motive')} rechts auf »Herz« klicken: es erscheint in der Rahmenmitte. Mit dem "
    "Eckgriff verkleinern oder ebenfalls über die Breite auf ein Maß bringen.",
]))
A(h2("Stern, Vieleck und Spirale"))
A(p(f"{M('Erstellen › Formen › Stern / Vieleck')} fragt Ecken, Durchmesser, Spitzen (klein = spitze "
    "Zacken), Drehung und »Abgerundet« ab. Mit »Vieleck statt Stern« entstehen gleichmäßige "
    f"Sechsecke, Achtecke usw. {M('Erstellen › Linien › Spirale')} legt eine Spirale als Linie an "
    "(Windungen, Durchmesser, Innenradius)."))
A(img("ex_starspiral", 100, "Verschiedene Einstellungen von Stern, Vieleck und Spirale"))
A(ex("Eine Sonne", [
    f"{M('Stern / Vieleck')}: 12 Ecken, Durchmesser 40 mm, Spitzen 0,75 – ergibt einen Strahlenkranz.",
    "Garnfarbe Orange, Füllart »Spiralfüllung« für einen schönen Glanz von innen nach außen.",
    "Einen gelben Kreis (25 mm) darüberlegen und beide mit Strg+M mittig ausrichten.",
]))
A(h2("Linien"))
A(p(f"Linie ({K('L')}): Punkte klicken (links Ecke, rechts Rundung), Doppelklick oder {K('Enter')} "
    f"beendet. Freihand ({K('F')}): mit gedrückter Maustaste zeichnen. Linien werden als Stepp-, "
    "Bohnen-, Satin-, Zickzack-, E- oder manueller Stich gestickt (siehe Kapitel 5)."))
A(ex("Wellenlinie unter einem Namen", [
    f"Linie ({K('L')}) wählen. Links mit <b>Linksklick</b> beginnen.",
    "Für die Wellenberge und -täler jeweils mit <b>Rechtsklick</b> einen Rundungspunkt setzen, "
    f"rechts mit Linksklick enden und {K('Enter')} drücken.",
    "In der Karte »Linie« die Art <i>Bohnenstich</i> und die Stichlänge 2,5 mm wählen – die Linie "
    "wird kräftig und gut sichtbar.",
]))
A(h2("Säulen-Satin"))
A(p(f"Werkzeug Säulen-Satin ({K('S')}): abwechselnd links und rechts der gewünschten Säule klicken – "
    "jedes Paar ist ein <i>Steg</i>, der die Stichrichtung festlegt. So dreht sich der Satinstich in "
    "Kurven sauber mit, wie bei Buchstaben in Profi-Stickschriften."))
A(ex("Blumenstiel, 3 mm breit", [
    f"Säulen-Satin ({K('S')}) wählen.",
    "Unten links neben den Stiel klicken, dann 3 mm weiter rechts – das ist das erste Klickpaar.",
    "Den Stiel hinauf alle 5–8 mm ein weiteres Paar setzen, in Biegungen dichter und immer quer zum "
    "Stiel.",
    f"Oben mit {K('Enter')} abschließen. Ein ausführliches Beispiel (Buchstabe D) steht unter "
    "<i>Nachzeichnen</i>.",
]))
A(h2("Schriftzüge"))
A(p(f"Textwerkzeug ({K('T')}) und auf die Arbeitsfläche klicken. In den Eigenschaften:"))
A(bullets([
    "<b>Stickschrift wählen …</b> – 129 professionell digitalisierte Schriften (Schreibschriften, "
    "Blockschriften, Monogramme, Applikationsschriften …) mit Vorschau, empfohlener Höhe und Lizenz.",
    "<b>Computerschrift</b> – jede installierte Schrift wird automatisch digitalisiert: schmale "
    "Striche als Satin, der genau der Buchstabenform folgt (dreht sich in Bögen mit, läuft an "
    "Strichenden spitz aus), breite Teile als Tatami. Abschaltbar mit »Schmale Striche als Satin«. "
    "Für sehr kleine Schrift sind Stickschriften trotzdem die beste Wahl.",
    "Höhe, Laufweite, Bogen (positiv = nach oben gewölbt), Fett/Kursiv, Satindichte und Zugausgleich.",
    "Mehrzeilig: einfach Zeilenumbrüche eingeben.",
]))
A(img("dialog_fonts", 85, "Die Auswahl der Stickschriften mit Vorschau"))
A(img("fonts", 92, "Drei Stickschriften und eine Computerschrift"))
A(tip("Halte die empfohlene Höhe der Stickschrift ein (steht in der Auswahl und in den "
      "Eigenschaften) – sonst wird die Schrift zu dicht oder zu locker. Manche Schriften bringen eigene "
      "Farben mit (z. B. mehrfarbige Zierschriften)."))
A(ex("Name auf ein Lätzchen, leicht gewölbt", [
    f"Textwerkzeug ({K('T')}) in den Rahmen klicken und »Emma« tippen.",
    "<b>Stickschrift wählen …</b> – z. B. eine Schreibschrift – und die Höhe auf 15 mm stellen "
    "(nicht unter die empfohlene Höhe der Schrift gehen).",
    "Bogen auf 20 stellen: der Name wölbt sich nach oben.",
    "Mit Strg+M in die Rahmenmitte setzen.",
]))
A(h3("Text an Pfad"))
A(p(f"Schriftzug und eine Linie auswählen, dann {M('Schrift › Text › Text an Pfad')}. Der Text "
    "folgt der Linie; in den Eigenschaften wählst du Ausrichtung (Anfang/Mitte/Ende), "
    "»Andere Seite« und »Lösen«."))
A(img("textpath", 55, "Schriftzug entlang eines Bogens"))
A(ex("Text im Bogen über einem Herz", [
    f"Linie ({K('L')}): links über dem Herz klicken, in der Mitte einen <b>Rechtsklick</b> etwas "
    f"höher, rechts klicken, {K('Enter')}.",
    "Einen Schriftzug »Für Oma« anlegen.",
    f"Schriftzug und Linie mit {K('Umschalt')}+Klick auswählen, {M('Schrift › Text › Text an Pfad')}.",
    "In den Eigenschaften unter »Am Pfad« die Ausrichtung <i>Mitte</i> wählen. Die Linie selbst "
    "wird nicht gestickt.",
]))
A(h3("Hüllformen"))
A(p(f"{M('Schrift › Text › Hüllform ▾')} biegt den ganzen Schriftzug in eine Form – wie die "
    "»Envelopes« in Profi-Programmen: Bogen oben, Bogen unten, Fass, Brücke, Doppelbogen, Taille, "
    "Raute, Welle, Wimpel und Rampe. Rechts in den Eigenschaften stellst du die <b>Stärke</b> ein. "
    "Die Stiche werden nach dem Verbiegen neu berechnet – Satindichte und Unterlage bleiben richtig."))
A(img("ex_envelopes", 100, "Hüllformen mit einer Stickschrift (Stärke 40 %)"))
A(ex("Vereinsschriftzug für eine Kappe", [
    "Schriftzug »TEAM 26« in einer kräftigen Blockschrift, Höhe 16 mm.",
    f"{M('Schrift › Hüllform ▾ › Bogen oben')} – die Mitte wölbt sich nach oben.",
    "Stärke auf 35 % stellen. Für einen klassischen Trikot-Look »Doppelbogen« probieren.",
]))
A(h3("Einzelne Buchstaben"))
A(p(f"Im <b>Punkte-Werkzeug</b> ({K('N')}) bekommt jeder Buchstabe eines gewählten Schriftzugs eine "
    "Raute als Anfasser: einfach ziehen, mit " + K("Umschalt") + " nur waagerecht (Laufweite "
    "zwischen zwei Buchstaben). Rechts in der Karte <b>Einzelne Buchstaben</b> wählst du einen "
    "Buchstaben und stellst Versatz, Drehung und Größe genau ein. Der Text bleibt dabei änderbar; "
    "»Zurücksetzen« stellt einen, »Alle« jeden Buchstaben zurück."))
A(ex("Großen Anfangsbuchstaben hervorheben", [
    "Schriftzug »Anna« anlegen und auswählen.",
    "Rechts unter <i>Einzelne Buchstaben</i> den Buchstaben »A« wählen, Größe 140 %.",
    f"Im Punkte-Werkzeug ({K('N')}) das »n« daneben mit Umschalt etwas nach rechts ziehen, damit "
    "nichts überlappt.",
]))
A(h2("Bild-Assistent (automatisch digitalisieren)"))
A(p(f"{M('Erstellen › Automatisch › Bild-Assistent')} wandelt PNG, JPG oder SVG in Stickflächen um: "
    "Farben werden reduziert, jede Farbe wird eine eigene Fläche mit Tatami-Füllung (schmale Teile "
    "als Satin). Links siehst du das Original, rechts das Ergebnis – wahlweise als <b>Flächen</b> "
    "oder als echte <b>Stiche</b>."))
A(bullets([
    "<b>Zoomen</b>: Mausrad (an der Mausposition), Knöpfe − / +, »⤢« bzw. Doppelklick passt ein, "
    "»1:1« zeigt Originalpixel. <b>Verschieben</b>: Ziehen mit der Maus.",
    "<b>Ansichten koppeln</b>: Original und Ergebnis zeigen beim Zoomen denselben Ausschnitt – so "
    "vergleichst du Details direkt.",
    "<b>Schieberegler</b> für Garnfarben, Breite und <b>Detailgenauigkeit</b>: nach rechts = feiner "
    "(kleine Teile bleiben erhalten, mehr Stiche), nach links = glattere Konturen. Die Vorschau "
    "rechnet neu, sobald der Regler ruht.",
]))
A(img("dialog_digitize", 100, "Bild-Assistent: hineingezoomt, rechts als Stiche"))
A(p("Danach kannst du jede Fläche wie eine gezeichnete Form bearbeiten. Nach dem Digitalisieren "
    f"lohnt {M('Optimieren › Kleinteile entfernen')} (Kapitel 8)."))
A(ex("Vereinslogo aus einer PNG-Datei", [
    f"{M('Bild-Assistent')} ({K('Strg+B')}) öffnen und das Logo wählen.",
    "Garnfarben auf 4 stellen (so viele Farben, wie das Logo hat), Breite 80 mm.",
    "Detailgenauigkeit zuerst in der Mitte lassen; mit dem Mausrad in beide Ansichten zoomen und "
    "vergleichen. Fehlen feine Teile, den Regler nach rechts schieben.",
    "Rechts auf <b>Stiche</b> umschalten, prüfen, dann übernehmen.",
    f"{M('Optimieren › Kleinteile entfernen')} und {M('Überlappung entfernen')} – fertig zum Sticken.",
]))
A(tip("Wo es sinnvoll ist, haben Zahlenfelder einen Schieberegler – in den Eigenschaften (Winkel, "
      "Dichte, Stichlänge, Breite, Zugausgleich, Feinheiten …), im Fotostich und in den "
      "Einstellungen. Das Mausrad verstellt einen Regler erst, wenn er angeklickt ist – so scrollt "
      "die Seitenleiste nicht versehentlich Werte weg."))
A(h2("Fotostich"))
A(p(f"{M('Erstellen › Automatisch › Fotostich')} macht aus einem Foto eine Stickerei – mit "
    "Live-Vorschau, Stichzahl und Stickzeit:"))
A(bullets([
    "<b>Farbig</b>: 2–16 Garnfarben (passend zur gewählten Garnkarte), helle Lagen zuerst, dunkle "
    "Details obendrauf, jede Lage mit eigener Stichrichtung. Option »Hintergrund weglassen«.",
    "<b>Einfarbig (Linienschraffur)</b>: Zickzacklinien, die in dunklen Bereichen breiter und "
    "dichter werden – ideal für Porträts. Linienabstand, Richtung, Kontrast und »hell auf dunklem "
    "Stoff« einstellbar.",
]))
A(img("dialog_photo", 100, "Fotostich: Foto und Stickerei nebeneinander, beide zoombar"))
A(tip("Fotos mit klarem Motiv und gutem Kontrast wirken am besten. 6–8 Farben ergeben sichtbare "
      "Farbstufen – das ist bei dieser Technik normal. Immer zuerst auf einem Stoffrest testen.",
      "Achtung"))
A(ex("Porträt eines Hundes, einfarbig", [
    f"{M('Erstellen › Automatisch › Fotostich')} öffnen und das Foto wählen.",
    "Art <i>Einfarbig (Linienschraffur)</i>, Breite 90 mm, Linienabstand 1,2 mm.",
    "Kontrast erhöhen, bis Augen und Nase deutlich dunkel sind.",
    "Auf dunklem Stoff »hell auf dunklem Stoff« anhaken und eine helle Garnfarbe nehmen.",
    "Stichzahl und Stickzeit unten prüfen, dann übernehmen.",
]))
A(h2("Nachzeichnen"))
A(p(f"Im Reiter {M('Nachzeichnen')} legst du ein Bild oder SVG als halbtransparente Vorlage in den "
    "Rahmen (Deckkraft, Breite, Anzeigen, Fixiert). Mit Vieleck, Linie oder Säulen-Satin zeichnest du "
    f"darüber nach. {K('Strg')} beim Abschließen einer Form schneidet sie als Loch aus der gewählten "
    f"Form aus. {M('Farbe aufnehmen')} (Pipette) überträgt eine Farbe der Vorlage auf die Auswahl."))
A(h3("Welches Werkzeug für welchen Strich?"))
A(table([
    ["Strich unter 1,5 mm", "Linie (Steppstich oder Bohnenstich)"],
    ["Strich 1,5–8 mm", "<b>Säulen-Satin</b> – glänzend, die Stiche drehen in Kurven mit"],
    ["Strich über 8 mm, große Flächen", "<b>Vieleck</b> mit Tatami-Füllung, Löcher mit Strg"],
    ["Elegante Schwünge", "<b>Bézier-Stift</b>, danach mit dem Punkte-Werkzeug feinjustieren"],
], ["Breite in der Vorlage", "Werkzeug"], [34, 66]))
A(img("ex_trace_d", 100, "Beispiel: ein großes D aus zwei Satinsäulen"))
A(ex("Ein großes D nachzeichnen (40 mm hoch)", [
    f"{M('Nachzeichnen › Bild als Vorlage')} ({K('Strg+Umschalt+B')}): Bild mit dem D wählen, "
    "Breite so einstellen, dass das D 40 mm hoch ist, Deckkraft 40 %, <i>Fixiert</i> anhaken.",
    f"Hineinzoomen und mit {K('%')} das Einrasten ausschalten.",
    f"<b>Strich</b>: Säulen-Satin ({K('S')}), oben links und oben rechts an den Strich klicken "
    f"(S1), dann unten links und unten rechts (S2), {K('Enter')}.",
    "<b>Bogen</b>: wieder Säulen-Satin. Oben beginnen, jeweils außen und gegenüber innen klicken – "
    "etwa alle 5–8 mm ein Paar, immer quer zum Bogen wie Radspeichen (1 bis 11). Den Bogen oben "
    f"und unten etwa 1 mm in den Strich hineinragen lassen. {K('Enter')}.",
    f"Beide Säulen auswählen, {M('Anordnen › Gruppieren')} – mit dem Simulator ({K('F5')}) prüfen.",
]))
A(tip("Ein sehr fettes D zeichnest du stattdessen mit dem Vieleck: Außenkontur (Ecken mit "
      "Linksklick, Bogen mit Rechtsklick), dann bei gewählter Form das Innere nachfahren und beim "
      "Abschließen Strg halten – so entsteht das Loch."))
A(ex("Garnfarbe aus der Vorlage übernehmen", [
    "Eine nachgezeichnete Fläche auswählen.",
    f"{M('Nachzeichnen › Farbe aufnehmen')} und in der Vorlage auf die gewünschte Farbe klicken.",
    "Die Fläche bekommt die nächstliegende Garnfarbe der gewählten Garnkarte.",
]))
A(h2("Stickdateien öffnen und importieren"))
A(p(f"{M('Start › Datei › Importieren')} ({K('Strg+I')}) liest PES, DST, JEF, EXP, VP3, XXX, "
    "HUS, VIP, SEW, PEC, U01, TBF, PMV, CSV, JSON und rund 25 weitere Formate. Importierte Dateien "
    "bleiben als Stiche erhalten; Farben lassen sich in den Eigenschaften ändern. Mit "
    f"{M('Erstellen › Automatisch › Umriss aus Stickdatei')} rekonstruierst du daraus bearbeitbare Formen."))
A(p(f"Der <b>Design-Browser</b> ({K('Strg+Umschalt+O')}) zeigt alle Stickdateien eines Ordners mit "
    "Vorschaubildern."))
A(ex("Gekaufte PES-Datei umfärben und ergänzen", [
    f"{M('Start › Datei › Importieren')} ({K('Strg+I')}) und die PES-Datei wählen.",
    "Ein Farbteil anklicken und unten in der Garnfarben-Leiste eine neue Farbe wählen.",
    "Einen Schriftzug darunter setzen, alles auswählen und gruppieren.",
    f"Soll das Motiv größer werden: {M('Umriss aus Stickdatei')} – daraus entstehen bearbeitbare "
    "Formen, die sich ohne Dichteprobleme skalieren lassen.",
]))

# ---------------------------------------------------------------- 4 Bearbeiten
A(h1("Bearbeiten, Anordnen und Gruppieren"))
A(h2("Auswählen, verschieben, skalieren, drehen"))
A(bullets([
    f"Klick wählt ein Objekt, {K('Umschalt')}+Klick oder ein Rahmen wählt mehrere, "
    f"{K('Strg+A')} alle.",
    "Ziehen verschiebt, Pfeiltasten verschieben in kleinen Schritten.",
    "<b>Eckgriffe</b> skalieren, der runde Griff oben dreht (mit Umschalt in 15°-Schritten). "
    "Bei mehreren ausgewählten Objekten wirken die Griffe auf alle zusammen.",
    "Genaue Werte: Eigenschaften › Position, Breite/Höhe (mit »Proportional«), Drehung.",
    "Beim Skalieren werden die Stiche neu berechnet – die Dichte bleibt richtig.",
]))
A(ex("Ein Motiv auf genau 50 mm Breite bringen und drehen", [
    "Das Motiv anklicken.",
    "Rechts unter Größe <i>Proportional</i> anhaken und Breite 50 mm eintragen.",
    "Drehung 15° eintragen – oder den runden Griff mit gedrückter Umschalt-Taste ziehen.",
]))
A(h2("Gruppieren"))
A(p(f"Mehrere Objekte auswählen und {M('Anordnen › Gruppe › Gruppieren')} ({K('Strg+Alt+G')}). Danach:"))
A(bullets([
    "Ein Klick auf ein Objekt wählt die <b>ganze Gruppe</b>.",
    "Verschieben, Skalieren, Drehen, Spiegeln und Duplizieren wirken auf alle Objekte zusammen; "
    "die Abstände wachsen beim Skalieren mit.",
    "Rechts erscheint die Karte <b>Gruppe</b> mit der Gesamtbreite und -höhe – dort lässt sich die "
    "Gruppe auf ein genaues Maß bringen (z. B. »80 mm breit«).",
    f"{K('Alt')}+Klick wählt ein einzelnes Objekt innerhalb der Gruppe.",
    f"{M('Gruppe auflösen')} ({K('Strg+Alt+Umschalt+G')}) hebt die Gruppierung auf.",
    "In der Objektliste steht hinter gruppierten Objekten »▣ Gruppe 1«, »▣ Gruppe 2« …",
]))
A(ex("Logo mit Schriftzug auf 80 mm bringen", [
    f"Logo und Schriftzug mit einem Rahmen auswählen, {K('Strg+Alt+G')}.",
    "Rechts in der Karte <i>Gruppe</i> die Breite 80 mm eintragen – Logo, Schrift und der Abstand "
    "dazwischen wachsen gemeinsam.",
    f"Nur die Schrift umfärben: {K('Alt')}+Klick auf den Schriftzug, dann eine Garnfarbe wählen.",
]))
A(img("screen_group", 100, "Eine gewählte Gruppe: Griffe um alle Objekte, rechts die Karte »Gruppe«"))
A(tip("Gedrehte Gruppen lassen sich nur proportional skalieren (sonst würden schräge Objekte "
      "verzerrt). Bei Drehungen um 90° geht auch »nur breiter«."))
A(h2("Gestalten wie in Inkscape"))
EX_DESIGN = [
    "Drei überlappende Kreise und ein Rechteck zu einer Wolke verbinden.",
    "Kreis über ein Quadrat legen, beide wählen: das Quadrat bekommt ein rundes Loch (Fenster).",
    "Kreis und Quadrat: nur die gemeinsame Ecke bleibt übrig.",
    "Zwei Ringe ineinander: die Überlappung wird frei – ein Kettenglied.",
    "Ball mit zwei Streifen darüber: 3 Stücke, jedes in eigener Farbe (Wasserball).",
    "Digitalisiertes Logo: jedes Teil einzeln färben oder löschen.",
    "Drei Sterne: »Oben« macht sie oben bündig.",
    "Fünf Knöpfe in eine Reihe mit gleichen Abständen bringen.",
    "Hintergrund-Rechteck sperren, damit es beim Arbeiten an der Schrift nicht verrutscht.",
    "Füllung 0,5 mm erweitern, damit sie sicher unter den Satinrand reicht.",
    "Herz mit 2 mm Abstand und 2,5 mm Satin umranden: fertiger Aufnäher.",
    "Ein Herz zu 4 × 2 Herzen für eine Bordüre; ein Blütenblatt 8-mal im Kreis = Blume.",
    "Sonne: 12 Ecken, Spitzen 0,75. Sechseck: Vieleck mit 6 Ecken.",
    "Schneckenhaus: 4 Windungen, Bohnenstich.",
    "Logo als Vorlage: Fläche wählen, Pipette aufs Rot – passende Garnfarbe.",
    "Namen in die Rahmenmitte ziehen, bis die rosa Hilfslinie erscheint.",
]
A(table(with_ex(EX_DESIGN, [
    ["Kombinieren", "Anordnen", "Formen zu einer verbinden (Inkscape: Vereinigung), " + K("Strg+G")],
    ["Ausschneiden", "Anordnen", "Obere Form aus der unteren herausschneiden (Differenz)"],
    ["Schnittmenge", "Anordnen", "Nur die gemeinsame Fläche aller Formen behalten"],
    ["Exklusion", "Anordnen", "Überlappende Bereiche entfernen (Exklusiv-Oder)"],
    ["Teilen", "Anordnen", "Unterste Form an den oberen Umrissen in Stücke schneiden (Division) – "
     "jedes Stück einzeln färbbar"],
    ["Zerlegen", "Anordnen", "Mehrteilige Form in einzelne Formen trennen, " + K("Strg+Umschalt+G")],
    ["Ausrichten ▾", "Anordnen", "Links, mittig, rechts, oben, unten – Bezug: Auswahl oder Stickrahmen "
     "(bei einem einzelnen Objekt immer der Rahmen). Gruppen zählen als ein Objekt."],
    ["Verteilen ▾", "Anordnen", "Ab drei Objekten: gleiche Abstände waagerecht oder senkrecht"],
    ["Sperren", "Anordnen › Ebenen", "Nicht mehr anklickbar/verschiebbar, " + K("Strg+Alt+L") +
     "; einzeln entsperren über das Schloss in der Objektliste"],
    ["Erweitern / Schrumpfen", "Form bearbeiten", "Form rundum um einen Abstand vergrößern/verkleinern"],
    ["Umriss", "Form bearbeiten", "Geschlossene Linie (Satin, Bohnen- oder Steppstich) im Abstand um "
     "die Auswahl – z. B. als Rand für einen Aufnäher"],
    ["Kopien im Raster / Kreis", "Form bearbeiten", "Auswahl wiederholen: Spalten × Zeilen mit Lücke, "
     "oder n-mal im Kreis, auf Wunsch mitgedreht (Blüten, Kränze)"],
    ["Stern / Vieleck", "Erstellen", "Ecken, Durchmesser, Spitzen, Drehung, abgerundet"],
    ["Spirale", "Erstellen", "Windungen, Durchmesser, Innenradius – als Linie"],
    ["Farbe aufnehmen", "Nachzeichnen", "Pipette: Farbe in der Vorlage anklicken, die Auswahl bekommt "
     "die nächstliegende Garnfarbe"],
    ["Einrasten", "Ansicht › Raster ▾", "Beim Verschieben an Raster, Rahmenmitte und Kanten/Mitten "
     "anderer Objekte; rosa Hilfslinie zeigt den Treffer. Der Pfeil am Raster-Knopf schaltet das "
     "Einrasten ein/aus, wählt die Ziele und die Rasterweite. Taste " + K("%") +
     ", Alt beim Ziehen = ohne."],
]), ["Befehl", "Reiter", "Wirkung", "Beispiel"], [16, 13, 37, 34]))
A(img("ex_pathops", 100, "Pfad-Operationen: jeweils vorher (rot unten, blau oben) und nachher"))
A(ex("Haus mit Fenster (Ausschneiden)", [
    "Ein Rechteck 40 × 30 mm zeichnen (Hauswand), darüber ein Quadrat 8 × 8 mm (Fenster).",
    f"Beide auswählen und {M('Anordnen › Ausschneiden')}: in der Wand ist jetzt ein Loch.",
    "Unter dem Loch wird nicht gestickt – der Stoff ist das Fenster.",
]))
A(img("ex_align", 100, "Ausrichten und Verteilen: vorher und nachher"))
A(ex("Drei Motive bündig und gleichmäßig verteilen", [
    f"Die drei Motive mit {K('Umschalt')}+Klick auswählen.",
    f"{M('Anordnen › Ausrichten ▾ › Vertikal zentrieren')} – alle stehen auf einer Höhe.",
    f"{M('Verteilen ▾ › Waagerecht gleichmäßig verteilen')} – die Lücken dazwischen sind gleich groß.",
    "Im Menü »Ausrichten« bei »Bezug« den Stickrahmen wählen, um an den Rahmen auszurichten.",
]))
A(img("ex_offset", 100, "Erweitern, Schrumpfen und Umriss"))
A(ex("Aufnäher aus einem Herz (Umriss)", [
    "Ein Herz (40 mm) mit Tatami-Füllung anlegen.",
    f"{M('Form bearbeiten › Versatz › Umriss')}: Abstand 2 mm, Stichart »Satin (Patch-Rand)«, "
    "Breite 2,5 mm.",
    "Der Umriss wird als letztes gestickt – genau richtig für einen Aufnäher-Rand.",
]))
A(img("ex_copies", 100, "Kopien im Raster und im Kreis"))
A(ex("Blume aus einem Blütenblatt", [
    "Eine schmale Ellipse (7 × 16 mm) als Blütenblatt zeichnen.",
    f"{M('Form bearbeiten › Kopien › Kreis-Kopien')}: Anzahl 8, Radius 10 mm, »mitdrehen« anhaken.",
    "Einen gelben Kreis (8 mm) in die Mitte legen.",
    f"Alles auswählen und gruppieren ({K('Strg+Alt+G')}).",
]))
A(h2("Schatten"))
A(p(f"{M('Form bearbeiten › Versatz › Schatten')} (auch unter Schrift) legt einen versetzten Schatten "
    "hinter Schriftzüge und Formen. Wähle Versatz, Farbe und ob der Schatten als Fläche oder nur als "
    "Satinkontur gestickt wird. Der verdeckte Teil wird ausgespart – das spart Stiche."))
A(img("ex_shadow", 70, "Schriftzug ohne und mit Schatten"))
A(ex("Schrift mit Schatten auf einem Trikot", [
    "Schriftzug in Gelb auf rotem Stoff anlegen und auswählen.",
    f"{M('Schrift › Schatten')}: Versatz 1,5 mm nach rechts und unten, Dunkelgrau, als Fläche.",
    "Der Schatten wird vor der Schrift gestickt und liegt dahinter.",
]))
A(h2("Lineal und Messen"))
A(p(f"Oben und links zeigen <b>Lineale</b> die Millimeter ab der Rahmenmitte, die Mausposition ist "
    f"markiert ({M('Ansicht › Messen › Lineal')} blendet sie aus). Das <b>Messwerkzeug</b> ({K('M')}) "
    "misst von Punkt zu Punkt: Abstand, waagerecht, senkrecht und Winkel stehen an der Linie und in "
    "der Statuszeile; mit " + K("Umschalt") + " in 45°-Schritten."))
A(ex("Abstand zwischen Logo und Schrift prüfen", [
    f"{K('M')} drücken.",
    "Von der Unterkante des Logos zur Oberkante der Schrift ziehen.",
    "Die Anzeige sagt z. B. »8,5 mm« – bei Bedarf die Schrift verschieben und erneut messen.",
]))
A(h2("Weitere Befehle"))
A(table([
    ["Duplizieren", K("Strg+D"), "Kopie, leicht versetzt (Gruppen werden als neue Gruppe kopiert)."],
    ["Kopieren / Einfügen", K("Strg+C") + " / " + K("Strg+V"), "Auch zwischen Designs."],
    ["Zentrieren", K("Strg+M"), "Auswahl (oder ganzes Design) in die Rahmenmitte."],
    ["Spiegeln ↔ / ↕", "", "An der Mitte der Auswahl; Gruppen tauschen dabei auch die Plätze."],
    ["Früher / Später sticken", K("Strg+↑") + " / " + K("Strg+↓"),
     "Stickreihenfolge ändern (Optimieren › Reihenfolge oder Objektliste)."],
    ["Löschen", K("Entf"), ""],
    ["Rückgängig / Wiederholen", K("Strg+Z") + " / " + K("Strg+Y"), "Viele Schritte zurück."],
], ["Befehl", "Taste", "Hinweis"], [28, 22, 50]))
A(img("ex_mirror", 60, "Spiegeln: ein Blatt dupliziert und gespiegelt"))
A(ex("Symmetrisches Blätterpaar", [
    f"Ein Blatt auswählen und duplizieren ({K('Strg+D')}).",
    f"Die Kopie mit {M('Anordnen › Spiegeln ↔')} umdrehen und nach rechts schieben.",
    f"Beide wählen, {M('Ausrichten ▾ › Vertikal zentrieren')} – das Paar ist symmetrisch.",
]))
A(h2("Die Objektliste"))
A(p("Im Reiter <i>Objekte</i> rechts steht die Stickreihenfolge von oben nach unten. Ziehen sortiert "
    "um, Doppelklick benennt um, das Auge blendet aus (ausgeblendete Objekte werden nicht gestickt). "
    "Unten findest du die <b>Design-Info</b> mit Stichzahl, Farbfolge und Stickzeit."))
A(img("panel_objects", 38, "Objektliste mit Vorschaubildern und Stichzahl"))
A(ex("Die Schrift soll zuletzt gestickt werden", [
    "Im Reiter <i>Objekte</i> den Schriftzug anfassen und ganz nach unten ziehen.",
    f"Oder den Schriftzug wählen und {K('Strg+↓')} drücken, bis er unten steht.",
    "Mit dem Simulator prüfen: jetzt kommt die Schrift nach allen Flächen.",
]))
A(h2("Punkte bearbeiten"))
EX_NODES = [
    "Die Spitze eines Sterns weiter nach außen ziehen.",
    "Am Rand eines Herzens einen Punkt einfügen und nach innen ziehen – eine Delle.",
    "Sechseck: alle Punkte auf »Rundung« – eine weiche Blob-Form.",
    "Offene Linie zum Kreis schließen; zwei Stiele zu einer Linie verbinden.",
    "Kreislinie an einem Punkt öffnen – ein Bogen für »Text an Pfad«.",
    "Zwei Blüten mit einem Stiel verbinden.",
    "Nach dem Bild-Assistenten: zackige Kontur glätten.",
    "Freihand-Linie mit 200 Punkten auf 20 reduzieren.",
    "Ein Stück aus einem Rechteck wegradieren – eine Bruchkante.",
]
A(p(f"Mit dem Punkte-Werkzeug ({K('N')}) erscheinen die Punkte der gewählten Form oder Linie:"))
A(table(with_ex(EX_NODES, [
    ["Punkt verschieben", "Ziehen; mehrere mit Umschalt oder Rahmen wählen."],
    ["Punkt einfügen", f"Über die Kante fahren (»+«) und klicken, oder {K('Einfg')} setzt Punkte "
     "zwischen die gewählten. Rechtsklick auf die Kante: gezielt Ecke oder Rundung. Bei Säulen-Satin "
     f"entsteht ein Punktepaar; offene Linien mit {K('Strg')}+Klick verlängern."],
    ["Ecke / Rundung", "Rechtsklick auf einen Punkt oder Knöpfe »Ecke«/»Rundung«."],
    ["Punkte verbinden", f"{K('Strg+J')}: beide Endpunkte einer Linie = schließen, Nachbarpunkte = "
     "verschmelzen, zwei Linien = zu einer verbinden."],
    ["Auftrennen", f"{K('Strg+Umschalt+J')}: Linie am gewählten Punkt öffnen bzw. teilen."],
    ["Mit Linie verbinden", f"Werkzeug {K('K')}: zwei Punkte nacheinander anklicken – dazwischen "
     "entsteht eine Linie (rastet auf Punkten ein, Umschalt = 15°-Schritte)."],
    ["Rundungen erkennen", "Eckige, digitalisierte Konturen in wenige saubere Ecken und Rundungen "
     "verwandeln."],
    ["Punkte reduzieren", "Weniger Punkte – übersichtlicher beim Bearbeiten."],
    ["Radierer", f"Werkzeug {K('X')}: wie im Malprogramm mit gedrückter Maustaste über eine Form "
     "wischen, der runde Pinsel entfernt alles, was er überstreicht (Kreis am Mauszeiger zeigt die "
     f"Größe). {K('[')} / {K(']')} = kleiner/größer, Größen auch über den Pfeil am Knopf. "
     "Umschalt + Ziehen umfährt einen Bereich (Lasso). Durchgeschnittene Linien bleiben in allen "
     "Stücken erhalten."],
]), ["Aktion", "So geht's", "Beispiel"], [18, 50, 32]))
A(h2("Teile: Zerlegen, Kombinieren, Ausschneiden"))
A(p("<b>Zerlegen</b> macht aus einer mehrteiligen Form einzelne Formen, <b>Kombinieren</b> fasst "
    "Formen zu einer zusammen, <b>Ausschneiden</b> schneidet die oben liegende Form aus der unteren "
    "heraus (Loch). Schriftzüge lassen sich mit <b>In Form umwandeln</b> wie Formen bearbeiten."))
A(ex("Initiale mit Herz-Loch", [
    "Einen Schriftzug »A« (40 mm, Blockschrift) anlegen.",
    f"{M('Schrift › Umwandeln › In Form umwandeln')} – jetzt ist das A eine Form.",
    "Ein kleines Herz auf den Querbalken legen, beides wählen, Ausschneiden.",
]))

# ---------------------------------------------------------------- Designstudio
A(h1("Eigene Designs von Grund auf"))
A(p("Alles, womit du komplett eigene Designs baust: freies Zeichnen mit Bézierkurven "
    "(Erstellen › Linien), Ebenen (Anordnen › Ebenen), eine eigene Bibliothek und fertige Vorlagen "
    "(Erstellen › Vorlagen & Bibliothek) und eigene Stickschriften (Schrift › Eigene Schriften)."))
A(h2("Bézier-Stift"))
A(table([
    ["Klick", "Eckpunkt setzen (gerade Strecke)"],
    ["Klicken und ziehen", "Kurvenpunkt mit zwei Anfassern – die Ziehrichtung gibt die Kurve vor; "
     + K("Alt") + " beim Ziehen = nur der Ausgangs-Anfasser"],
    ["Klick auf den Startpunkt", "Form schließen (gefüllte Fläche)"],
    [K("Enter") + " / Doppelklick / Rechtsklick", "Offene Linie beenden"],
    [K("Rücktaste"), "Letzten Punkt zurücknehmen"],
    [K("Esc"), "Abbrechen"],
], ["Aktion", "Wirkung"], [32, 68]))
A(p("Im <b>Punkte-Werkzeug</b> (N) zeigt ein gewählter Punkt seine Anfasser (lila). Anfasser ziehen "
    "formt die Kurve; an glatten Punkten (rund dargestellt) bleibt der Gegen-Anfasser in einer Linie, "
    "an Eckpunkten (eckig) bewegen sich beide unabhängig. Rechtsklick auf einen Punkt: <i>Bézier-"
    "Anfasser hinzufügen</i> (die Form bleibt erhalten) oder <i>entfernen</i>. Ein Klick auf eine "
    "Bézierkurve fügt einen Punkt ein, ohne die Form zu verändern."))
A(img("ds_bezier", 70, "Blatt mit Bézierkurven: gewählter Punkt mit seinen Anfassern"))
A(ex("Ein Blatt mit dem Bézier-Stift", [
    f"Bézier-Stift ({K('B')}) wählen.",
    "Unten (Stielansatz) einmal <b>klicken</b> – ein Eckpunkt.",
    "Oben an der Blattspitze klicken und die Maus <b>nach rechts ziehen</b> – die linke Blatthälfte "
    "wird zur Kurve.",
    "Auf den Startpunkt klicken und dabei nach links ziehen – die Form schließt sich als Blatt.",
    f"Mit dem Punkte-Werkzeug ({K('N')}) die lila Anfasser nachziehen, bis die Form gefällt.",
]))
A(h2("Ebenen"))
A(p("Reiter <b>Ebenen</b> rechts: Neue Objekte landen in der <i>aktiven</i> Ebene (fett). Das Auge "
    "blendet eine Ebene aus – sie wird dann auch nicht gestickt –, das Schloss sperrt sie. Pfeile "
    "ändern die Reihenfolge: gestickt wird von der untersten zur obersten Ebene. »Auswahl hierher« "
    "verschiebt Objekte in die aktive Ebene, Doppelklick benennt um."))
A(img("ds_layers", 38, "Reiter »Ebenen«"))
A(ex("Hintergrund und Schrift trennen", [
    f"{M('Anordnen › Ebenen › Neue Ebene')}: »Hintergrund« und »Schrift« anlegen.",
    "»Hintergrund« aktiv (fett) machen und die Flächen zeichnen, dann »Schrift« aktiv machen und "
    "den Namen setzen.",
    "Das Schloss bei »Hintergrund« sperrt die Flächen – du kannst die Schrift frei verschieben.",
    "Das Auge bei »Schrift« blendet sie aus, z. B. für einen Probestich nur des Hintergrunds.",
]))
A(h2("Eigene Bibliothek"))
A(p("Reiter <b>Bibliothek</b>: <i>Auswahl speichern</i> oder <i>Design speichern</i> legt ein Element "
    "mit Vorschaubild an (Name und Kategorie frei wählbar). Doppelklick fügt es in jedes Design ein – "
    "Gruppen bleiben erhalten. Suche, Kategorien, Umbenennen und Löschen per Rechtsklick."))
A(ex("Das Vereinswappen immer wieder verwenden", [
    "Das fertige Wappen auswählen.",
    f"{M('Erstellen › In Bibliothek')}: Name »Wappen TSV«, Kategorie »Verein«.",
    "In jedem neuen Design: Reiter <i>Bibliothek</i> rechts, Kategorie »Verein«, Doppelklick auf das "
    "Wappen – es wird als Gruppe eingefügt.",
]))
A(h2("Design-Vorlagen"))
A(p("Zwölf anpassbare Layouts mit Live-Vorschau: Namensschild, Wappen/Abzeichen, Rund-Emblem mit "
    "Text im Bogen, Blätterkranz, Monogramm, Aufnäher, Geburtsanzeige, Hochzeit, Banner, Bordüre, "
    "Herz mit Namen und Zierrahmen. Zu lange Texte werden automatisch verkleinert. Texte, Schrift, Größe und Farben einstellen, "
    "<i>Einfügen</i> – das Ergebnis ist eine Gruppe aus normalen Objekten und lässt sich weiter "
    "bearbeiten."))
A(img("ds_templates", 100, "Vorlagen-Fenster mit Feldern und Live-Vorschau"))
A(img("ds_template_grid", 62, "Alle Vorlagen mit Standardwerten"))
A(ex("Geburtsanzeige für ein Kissen", [
    f"{M('Erstellen › Design-Vorlagen')}, links »Geburt« wählen.",
    "Name, Datum sowie Gewicht und Größe eintragen; die Vorschau rechts zeigt das Ergebnis sofort.",
    "Schrift und Farben wählen, Größe 120 mm, <i>Einfügen</i>.",
    f"Einzelne Teile ändern: {K('Alt')}+Klick, z. B. auf den Stern, und umfärben.",
]))
A(h2("Schrift-Werkstatt"))
A(bullets([
    "<b>Aus Computerschrift</b>: Schrift, Versalhöhe und Stickart wählen – jedes Zeichen wird "
    "automatisch digitalisiert (schmale Striche als Satin, breite Teile als Füllung).",
    "<b>Eigene Zeichen</b>: ein Zeichen zeichnen (Satinsäulen, Linien, Formen), alle Teile auswählen, "
    "Schrift-Werkstatt öffnen, Zeichen angeben, übernehmen. Die Unterkante der Auswahl ist die "
    "Grundlinie (bei g, j, p, q, y die Oberkante plus Versalhöhe).",
    "<b>Meine Schriften</b>: Übersicht mit Probe, Löschen. Eigene Schriften erscheinen in der "
    "Stickschrift-Auswahl wie die mitgelieferten.",
]))
A(img("ds_fontshop", 95, "Schrift-Werkstatt: Stickschrift aus einer Computerschrift erzeugt"))
A(ex("Das nachgezeichnete D in die eigene Schrift aufnehmen", [
    "Das D wie in Kapitel 3 aus zwei Satinsäulen nachzeichnen.",
    f"Beide Säulen auswählen und {M('Schrift › Schrift-Werkstatt')} öffnen.",
    "Reiter <i>Eigene Zeichen</i>: Schriftname »Meine Schrift«, Zeichen »D«, übernehmen.",
    "Weitere Buchstaben genauso hinzufügen. Danach tippst du mit dem Schriftzug-Werkzeug in "
    "»Meine Schrift« – wie mit jeder anderen Stickschrift.",
]))
A(tip("Automatisch erzeugte Schriften sind eine gute Grundlage; für sehr kleine Schrift oder "
      "verschnörkelte Serifen liefern selbst gezeichnete Satinsäulen das sauberste Stickbild."))

# ---------------------------------------------------------------- 5 Füllungen & Linien
A(h1("Füllarten, Ränder und Linien"))
A(p("Jede Form hat eine <b>Füllung</b> (Karte »Füllstich«) und einen <b>Rand</b> (Karte »Rand«). "
    "Linien haben nur die Karte »Linie«."))
A(h2("Füllarten im Überblick"))
EX_FILL = [
    "Große Flächen: Herz, Logo-Hintergrund.",
    "Schmale Blätter, Blockbuchstaben bis 8 mm Strichbreite.",
    "Wasser, wehende Fahne.",
    "Blütenblatt mit Reihen entlang der Mittelrippe.",
    "Spiegelei, Teich, Zielscheibe.",
    "Landhaus-Herz, Weihnachtsmotive.",
    "Kinder-Design: Herz mit kleinen Sternen gefüllt.",
    "Leichte Füllung auf T-Shirts, Fischernetz.",
    "Sonne, Schneckenhaus, Bonbon.",
    "Quilt-Look, Teddyfell.",
    "Rose, Holzmaserung.",
    "Sonnenuntergang von Gelb über Orange nach Rot.",
    "Schottenkaro-Herz, Kissen im Landhausstil.",
    "Großer Stoffbuchstabe auf einem Kissen.",
]
A(img("fills", 100, "Alle Füllarten (30 × 30 mm)"))
A(table(with_ex(EX_FILL, [
    ["Tatami", "Die Standardfüllung: dichte Reihen mit versetzten Einstichen. Winkel, Reihenabstand, "
     "Stichlänge, Muster, Unterlage, Zugausgleich."],
    ["Satin", "Lange Satinstiche quer über die Fläche – glänzend, für schmale Flächen."],
    ["Wellenfüllung", "Reihen in Wellenform (Wellengröße einstellbar)."],
    ["Geführte Füllung", "Reihen folgen einer Führungslinie: Fläche und Linie auswählen, dann "
     "Sticken › Füllung › Geführte Füllung."],
    ["Konturfüllung", "Linien parallel zum Umriss."],
    ["Kreuzstich", "Kreuze im Raster (Kreuzgröße)."],
    ["Motivfüllung", "Kleine Herzen, Sterne, Kreise, Rauten oder Blumen."],
    ["Netz / Kreuzschraffur", "Offenes Gitter – der Stoff scheint durch."],
    ["Spiralfüllung", "Eine Spirale von der Mitte nach außen."],
    ["Mäander", "Verschlungene Linie im Quilt-Stil."],
    ["Ripple", "Konturlinien von außen nach innen."],
    ["Farbverlauf", "2–5 Garnfarben gehen ineinander über (siehe unten)."],
    ["Schottenkaro (Tartan)", "Karomuster mit Längs- und Querstreifen (siehe unten)."],
    ["Applikation", "Stoff aufnähen: Platzierungslinie – Stopp – Heftstich – Stopp – Satinrand."],
]), ["Füllart", "Beschreibung", "Beispiel"], [20, 46, 34]))
A(h2("Tatami-Einstichmuster"))
A(p(f"Bei Tatami und geführter Füllung bestimmt {M('Muster')}, wo die Nadel in den Reihen einsticht. "
    "Es entsteht ein feines Relief im Garn – 15 Muster stehen zur Wahl:"))
A(img("patterns", 100, "Die 15 Tatami-Muster (Stichlänge 3,5 mm)"))
A(tip("Das Muster sieht man am besten bei glänzendem Garn, größerer Stichlänge (3–4 mm) und "
      "großen Flächen. »Gestreut« vermeidet jedes sichtbare Muster."))
A(ex("Relief in einer großen Fläche", [
    "Ein Rechteck 60 × 40 mm mit Tatami anlegen.",
    "In der Karte »Füllstich« das Muster <i>Rauten</i> wählen und die Stichlänge auf 3,5 mm stellen.",
    "In der realistischen Ansicht erscheint ein feines Rautenmuster im Garn.",
]))
A(h2("Farbverlauf und Schottenkaro"))
A(p("<b>Farbverlauf</b>: Füllart »Farbverlauf« wählen, Farbe 1 und 2 setzen, mit »Farbanzahl« bis "
    "zu drei weitere Farben hinzufügen. Die Reihen werden fein gestreut gemischt; zusammen ergeben "
    "sie die volle Dichte. »Verlauf umkehren« dreht die Richtung."))
A(p("<b>Schottenkaro</b>: Füllart »Schottenkaro (Tartan)«, dann eine Vorlage wählen (Royal Stewart, "
    "Black Watch, MacLeod, Buchanan, Holzfäller, Vichy) oder mit »…« eigene Streifen (Farbe und Breite) "
    "festlegen. »Streifenbreite« skaliert alles, »Gespiegelt wiederholen« ergibt das klassische "
    "Tartan-Muster. Gestickt werden erst alle Längs-, dann die Querstreifen."))
A(img("gradient_tartan", 100, "Farbverläufe und drei Tartan-Vorlagen"))
A(ex("Sonnenuntergang", [
    "Einen Kreis (60 mm) zeichnen, Füllart <i>Farbverlauf</i>.",
    "Farbe 1 Gelb, Farbe 2 Orange, mit »Farbanzahl« eine dritte Farbe Rot dazunehmen.",
    "Mit »Verlauf umkehren« drehst du die Richtung, falls Rot auf der falschen Seite liegt.",
]))
A(h2("Applikation"))
A(p("Füllart »Applikation«: Die Maschine stickt eine Platzierungslinie und stoppt. Du legst den "
    "Applikationsstoff auf, sie heftet ihn fest (Zickzack oder Steppstich) und stoppt erneut – jetzt "
    "den überstehenden Stoff abschneiden. Zum Schluss deckt ein Satinrand die Kante ab. Die "
    "Satinbreite stellst du in der Karte »Applikationsrand« ein."))
A(img("applique", 40, "Herz als Applikation (die Fläche zeigt den aufgelegten Stoff)"))
A(h3("Schneidedatei für Applikationen"))
A(p(f"{M('Export › Schneidedatei')} speichert alle Applikationsformen als SVG in Originalgröße – für "
    "Schneideplotter wie Cricut, Brother ScanNCut oder Silhouette. Der Stoff wird so exakt passend "
    "zugeschnitten und schon vor dem Sticken aufgelegt. Eine Zugabe (z. B. 1 mm) ist möglich."))
A(ex("Applikationsstoff mit dem Plotter schneiden", [
    "Das Design mit der Applikationsfläche fertigstellen.",
    f"{M('Export › Schneidedatei')}, Zugabe 0 mm, als SVG speichern.",
    "Die SVG im Programm des Plotters öffnen (Maßstab 100 %), Stoff auf die Matte, schneiden.",
]))
A(h2("Rand- und Linienarten"))
EX_LINES = [
    "Feine Details wie Augen und Wimpern, Konturen für Redwork.",
    "Unterstreichung unter einem Namen, Blumenstiele, Quiltlinien.",
    "Rand um einen Aufnäher, Kontur um eine Tatami-Fläche.",
    "Applikation festnähen, Stoffkante versäubern.",
    "Applikationskante im Landhausstil.",
    "Dekorative Punktlinie, jeder Einstich genau gesetzt.",
    "Herzranke um ein Babylätzchen, Muschelkante um ein Kissen.",
]
A(img("lines", 100, "Rand- und Linienarten"))
A(table(with_ex(EX_LINES, [
    ["Steppstich", "Einfache Linie; Stichlänge einstellbar. »Ecken genau einstechen« trifft jede Ecke."],
    ["Bohnenstich", "Jeder Stich mehrfach (vor-zurück-vor) – kräftige Linie. »Wiederholungen« 1 = "
     "dreifach, 2 = fünffach. Das <b>Muster</b>-Feld erlaubt Folgen: »1 0« abwechselnd dreifach und "
     "einfach, »2 0 0« Perlenmuster."],
    ["Satinstich", "Satinband mit Breite und Dichte. Spitze Ecken bekommen eine <b>Gehrung</b> "
     "(siehe unten)."],
    ["Zickzack", "Offener Zickzack (Breite, Abstand)."],
    ["E-Stich", "Deckenstich: Grundlinie mit Zacken – ideal für Applikationen."],
    ["Manuell", "Jeder Punkt der Linie ist genau ein Einstich."],
    ["Motivstich", "Kleine Motive (Herzen, Sterne, Blätter …) oder Muschelkante, Welle, Schlaufen "
     "entlang der Linie (siehe unten)."],
]), ["Art", "Beschreibung", "Beispiel"], [16, 50, 34]))
A(h2("Motivstich-Linie"))
A(p("Stichart <b>Motivstich</b> (bei Linien und Rändern) wiederholt kleine Motive entlang der Linie: "
    "Herzen, Sterne, Kreise, Rauten, Blätter, Blüten oder durchgehend als Muschelkante, Welle, Zacken "
    "und Schlaufen. Einstellbar sind Motivgröße, Abstand, »Abwechselnd oben/unten« (ergibt eine "
    "Ranke) und »Kräftig« (Bohnenstich)."))
A(img("ex_motiflines", 90, "Motivstich-Linien entlang einer Welle"))
A(ex("Blätterranke um einen Namen", [
    "Mit der Linie (L) einen geschwungenen Bogen unter den Namen zeichnen.",
    "Rechts unter <i>Linie</i>: Stichart <i>Motivstich</i>, Motiv »Blätter«, Größe 7 mm, Abstand 1 mm.",
    "»Abwechselnd oben/unten« anhaken – fertig ist die Ranke. Garnfarbe Grün.",
]))
A(h2("Satin-Ecken mit Gehrung"))
A(p("An spitzen Ecken (ab 35°) fächern die Satinstiche um die Ecke: Innen bleibt der Einstich an der "
    "Gehrung und die Stiche werden verkürzt (kein Garnstau, kein Fadenbruch), außen reicht der Satin "
    "bis in die Ecke (keine Lücke). Gerade Stücke behalten senkrechte Stiche. Abschaltbar unter "
    f"{M('Feinheiten › Satin-Ecken')}."))
A(img("satin_corners", 85, "Links ohne, rechts mit Gehrung"))
A(ex("Quadrat mit sauberen Satin-Ecken", [
    "Ein Quadrat 30 × 30 mm zeichnen, Rand <i>Satinstich</i>, Breite 3 mm.",
    "Simulator öffnen: an den Ecken fächern die Stiche, innen kürzer – kein Garnknubbel.",
    f"Zum Vergleich {M('Feinheiten › Satin-Ecken')} auf »Einfach« stellen.",
]))

# ---------------------------------------------------------------- 6 Satinsäulen
A(h1("Satinsäulen"))
EX_SATIN = [
    "E-Stich für einen Applikationsrand.",
    "0,35 mm für mehr Glanz auf dunklem Stoff; 0,5 mm auf dünnem Stoff.",
    "0,2 mm auf T-Shirts, damit Buchstaben nicht dünner wirken.",
    "Die enge Kurve im »S« bleibt flach.",
    "Säule 12 mm breit: Teilung bei 7 mm, »Zufällig teilen« an.",
    "Buchstabe endet nah am nächsten – weniger Sprünge.",
]
A(p("Satinsäulen (Werkzeug Säulen-Satin oder Sticken › Satin › In Säulen-Satin) sind die Profi-Technik "
    "für Schrift, Ränder und schmale Formen. Die Karte »Satinstich« bietet:"))
A(table(with_ex(EX_SATIN, [
    ["Satinart", "Satin, Zickzack-Satin oder E-Stich."],
    ["Dichte", "Abstand der Stiche (0,4 mm Standard)."],
    ["Zugausgleich", "Macht die Säule etwas breiter, weil der Faden den Stoff zusammenzieht."],
    ["Kurze Stiche", "In engen Kurven wird an der Innenseite jeder zweite Stich eingerückt "
     "(Anteil der Breite) – kein Garnstau."],
    ["Max. Stichlänge", "Breitere Satinstiche werden geteilt; »Zufällig teilen« versetzt die "
     "Teilungspunkte, damit keine Linie in der Mitte entsteht."],
    ["Start / Ende", "Wo die Säule beginnt und endet (wichtig für Schriften und Wege)."],
]), ["Einstellung", "Wirkung", "Beispiel"], [18, 48, 34]))
A(img("satin_types", 100, "Satinarten, Zufall, kurze Stiche in Kurven, mehrfarbiger Satin"))
A(h2("Satin-Werkzeuge"))
EX_SATTOOLS = [
    "Wellenlinie wird ein 3 mm breites Satinband (Bild unten).",
    "Säule ist zu dünn geraten – als Bohnenstich-Linie weiter.",
    "Der Stiel soll unten beginnen, wo die Blüte endet.",
    "Langen Rand in zwei Hälften teilen und zweifarbig sticken.",
    "Schreibschrift aus 8 Säulen: ein Weg, keine Sprünge.",
    "Regenbogen-Bogen in 6 Farben.",
]
A(table(with_ex(EX_SATTOOLS, [
    ["In Säulen-Satin", "Linie wird zur Satinsäule (Breite wie der Satinrand)."],
    ["In Linie umwandeln", "Säule wird zur Mittellinie."],
    ["Richtung umkehren", "Säule bzw. Linie von der anderen Seite sticken."],
    ["Satin teilen", "Im Punkte-Werkzeug ein Paar wählen, dann teilen."],
    ["<b>Auto-Satin</b>", "Mehrere Satinsäulen/Satinlinien auswählen: kürzeste Reihenfolge, "
     "passende Richtung, Wege als Steppstich verdeckt unter den Säulen statt Sprüngen."],
    ["<b>Mehrfarbiger Satin</b>", "Eine Säule der Länge nach in 2–6 farbige, leicht überlappende "
     "Streifen teilen."],
]), ["Befehl (Sticken › Satin)", "Wirkung", "Beispiel"], [24, 42, 34]))
A(img("autosatin", 85, "Auto-Satin: orange gestrichelt = Sprünge, rotes ✕ = Fadenschnitt"))
A(img("ex_satinline", 100, "In Säulen-Satin umwandeln und Mittellinie"))
A(ex("Regenbogen mit Mehrfarbigem Satin", [
    "Mit Säulen-Satin einen Bogen zeichnen, 12 mm breit.",
    f"{M('Sticken › Satin › Mehrfarbiger Satin')}: 6 Farben von Rot bis Violett, Überlappung klein.",
    "Es entstehen 6 schmale Säulen nebeneinander – ein Regenbogen.",
]))
A(h2("3D-Puff"))
A(p(f"{M('Sticken › Effekte › 3D-Puff')} richtet ausgewählte Satinsäulen, Satinlinien oder "
    "Schriftzüge für Schaumstoff (Puffy Foam) ein:"))
A(bullets([
    "dichter Satin (0,25 mm), keine bzw. nur Mittellinien-Unterlage, kein Zugausgleich, keine Teilung;",
    "<b>Endkappen</b> an beiden Säulenenden – sie schneiden den Schaum sauber ab;",
    "die Puff-Objekte kommen ans Ende, davor hält die Maschine an (Stopp).",
]))
A(steps(["Flache Teile des Designs sticken – die Maschine stoppt.",
         "Schaumstoff (2–3 mm, in Garnfarbe) über die Puff-Stelle legen.",
         "Weitersticken: die Satinstiche drücken den Schaum herunter und stanzen ihn aus.",
         "Überstehenden Schaum abreißen, Reste kurz mit Heißluft (Föhn) schrumpfen."]))
A(img("puff", 85, "Normale Säule und 3D-Puff-Säule mit Endkappen"))
A(img("ex_cap", 45, "Beispiel: Puff-Schriftzug für eine Kappe"))
A(tip("Puff wirkt erst ab etwa 3 mm Säulenbreite – das Programm warnt bei schmaleren Säulen. "
      "Für Kappen zusätzlich die Stoffart »Kappe« wählen.", "Achtung"))

# ---------------------------------------------------------------- 7 Feinheiten
A(h1("Feinheiten – Profi-Einstellungen je Objekt"))
EX_FINE = [
    "Kleine Punkte im Design ohne Unterlage – kein Knubbel.",
    "Eine 1,5 mm schmale Haarlinie bleibt weich.",
    "»Einfach« für einen Retro-Look.",
    "Puff-Schriftzug für eine Kappe.",
    "Abstand 3 mm und Einzug 0,5 mm auf Frottee.",
    "Zwei Lagen auf einer Strickjacke.",
    "Saubere Kante bei einer Tatami-Fläche ohne Rand.",
    "Kontur + Zickzack für breite Buchstaben auf Fleece.",
    "+0,4 mm, damit die Fläche unter den Satinrand reicht.",
    "Große Hintergrundfläche ohne Musterstreifen.",
    "Gras, Fell, Federn.",
    "»Stern« auf glatten Stoffen; »aus« für Dateien mit eigenem Vernähen.",
]
A(p("Die unterste Karte der Eigenschaften heißt <b>Feinheiten</b>. Sie zeigt nur, was für das "
    "gewählte Objekt etwas bewirkt. Die Standardwerte passen für die meisten Designs."))
A(img("props_bottom", 40, "Karte »Feinheiten« einer Fläche"))
A(table(with_ex(EX_FINE, [
    ["Unterlage nach Größe", "Teile unter 2 mm Breite: keine Unterlage, unter 5 mm: nur Randlinie, "
     "größer: volle Unterlage (bei neuen Objekten an)."],
    ["Satindichte nach Breite", "Schmale Säulen lockerer (nicht steif), breite etwas dichter "
     "(bei neuen Objekten an)."],
    ["Satin-Ecken", "Gehrung (sauber) oder einfach."],
    ["3D-Puff (Endkappen)", "Endkappen für Schaumstoff (Satinsäulen)."],
    ["Unterlage-Winkel / -Abstand / -Einzug", "Richtung (90° = quer zum Deckstich), Reihenabstand "
     "und Abstand zum Rand der Unterlage."],
    ["Unterlage-Lagen", "Eine Lage oder zwei gekreuzte Lagen (für dehnbare Stoffe)."],
    ["Randlinie unter der Füllung", "Steppstich-Kontur vor den Unterlagenreihen."],
    ["Satin-Unterlage", "Säulen: Automatisch, Keine, Mittellinie, Kontur, Zickzack oder Kombinationen."],
    ["Erweitern", "Füllfläche vergrößern/verkleinern (mm) – z. B. damit sie unter den Satinrand reicht."],
    ["Zufällige Stichlänge", "Stichlänge zufällig variieren – keine sichtbaren Einstichmuster."],
    ["Zufällige Breite / Abstand", "Säulen natürlicher, z. B. für Fell oder Gras."],
    ["Vernähen", "Form der Vernähstiche (siehe Bild) und »Vor jedem Sprung vernähen«."],
]), ["Einstellung", "Wirkung", "Beispiel"], [24, 44, 32]))
A(img("underlay", 92, "Unterlage: ohne, eine Lage mit Randlinie, zwei gekreuzte Lagen (hier locker gestickt, damit sie sichtbar ist)"))
A(img("ties", 80, "Vernähstich-Arten (stark vergrößert, rote Punkte = Einstiche)"))
A(ex("Lücken zwischen Füllung und Rand beseitigen", [
    "Die Fläche wählen, deren Satinrand nicht ganz anliegt.",
    f"{M('Feinheiten › Erweitern')} auf 0,4 mm stellen – die Füllung reicht jetzt unter den Rand.",
    "Bei dehnbarem Stoff zusätzlich den Zugausgleich um 0,1–0,2 mm erhöhen.",
]))

# ---------------------------------------------------------------- 8 Umwandeln & verbessern
A(h1("Umwandeln und Stickbild verbessern"))
EX_CONVERT = [
    "Initiale »A« in eine Form umwandeln und ein Herz ausschneiden.",
    "Digitalisierte Kontur mit 300 Punkten übersichtlich machen.",
    "Einen einzelnen störenden Stich von Hand löschen.",
    "Schmaler Ring wird eine Bohnenstich-Linie (Bild in Kapitel 6).",
    "Altes DST-Logo neu digitalisieren.",
    "Name auf ein Frottee-Handtuch: der Flor bleibt unten.",
    "Blatt + Linie entlang der Mittelrippe.",
    "Blume aus Linien ohne einen Sprung (Bild unten).",
    "Wie Redwork, aber weniger doppelte Strecken.",
    "Herz: Start unten an der Spitze, Ende oben, wo die Schrift beginnt.",
]
A(p("Die Befehle stehen in den Reitern <b>Schrift › Umwandeln</b>, <b>Sticken</b> und "
    "<b>Optimieren</b>."))
A(table(with_ex(EX_CONVERT, [
    ["In Form umwandeln", "Schriftzug wird zu bearbeitbaren Formen."],
    ["Punkte reduzieren", "Weniger Punkte."],
    ["In Stiche umwandeln", "Form wird zu festen Stichen – um einzelne Sprünge/Stiche von Hand zu "
     "bearbeiten."],
    ["Mittellinie", "Aus einer schmalen Fläche (z. B. digitalisierte Schrift) eine Linie zum Sticken."],
    ["Umriss aus Stickdatei", "Aus einer importierten Stickdatei bearbeitbare Formen je Farbe."],
    ["Knockdown", "Lockere Füllung in Stofffarbe unter dem Motiv – drückt Frottee/Fleece-Flor "
     "herunter."],
    ["Geführte Füllung / Pfad lösen", "Führungslinie zuordnen bzw. wieder lösen."],
    ["Redwork", "Ausgewählte Steppstichlinien als ein Weg ohne Sprung; jede Strecke genau zweimal "
     "(Rückweg in denselben Einstichen)."],
    ["Auto-Route", "Wie Redwork, aber jede Strecke nur einmal und nur wo nötig doppelt."],
    ["Start-/Endpunkt", "Für Flächen und Säulen festlegen, wo gestickt wird (Sticken › "
     "Start & Ende)."],
]), ["Befehl", "Wirkung", "Beispiel"], [20, 44, 36]))
A(img("ex_redwork", 100, "Redwork und Auto-Route: orange = Sprünge, rotes ✕ = Fadenschnitt"))
A(ex("Blume aus Linien ohne Sprung (Redwork)", [
    "Blütenblätter und Stiel als einzelne Linien im Steppstich zeichnen; die Enden sollen sich "
    "berühren.",
    f"Alle Linien auswählen ({K('Strg+A')}) und {M('Sticken › Linien führen › Redwork')}.",
    "Die Statuszeile meldet »ohne Sprung« – die Maschine stickt alles in einem Zug.",
]))
A(ex("Name auf ein Frottee-Handtuch (Knockdown)", [
    "Stoffart »Frottee« wählen und den Schriftzug anlegen.",
    f"Schriftzug auswählen, {M('Sticken › Effekte › Knockdown')}.",
    "Darunter entsteht eine lockere Fläche in Stofffarbe, die den Flor niederdrückt – die Schrift "
    "versinkt nicht.",
]))
A(h2("Überlappung entfernen"))
A(p(f"{M('Optimieren › Verbessern › Überlappung entfernen')}: Flächen, die von später "
    "gestickten Objekten verdeckt werden, werden nicht doppelt gestickt. Ein schmaler Rand "
    "(Standard 1 mm) bleibt überlappend, damit durch Verzug keine Lücke entsteht. Ergebnis: weniger "
    "Stiche, weichere und flachere Stickerei."))
A(img("overlap", 85, "Beispiel: 17 % weniger Stiche"))
A(tip("Formen mit eigenem Rand werden übersprungen (der Rand würde sonst der neuen Kontur folgen). "
      "Spart das Aussparen kaum Stiche – etwa bei kleinen Überdeckungen –, bleibt die Form "
      "unverändert; die Statuszeile sagt es dir."))
A(ex("Blume auf einem Blatt", [
    "Erst ein großes grünes Blatt, darüber eine rote Blüte zeichnen.",
    f"Beide auswählen, {M('Optimieren › Verbessern › Überlappung entfernen')}, Rand 1 mm.",
    "Unter der Blüte wird das Blatt nicht mehr gestickt – weniger Stiche, weicher Stoff.",
]))
A(h2("Kleinteile entfernen"))
A(p("Löscht winzige Flächenstücke und Löcher (Standard unter 2 mm²) sowie Linien unter 2 mm – "
    "sie entstehen oft beim Digitalisieren und ergeben nur Sprünge und Fadensalat."))
A(img("ex_cleanup", 70, "Kleinteile entfernen: die Fussel-Flächen und ihre Sprünge verschwinden"))
A(ex("Logo nach dem Bild-Assistenten säubern", [
    "Alle Objekte auswählen.",
    f"{M('Optimieren › Verbessern › Kleinteile entfernen')}, Grenze 2 mm².",
    "Die Statuszeile meldet, wie viele Teile entfernt wurden; Sprünge zu den Fusseln fallen weg.",
]))
A(h2("Kurvenanpassung"))
A(p(f"{M('Einstellungen › Sticken › Kurvenanpassung')}: Steppstiche werden in engen Kurven "
    "automatisch kürzer, sodass sie höchstens 0,2 mm von der Linie abweichen. Gerade Strecken "
    "behalten die volle Stichlänge."))
A(img("curves", 70, "Kreis (10 mm) mit 3-mm-Steppstich"))
A(ex("Kleine Kreise rund statt eckig", [
    f"{M('Einstellungen › Sticken')}: Kurvenanpassung 0,2 mm.",
    "Einen Kreis (10 mm) mit Steppstich-Rand und Stichlänge 3 mm zeichnen.",
    "In der Stichansicht ist der Rand jetzt rund – ohne die Stichlänge auf gerader Strecke zu "
    "verkürzen.",
]))
A(h2("Dichteprüfung"))
A(p(f"{M('Optimieren › Prüfen › Dichte prüfen')} färbt Stellen, an denen zu viel Garn übereinanderliegt "
    "(gelb = viel, rot = zu viel, z. B. drei Lagen übereinander). Dort Überlappungen entfernen, "
    "Dichte verringern oder Objekte aussparen."))
A(img("screen_density", 70, "Dichteprüfung: drei übereinanderliegende Flächen – in der Mitte rot"))
A(ex("Zu dichte Stellen finden und beheben", [
    f"{M('Optimieren › Prüfen › Dichte prüfen')} – rote Stellen erscheinen.",
    "Die betroffenen Objekte wählen und Überlappung entfernen, oder die Dichte der unteren "
    "Fläche von 0,4 auf 0,5 mm erhöhen (lockerer).",
    "Erneut prüfen, bis nur noch gelbe oder keine Stellen übrig sind.",
]))

# ---------------------------------------------------------------- 9 Reihenfolge & Simulator
# ---------------------------------------------------------------- Verzieren
A(h1("Verzieren: Wiederholen, Muster, Strass und Malen"))
A(p(f"Der Reiter {M('Verzieren')} sammelt alles, was aus einem Motiv mehr macht: Wiederholungen, "
    "Rahmen, Muster, Schmucksteine, Skizzen und gemalte Bilder. Fast alle Funktionen öffnen ein "
    "Vorschaufenster: links die Varianten, in der Mitte die Einstellungen, rechts die Vorschau mit "
    f"Stichzahl und Größe. Das Ergebnis wird als <b>Gruppe</b> eingefügt – mit {K('Alt')}+Klick "
    "wählst du ein einzelnes Teil, um Farbe oder Stichart zu ändern."))
A(h2("Encore – Muster wiederholen"))
A(p(f"Ein Motiv (oder eine Gruppe) wählen, dann {M('Verzieren › Wiederholen › Encore')}. Die Kopien "
    "ersetzen das Original; Strg+Z stellt es wieder her."))
A(img("encore_grid", 100, "Ein Herz – fünf Anordnungen"))
A(table([
    ["Kreis", "Kopien gleichmäßig um die Mitte – Kränze, Blüten, Mandalas. Anzahl, Radius, Startwinkel."],
    ["Bogen", "Kopien auf einem Bogen (nach oben oder unten offen); die letzte Kopie darf kleiner "
     "werden."],
    ["Linie / Bordüre", "Kopien in einer Reihe mit Abstand, Winkel und Wellenversatz – für Borten."],
    ["Rechteck-Rahmen", "Kopien rund um ein Rechteck, auf Wunsch mit besetzten Ecken."],
    ["Form-Rahmen", "Kopien auf dem Umriss von Herz, Stern, Oval, Raute, Sechseck, Tropfen oder Wolke."],
    ["Entlang der Linie", "Erscheint, wenn du zusätzlich eine Linie mit Strg+Klick wählst: Die Kopien "
     "folgen deinem eigenen Pfad."],
], ["Anordnung", "Wofür"], [24, 76]))
A(p("Für alle Anordnungen gilt: »Kopien mitdrehen« lässt sie der Richtung folgen, »Jede zweite Kopie "
    "spiegeln« ergibt symmetrische Bordüren."))
A(img("dialog_encore", 65, "Encore-Fenster: links die Anordnung, rechts die Vorschau"))
A(ex("Herzkranz für ein Kissen", [
    f"Im Reiter {M('Motive')} ein Herz einfügen und auf 16 mm verkleinern.",
    f"{M('Verzieren › Encore')}, links »Kreis«, Anzahl 10, Radius 35 mm.",
    "»Übernehmen« – zehn Herzen als Gruppe. Mit Alt+Klick jedes zweite Herz rosa färben.",
]))
A(h2("Rahmen & Schnörkel"))
A(p(f"{M('Verzieren › Rahmen › Rahmen & Schnörkel')} fügt fertige Zierelemente ein: Rahmen mit "
    "Eckschnörkeln, Bogenkante, Wellenrahmen, Rahmen mit Punkten, Doppelrahmen, Trenner, "
    "Eckschnörkel, ein Herz aus Schnörkeln und eine Ranke. Breite, Höhe, Linienstärke, Stichart und "
    "Farben stellst du im Fenster ein."))
A(img("orn_grid", 75, "Die neun Zierelemente"))
A(h2("Strass & Perlen"))
A(p(f"Eine Form, Linie oder einen Schriftzug wählen, dann {M('Verzieren › Strass & Perlen › Strass')}. "
    "Die Steine setzt StichWizard entlang der Kontur, als Fläche (versetzt wie Waben oder gerade) "
    "oder beides. Steingrößen SS6 bis SS30 (2,0–6,4 mm), Art Kristall, Perle oder matt."))
A(img("stones_grid", 80, "Strass auf einem Stern: Kontur, Fläche, beides"))
A(p("Steine werden nicht gestickt. Sie erscheinen in der Vorschau und auf einer eigenen "
    f"<b>Strass-Schablone</b> ({M('Verzieren › Strass & Perlen › Schablone')}, auch unter Export): als "
    "SVG für den Schneideplotter (Löcher 0,4 mm größer als der Stein) oder als PDF mit Stückliste zum "
    "Drucken. In den Eigenschaften (Karte <i>Strass & Perlen</i>) änderst du später Größe, Art und "
    "Farbe."))
A(ex("Glitzerstern auf einem T-Shirt", [
    "Einen Stern mit 40 mm einfügen und auswählen.",
    f"{M('Verzieren › Strass')}, »Kontur und Fläche«, Steingröße SS10.",
    f"{M('Strass-Schablone')} als SVG speichern, mit dem Plotter aus Strassfolie schneiden, Steine "
    "einbürsten und nach dem Sticken aufbügeln.",
]))
A(h2("Spirograph"))
A(p(f"{M('Verzieren › Muster › Spirograph')} zeichnet Kurven wie mit dem Spirographen aus der Kindheit: "
    "Innenrad, Außenrad, Rosette und Guilloche-Ring (wie auf Geldscheinen). Mehrere Lagen in "
    "verschiedenen Farben ergeben Mandalas."))
A(img("spiro_grid", 80, "Die vier Spirograph-Arten"))
A(h2("Text in Form (Word Sculpt)"))
A(p(f"{M('Verzieren › Muster › Text in Form')} füllt eine Form mit Wörtern: Herz, Stern, Kreis, "
    "Oval und weitere – oder die gewählte eigene Form. Zeilen, die nicht passen, werden gestaucht, "
    "gedehnt oder bekommen andere Wörter aus deiner Liste. Die Wörter wiederholen sich, bis die Form "
    "voll ist (abschaltbar); auf Wunsch kommt die Kontur der Form dazu."))
A(img("wordsculpt", 80, "Text in Form"))
A(tip("Unter etwa 5 mm Zeilenhöhe werden Buchstaben unsauber. Ist die Form zu klein, meldet das "
      "Programm das – dann die Form größer oder die Zeilen höher einstellen."))
A(h2("Sketch – mit Stichen zeichnen"))
A(p(f"Werkzeug {M('Verzieren › Zeichnen & Malen › Sketch')} ({K('D')}): Mit gedrückter Maustaste "
    "zeichnen, jeder Strich wird sofort eine Stichlinie. Der Pfeil am Knopf wählt den Stil: "
    "<b>Bleistift</b> (Skizzenstich), Steppstich, Bohnenstich, Zickzack oder Satin 2/4 mm."))
A(img("sketch", 60, "Der Skizzenstich läuft mehrmals leicht versetzt – wie ein Bleistiftstrich"))
A(p("Beim Skizzenstich stellst du in den Eigenschaften der Linie die <b>Streuung</b> (wie weit die "
    "Durchgänge auseinanderliegen) und die <b>Extra-Durchgänge</b> ein."))
A(h2("Mal-Atelier und Druck-Applikation"))
A(p(f"{M('Verzieren › Zeichnen & Malen › Mal-Atelier')} ist ein kleines Malprogramm: Pinsel, Radierer, "
    "Linie, Rechteck, Ellipse, Füllen, Farbpipette und Text, dazu Stärke und Deckkraft. Ein Bild "
    "lässt sich laden und weiterbemalen. Unter <b>Verwenden</b> legst du fest, was daraus wird:"))
A(table([
    ["Als Druck-Applikation einfügen", "Das Bild wird auf Stoff gedruckt (Tintenstrahl-Stoff oder "
     "Transferpapier) und im Rahmen mit einem Satinrand aufgestickt. Umriss: abgerundetes Rechteck, "
     "Oval oder der Umriss des Motivs."],
    ["Als Vorlage zum Nachzeichnen", "Das Bild liegt als Vorlage unter dem Design."],
    ["Mit dem Bild-Assistenten sticken", "Das Bild geht direkt an den Bild-Assistenten."],
], widths=[32, 68]))
A(img("dialog_paint", 70, "Mal-Atelier"))
A(img("print_applique", 55, "Druck-Applikation: Druckbild und gestickter Rand"))
A(p(f"Zum Drucken: {M('Verzieren › Druckvorlage')} (auch unter Export) erzeugt ein PDF mit allen "
    "Druckbildern in Originalgröße. Für Transfer- oder Bügelpapier wird das Bild gespiegelt. Beim "
    "Sticken hält die Maschine nach der Platzierungslinie an: Druck auflegen, weitersticken. Ein "
    "Doppelklick auf das Druckbild öffnet das Mal-Atelier wieder."))
A(ex("Gemaltes Bild als Aufnäher", [
    f"{M('Mal-Atelier')}: Bild 60 × 60 mm, eine Sonne malen.",
    "Verwenden: »Als Druck-Applikation einfügen«, Umriss »Umriss des Motivs«, Satinrand 3 mm.",
    f"{M('Druckvorlage')} drucken (Stoffdruckpapier, 100 %), ausschneiden.",
    "Sticken: Platzierungslinie – Stopp – Druck auflegen – Heftstich und Satinrand.",
]))

# ---------------------------------------------------------------- Assistenten
A(h1("Assistenten: Projekt im Rahmen, Kreuzstich, Quilt, Stammbaum"))
A(h2("Projekt im Rahmen (In-the-Hoop)"))
A(p(f"{M('Erstellen › Vorlagen & Bibliothek › Projekt im Rahmen')} legt fertige Nähprojekte an, die "
    "komplett im Stickrahmen entstehen – ohne Nähmaschine. Zur Wahl stehen Untersetzer, "
    "Schlüsselanhänger, Gepäckanhänger, Baumschmuck, Karte & Lesezeichen, Kartenetui, Handyhülle, "
    "Pass- & Buchhülle, Reißverschluss-Etui und Kuschelfigur. Größe, Form, Text, Motiv und Farben "
    "stellst du im Fenster ein."))
A(img("ith_grid", 100, "Die zehn Projekte"))
A(img("dialog_ith", 70, "Projekt im Rahmen: Einstellungen und Vorschau"))
A(p("Jedes Projekt besteht aus nummerierten <b>Arbeitsschritten</b>. Nach jedem Schritt hält die "
    "Maschine an (auch Mehrnadel-Maschinen), damit du Stoff, Vlies oder Reißverschluss auflegen "
    "kannst. »Farben zusammenfassen« wird dabei abgeschaltet, damit die Reihenfolge stimmt."))
A(table([
    ["1. Platzierungslinie", "Zeigt auf dem eingespannten Vlies, wohin der Stoff kommt."],
    ["2. Heftstich", "Hält den aufgelegten Stoff (und Volumenvlies oder Filz) fest."],
    ["3. Motiv", "Das eigentliche Stickmotiv."],
    ["4. Rückseite", "Rahmen umdrehen, Rückseitenstoff unterkleben, Heftstich durch alle Lagen."],
    ["5. Satinrand", "Deckt alle Stoffkanten ab – danach ausschneiden."],
], ["Schritt (Untersetzer)", "Was passiert"], [28, 72]))
A(p(f"{M('Export › Projekt-Anleitung')} schreibt ein PDF mit Vorschau, Materialliste, Zuschnittmaßen "
    "und allen Arbeitsschritten in der Garnfarbe des Schritts – zum Ausdrucken neben der Maschine."))
A(ex("Schlüsselanhänger mit Namen", [
    f"{M('Projekt im Rahmen')}, links »Schlüsselanhänger«, Text »Lena«.",
    "»Einfügen«, dann Export › Projekt-Anleitung drucken.",
    "Mit Reißvlies einspannen und Schritt für Schritt nach der Anleitung sticken; zum Schluss "
    "ausschneiden und eine Öse durch das Loch ziehen.",
]))
A(tip("Wird das Projekt größer als dein Rahmen, warnt das Programm. Dann im Fenster die Größe "
      "verringern oder einen größeren Rahmen wählen."))
A(h2("Kreuzstich-Atelier"))
A(p(f"{M('Verzieren › Kreuzstich')} öffnet ein Raster wie auf Kreuzstichpapier. Werkzeuge: volles "
    "Kreuz, halbe Kreuze (/ und \\), Viertelkreuz, Rückstich (Linie zwischen den Ecken), Füllen, "
    "Farbpipette und Radierer; Rechtsklick radiert. Darunter Kästchenzahl, Kästchengröße "
    "(z. B. 2,5 mm) und Fadenstärke."))
A(img("dialog_cross", 80, "Kreuzstich-Atelier mit einem aus einem Bild erzeugten Muster"))
A(p("<b>Bild laden → Kreuzstich</b> verkleinert ein Foto oder eine Grafik auf das Raster und "
    "reduziert es auf wenige Garnfarben; helle Bereiche bleiben auf Wunsch frei. Gestickt werden die "
    "Kreuze farbweise in Reihen hin und zurück – wie von Hand, mit möglichst wenig Sprüngen. Ein "
    "Doppelklick auf das Kreuzstich-Objekt öffnet das Atelier wieder."))
A(img("cross_ex", 40, "Das Muster als Stickerei"))
A(ex("Blume aus einem Bild", [
    f"{M('Verzieren › Kreuzstich')}, »Bild laden → Kreuzstich …«, eine einfache Grafik wählen.",
    "Breite 36 Kästchen, 3 Garnfarben, »Helle Bereiche frei lassen«.",
    "Einzelne Kästchen mit dem Kreuz-Werkzeug nachbessern, Umrisse mit Rückstich betonen.",
    "»Übernehmen« – das Muster steht als ein Objekt im Design.",
]))
A(h2("Quiltblock"))
A(p(f"{M('Verzieren › Assistenten › Quiltblock')} erzeugt Quiltmuster für einen Block aus Oberstoff, "
    "Vlies und Rückseite: Echo-Quilting (Linien folgen dem Motiv), Stippling (Mäander), "
    "Kreuzschraffur, Konturlinien und Spirale. Blockform (Quadrat, Rechteck, Kreis, Sechseck), Motiv "
    "in der Mitte, Linienabstand und Stichart stellst du ein. Gequiltet wird ohne Unterlage, die "
    "Linien laufen möglichst ohne Sprung."))
A(img("quilt_grid", 100, "Die fünf Quiltmuster mit Herz in der Mitte"))
A(h2("Stammbaum"))
A(p(f"{M('Verzieren › Assistenten › Stammbaum')} setzt Namen (und auf Wunsch Jahreszahlen) in eine "
    "<b>Ahnentafel</b> (Kinder, Eltern, Großeltern, auf Wunsch Urgroßeltern) oder einen "
    "<b>Familienbaum</b> mit Stamm und Ästen. Rahmen um die Namen, Linienart, Schrift und Farben sind "
    "einstellbar."))
A(img("family", 90, "Ahnentafel und Familienbaum"))
A(ex("Familienbaum als Geschenk", [
    f"{M('Stammbaum')}, »Familienbaum«, Namen mit Komma getrennt eintragen.",
    "Titel »Familie Berger«, Schrift »Blockschrift«, Rahmen »Abgerundet«.",
    "Größe an den Rahmen anpassen – zu große Bäume meldet das Programm.",
]))

A(h1("Stichreihenfolge, Sprünge und Simulator"))
A(h2("So plant StichWizard die Reihenfolge"))
A(bullets([
    "<b>Element für Element</b>: Jede Fläche wird komplett fertig gestickt – Unterlage, Füllung und "
    "ihr eigener Rand in gleicher Farbe –, erst dann geht es zum nächsten Element.",
    "Innerhalb einer Fläche laufen Verbindungen als Steppstich <b>unter noch kommenden Reihen</b> "
    "oder am Rand entlang. Läge ein Weg sichtbar auf fertigen Reihen, wird stattdessen gesprungen "
    "und geschnitten.",
    "Jede Fläche endet möglichst nah am nächsten Element.",
    "Sprünge ab der eingestellten Länge (Standard 3 mm) werden geschnitten – es bleibt kein Faden "
    "auf dem Stoff.",
    "<b>Farben zusammenfassen</b> (Optimieren › Reihenfolge): gleiche Garnfarben nacheinander, ohne "
    "Überlappungen zu vertauschen. Ein Maschinenstopp (Applikation, 3D-Puff) ist dabei eine Grenze.",
]))
A(img("ex_jumps", 55, "Sprünge (orange) und Schnitte (rot) im Beispiel-Design"))
A(ex("Weniger Farbwechsel", [
    "Ein Design mit drei roten und zwei blauen Herzen, abwechselnd angelegt.",
    f"{M('Optimieren › Reihenfolge › Farben zusammenfassen')}: erst alle roten, dann alle blauen.",
    "Statt 5 nur noch 2 Garnwechsel – Herzen, die sich überlappen, behalten ihre Reihenfolge.",
]))
A(h2("Simulator & Optimierer"))
A(p(f"{K('F5')} (oder {K('F6')}) öffnet den Simulator: Die Stickerei entsteht Stich für Stich wie "
    "auf der Maschine. Mit dem Tempo-Regler (1–5000 Stiche/s, »wie Maschine«) steuerst du die "
    "Geschwindigkeit, »◀ / ▶« springt zum vorigen/nächsten Sprung."))
A(img("screen_simulator", 100, "Simulator & Optimierer"))
A(bullets([
    "Rechts: Stiche, Sprünge, Schnitte und Stickzeit – vorher → jetzt.",
    "Nummerierte Sprünge mit Richtungspfeil; jeden Sprung einzeln bearbeiten (Schnitt setzen/"
    "entfernen) oder alle auf einmal (»Schnitt entfernen bei Sprüngen unter …«).",
    "<b>Reihenfolge</b>: Teil nach einem Sprung früher/später sticken oder umdrehen; automatisch "
    "(kürzeste Wege) oder von Hand.",
]))
A(ex("Vor dem Export prüfen", [
    f"{K('F5')} drücken, Tempo auf »wie Maschine«.",
    "Mit »▶« von Sprung zu Sprung springen: unnötige Sprünge fallen sofort auf.",
    "Rechts »Reihenfolge automatisch« – Stiche, Sprünge und Stickzeit vorher → nachher vergleichen.",
]))
A(h2("Sprünge von Hand bearbeiten"))
A(p(f"Werkzeug {M('Sprünge bearbeiten')} ({K('J')}): Sprünge erscheinen orange, Fadenschnitte als "
    "rotes ✕. Klick auf einen Sprung: Schnitt setzen/entfernen oder mit Stichen verbinden – das "
    "Programm sagt, ob der Verbindungsfaden später überstickt wird. Zwischen zwei Objekten steuerst "
    "du den Schnitt auch in den Eigenschaften unter <b>Schnitt danach</b> (automatisch, immer, nie, "
    "Stopp)."))
A(p(f"<b>Sprungstiche optimieren</b> (Optimieren › Sprünge) ordnet importierte Stickdateien neu und "
    "führt Verbindungen verdeckt; eigene Designs werden beim Export automatisch optimiert."))
A(ex("Einen kurzen Sprung ohne Schnitt lassen", [
    f"Werkzeug {M('Sprünge bearbeiten')} ({K('J')}) wählen.",
    "Auf den orange gestrichelten Sprung zwischen zwei nahen Buchstaben klicken.",
    "»Schnitt entfernen« – die Maschine fährt ohne Abschneiden weiter (spart Zeit). Das Programm "
    "sagt, ob der Faden später überstickt wird.",
]))

A(h2("Stich-Editor"))
A(p(f"{M('Optimieren › Stiche › Stich-Editor')} zeigt das gewählte Objekt Stich für Stich – ideal für "
    "importierte Stickdateien. Mit ◀ / ▶ oder dem Regler gehst du von Stich zu Stich; X und Y, Art "
    "(Stich, Sprung, Fadenschnitt, Stopp) und Blockfarbe lassen sich direkt ändern. Ziehen verschiebt "
    "Stiche, Entf löscht, Einfg fügt einen ein, »Farbwechsel ab hier« teilt den Farbblock."))
A(img("dialog_stitcheditor", 95, "Stich-Editor"))
A(bullets([
    "<b>Aufräumen</b>: »Entfernen« löscht alle Stiche kürzer als z. B. 0,4 mm (Fadenrisse), "
    "»Teilen« zerlegt zu lange Stiche (z. B. über 7 mm).",
    "Formen und Schriftzüge werden dafür in feste Stiche umgewandelt – erst beim Übernehmen, "
    "Strg+Z macht es rückgängig.",
]))

# ---------------------------------------------------------------- 10 Export
A(h1("Export, Arbeitsblatt und Weitergabe"))
A(h2("Für Maschine exportieren"))
A(p(f"{M('Export › Für Maschine exportieren')} ({K('Strg+E')}) – Format nach Dateiendung wählen:"))
A(table([
    ["PES / PEC", "Brother, Babylock, Deco (PES 6 mit Garnname und Nummer)"],
    ["DST", "Tajima – universell, ohne Farben"],
    ["JEF", "Janome, Elna"],
    ["EXP", "Melco, Bernina"],
    ["VP3", "Pfaff, Husqvarna Viking"],
    ["XXX", "Singer, Compucon"],
    ["U01", "Barudan"],
    ["TBF", "Tajima mit Farben"],
    ["PMV", "Brother Strick-/Stickmaschine"],
    ["ZIP", "PES, DST, JEF, EXP, VP3, XXX, U01 und Stichliste in einem Archiv"],
    ["SVG", "Vektorgrafik"],
    ["CSV / TXT / JSON", "Stichliste als Tabelle, Text oder Daten"],
    ["G-Code", "für CNC-Maschinen und Plotter"],
    ["COL / EDR / INF", "Farblisten"],
], ["Format", "Maschinen / Verwendung"], [22, 78]))
A(h2("An Maschine senden"))
A(p(f"{M('Export › Maschine › An Maschine senden')} speichert das Design in einem Schritt im Format "
    "deiner Stickmaschine auf den USB-Stick. Eingesteckte Sticks und SD-Karten erkennt das Programm "
    "selbst; interne Festplatten erscheinen nie. Über »Anderer Ordner …« legst du zusätzlich z. B. "
    "den Netzwerkordner der Maschine an – er wird gemerkt."))
A(img("dialog_send", 55, "An Maschine senden"))
A(bullets([
    "Der Dateiname wird ohne Umlaute und Leerzeichen geschrieben; »Kurzer Dateiname« kürzt auf "
    "8 Zeichen für ältere Maschinen.",
    "Das Format kommt aus der gewählten Stickmaschine und lässt sich hier ändern.",
    "Auf Wunsch wird das Arbeitsblatt (PDF) mitkopiert und der Stick danach ausgeworfen (Linux).",
]))
A(ex("Design für eine Brother-Maschine auf den USB-Stick", [
    "USB-Stick einstecken.",
    f"{M('Export › An Maschine senden')}: Der Stick steht schon in der Liste, Format PES, Name »Emma«.",
    "»Senden« – danach den Stick abziehen und in die Maschine stecken: Farben und Garnnummern "
    "erscheinen am Display.",
]))
A(h2("Stickmaschine wählen"))
A(p(f"{M('Export › Stickmaschine')} (auch unter Einstellungen › Allgemein) stellt StichWizard auf "
    "deine Maschine ein. Mitgeliefert sind Profile für TEXI IRIS 10, Brother PR1055X, PR680W und "
    "Innov-is 800E, Janome MB-7 sowie je ein allgemeines Profil für Mehrnadel- (DST) und "
    "Einnadel-Maschinen. Über »Eigene Maschine anlegen …« trägst du Nadelzahl, Stickfeld, Format, "
    "Tempo und Nadelsystem selbst ein."))
A(table([
    ["Rahmen", "Die Rahmen der Maschine erscheinen in der Rahmenliste; ein Rahmen, der größer als "
     "das Stickfeld ist, wird gemeldet."],
    ["Exportformat", "Wird für »Für Maschine exportieren« vorausgewählt (z. B. DST bei der Texi)."],
    ["Stickzeit", "Rechnet mit einem praxisnahen Tempo der Maschine."],
    ["Stopps", "Mehrnadel-Maschinen wechseln die Farbe ohne anzuhalten. Damit sie bei Applikation "
     "oder 3D-Puff trotzdem stoppen, steht der Stopp ausdrücklich in der Datei – in DST als eigener "
     "Schritt ohne Stiche, an dem du an der Maschine »Pause/Stopp« setzt."],
    ["Nadel", "Empfehlung je Stoffart mit Nadelsystem, z. B. »DBxK5 75/11, Kugelspitze« für Jersey "
     "oder »80/12 Titan« für Kappen. Steht auch auf dem Arbeitsblatt."],
    ["Nadelplan", "Das Arbeitsblatt ordnet jeder Farbe eine Nadel zu (gleiche Farbe = gleiche Nadel) "
     "und warnt, wenn das Design mehr Farben als die Maschine Nadeln hat."],
], ["Was", "Wirkung"], [18, 82]))
A(ex("TEXI IRIS 10 einstellen", [
    f"{M('Export › Stickmaschine › TEXI IRIS 10')} wählen.",
    "Die Rahmen 110 × 110, 190 × 140 und 310 × 210 mm stehen jetzt in der Liste, das Format ist DST.",
    f"{M('Stickmaschine › Maschinen-Info und Nadel …')} zeigt die Nadel für die gewählte Stoffart.",
    "Arbeitsblatt drucken: Der Nadelplan sagt dir, welches Garn auf welche Nadel kommt.",
]))
A(tip("Die Angaben der Profile stammen von Herstellern und Händlern – bitte mit dem Handbuch deiner "
      "Maschine abgleichen. Abweichende Rahmen legst du als eigenen Rahmen an."))
A(h2("Mehrfach-Rahmung"))
A(p(f"Ist ein Design größer als dein Rahmen, teilt {M('Export › Mehrfach-Rahmung')} es in "
    "überlappende Rahmungen. Objekte bleiben möglichst ganz; nur große Flächen und Linien werden an "
    "der Teilung geschnitten (Schriften möglichst so platzieren, dass sie in eine Rahmung passen). In "
    "jedem Überlappungsstreifen sitzen rote <b>Passmarken</b> (Kreuze): Sie werden am Ende eines Teils "
    "und am Anfang des nächsten an derselben Stelle gestickt."))
A(img("ex_multihoop", 100, "400 mm breites Design im 190 × 140-Rahmen: drei Rahmungen mit Passmarken"))
A(ex("Jackenrücken in drei Rahmungen", [
    f"{M('Export › Mehrfach-Rahmung')}: Rahmen 190 × 140 mm, Überlappung 12 mm.",
    "Die Vorschau zeigt drei Teile – »Teile exportieren …« speichert sie als Dateien plus Übersichtsbild.",
    "Teil 1 sticken (am Ende die Passmarken), Stoff neu einspannen.",
    "Bei Teil 2 stickt die Maschine zuerst die Passmarken: liegen sie genau auf den Kreuzen von "
    "Teil 1, weitersticken; sonst Rahmen nachjustieren.",
]))
A(h2("Garnvorrat"))
A(p("Unten in der Garnleiste öffnet der Pfeil an <b>Anpassen ▾</b> <i>Mein Garnvorrat …</i>: Hake "
    "die Garne an, die du besitzt (aus jeder Garnkarte). <i>An meinen Garnvorrat anpassen</i> stellt "
    "dann alle Farben des Designs auf deine nächstliegenden Garne um und nennt Farben, die deutlich "
    "abweichen."))
A(ex("Gekauftes Design mit eigenen Garnen sticken", [
    "Einmalig: Garnvorrat öffnen, Garnkarte wählen, die vorhandenen Garne anhaken.",
    "Die Stickdatei importieren.",
    "»Anpassen ▾ › An meinen Garnvorrat anpassen« – alle Farben sind jetzt Garne aus deinem Schrank.",
]))
A(h2("Mehrfach-Export mit Namensliste"))
A(p("Exportiert in mehrere Formate auf einmal. Mit einer <b>Namensliste</b> entsteht für jeden "
    "Namen eine eigene Datei – der gewählte Schriftzug wird jeweils ersetzt (z. B. für Vereins-"
    "Shirts). Auf Wunsch packt »Alles in ein ZIP-Archiv« jede Variante in ein ZIP."))
A(img("dialog_multiexport", 55, "Mehrfach-Export"))
A(ex("Zwölf Vereins-Shirts mit Namen", [
    "Design mit dem Vereinslogo und einem Schriftzug »Name« anlegen.",
    f"{M('Export › Mehrfach-Export')}: Formate PES und DST, den Schriftzug als Platzhalter wählen.",
    "Die zwölf Namen untereinander eintragen (oder einfügen), »Alles in ein ZIP-Archiv« anhaken.",
    "Exportieren: für jeden Namen eine eigene Datei.",
]))
A(h2("Arbeitsblatt und Bild"))
A(p(f"{M('Export › Arbeitsblatt (PDF)')} ({K('Strg+P')}): Vorschau, Maße, Stichzahl, Stickzeit, "
    "Farbfolge mit Garnnummern und eine <b>1:1-Schablone</b> zum Positionieren auf dem Stoff. "
    f"{M('Als Bild speichern')} erzeugt eine PNG-Vorschau."))
A(ex("Motiv genau auf eine Tasche setzen", [
    f"{K('Strg+P')} – Arbeitsblatt als PDF speichern und in Originalgröße (100 %) drucken.",
    "Die 1:1-Schablone ausschneiden, auf die Tasche legen und die Mitte mit Kreide markieren.",
    "Beim Einspannen die Rahmenmitte auf die Markierung setzen; die Farbfolge liegt neben der "
    "Maschine.",
]))

A(h2("Strass-Schablone, Projekt-Anleitung und Druckvorlage"))
A(table([
    ["Strass-Schablone", "SVG für den Schneideplotter oder PDF mit Stückliste – siehe "
     "<i>Strass & Perlen</i>."],
    ["Projekt-Anleitung", "PDF mit Material, Zuschnitt und Arbeitsschritten eines Projekts im "
     "Rahmen."],
    ["Druckvorlage", "PDF mit allen Druckbildern der Druck-Applikationen in Originalgröße, auf Wunsch "
     "gespiegelt für Transferpapier."],
], widths=[24, 76]))
A(h2("Simulationsvideo"))
A(p(f"{M('Export › Drucken & Bild › Simulationsvideo')} nimmt die Entstehung des Designs als MP4 auf – "
    "Stich für Stich, mit roter Nadelmarkierung und einer Infoleiste (Farbe, Garnname, Stich, "
    "Fortschritt). Am Ende bleibt das fertige Design zwei Sekunden stehen. Wählbar sind Dauer, "
    "Größe (HD, Full HD, quadratisch für Instagram, Hochformat für Reels/Stories), Bilder je "
    "Sekunde und ob der Stickrahmen zu sehen ist."))
A(img("video_frame", 70, "Ein Bild aus dem Simulationsvideo"))
A(tip("Für MP4 braucht es das Programm <b>ffmpeg</b> (unter Linux meist installiert oder über die "
      "Paketverwaltung erhältlich). Fehlt es, speichert StichWizard das Video als Einzelbilder "
      "(PNG) in einen Ordner."))

A(h2("Produktvorschau"))
A(p(f"{M('Ansicht › Vorschau › Produktvorschau')} ({K('F7')}, auch unter Export) zeigt den Entwurf in "
    "<b>Originalgröße</b> auf einem Produkt: T-Shirt (vorne und hinten), Kapuzenpulli, Polo-Shirt, "
    "Schürze, Kappe, Tragetasche, Handtuch, Kissen oder Lätzchen. Wähle Farbe und Position (z. B. "
    "»Brust links«, »Ärmel links«, »Nacken« oder »Über der Bordüre«). Auf der Kappe wölbt sich der "
    "Entwurf mit der Rundung. Ist der Entwurf größer als für die Stelle üblich, steht ein Hinweis "
    "darunter."))
A(table([
    ["Mausrad", "Zoomen an der Mausposition (auch Knöpfe −/+, »Einpassen«, »Auf Motiv«)"],
    ["Motiv ziehen", "Motiv auf dem Produkt verschieben – mit Umschalt nur waagerecht oder "
     "senkrecht; Pfeiltasten verschieben um 1 mm (Umschalt: 10 mm)"],
    ["Daneben ziehen", "Ansicht verschieben; Doppelklick passt das ganze Produkt ein"],
    ["Drehung, Größe", "Motiv in der Vorschau drehen und skalieren; »Übernehmen« wendet beides "
     "auf das Design an (rückgängig mit Strg+Z), »Zurücksetzen« stellt alles zurück"],
    ["Hilfslinien", "Üblicher Bereich der Position (gestrichelt) und Abstand der Oberkante zum "
     "Kragen – für Brustlogos sind 7–9 cm üblich"],
], ["Bedienung", "Wirkung"], [22, 78]))
A(img("mockups", 100, "Produktvorschau: dasselbe Design auf verschiedenen Produkten"))
A(p("Das Fenster bleibt offen, während du weiterarbeitest, und aktualisiert sich von selbst. Wechselst "
    "du im Hauptfenster auf einen Kappenrahmen oder eine andere Stofffarbe, zieht die Vorschau mit. "
    "»Als Bild speichern« erzeugt ein PNG."))
A(ex("Kunden einen Entwurf zeigen", [
    "Logo und Schriftzug fertig gestalten.",
    f"{K('F7')} drücken, Produkt »T-Shirt«, Farbe »Marine«, Position »Brust links«.",
    "»Auf Motiv« – die Hilfslinie zeigt den Abstand zum Kragen. Das Logo mit der Maus so ziehen, "
    "dass etwa 8 cm angezeigt werden; wirkt es zu groß, unter »Größe« z. B. 90 % testen und "
    "»Übernehmen«.",
    "»Als Bild speichern …« und das PNG an den Kunden schicken.",
]))

# ---------------------------------------------------------------- 11 Einstellungen
A(h1("Einstellungen und Oberfläche"))
A(p(f"{M('Einstellungen')} (Zahnrad oben rechts):"))
A(table([
    ["Allgemein", "Standard-Rahmen und -Stoff, Exportformat, Maschinengeschwindigkeit (für die "
     "Stickzeit), Rückgängig-Schritte, KI-Schnittstelle, Optimieren beim Export."],
    ["Neue Objekte", "Garnfarbe, Reihenabstand, Unterlage und Schriftart neuer Objekte."],
    ["Sticken", "Fadenschnitt ab Sprunglänge, Vernähen (Halbstich, kräftig, vor/zurück, Pfeil, Stern, "
     "Dreieck, Zickzack, aus), Mindeststichlänge, Kurvenanpassung."],
    ["Oberfläche", "Farbschema hell/dunkel, Schriftgröße, Menüband groß/kompakt/nur Symbole, "
     "Werkzeugleiste links/rechts/aus, Seitenleiste links/rechts, Garnfarben-Leiste, eigener Reiter "
     "»★ Favoriten« mit deinen wichtigsten Funktionen."],
], ["Reiter", "Inhalt"], [18, 82]))
A(img("settings_sticken", 60, "Einstellungen › Sticken"))
A(img("screen_dark", 80, "Dunkles Farbschema"))
A(ex("Farbschema und Favoriten einrichten", [
    f"{M('Ansicht › Farbschema')}: »Dunkel« und die Akzentfarbe »Zauberer-Violett« wählen.",
    f"{M('Ansicht › Oberfläche anpassen')}: im Reiter <i>Oberfläche</i> die Funktionen anhaken, die "
    "du oft brauchst – sie erscheinen im Reiter »★ Favoriten« ganz links.",
    "Ist der Bildschirm klein: Menüband »kompakt« oder »nur Symbole«.",
]))

# ---------------------------------------------------------------- 12 KI
A(h1("KI-Anbindung"))
A(p("Über das <b>Model Context Protocol (MCP)</b> kann ein KI-Assistent wie Claude StichWizard "
    "direkt bedienen: Designs lesen, Schriftzüge und Formen anlegen, Farben, Füllarten und alle "
    "Feinheiten ändern, Bilder digitalisieren, Vorschauen ansehen und exportieren. Jede Änderung "
    "erscheint sofort im Fenster und lässt sich mit Strg+Z rückgängig machen."))
A(p(f"{M('Hilfe › KI-Anbindung (MCP)')} zeigt die Befehle zum Einrichten mit Kopier-Knopf. Für "
    "Claude Code (Flatpak):"))
A('<p class="code">claude mcp add stichwizard -- flatpak run --command=stichwizard-mcp '
  'local.stichwizard.StichWizard</p>')
A(p("Ist StichWizard nicht geöffnet, startet der MCP-Server es automatisch. Ein-/ausschalten unter "
    "Einstellungen › Allgemein."))
A(ex("Ein Design mit dem KI-Assistenten", [
    "KI-Schnittstelle einrichten wie oben beschrieben und StichWizard öffnen.",
    "Dem Assistenten schreiben: »Setze den Namen Lena in einer Schreibschrift, 15 mm hoch, mittig "
    "in den Rahmen und lege ein rosa Herz dahinter.«",
    "Das Ergebnis erscheint sofort im Fenster und lässt sich wie selbst gezeichnet weiter bearbeiten "
    "– oder mit Strg+Z zurücknehmen.",
]))

# ---------------------------------------------------------------- 13 Beispiele
A(h1("Beispiele Schritt für Schritt"))
A(h2("Beispiel 1: Namensschild mit Satinrand"))
A(steps([
    "Rahmen 130 × 180 mm, Stoffart »Webware«.",
    f"Rechteck ({K('R')}) aufziehen, in den Eigenschaften Breite 70 mm, Höhe 26 mm; Füllart Tatami, "
    "Garnfarbe hell, Stichwinkel 0°.",
    "Rand: Satinstich, Breite 3 mm, Garnfarbe Orange – die Ecken bekommen automatisch eine Gehrung.",
    f"Textwerkzeug ({K('T')}) in die Mitte klicken, »Mia« eingeben, Stickschrift wählen, Höhe 14 mm.",
    f"Beide Objekte wählen und {K('Strg+Alt+G')} – jetzt gemeinsam zentrieren ({K('Strg+M')}) "
    "und bei Bedarf auf genau 80 mm Breite bringen.",
    f"{K('F5')} Simulator prüfen, dann exportieren.",
]))
A(f'<table width="100%"><tr><td align="center"><img src="img/step_badge1.png" width="{{W40}}"><br>'
  f'<span class="cap">Schritt 2–3</span></td><td align="center"><img src="img/step_badge2.png" '
  f'width="{{W40}}"><br><span class="cap">Schritt 4</span></td></tr></table>')
A(h2("Beispiel 2: Logo aus einem Bild"))
A(steps([
    "Bild-Assistent: PNG wählen, Farbanzahl und Breite einstellen, übernehmen.",
    "Optimieren › Kleinteile entfernen (2 mm²) – Fussel-Flächen verschwinden.",
    "Optimieren › Überlappung entfernen – verdeckte Flächen werden nicht doppelt gestickt.",
    "Stoffart passend wählen (z. B. Polo/Piqué).",
    "Optimieren › Dichte prüfen: rote Stellen ausbessern.",
    "Optimieren › Farben zusammenfassen, dann exportieren.",
]))
A(h2("Beispiel 3: Applikation mit Namen"))
A(steps([
    "Abgerundetes Rechteck zeichnen, Füllart »Applikation«, Stofffarbe = Farbe des Applikationsstoffs.",
    "Applikationsrand: Satinbreite 3 mm, Garnfarbe passend.",
    "Schriftzug darüber setzen.",
    "Sticken: Platzierungslinie → Stopp (Stoff auflegen) → Heftstich → Stopp (Stoff zurückschneiden) "
    "→ Satinrand → Name.",
]))
A(img("ex_applique_name", 45, "Applikation mit Namen"))
A(h2("Beispiel 4: 3D-Puff-Schriftzug auf einer Kappe"))
A(steps([
    "Rahmen für Kappen wählen, Stoffart »Kappe«.",
    "Blockschrift mit mindestens 3 mm Strichbreite setzen, Höhe ab 20 mm.",
    "Schriftzug auswählen, Sticken › Effekte › 3D-Puff.",
    "Sticken wie in Kapitel 6 beschrieben (Stopp → Schaum auflegen → weiter).",
]))

# ---------------------------------------------------------------- 14 Tipps & Tasten
A(h1("Tipps, Vlies und Tastenkürzel"))
A(h2("Welches Vlies?"))
A(table([
    ["Webware, Baumwolle, Leinen", "Abreißvlies", "–"],
    ["T-Shirt, Jersey, Strick", "Schneidvlies (Cut-away)", "bei Details: wasserlöslich"],
    ["Polo, Piqué", "Schneidvlies", "wasserlösliches Topping"],
    ["Frottee, Fleece, Plüsch", "Abreiß- oder Schneidvlies", "wasserlösliches Topping + Knockdown"],
    ["Jeans, Canvas", "Abreißvlies", "–"],
    ["Kappe", "Kappen-Abreißvlies (fest)", "–"],
    ["Leder, Kunstleder", "Schneidvlies (nicht klebend)", "Ledernadel, wenig Stiche"],
    ["Seide, feine Stoffe", "feines Abreiß- oder wasserlösliches Vlies", "Nadel 65/9"],
], ["Stoff", "Vlies (unten)", "Topping / Besonderes"], [32, 34, 34]))
A(h2("Häufige Probleme"))
A(table([
    ["Lücken zwischen Füllung und Rand", "Zugausgleich erhöhen, Feinheiten › Erweitern 0,3–0,5 mm, "
     "Stoffart prüfen, festeres Vlies."],
    ["Stickerei bretthart", "Dichte verringern, Überlappung entfernen, Stoffart »Jeans«."],
    ["Fadenbruch in engen Kurven", "Kurze Stiche (Satin) einschalten, Satin-Ecken mit Gehrung."],
    ["Viele Sprünge", "Farben zusammenfassen, Auto-Satin, Redwork/Auto-Route für Linien, "
     "Simulator › Reihenfolge."],
    ["Kleine Schrift unleserlich", "Stickschrift statt Computerschrift, empfohlene Höhe einhalten."],
    ["Flor schaut durch (Frottee)", "Stoffart Frottee, Knockdown, Topping."],
], ["Problem", "Lösung"], [32, 68]))
A(h2("Tastenkürzel"))
A("@@KEYS@@")
A(p(f"{K('F1')} zeigt die Übersicht der Tastenkürzel jederzeit im Programm (mit Suche)."))

HTML_BODY = "\n".join(parts)

# ===================================================================== Tastenkürzel
# aus dem Programm übernehmen (immer aktuell)
import tempfile
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())
from stichwizard.mainwindow import MainWindow
_w = MainWindow()
krows = []
for group, rows in _w.shortcut_groups():
    krows.append([f"<b>{group}</b>", ""])
    for action, keys in rows:
        if keys:
            krows.append([action, f'<span class="key">{keys}</span>'])
half = (len(krows) + 1) // 2
keys_html = ('<table width="100%"><tr><td width="50%" valign="top">' +
             table(krows[:half], widths=[62, 38]) + '</td><td width="50%" valign="top">' +
             table(krows[half:], widths=[62, 38]) + "</td></tr></table>")
HTML_BODY = HTML_BODY.replace("@@KEYS@@", keys_html)
_w.close()

# ===================================================================== Satz
CSS = f"""
body {{ font-family: 'DejaVu Sans'; font-size: 9.5pt; color: #2B2D3A; }}
h1 {{ font-size: 20pt; color: #1F2433; margin-top: 0px; margin-bottom: 10px; }}
h2 {{ font-size: 13pt; color: {ACCENT}; margin-top: 14px; margin-bottom: 4px; }}
h3 {{ font-size: 11pt; color: #1F2433; margin-top: 10px; margin-bottom: 2px; }}
p {{ margin-top: 3px; margin-bottom: 5px; line-height: 125%; }}
li {{ margin-bottom: 3px; }}
.cap {{ font-size: 8pt; color: #6B7280; margin-top: 0px; margin-bottom: 10px; text-align: center; }}
.title {{ font-size: 34pt; font-weight: bold; color: #3A2F7A; margin-top: 14px; margin-bottom: 0px; }}
.subtitle {{ font-size: 18pt; color: {ACCENT}; margin-top: 2px; }}
.meta {{ font-size: 10pt; color: #6B7280; }}
.key {{ font-family: 'DejaVu Sans Mono'; font-size: 8.5pt; background-color: #EEF0F4; }}
.code {{ font-family: 'DejaVu Sans Mono'; font-size: 8pt; background-color: #F1F3F6; }}
th {{ font-weight: bold; }}
"""


def build(toc_pages=None):
    writer = QPdfWriter(OUT)
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(18, 16, 18, 18), QPageLayout.Millimeter)
    writer.setTitle("StichWizard – Funktionsanleitung")
    writer.setCreator("StichWizard " + __version__)
    pr = writer.pageLayout().paintRectPixels(300)
    W, H = pr.width(), pr.height()
    footer = 60                                    # Pixel für die Fußzeile
    doc = QTextDocument()
    doc.documentLayout().setPaintDevice(writer)
    doc.setPageSize(QSizeF(W, H - footer))
    doc.setDefaultStyleSheet(CSS)
    doc.setDefaultFont(QFont("DejaVu Sans", 9))
    # Bilder als Ressourcen, Breite in Pixel der Seite
    body = HTML_BODY
    k = 96.0 / 300.0                 # QTextDocument: Bildmaße in logischen Pixeln (96 dpi)

    def captioned(mm):
        """Bild mit eingezeichneter Bildunterschrift (bleibt so auf derselben Seite)."""
        name, pct, cap = mm.group(1), int(mm.group(2)), mm.group(3)
        src = QImage(os.path.join(IMG, name + ".png"))
        dw = W * pct / 100 * 0.98                     # Breite auf der Seite (Gerätepixel)
        if cap:
            scale = dw / src.width()
            fpx = max(8, int(8 * 300 / 72 / scale))    # 8 pt Schrift
            font = QFont("DejaVu Sans")
            font.setPixelSize(fpx)
            capimg = QImage(src.width(), src.height() + int(fpx * 2.2), QImage.Format_ARGB32)
            capimg.fill(QColor("#FFFFFF"))
            pp = QPainter(capimg)
            pp.setRenderHint(QPainter.Antialiasing)
            pp.drawImage(0, 0, src)
            pp.setFont(font)
            pp.setPen(QColor("#6B7280"))
            pp.drawText(QRectF(0, src.height() + fpx * 0.4, src.width(), fpx * 1.8),
                        Qt.AlignHCenter | Qt.AlignTop, cap)
            pp.end()
            src = capimg
            name = name + "__cap"
        doc.addResource(QTextDocument.ImageResource, QUrl(f"img/{name}.png"), src)
        return (f'<img src="img/{name}.png" width="{int(dw * k)}" '
                f'height="{int(dw * k * src.height() / src.width())}">')
    body = re.sub(r"@@IMG\|([^|]+)\|(\d+)\|(.*?)@@", captioned, body)
    for m in set(re.findall(r'src="img/([^"]+)\.png"', body)):
        if m.endswith("__cap"):
            continue
        im = QImage(os.path.join(IMG, m + ".png"))
        doc.addResource(QTextDocument.ImageResource, QUrl(f"img/{m}.png"), im)
    body = re.sub(r"\{W(\d+)\}", lambda mm: str(int(W * int(mm.group(1)) / 100 * 0.98 * k)), body)
    toc = ['<table width="100%" cellpadding="3">']
    for n, title, anchor in CH:
        pg = toc_pages.get(anchor, "") if toc_pages else "00"
        toc.append(f'<tr><td width="8%"><b style="color:{ACCENT}">{n}</b></td><td>{title}</td>'
                   f'<td width="8%" align="right">{pg}</td></tr>')
    toc.append("</table>")
    body = body.replace("@@TOC@@", "".join(toc))

    def sized(mm):                                  # Höhe passend zur Breite angeben
        name, wd = mm.group(1), int(mm.group(2))
        im = QImage(os.path.join(IMG, name + ".png"))
        return f'<img src="img/{name}.png" width="{wd}" height="{int(wd * im.height() / im.width())}">'
    body = re.sub(r'<img src="img/([^"]+)\.png" width="(\d+)">', sized, body)
    # Überschriften nicht allein unten auf der Seite stehen lassen: betroffene Überschriften
    # bekommen im HTML einen Seitenumbruch, dann wird neu gesetzt (nachträgliches Ändern der
    # Absätze würde Qt nicht vollständig neu umbrechen)
    from PySide6.QtGui import QTextBlockFormat
    ph = H - footer
    breaks = set()

    box_breaks = set()          # Beispiel-Kästen, die nicht über zwei Seiten laufen sollen
    BOX = 'style="background:#EDE7F6;'

    def with_breaks(html):
        k = [0]

        def mark(mm):
            k[0] += 1
            tag = mm.group(1)
            return (f'<{tag} style="page-break-before:always">' if k[0] in breaks else f"<{tag}>")
        html = re.sub(r"<(h[23])>", mark, html)
        n = [0]

        def mark_box(mm):
            n[0] += 1
            return ('style="page-break-before:always; background:#EDE7F6;' if n[0] in box_breaks
                    else mm.group(0))
        return re.sub(re.escape(BOX), mark_box, html)
    for _ in range(14):
        doc.setHtml(f"<html><body>{with_breaks(body)}</body></html>")
        lay = doc.documentLayout()
        doc.pageCount()
        blk, n_head, new = doc.begin(), 0, set()
        while blk.isValid():
            if blk.blockFormat().headingLevel() in (2, 3):
                n_head += 1
                if n_head not in breaks:
                    top = lay.blockBoundingRect(blk).top()
                    nxt = blk.next()
                    if nxt.isValid():
                        nb = lay.blockBoundingRect(nxt)
                        if int(top // ph) != int(nb.bottom() // ph) and (top % ph) > ph * 0.55:
                            new.add(n_head)
            blk = blk.next()
        new_box, n_box = set(), 0
        for fr in doc.rootFrame().childFrames():
            if fr.frameFormat().background().color().name().lower() != "#ede7f6":
                continue
            n_box += 1
            r = lay.frameBoundingRect(fr)
            if n_box not in box_breaks and int(r.top() // ph) != int((r.bottom() - 1) // ph) \
                    and r.height() < ph * 0.6:
                new_box.add(n_box)
        if not new and not new_box:
            break
        breaks |= new
        box_breaks |= new_box
    # Kontrolle: jeder Absatz mit Inhalt muss gesetzt sein (sonst fehlt er im PDF)
    blk, empty = doc.begin(), []
    while blk.isValid():
        if blk.text().strip() and blk.layout().lineCount() == 0:
            empty.append(blk.text()[:40])
        blk = blk.next()
    if empty:
        raise SystemExit(f"Nicht gesetzte Absätze: {empty[:5]}")
    # Seiten der Kapitel bestimmen (Anker -> y-Position)
    pages = {}
    lay = doc.documentLayout()
    blk = doc.begin()
    while blk.isValid():
        it = blk.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                for name in frag.charFormat().anchorNames():
                    y = lay.blockBoundingRect(blk).top()
                    pages[name] = int(y // (H - footer)) + 1
            it += 1
        blk = blk.next()
    painter = QPainter(writer)
    n = doc.pageCount()
    for i in range(n):
        if i:
            writer.newPage()
        painter.save()
        painter.translate(0, -i * (H - footer))
        doc.drawContents(painter, QRectF(0, i * (H - footer), W, H - footer))
        painter.restore()
        if i:                                       # Fußzeile ab Seite 2
            painter.setPen(QPen(QColor("#C9CED8"), 2))
            painter.drawLine(0, H - footer + 10, W, H - footer + 10)
            f = QFont("DejaVu Sans", 7)
            painter.setFont(f)
            painter.setPen(QColor("#6B7280"))
            painter.drawText(QRectF(0, H - footer + 14, W, footer - 14), Qt.AlignLeft | Qt.AlignVCenter,
                             f"StichWizard {__version__} – Funktionsanleitung")
            painter.drawText(QRectF(0, H - footer + 14, W, footer - 14), Qt.AlignRight | Qt.AlignVCenter,
                             f"Seite {i + 1} von {n}")
    painter.end()
    return pages, n


os.makedirs(os.path.dirname(OUT), exist_ok=True)
pages, n = build()
pages2, n = build(pages)            # zweiter Durchlauf mit Seitenzahlen im Inhaltsverzeichnis
if pages2 != pages:
    pages3, n = build(pages2)
print(f"PDF: {OUT} ({n} Seiten)")
