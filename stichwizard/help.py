"""Hilfe: Tastenkürzel-Übersicht, Kurzanleitung, Über."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from . import MONO_FONT, __version__, icons


class ShortcutsDialog(QDialog):
    """groups: [(Gruppenname, [(Aktion, Tasten), …]), …]"""

    def __init__(self, groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tastenkürzel")
        self.setWindowIcon(icons.icon("keyboard"))
        self.resize(560, 640)
        v = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen … (z. B. »zoom« oder »Strg+G«)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        v.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setObjectName("shortcuts")
        self.tree.setHeaderLabels(["Aktion", "Taste / Maus"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        bold = QFont()
        bold.setBold(True)
        mono = QFont(MONO_FONT)
        mono.setStyleHint(QFont.Monospace)
        for name, rows in groups:
            g = QTreeWidgetItem([name])
            g.setFont(0, bold)
            g.setFirstColumnSpanned(True)
            g.setFlags(Qt.ItemIsEnabled)
            self.tree.addTopLevelItem(g)
            for action, keys in rows:
                it = QTreeWidgetItem(g, [action, keys])
                it.setFont(1, mono)
            g.setExpanded(True)
        v.addWidget(self.tree, 1)
        hint = QLabel("Tipp: Mit F1 öffnest du diese Übersicht jederzeit.")
        hint.setObjectName("muted")
        v.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.search.setFocus()

    def _filter(self, text):
        t = text.lower().replace(" ", "")
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            group_hit = t in g.text(0).lower()
            visible = 0
            for j in range(g.childCount()):
                c = g.child(j)
                hit = not t or group_hit or t in c.text(0).lower().replace(" ", "") \
                    or t in c.text(1).lower().replace(" ", "")
                c.setHidden(not hit)
                visible += hit
            g.setHidden(visible == 0)


GUIDE = """
<h2>Kurzanleitung</h2>
<p><b>Menüband</b> – nach Arbeitsschritten geordnet wie in Profi-Sticksoftware:
<i>Start</i> (Datei, Rückgängig, Rahmen/Stoff) · <i>Erstellen</i> (Formen, Linien, Bézier-Stift,
Bild-Assistent, Fotostich, Vorlagen, Bibliothek, Stickdatei) · <i>Schrift</i> (Schriftzug, Text an
Pfad, Schrift-Werkstatt) · <i>Nachzeichnen</i> · <i>Form bearbeiten</i> (Punkte, Versatz, Kopien) ·
<i>Anordnen</i> (Gruppe, Pfad-Operationen, Ausrichten, Ebenen) · <i>Sticken</i> (Satin, Linien
führen, Füllung, Effekte, Start &amp; Ende) · <i>Optimieren</i> (Verbessern, Reihenfolge, Sprünge,
Prüfen) · <i>Ansicht</i> · <i>Export</i> · <i>Hilfe</i>.</p>
<h3>1. Rahmen und Stoff wählen</h3>
<p>Reiter <b>Start</b> › <i>Stickrahmen &amp; Stoff</i>. Den Rahmen, der bei jedem neuen Design
vorausgewählt ist, legst du unter <b>Einstellungen</b> (Strg+,) fest. Passt keine Größe zu
deiner Maschine, wähle ganz unten in der Rahmenliste <b>Eigener Rahmen …</b> und gib Breite und
Höhe des Stickfelds ein (20–1500 mm, optional mit Namen). Eigene Rahmen bleiben gespeichert,
Designs nehmen ihre Rahmengröße in der Projektdatei mit; »Eigenen Rahmen löschen …« entfernt
einen wieder. Für Kappen gibt es zwei <b>Kappenrahmen</b> (130 × 60 mm und breit 360 × 75 mm) –
dabei wird die Stoffart automatisch auf »Kappe« gestellt.</p>
<p><b>Schrift gestalten</b>: <i>Hüllform</i> (Schrift › Hüllform ▾ – Bogen oben/unten, Fass,
Brücke, Doppelbogen, Taille, Raute, Welle, Wimpel, Rampe; Stärke rechts in den Eigenschaften).
<i>Einzelne Buchstaben</i>: im Punkte-Werkzeug (N) an der Raute eines Buchstabens ziehen
(Umschalt = nur waagerecht) oder rechts unter »Einzelne Buchstaben« Versatz, Drehung und Größe
einstellen. <i>Schatten</i> (Schrift bzw. Form bearbeiten › Versatz): versetzter Schatten hinter
Schrift und Formen, verdeckte Teile werden ausgespart.</p>
<p><b>Motivstich</b> (Stichart bei Linien und Rändern): Herzen, Sterne, Kreise, Rauten, Blätter,
Blüten oder durchgehend Muschelkante, Welle, Zacken, Schlaufen entlang der Linie – mit Größe,
Abstand, »Abwechselnd oben/unten« (Ranke) und »Kräftig« (Bohnenstich).</p>
<p><b>Lineal und Messen</b> (Ansicht › Messen): Lineale in mm ab Rahmenmitte; Messwerkzeug (M)
zeigt Abstand, waagerecht/senkrecht und Winkel (Umschalt = 45°-Schritte).</p>
<p><b>Mehrfach-Rahmung</b> (Export): Designs, die größer als der Rahmen sind, in überlappende
Rahmungen mit Passmarken teilen und jeden Teil als Datei ausgeben. <b>Schneidedatei</b> (Export):
Applikationsformen als SVG in Originalgröße für Schneideplotter. <b>Garnvorrat</b> (Garnleiste ›
Anpassen ▾): eigene Garne anhaken und Designs auf sie umstellen.</p>
<p><b>Stickmaschine</b> (Export › Stickmaschine oder Einstellungen › Allgemein): Profile
für TEXI IRIS 10, Brother PR1055X/PR680W/Innov-is 800E, Janome MB-7 sowie allgemeine Mehrnadel-
und Einnadel-Maschinen – oder eine eigene Maschine. Das Profil stellt die Rahmen der Maschine,
das Exportformat und das Tempo für die Stickzeit ein, warnt bei zu großen Rahmen und empfiehlt je
Stoffart die passende Nadel (z. B. DBxK5 75/11 Kugelspitze für Jersey). Bei Mehrnadel-Maschinen
mit automatischem Farbwechsel schreibt StichWizard Stopps (Applikation, 3D-Puff) ausdrücklich in
die Datei; in DST wird daraus ein eigener Schritt ohne Stiche, an dem du an der Maschine
»Pause/Stopp« setzt. Das Arbeitsblatt zeigt dazu einen <b>Nadelplan</b> (welche Farbe auf
welche Nadel).</p>
<p><b>Produktvorschau</b> (F7, Ansicht › Vorschau): zeigt den Entwurf in Originalgröße auf
T-Shirt (vorne/hinten), Kapuzenpulli, Polo, Schürze, Kappe, Tragetasche, Handtuch, Kissen oder
Lätzchen – mit Farbe und Position (z. B. Brust links, Ärmel, Nacken). Mausrad = zoomen an der
Mausposition, Motiv ziehen = verschieben (Umschalt = gerade, Pfeiltasten = 1 mm), daneben ziehen
= Ansicht verschieben, Doppelklick = einpassen. Drehung und Größe stellst du unter »Motiv
anordnen« ein; »Übernehmen« wendet sie auf das Design an. Hilfslinien zeigen den üblichen Bereich
der Position und den Abstand zum Kragen (Brustlogos: 7–9 cm). Das Fenster bleibt offen und
aktualisiert sich beim Weiterarbeiten; »Als Bild speichern« erzeugt ein PNG ohne Hilfslinien.</p>
<h3>2. Motiv erstellen</h3>
<ul>
<li><b>Formen</b> zeichnen (R, E, P) oder ein fertiges Motiv aus <b>Motive</b> rechts wählen.</li>
<li><b>Schriftzug</b> (T): in den Rahmen klicken und Text eingeben. Rechts unter
<i>Eigenschaften › Stickschrift</i> eine der 129 professionell digitalisierten
<b>Stickschriften</b> wählen (mit Vorschau, empfohlener Höhe und Lizenz) – sie sticken viel
sauberer als Computerschriften, auch klein. Computerschriften werden wie in Profi-Programmen
gestickt: schmale Striche als <i>Satin</i>, der der Buchstabenform folgt und sich in Bögen mitdreht,
breite Teile als Tatami (abschaltbar: <i>Schmale Striche als Satin</i>).</li>
<li><b>Säulen-Satin</b> (S): abwechselnd links und rechts der Säule klicken – jedes Paar legt
die Stichrichtung fest. Ideal für Ranken, Stiele, Konturen und eigene Buchstaben.</li>
<li><b>Applikation</b>: Form zeichnen, Stichart »Applikation« wählen – das Programm stickt
Platzierungslinie, hält an, Heftstich, hält an (Stoff zuschneiden), dann den Satinrand.</li>
<li><b>Bild-Assistent</b> (Strg+B): PNG, JPG oder SVG automatisch in Stickflächen umwandeln – Original und Ergebnis (Flächen oder Stiche) nebeneinander, mit dem Mausrad zoombar, Detailgenauigkeit per Schieberegler.</li>
<li><b>AI / PDF öffnen</b> (Strg+Umschalt+I, Start › Datei, oder einfach über »Öffnen«):
Vektorgrafiken aus Adobe Illustrator (.ai, »PDF-kompatibel« gespeichert – das ist der Standard)
und PDF werden zu bearbeitbaren Formen und Linien – mit Originalfarben (auch CMYK und
Schmuckfarben), Kurven und Löchern, in Originalgröße oder passend zum Rahmen. Optionen:
<i>Verdeckte Teile weglassen</i> (was darüberliegt, wird darunter nicht gestickt),
<i>Weiße Flächen weglassen</i> (dort bleibt der Stoff frei), <i>Gleiche Farben zusammenfassen</i>,
<i>Konturen als Linien</i> (ab 1 mm als Satin). Mit einer Schnittmaske ausgeschnittene Bilder
werden als Fläche übernommen. Nicht in Pfade umgewandelter Text und eingebettete Fotos werden
gemeldet. AI- und PDF-Dateien lassen sich außerdem als Vorlage, im Bild-Assistenten und bei
»Bitmap nachzeichnen« verwenden.</li>
<li><b>Bitmap nachzeichnen</b> (Strg+Alt+B, Reiter Nachzeichnen › Bild als Vorlage):
wie in Inkscape, aber mit mehr Reglern. <i>Einzelner Scan</i>: <i>Helligkeitsschwelle</i> (alles
dunkler als die Schwelle wird Fläche), <i>Kantenerkennung</i>, <i>Mittellinie</i> (Strichzeichnungen
werden zu Linien). <i>Mehrere Scans</i>: <i>Helligkeitsstufen</i>, <i>Farben</i> oder
<i>Graustufen</i> – je Stufe eine Fläche, wahlweise gestapelt, Hintergrund weglassbar.
Feinheiten: <i>Weichzeichnen</i> (gegen Rauschen), <i>Flecken unterdrücken</i> (Teile und Löcher
unter x mm²), <i>Ecken glätten</i> (0 = pixelgenau eckig, höher = mehr Rundungen),
<i>Toleranz</i> (Abweichung vom Bild – kleiner = genauer, mehr Knoten), <i>Abtastung</i>.
Die Ansicht <i>Konturen + Knoten</i> zeigt die Pfade rot über dem Original (Ecken rot, Rundungen
blau) – hineinzoomen und Regler nachstellen; Knotenzahl steht unten links. Ist eine Vorlage
geladen, wird sie nachgezeichnet und das Ergebnis genau daraufgelegt. Sticken als Flächen,
Flächen mit Satin für schmale Teile, Umriss (Stepp- oder Satinstich) oder Mittellinien.</li>
<li><b>Nachzeichnen</b>: Bild als Vorlage laden (Strg+Umschalt+B) und mit Vieleck oder Linie
nachfahren – wie in Profi-Programmen: <b>Linksklick = Eckpunkt</b>, <b>Rechtsklick =
Rundungspunkt</b>. Klick auf den Startpunkt oder Enter schließt die Form. Hältst du beim
Abschließen <b>Strg</b>, wird die neue Kontur zum Loch in der ausgewählten Form (z. B. das
Innere eines »O«).</li>
</ul>
<h3>3. Bearbeiten</h3>
<ul>
<li>Verschieben: Objekt ziehen oder Pfeiltasten (Umschalt = 10 mm).</li>
<li>Größe/Drehen: Eckgriffe bzw. runder Griff oben (Umschalt = 15°-Schritte).</li>
<li>Farbe: Garnpalette unten – Linksklick = Füllung, Rechtsklick = Rand. Links daneben eine
<b>Garnkarte</b> wählen (Madeira, Isacord, Gunold, Brother, Sulky …) – dann stehen überall die
echten Garnnummern; »Anpassen« setzt alle Farben auf die nächste Garnfarbe der Karte.</li>
<li>Füllmuster: rechts unter <i>Eigenschaften › Füllstich › Stichart</i> – Tatami mit
Einstichmustern, Satin, Wellen-, Kontur-, Kreuzstich-, Motiv- oder Netzfüllung. Bei leichten
Füllungen (Kreuzstich, Motiv, Netz) schaut der Stoff durch; ein Rand macht die Form sichtbar.</li>
<li><b>Weitere Sticharten</b> (wie in Ink/Stitch): <i>Spiralfüllung</i> von der Mitte nach außen,
<i>Mäander</i> im Quilt-Stil, <i>Ripple</i> (Konturlinien), <i>Farbverlauf</i> mit zwei Garnfarben.
Ränder und Linien zusätzlich als <i>Zickzack</i>, <i>E-Stich</i> (Applikationskante, Zacken nach
innen) oder <i>Bohnenstich</i> mit wählbaren Wiederholungen; Linien auch als <i>manueller Stich</i>
(jeder Punkt ein Einstich). Säulen-Satin wahlweise als Satin, Zickzack-Satin oder E-Stich.</li>
<li><b>Satin</b> (Sticken › Satin): Linie in Säulen-Satin umwandeln und zurück, Stickrichtung
umkehren, Satinsäule am gewählten Punktepaar teilen. <b>Erzeugen</b>: Mittellinie einer schmalen
Fläche (Schrift › Umwandeln), Umriss aus einer importierten Stickdatei zum Neu-Digitalisieren
(Erstellen › Automatisch), Knockdown-Fläche gegen hohen Flor wie Frottee oder Fleece (Sticken › Effekte).</li>
<li><b>Text an Pfad</b> (Schrift › Text): Schriftzug und eine
Linie auswählen (Umschalt+Klick), dann <i>Text an Pfad</i> – die Buchstaben stehen auf der Linie
und drehen sich mit ihr, mit Computer- und Stickschriften. Rechts unter <i>Am Pfad</i>: Anfang,
Mitte oder Ende und <i>Andere Seite</i>. <b>Pfad lösen</b> setzt den Text wieder gerade und macht
den Pfad wieder zur Linie.</li>
<li><b>Geführte Füllung</b> (wie Ink/Stitch »Guided Fill«): Fläche(n) und eine Linie auswählen,
dann <i>Geführte Füllung</i> – die Füllreihen sind Kopien dieser Führungslinie und folgen ihrem
Schwung (z. B. für Blätter, Haare, Federn). Ausgewählt erscheint die Führungslinie lila
gestrichelt; Reihenabstand, Stichlänge, Einstichmuster und Unterlage wie bei Tatami. Wo die
Linie steil ansteigt, liegen die Reihen enger – sanfte Schwünge sticken am schönsten.
<i>Pfad lösen</i> holt die Linie zum Bearbeiten zurück.</li>
<li><b>Redwork</b> und <b>Auto-Route</b> (Sticken › Linien führen): mehrere
Steppstichlinien auswählen – sie werden zu einem durchgehenden Weg verbunden, wo sie sich kreuzen
oder berühren, und ohne Sprung gestickt. <i>Redwork</i> stickt jede Strecke genau zweimal (hin
und zurück, Ende am Anfang, Rückweg in denselben Einstichen), <i>Auto-Route</i> jede Strecke
einmal und nur dort ein zweites Mal, wo es anders nicht weitergeht. Getrennte Linien ergeben
getrennte Wege. Die Option <i>Ecken genau einstechen</i> (rechts unter Linie) trifft jede Ecke
und Kreuzung genau.</li>
<li><b>Startpunkt</b> und <b>Endpunkt</b> (Sticken › Start &amp; Ende, oder rechts unter
<i>Start / Ende</i>): Fläche oder Satinsäule auswählen, Knopf drücken und die Stelle anklicken
(wie die Ink/Stitch-Befehle). Flächen beginnen dort und enden möglichst am Endpunkt
(notfalls mit einem kurzen Weg am Rand), Satinsäulen werden passend herum gestickt – liegen
Start und Ende am selben Ende, läuft die Unterlage hin und der Satin zurück. Ausgewählt zeigt ein
grünes S bzw. rotes E die Punkte.</li>
<li><b>Säulen-Satin</b> verfeinern (rechts unter Satinstich): <i>Kurze Stiche</i> rückt in engen
Kurven an der Innenseite jeden zweiten Stich ein (Anteil der Breite, sobald die Einstiche enger als
<i>… ab Abstand</i> liegen) – kein Garnknoten, kein Fadenbruch. <i>Max. Stichlänge</i> teilt breite
Säulen; <i>Zufällig teilen</i> versetzt die Teilungspunkte, damit keine Linie in der Mitte
entsteht.</li>
<li><b>Stopp nach Objekt</b>: rechts unter <i>Schnitt danach › Schnitt + Stopp</i> – die Maschine
hält an, z. B. für Applikationsstoff oder Puffschaum.</li>
<li><b>Dichte prüfen</b> (Ansicht): gelb = etwa zwei Stichlagen übereinander, rot = drei und mehr –
dort wird die Stickerei hart, Faden oder Nadel können brechen.</li>
<li><b>Mehrfach-Export</b> (Export): mehrere Formate auf einmal, mit Namensliste eine Datei je Name.
Im Stickschrift-Fenster blendet ein Filter Schriften aus, denen Zeichen deines Textes fehlen.</li>
<li><b>Einstellungen › Sticken</b>: Vernähen (Standard, kräftig, aus) und Mindeststichlänge.</li>
<li><b>Farbwahl</b>: Das Farbfenster passt sich dem Bildschirm an; bei großen Garnkarten gibt es
eine Suche (Nummer oder Name) und eine <i>Liste</i> mit Nummer und Name. In der Garnfarben-Leiste
unten blättert das Mausrad seitlich, <i>Alle …</i> öffnet das große Farbfenster.</li>
<li><b>Simulation</b>: Der <i>Tempo</i>-Regler stellt die Geschwindigkeit stufenlos ein – von Stich
für Stich bis sehr schnell; »wie Maschine« entspricht der eingestellten Stickgeschwindigkeit.</li>
<li><b>Sprungreihenfolge</b> (Simulator & Optimierer, F5 oder F6): Jeder Sprung trägt seine
Nummer und einen Pfeil in Stickrichtung; schon gestickte Sprünge sind kräftig, kommende blass. Einen
Sprung anklicken, dann unter <i>Reihenfolge</i>: <i>Früher</i> / <i>Später</i> stickt das Teil danach
einen Platz früher bzw. später, <i>Umdrehen</i> stickt es von der anderen Seite her (auch per
Rechtsklick im Bild). Zwischen Objekten gleicher Farbe schaltet das auf »von Hand«; der Haken
<i>automatisch auf kürzestem Weg</i> stellt die automatische Reihenfolge wieder her.</li>
<li><b>Element für Element</b>: Jede Fläche wird für sich fertig gestickt – erst die Unterlage, dann
die Füllung und (bei gleicher Farbe) ihr eigener Rand –, erst dann springt die Nadel zum nächsten
Element. Jede Fläche endet möglichst nah am nächsten Element, innerhalb einer Fläche wird nicht
gesprungen (Wege laufen verdeckt unter späteren Reihen bzw. unter dem noch folgenden Rand). Sprünge
ab der unter <i>Einstellungen › Sticken</i> eingestellten Länge (Standard 3 mm) werden geschnitten.</li>
<li><b>Oberfläche anpassen</b> (Ansicht › Oberfläche anpassen oder Einstellungen › Oberfläche):
helles oder dunkles Farbschema, Schriftgröße, Menüband groß, kompakt oder nur mit Symbolen,
Werkzeugleiste links, rechts oder ausgeblendet, Eigenschaften-Leiste links oder rechts, Garnfarben-
Leiste ein/aus und ein eigener Reiter <i>★ Favoriten</i> mit deinen wichtigsten Funktionen.</li>
<li><b>Fotostich</b> (Erstellen › Automatisch): ein Foto als Stickerei – <i>farbig</i> mit 2–16
Garnfarben (helle Lagen zuerst, dunkle Details obendrauf, jede Lage mit eigener Stichrichtung) oder
<i>einfarbig</i> als Linienschraffur, deren Zickzack in dunklen Bereichen dichter wird. Mit
Live-Vorschau, Stichzahl und Stickzeit.</li>
<li><b>Eigene Designs</b> von Grund auf:
<i>Bézier-Stift</i> (Erstellen › Linien, B): Klick = Ecke, Klicken und Ziehen = Kurvenpunkt mit Anfassern, Klick auf den
Startpunkt schließt die Form, Enter/Doppelklick beendet eine offene Linie, Rücktaste nimmt den letzten
Punkt zurück. Im Punkte-Werkzeug zeigen gewählte Punkte ihre Anfasser (lila); ziehen formt die Kurve,
an glatten Punkten bleiben beide Anfasser in einer Linie. Rechtsklick auf einen Punkt: »Bézier-Anfasser
hinzufügen/entfernen«. <i>Ebenen</i> (Anordnen › Ebenen bzw. Reiter rechts): anlegen, umbenennen, ein-/ausblenden (wird dann
nicht gestickt), sperren, umsortieren – gestickt wird Ebene für Ebene von unten nach oben.
<i>Bibliothek</i> (Erstellen › Vorlagen &amp; Bibliothek): Auswahl oder ganzes Design als eigenes Element speichern, in Kategorien ordnen,
per Doppelklick einfügen. <i>Design-Vorlagen</i> (Erstellen): Namensschild, Wappen, Rund-Emblem, Blätterkranz,
Monogramm, Aufnäher, Geburt, Hochzeit, Banner, Bordüre, Herz mit Namen und Zierrahmen mit
Live-Vorschau. <i>Schrift-Werkstatt</i> (Schrift › Eigene Schriften): eigene Stickschriften aus einer
Computerschrift erzeugen oder aus selbst gezeichneten Zeichen zusammenstellen.</li>
<li><b>Gestalten wie in Inkscape</b>: <i>Pfad-Operationen</i> (Anordnen) – Kombinieren
(Vereinigung), Ausschneiden (Differenz), Schnittmenge, Exklusion, Teilen (Division) und Zerlegen;
<i>Ausrichten</i> (links, mittig, rechts, oben, unten – an der Auswahl oder am Rahmen) und
<i>Verteilen</i> (gleiche Abstände; Gruppen zählen als ein Objekt); <i>Sperren</i> (Anordnen › Ebenen, Strg+Alt+L,
entsperren über die Objektliste oder »Alle entsperren«). <i>Versatz</i> (Form bearbeiten):
Erweitern, Schrumpfen und Umriss – eine geschlossene Linie im Abstand um die Auswahl, z. B. als
Satinrand für einen Aufnäher. <i>Kopien</i> im Raster oder im Kreis (Form bearbeiten), <i>Stern/Vieleck</i> und
<i>Spirale</i> (Erstellen), <i>Farbe aufnehmen</i> aus der Vorlage (Nachzeichnen) und
<i>Einrasten</i> beim Verschieben an Raster, Rahmenmitte und anderen Objekten (Ansicht › Pfeil am
Raster-Knopf: ein/aus, Ziele, Rasterweite; Taste %; Alt beim Ziehen = ohne).</li>
<li><b>Gruppieren</b> (Anordnen › Gruppe, Strg+Alt+G): mehrere Objekte auswählen (Umschalt+Klick oder
Rahmen ziehen) und gruppieren. Ein Klick wählt dann die ganze Gruppe; verschieben, mit den Eckgriffen
skalieren und drehen, spiegeln und duplizieren wirkt auf alle zusammen. Rechts unter
<i>Eigenschaften</i> lässt sich die Gruppe auf eine genaue Breite/Höhe bringen – die Stiche werden
neu berechnet, die Dichte bleibt richtig. Alt+Klick wählt ein einzelnes Objekt der Gruppe,
<i>Gruppe auflösen</i> (Strg+Alt+Umschalt+G) hebt sie auf. Auch ohne Gruppe skalieren die Eckgriffe
alle ausgewählten Objekte gemeinsam.</li>
<li><b>Stoffart</b> (Start, rechts): Webware, T-Shirt/Jersey, Polo/Piqué, Frottee, Fleece,
Jeans, Kappe, Leder oder Seide – wie in Profi-Programmen werden Dichte, Zugausgleich und Unterlage
beim Sticken an den Stoff angepasst, ohne deine eingestellten Werte zu ändern. Der Hinweis in der
Statuszeile nennt passendes Vlies und Topping.</li>
<li><b>Stickbild verbessern</b> (Optimieren › Verbessern): <i>Überlappung entfernen</i> stickt Flächen, die von
später gestickten Objekten verdeckt werden, nicht doppelt – ein schmaler Rand (einstellbar) bleibt
überlappend gegen Lücken. Weniger Stiche, weichere und flachere Stickerei. Formen mit eigenem Rand
werden übersprungen. Das ändert die Form dauerhaft – wird das Motiv danach verschoben, sitzt das
Loch falsch. Dafür gibt es <i>Automatisch aussparen</i> (Knopf daneben): Verdecktes wird erst beim
Berechnen der Stiche weggelassen, die Formen bleiben unverändert. Schiebst du ein Motiv über eine
Fläche, wandert die Aussparung mit; schiebst du es weg, ist die Fläche wieder vollständig. Das gilt
für Flächen und Schriftzüge in Computerschrift (Stickschriften bringen ihre Stiche fertig mit); ein
Rand folgt weiter der Originalkontur. Verdecken können Flächen, Schriftzüge, Satinsäulen,
Satinlinien und Satinränder – ausgeblendete Objekte und Ebenen nicht. Über den Pfeil am Knopf
stellst du ein, wie weit die untere Fläche unter dem oberen Objekt weiterläuft (Standard 1 mm, gegen
Lücken durch Verzug). Einzelne Flächen nimmst du in den Eigenschaften aus (<i>Füllstich ›
Verdecktes aussparen</i>). Die Einstellung wird mit dem Projekt gespeichert; Stichansicht, Simulator
und Export zeigen dasselbe Ergebnis. <i>Kleinteile entfernen</i> löscht winzige Flächenstücke, Löcher und Linien
(z. B. nach dem Digitalisieren), die nur Sprünge und Fadensalat ergeben.</li>
<li><b>Satin-Ecken</b>: Satinlinien und Satinränder bekommen an spitzen Ecken eine Gehrung – die
Stiche fächern um die Ecke, innen werden sie verkürzt (keine Garnhäufung), außen bleibt keine Lücke.
Umschaltbar unter <i>Feinheiten › Satin-Ecken</i>.</li>
<li><b>Satindichte nach Breite</b> (Feinheiten, bei neuen Objekten an): schmale Satinsäulen werden
lockerer gestickt (nicht steif und wulstig), breite etwas dichter (deckt besser).</li>
<li><b>Unterlage nach Größe</b> (Feinheiten, bei neuen Objekten an): Teile unter 2 mm Breite
bekommen keine Unterlage, unter 5 mm nur die Randlinie, größere die volle Unterlage.</li>
<li><b>3D-Puff</b> (Sticken › Effekte): ausgewählte Satinsäulen, Satinlinien oder Schriftzüge
für Schaumstoff einrichten – dichter Satin ohne Unterlage, Endkappen an den Säulenenden, die
Puff-Objekte kommen zuletzt und davor hält die Maschine an. Dann Schaumstoff (2–3 mm, in Garnfarbe)
auflegen, weitersticken, Schaum abreißen und Reste kurz mit Heißluft schrumpfen. Puff wirkt ab
etwa 3 mm Säulenbreite.</li>
<li><b>Kurvenanpassung</b> (Einstellungen › Sticken): Steppstiche werden in engen Kurven
automatisch kürzer, sodass sie höchstens 0,2 mm von der Linie abweichen – Rundungen bleiben rund,
gerade Strecken behalten die volle Stichlänge.</li>
<li><b>Feinheiten</b> (Eigenschaften, unterste Karte – wie die Ink/Stitch-Parameter):
Unterlage der Fläche mit Winkel, Reihenabstand, Abstand zum Rand, ein oder zwei gekreuzte Lagen
und Randlinie; <i>Erweitern</i> vergrößert die Füllfläche (z. B. damit sie unter den Satinrand
reicht); <i>Zufällige Stichlänge</i> gegen sichtbare Einstichmuster; bei Satinsäulen die
<i>Satin-Unterlage</i> (Mittellinie, Kontur, Zickzack oder Kombinationen) sowie zufällige Breite
und zufälliger Stichabstand; <i>Vernähen</i> mit eigener Form je Objekt (Halbstich, vor und zurück,
Pfeil, Stern, Dreieck, Zickzack oder aus) und auf Wunsch vor jedem Sprung.</li>
<li><b>Auto-Satin</b> (Sticken › Satin): mehrere Satinsäulen bzw. Satinlinien
auswählen – sie werden in kürzester Reihenfolge und passender Richtung gestickt, die Wege dazwischen
laufen als Steppstich verdeckt unter den Säulen statt als Sprung.</li>
<li><b>Mehrfarbiger Satin</b>: eine Satinsäule der Länge nach in 2–6 farbige, leicht überlappende
Streifen teilen.</li>
<li><b>Bohnenstich-Muster</b> (Rand bzw. Linie, Stichart Bohnenstich): z. B. »1 0« sticht
abwechselnd dreifach und einfach, »2 0 0« ergibt ein Perlenmuster.</li>
<li><b>Tatami-Einstichmuster</b> (Füllstich › Muster): 15 Muster – neben Standard, Ziegel,
Fischgrät und Wellen auch große Ziegel, Zickzack, große Wellen, flache Diagonale, Köper, Rauten,
Karo, Schuppen und »Gestreut« (ohne sichtbares Muster). Das Muster entsteht nur durch die Lage der
Einstiche – am deutlichsten bei glänzendem Garn, größerer Stichlänge und flachem Licht.</li>
<li><b>Farbverlauf mit bis zu 5 Farben</b> und <b>Schottenkaro (Tartan)</b> als Füllarten. Für den
Tartan gibt es Vorlagen (Royal Stewart, Black Watch, Buchanan …) oder eigene Streifen über »…«;
erst werden alle Längsstreifen gestickt, dann die Querstreifen darüber.</li>
<li>Reiter <b>Form bearbeiten</b>: Punkte (N), Radierer (X); Reiter <b>Anordnen</b>: Zerlegen, Kombinieren,
Ausschneiden. Im Punkte-Werkzeug macht ein Rechtsklick auf einen Punkt ihn zur Ecke oder
Rundung.</li>
<li><b>Punkte einfügen</b>: im Punkte-Werkzeug mit der Maus über die Kante fahren – es erscheint
ein »+« – und klicken; der neue Punkt lässt sich gleich ziehen. Alternativ Punkte wählen und
<i>Punkt einfügen</i> (Einfg) drücken: setzt neue Punkte zwischen die gewählten. Rechtsklick auf
die Kante fügt gezielt einen Eck- oder Rundungspunkt ein. Bei Säulen-Satin entsteht dabei ein
Punktepaar auf beiden Seiten; offene Linien verlängerst du mit Strg+Klick neben dem Ende.</li>
<li><b>Punkte verbinden</b> (Strg+J): beide Endpunkte einer Linie wählen = Linie schließen;
benachbarte Punkte wählen = zu einem Punkt zusammenfassen; zwei oder mehr Linien auswählen = zu
einer Linie verbinden (die nächstgelegenen Enden werden verknüpft). <b>Auftrennen</b>
(Strg+Umschalt+J) öffnet eine geschlossene Linie am gewählten Punkt bzw. teilt eine offene
Linie dort in zwei.</li>
<li><b>Mit Linie verbinden</b> (K): ersten Punkt anklicken, dann den zweiten – dazwischen entsteht
eine Linie. Das Werkzeug rastet auf den Punkten aller Formen und Linien ein (auch über mehrere
Objekte hinweg). Klickst du Linienenden an, wird die Linie verlängert, geschlossen oder mit der
anderen Linie zu einer zusammengeführt. Umschalt = Winkel in 15°-Schritten. Sind im
Punkte-Werkzeug schon zwei Punkte gewählt, verbindet ein Klick auf den Knopf sie sofort.</li>
<li><b>Rundungen erkennen</b> verwandelt eckige, digitalisierte Konturen in wenige saubere
Ecken und Rundungen.</li>
<li>Stickreihenfolge: rechts unter <i>Objekte</i> per Ziehen umsortieren.</li>
</ul>
<h3>Video &amp; An Maschine senden</h3>
<ul>
<li><i>Export › An Maschine senden</i>: USB-Stick einstecken, Ziel wählen, »Senden« – die Datei
kommt im Format der eingestellten Maschine auf den Stick. Weitere Ordner (z. B. Netzwerkordner
der Maschine) lassen sich hinzufügen und werden gemerkt.</li>
<li><i>Export › Simulationsvideo</i>: MP4-Video, wie das Design entsteht – zum Zeigen oder
Teilen (benötigt ffmpeg).</li>
</ul>
<h3>Sketch &amp; Stich-Editor</h3>
<ul>
<li><b>Sketch</b> (Taste D, Verzieren › Zeichnen &amp; Malen): frei zeichnen, jeder Strich wird
gleich zu Stichen. Den Stil (Bleistift, Steppstich, Satin …) wählt der kleine Pfeil am Knopf.
Esc beendet das Werkzeug.</li>
<li><b>Stich-Editor</b> (Optimieren › Stiche oder Doppelklick auf eine Stickdatei): einzelne
Stiche wählen, verschieben, löschen und einfügen, Farbwechsel setzen, kurze Stiche entfernen,
lange teilen. Rechte Maustaste verschiebt die Ansicht, das Mausrad zoomt.</li>
</ul>
<h3>Malen &amp; Druck-Applikation</h3>
<ul>
<li><i>Verzieren › Zeichnen &amp; Malen › Mal-Atelier</i>: malen wie in einem kleinen Malprogramm. Unter
<i>Verwenden</i> wählen: Druck-Applikation, Vorlage zum Nachzeichnen oder Bild-Assistent.</li>
<li>Druck-Applikation: <i>Druckvorlage</i> in Originalgröße auf bedruckbaren Stoff drucken,
Platzierungslinie sticken, Stoff auflegen, Heftstich, dicht an der Naht zurückschneiden,
Satinrand sticken – die Maschine hält an den richtigen Stellen an.</li>
</ul>
<h3>Quiltblock &amp; Stammbaum</h3>
<ul>
<li><i>Verzieren › Quiltblock</i>: Block mit Motiv und Quiltmuster (Echo, Stippling,
Kreuzschraffur, Konturlinien, Spirale). Ist vorher eine Stickerei ausgewählt, kann der Block
auch um sie herum gequiltet werden.</li>
<li><i>Verzieren › Stammbaum</i>: Ahnentafel oder Familienbaum. Namen mit Komma trennen,
»Name / Jahr« ergibt eine zweite Zeile.</li>
</ul>
<h3>Kreuzstich</h3>
<ul>
<li><i>Verzieren › Kreuzstich</i> öffnet das Kreuzstich-Atelier: Kästchen mit der Maus belegen
(Ziehen zeichnet mehrere, Rechtsklick radiert), Rückstich durch Ziehen von Rasterpunkt zu
Rasterpunkt. <i>Bild laden</i> macht aus einem Bild ein Zählmuster.</li>
<li>Strg+Mausrad zoomt das Raster, Strg+Z / Strg+Y gelten im Atelier.</li>
<li>Ein Kreuzstich-Objekt lässt sich verschieben, drehen und skalieren wie jedes andere –
Doppelklick öffnet es wieder im Atelier.</li>
</ul>
<h3>Projekt im Rahmen</h3>
<ul>
<li><i>Erstellen › Projekt im Rahmen</i>: Untersetzer, Anhänger, Baumschmuck, Etuis, Hüllen
und mehr – ganz im Stickrahmen genäht. Die Maschine hält nach jedem Arbeitsschritt an
(Stoff auflegen, Rückseite ankleben …).</li>
<li><i>Export › Projekt-Anleitung</i> speichert die Schritt-für-Schritt-Anleitung mit Material
und Zuschnitt als PDF.</li>
<li>Für Projekte bleibt »Farben zusammenfassen« aus, damit die Schritte in ihrer Reihenfolge
gestickt werden.</li>
</ul>
<h3>Verzieren</h3>
<ul>
<li><b>Encore</b>: Motiv auswählen, dann <i>Verzieren › Encore</i> – Kopien im Kreis, im Bogen,
als Bordüre, als Rechteck- oder Formrahmen. Mit Strg+Klick zusätzlich eine Linie wählen, dann
verteilt Encore das Motiv <i>entlang der Linie</i>. Strg+Z holt das Original zurück.</li>
<li><b>Rahmen &amp; Schnörkel</b>: fertige Zierrahmen, Bogenkanten, Schnörkel und Ranken – im
Fenster Größe, Stichart und Farben einstellen.</li>
<li><b>Spirograph</b>: Muster wie mit dem Zahnrad-Spielzeug – Zähne von Ring und Rad
bestimmen die Schleifen, der Stiftabstand ihre Form; mehrere Lagen in zwei Farben.</li>
<li><b>Text in Form</b>: Wörter füllen ein Herz, einen Kreis … oder die ausgewählte Form. Die
Wörter wiederholen sich, bis die Form voll ist.</li>
<li><b>Strass &amp; Perlen</b>: Form, Linie oder Schrift wählen – Steine entlang der Kontur oder
als Füllung. Steine werden nicht gestickt; <i>Strass-Schablone</i> speichert die Löcher als SVG
(Schneideplotter) oder PDF in Originalgröße.</li>
</ul>
<h3>4. Prüfen und exportieren</h3>
<ul>
<li><i>Design-Info</i> unter <i>Objekte</i>: Stichzahl, Farbfolge, Stickzeit.</li>
<li><b>Simulator &amp; Optimierer</b> (F5 oder F6): zeigt Stich für Stich, wie die Maschine stickt – mit nummerierten Sprüngen und Schnitten.
»◀ / ▶« springt zum vorigen/nächsten Sprung, rechts siehst du Stiche, Sprünge, Schnitte und
Stickzeit (vorher → jetzt) und kannst jeden Sprung direkt bearbeiten – einzeln oder alle auf
einmal (z. B. Schnitte bei kurzen Sprüngen entfernen).</li>
<li><b>Sprünge bearbeiten</b> (J): zeigt alle Sprünge (orange) und Fadenschnitte (rot ✕).
Klick auf einen Sprung: Fadenschnitt setzen/entfernen oder mit Stichen verbinden – das Programm
sagt dir, ob der Verbindungsfaden später überstickt wird. Klick auf einen Stich einer Stickdatei:
in einen Sprung umwandeln. Zwischen zwei Objekten steuerst du den Schnitt auch rechts unter
<i>Schnitt danach</i>.</li>
<li><b>Sprungstiche optimieren</b> (Optimieren › Sprünge) für importierte Stickdateien; eigene Formen
werden beim Export automatisch optimiert.</li>
<li><b>Stichreihenfolge</b>: Flächen, Schriftzüge und Stickschriften werden automatisch so
gestickt, dass möglichst wenig gesprungen wird – Verbindungen laufen verdeckt unter Reihen, die
noch kommen. Sprünge bleiben nur zwischen getrennten Teilen (z. B. einzelnen Buchstaben).
Die Reihenfolge dieser Teile – und gleichfarbiger Objekte – wird als ganzer Weg geplant (ab 1.23):
nicht einfach immer zum nächstgelegenen Teil, sondern so, dass alle Sprünge zusammen am kürzesten
sind. So bleibt kein einzelnes Teil liegen, zu dem am Ende quer über das Motiv zurückgesprungen
wird – mehrzeilige Schriftzüge werden z. B. Zeile für Zeile gestickt.
Innerhalb eines Buchstabens (Computer- und Stickschriften) geht es wie beim Auto-Satin in
Profi-Programmen: in jeden Strich mit der Unterlage hinein, mit dem Satin zurück – die Wege
dazwischen verschwinden unter Strichen, die noch kommen. Ein zusammenhängender Buchstabe wird so
ohne Sprung gestickt. In Füllungen werden winzige Reststücke nicht eigens angesprungen, und
längere Wege laufen lieber am Rand entlang, als zu springen.</li>
<li><b>Unterlage zuerst für alle Teile</b> (Eigenschaften › Füllstich): erst die Unterlage aller
Teile einer Form, danach der Füllstich – stabilisiert große oder mehrteilige Flächen besser,
kostet aber ein paar Sprünge mehr. Innerhalb einer zusammenhängenden Fläche kommt die
Unterlage immer zuerst.</li>
<li><b>Farben zusammenfassen</b> (Optimieren › Reihenfolge): gleiche Garnfarben nacheinander
sticken – weniger Farbwechsel, Überlappungen bleiben richtig.</li>
<li><b>Arbeitsblatt</b> (Strg+P): PDF mit Vorschau, Daten, Farbfolge mit Garnnummern und einer
1:1-Schablone zum Positionieren auf dem Stoff.</li>
<li><b>Design-Browser</b> (Strg+Umschalt+O): alle Stickdateien eines Ordners mit Vorschau.</li>
<li><b>Für Maschine exportieren</b> (Strg+E): PES, DST, JEF, EXP, VP3, XXX, U01, PEC, TBF, PMV;
dazu <i>ZIP</i> (die gängigen Formate in einem Archiv), Stichlisten als CSV, TXT oder JSON,
G-Code für CNC/Plotter und Farblisten (COL, EDR, INF). Der <i>Mehrfach-Export</i> packt auf
Wunsch alles in ein ZIP je Name.</li>
<li>Projekt speichern (Strg+S), damit du später weiterarbeiten kannst.</li>
</ul>
<p><b>Ausführliche Anleitung</b> mit Bildern und Beispielen: <i>Hilfe › Anleitung (PDF)</i>.</p>
<h3>Tipps</h3>
<ul>
<li>Schrift sollte mindestens 5–6 mm hoch sein, damit sie sauber stickt.</li>
<li>Erst ein Probestück auf einem Stoffrest sticken.</li>
</ul>
"""


class GuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kurzanleitung")
        self.setWindowIcon(icons.icon("help"))
        self.resize(620, 680)
        v = QVBoxLayout(self)
        t = QTextBrowser()
        t.setObjectName("guide")
        t.setHtml(GUIDE)
        v.addWidget(t, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)


ABOUT = f"""<h2>StichWizard {__version__}</h2>
<p>Sticksoftware für Linux – Formen, Schriftzüge, Bild-Digitalisierung und Export für
Stickmaschinen.</p>
<p>Gebaut mit Python, Qt (PySide6, LGPL), Shapely (mit GEOS), NumPy und pyembroidery.
Stickschriften und Garnkarten stammen aus dem Open-Source-Projekt Ink/Stitch – jede Schrift mit
eigener Lizenz. Alle Lizenztexte: »Lizenzen Dritter …«.</p>
<p>Für die private Nutzung.</p>"""


def licenses_dir():
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "licenses")


class LicensesDialog(QDialog):
    """Lizenzen der mitgelieferten Bestandteile: Übersicht und Volltexte."""

    def __init__(self, parent=None):
        import os
        from PySide6.QtWidgets import QListWidget, QPlainTextEdit
        super().__init__(parent)
        self.setWindowTitle("Lizenzen Dritter")
        self.resize(900, 640)
        h = QHBoxLayout(self)
        self.files = QListWidget()
        self.files.setFixedWidth(250)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont(MONO_FONT, 9))
        d = licenses_dir()
        names = sorted(os.listdir(d)) if os.path.isdir(d) else []
        first = "LIZENZEN-DRITTER.txt"
        names.sort(key=lambda n: (n != first, n.lower()))
        labels = {first: "Übersicht", "Stickschriften.txt": "Stickschriften (Urheber, Lizenz)"}
        for n in names:
            self.files.addItem(labels.get(n, n[:-4] if n.endswith(".txt") else n))
            self.files.item(self.files.count() - 1).setData(Qt.UserRole, os.path.join(d, n))
        self.files.currentItemChanged.connect(self._show)
        v = QVBoxLayout()
        v.addWidget(self.text, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        h.addWidget(self.files)
        h.addLayout(v, 1)
        if names:
            self.files.setCurrentRow(0)
        else:
            self.text.setPlainText("Die Lizenztexte wurden nicht gefunden (Ordner »licenses«).")

    def _show(self, cur, _prev=None):
        if cur is None:
            return
        try:
            with open(cur.data(Qt.UserRole), encoding="utf-8", errors="replace") as f:
                self.text.setPlainText(f.read())
        except OSError as e:
            self.text.setPlainText(str(e))


class McpDialog(QDialog):
    """Einrichtung der KI-Anbindung (MCP) mit kopierbaren Befehlen."""

    def __init__(self, command, status, parent=None):
        """command: Liste [programm, argumente …] zum Starten des MCP-Servers."""
        super().__init__(parent)
        self.setWindowTitle("KI-Anbindung (MCP)")
        self.setWindowIcon(icons.icon("ai"))
        self.resize(680, 620)
        v = QVBoxLayout(self)
        intro = QLabel(
            "<h3>KI-Assistenten mit StichWizard verbinden</h3>"
            "<p>Über das <b>Model Context Protocol (MCP)</b> kann ein KI-Assistent wie Claude "
            "StichWizard direkt bedienen: Designs lesen, Schriftzüge und Formen anlegen, Farben "
            "und Füllmuster ändern, Bilder digitalisieren, eine Vorschau ansehen und für die "
            "Maschine exportieren. Alles erscheint sofort hier im Fenster und lässt sich mit "
            "Strg+Z rückgängig machen.</p>"
            f"<p>Status: <b>{status}</b></p>")
        intro.setWordWrap(True)
        v.addWidget(intro)
        quoted = " ".join(f'"{c}"' if " " in c else c for c in command)
        claude_code = f"claude mcp add stichwizard -- {quoted}"
        import json as _json
        entry = {"command": command[0]}
        if len(command) > 1:
            entry["args"] = command[1:]
        desktop = _json.dumps({"mcpServers": {"stichwizard": entry}}, indent=2)
        for title, text, hint in (
                ("Claude Code (Terminal)", claude_code,
                 "Einmal im Terminal ausführen. Danach steht StichWizard in jeder Claude-Code-"
                 "Sitzung zur Verfügung."),
                ("Claude Desktop / andere MCP-Programme", desktop,
                 "In die MCP-Konfiguration des Programms eintragen (bei Claude Desktop: "
                 "Einstellungen › Entwickler › Konfiguration bearbeiten), dann neu starten.")):
            lab = QLabel(f"<b>{title}</b>")
            v.addWidget(lab)
            box = QPlainTextEdit(text)
            box.setReadOnly(True)
            mf = QFont(MONO_FONT, 9)
            mf.setStyleHint(QFont.Monospace)
            box.setFont(mf)
            box.setFixedHeight(46 if "\n" not in text else 150)
            row = QHBoxLayout()
            row.addWidget(box, 1)
            btn = QPushButton("Kopieren")
            btn.clicked.connect(lambda _=False, t=text, b=btn: (
                QApplication.clipboard().setText(t), b.setText("Kopiert ✓")))
            row.addWidget(btn, 0, Qt.AlignTop)
            v.addLayout(row)
            hl = QLabel(hint)
            hl.setWordWrap(True)
            hl.setObjectName("muted")
            v.addWidget(hl)
        ex = QLabel(
            "<b>Beispiele, was du der KI sagen kannst</b><ul>"
            "<li>»Schreib ›Emma‹ in Rosa als Bogen über ein Herz und zeig mir die Vorschau.«</li>"
            "<li>»Digitalisiere ~/Bilder/logo.png mit 4 Farben, 90 mm breit.«</li>"
            "<li>»Mach alle Flächen mit Kreuzstich und exportiere als PES auf den Desktop.«</li>"
            "</ul><p>Ist StichWizard nicht geöffnet, startet der MCP-Server es automatisch.</p>")
        ex.setWordWrap(True)
        v.addWidget(ex)
        v.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
