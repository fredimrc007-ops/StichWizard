# StichWizard – Sticksoftware für Linux

Desktop-Sticksoftware (Python + Qt/PySide6) mit Ribbon-Oberfläche, realistischer Fadenansicht
und Export für alle gängigen Stickmaschinen.

Ausführliche Anleitung mit Bildern: [docs/StichWizard-Anleitung.pdf](docs/StichWizard-Anleitung.pdf)
(neu erzeugen: `tools/manual/images.py`, dann `tools/manual/make_manual.py`).

## Starten

```bash
./stichwizard.sh
```

Voraussetzungen (CachyOS/Arch): `sudo pacman -S pyside6 python-shapely python-numpy`.
`pyembroidery` wird beim ersten Start automatisch in `.venv` installiert.

## Funktionen

- **Formen:** Rechteck, Ellipse, Vieleck, 20 fertige Motive (Herz, Stern, Blume, Pfote …)
- **Linien:** Punkt-für-Punkt oder Freihand als Stepp-, Dreifach- oder Satinstich
- **Stickschriften:** 129 professionell digitalisierte Schriften aus der Ink/Stitch-Sammlung
  (Schreibschriften, Blockschriften, Monogramme, College-, Applikations- und Zierschriften) mit
  Vorschau-Auswahl, empfohlener Größe und Lizenzangabe; dazu jede installierte Computerschrift,
  Laufweite und Bogentext
- **Säulen-Satin:** Satin zwischen zwei Führungslinien mit mitdrehender Stichrichtung
- **Applikation:** Platzierungslinie, Stopp, Heftstich, Stopp, Satinrand – automatisch
- **Garnkarten:** 75 Hersteller-Karten (Madeira, Isacord, Gunold, Brother, Sulky, Robison-Anton …)
  mit echten Nummern in Palette, Design-Info, Arbeitsblatt und PES-Export
- **Farben zusammenfassen**, **Design-Browser** mit Vorschaubildern, **Arbeitsblatt (PDF)** mit
  1:1-Schablone
- **Füllmuster:** Tatami (15 Einstichmuster: Ziegel, große Ziegel, Fischgrät, Zickzack, Wellen,
  große Wellen, Diagonalen, Köper, Rauten, Karo, Schuppen, gestreut …), Satin,
  Wellen-, Kontur-, Kreuzstich-, Motiv- (Herz, Stern, Kreis, Raute, Blume) und Netzfüllung
- **Stiche:** Winkel, Dichte, Stichlänge, Unterlage, Zugausgleich;
  Rand als Stepp-, Dreifach- oder Satinstich; automatische Vernähstiche und Fadenschnitte
- **Bild-Assistent:** PNG/JPG/SVG automatisch in Stickflächen umwandeln (Farbreduktion)
- **AI / PDF öffnen** (Strg+Umschalt+I oder „Öffnen“): Illustrator-Dateien (.ai, PDF-kompatibel)
  und PDF als bearbeitbare Formen und Linien – Originalfarben (RGB, CMYK, Schmuckfarben), Kurven,
  Löcher, Schnittmasken; verdeckte Teile und weiße Flächen werden auf Wunsch weggelassen; auch als
  Vorlage, im Bild-Assistenten und beim Nachzeichnen nutzbar (benötigt das Paket `pypdf`)
- **Bitmap nachzeichnen** (wie Inkscape, Strg+Alt+B): Helligkeitsschwelle, Kantenerkennung,
  Mittellinie, Helligkeitsstufen, Farben, Graustufen; Feinregler für Weichzeichnen, Flecken
  unterdrücken, Ecken glätten, Toleranz und Abtastung; Vorschau als Flächen, als Konturen mit
  Knoten über dem Original oder als Stiche; zeichnet eine geladene Vorlage deckungsgleich nach
- **Nachzeichnen:** Bild oder SVG als halbtransparente Vorlage in den Rahmen legen und von Hand
  nachzeichnen – Linksklick = Eckpunkt, Rechtsklick = Rundungspunkt (wie in Profi-Programmen),
  Strg beim Abschließen = Loch in der ausgewählten Form
- **Form bearbeiten:** Punkte verschieben/einfügen (Klick auf die Kante, Einfg, Rechtsklick; bei
  Säulen-Satin paarweise; Linien per Strg+Klick verlängern)/löschen, Punkte verbinden (Linie
  schließen, Nachbarpunkte zusammenfassen, Linien verketten – Strg+J), zwei Punkte mit einer
  Linie verbinden (Werkzeug K, rastet auf Punkten ein) und Linien auftrennen, Punkte verbinden (Strg+J:
  benachbarte Punkte verschmelzen, Linie schließen, zwei Linien zu einer verbinden) und zwischen Ecke und Rundung
  umschalten, „Rundungen erkennen“ für digitalisierte Konturen, Radierer, Formen zerlegen,
  kombinieren und ausschneiden, Schriftzug in Form umwandeln, Punkte reduzieren
- **Stickdateien öffnen/importieren:** PES, DST, JEF, EXP, VP3, XXX, HUS, VIP, SEW, PEC u. v. m.
- **Exportieren:** PES, DST, JEF, EXP, VP3, XXX, U01, PEC, TBF, PMV, ZIP, SVG, CSV, TXT, JSON,
  G-Code, Farblisten sowie PNG-Vorschau
- **Simulator & Optimierer** (F5/F6): realistische Sticksimulation mit eingeblendeten Sprüngen/Schnitten,
  Sprung-für-Sprung-Navigation, Vorher/Nachher-Übersicht, Bearbeitung einzeln oder gesammelt
- **Sprünge & Fadenschnitte von Hand bearbeiten** (Werkzeug J): Schnitt setzen/entfernen,
  Sprung mit Stichen verbinden (mit Hinweis, ob der Faden verdeckt wird), Stich in Sprung
  umwandeln, „Schnitt danach“ pro Objekt (automatisch/immer/nie), Formen in Stiche umwandeln
- **Funktionen wie in Ink/Stitch (ab 1.3):** Spiral-, Mäander-, Ripple- und Farbverlaufsfüllung;
  Ränder/Linien als Zickzack, E-Stich, Bohnenstich (Wiederholungen wählbar), manueller Stich;
  Säulen-Satin als Satin, Zickzack-Satin oder E-Stich; Linie ↔ Säulen-Satin, Richtung umkehren,
  Satin teilen, Mittellinie (Fill to Stroke), Umriss aus Stickdatei, Knockdown; Stopp nach Objekt;
  Dichteprüfung; Mehrfach-Export mit Namensliste; Zeichenfilter für Stickschriften; Vernähen und
  Mindeststichlänge einstellbar
- **Weitere Ink/Stitch-Funktionen (ab 1.4):**
  - **Text an Pfad:** Schriftzug (Computer- oder Stickschrift) entlang einer ausgewählten Linie –
    Ausrichtung Anfang/Mitte/Ende, „Andere Seite“, „Pfad lösen“
  - **Geführte Füllung:** neue Füllart, deren Reihen einer zugeordneten Führungslinie folgen
    (Fläche + Linie auswählen › „Geführte Füllung“)
  - **Redwork** und **Auto-Route** für Steppstichlinien: alle ausgewählten Linien als ein
    durchgehender Weg ohne Sprung – Redwork jede Strecke genau zweimal (Ende am Anfang, Rückweg
    in denselben Einstichen), Auto-Route jede Strecke einmal und nur wo nötig ein zweites Mal
  - **Startpunkt/Endpunkt** je Fläche oder Satinsäule anklicken (wie die Ink/Stitch-Befehle)
  - **Säulen-Satin:** Kurze Stiche in engen Kurven (Einrückung und Abstand einstellbar),
    Max. Stichlänge und „Zufällig teilen“ für breite Säulen
- **Menüband nach Arbeitsschritten (ab 1.15):** Start · Erstellen · Verzieren · Schrift · Nachzeichnen ·
  Form bearbeiten · Anordnen · Sticken · Optimieren · Ansicht · Export · Hilfe – geordnet wie in
  Profi-Sticksoftware; Farbschema hell/dunkel mit 7 Akzentfarben (Ansicht › Farbschema);
  Karo-Raster im Rahmen (jede 5. Linie kräftiger)
- **Eigene Designs (ab 1.14):** Bézier-Stift mit Anfassern (auch im Punkte-Werkzeug), Ebenen,
  eigene Bibliothek mit Kategorien, 12 Design-Vorlagen (Namensschild, Wappen, Emblem, Kranz,
  Monogramm, Aufnäher, Geburt, Hochzeit, Banner, Bordüre, Herz mit Namen, Zierrahmen) und
  Schrift-Werkstatt für eigene Stickschriften
- **Gestalten wie in Inkscape (ab 1.13):** Schnittmenge, Exklusion, Teilen (Division);
  Ausrichten & Verteilen (an Auswahl oder Rahmen); Erweitern, Schrumpfen, Umriss/Patch-Rand;
  Kopien im Raster und im Kreis; Stern/Vieleck und Spirale; Sperren; Einrasten mit Hilfslinien;
  Farbpipette aus der Vorlage
- **Profi-Automatiken (ab 1.11):** Satin-Ecken mit Gehrung, Satindichte nach Breite,
  Unterlage nach Objektgröße, 3D-Puff-Voreinstellung (Endkappen, Stopp, Puff zuletzt);
  „Farben zusammenfassen“ respektiert Maschinenstopps
- **Gruppieren & besseres Stickbild (ab 1.10):**
  - **Gruppieren** (Strg+Alt+G): Gruppe gemeinsam wählen, verschieben, skalieren (Eckgriffe oder genaue
    Breite/Höhe), drehen, spiegeln, duplizieren; Alt+Klick wählt ein Einzelobjekt
  - **Stoffart** (Webware, Jersey, Piqué, Frottee, Fleece, Jeans, Kappe, Leder, Seide) passt Dichte,
    Zugausgleich und Unterlage an – wie Hatch/Wilcom/PE-Design
  - **Überlappung entfernen**: verdeckte Bereiche nicht doppelt sticken (Rand bleibt überlappend) –
    einmalig; die automatische, mitwandernde Variante ist »Automatisch aussparen«
  - **Kleinteile entfernen**: winzige Flächenstücke, Löcher und Linien aufräumen
  - **Kurvenanpassung**: Steppstich in engen Kurven automatisch kürzer
- **Weitere Ink/Stitch-Funktionen (ab 1.9):**
  - **Feinheiten** je Objekt: Flächen-Unterlage (Winkel, Abstand, Einzug, 1–2 Lagen, Randlinie),
    Erweitern, zufällige Stichlänge, Satin-Unterlage (Mittellinie/Kontur/Zickzack), zufällige
    Satinbreite und -abstand, Vernähstich-Art (Halbstich, vor/zurück, Pfeil, Stern, Dreieck,
    Zickzack, aus) und Vernähen vor jedem Sprung
  - **Auto-Satin:** Satinsäulen in kürzester Reihenfolge, Verbindungen verdeckt unter den Säulen
  - **Mehrfarbiger Satin** (2–6 Streifen) und **Bohnenstich-Muster** (z. B. „1 0“)
  - **Farbverlauf mit bis zu 5 Farben** und **Schottenkaro (Tartan)** mit Vorlagen oder eigenen Streifen
  - **Export:** zusätzlich TBF, PMV, ZIP, CSV, TXT, JSON, G-Code und Farblisten (COL, EDR, INF);
    Mehrfach-Export als ZIP
- **Farbwahl für große Garnkarten:** Farbfenster passt sich dem Bildschirm an, mit Suche und
  Listenansicht; Garnfarben-Leiste mit Mausrad-Blättern und »Alle …«
- **Oberfläche anpassen (ab 1.7):** hell/dunkel, Schriftgröße, Menüband groß/kompakt/nur Symbole,
  Werkzeug- und Seitenleiste links oder rechts, Garnfarben-Leiste ein/aus, eigener Favoriten-Reiter
- **Fotostich:** Foto farbig (2–16 Garne, Lagen hell → dunkel) oder als einfarbige Linienschraffur
- **Simulator & Optimierer** sind ein gemeinsames Fenster (F5 oder F6)
- **Element für Element (ab 1.6):** jede Fläche komplett (Unterlage → Füllung → eigener Rand in
  gleicher Farbe), Ende nahe am nächsten Element, keine Sprünge innerhalb einer Fläche; Sprünge ab
  einstellbarer Länge (Standard 3 mm) werden geschnitten
- **Sprungreihenfolge in der Simulation:** nummerierte Sprünge mit Richtungspfeil; Teil nach einem
  Sprung früher/später sticken oder umdrehen; Reihenfolge automatisch (kürzeste Wege) oder von Hand
- **Stufenloser Tempo-Regler** im Simulator & Optimierer (1–5000 Stiche/s, »wie Maschine«)
- **Intelligente Stichreihenfolge (Auto-Füllung, ab 1.2):** Flächen werden Insel für Insel
  gestickt (Unterlage, dann Deckstich, dann die nächste). Innerhalb einer Fläche laufen die
  Verbindungen als Steppstich unter noch kommenden Reihen bzw. am Rand entlang statt zu springen;
  die Reihenfolge der Abschnitte wird so gewählt, dass nichts abgeschnitten zurückbleibt.
  Stickschriften werden automatisch geführt (Satinsäulen in passender Richtung, Verbindungen
  unter späteren Säulen), gleichfarbige Objekte in kürzester Reihenfolge gestickt.
  Beispiele: „Die Hafnerei 100mm“ 134 → 16 Sprünge, digitalisiertes Bild 98 → 24,
  Text in Computerschrift 210 → 28
- **Unterlage zuerst für alle Teile** (Eigenschaften › Füllstich): erst die Unterlage aller Teile
  einer Form, dann der Füllstich – gegen Verzug bei großen/mehrteiligen Flächen (mehr Sprünge)
- **Sprungstiche optimieren:** importierte Stickdateien per Knopfdruck (Reiter „Optimieren“),
  eigene Designs automatisch beim Export – Teile werden neu geordnet und Verbindungen
  verdeckt unter später gestickten Bereichen geführt (z. B. „Die Hafnerei 6cm“: 79 → 34
  Sprünge, 24 → 16 Fadenschnitte)
- **Simulator & Optimierer** (F5/F6), Stickreihenfolge per Drag & Drop, Design-Info mit Farbfolge
- Stickrahmen von 100×100 bis 360×200 mm plus eigene Rahmengrößen (»Eigener Rahmen …«), Stofffarben, Rückgängig/Wiederholen
- **Kappenrahmen** (130 × 60 und 360 × 75 mm, Stoffart »Kappe« automatisch) und **Produktvorschau** (F7):
  Entwurf in Originalgröße auf T-Shirt, Kappe, Tasche, Handtuch, Kissen oder Lätzchen – live, als PNG speicherbar
- **Maschinenprofile** (TEXI IRIS 10, Brother PR1055X/PR680W/800E, Janome MB-7, allgemein, eigene): Rahmen,
  Format, Tempo, ausdrückliche Stopps für Mehrnadel-Maschinen, Nadelempfehlung je Stoff, Nadelplan
- **Simulationsvideo & An Maschine senden (ab 1.31, Reiter »Export«):**
  - **An Maschine senden:** Design im Format der eingestellten Maschine (z. B. TEXI IRIS 10 →
    DST) direkt auf den USB-Stick – eingesteckte Sticks und SD-Karten werden erkannt (interne
    Platten nie), weitere Zielordner (z. B. Netzwerkordner der Maschine) werden gemerkt;
    maschinenfreundliche Dateinamen (ohne Umlaute, auf Wunsch 8 Zeichen), Arbeitsblatt (PDF)
    mitkopieren, unter Linux danach Stick auswerfen
  - **Simulationsvideo (MP4):** das Design entsteht Stich für Stich – mit Nadel, Infoleiste
    (Garnfarbe, Stichzahl, Fortschritt) und Stickrahmen; HD, Full HD, quadratisch oder
    Hochformat, 25/30/60 Bilder je Sekunde. Braucht ffmpeg – ohne ffmpeg entstehen Einzelbilder
    (PNG)
- **Sketch & Stich-Editor (ab 1.30):**
  - **Sketch** (Verzieren › Zeichnen & Malen, Taste D): mit gedrückter Maustaste zeichnen –
    jeder Strich wird sofort zur Stichlinie, das Werkzeug bleibt für weitere Striche aktiv. Stil
    über den Pfeil am Knopf: Bleistift (neuer **Skizzenstich**: mehrere leicht versetzte
    Durchgänge wie skizziert), Stepp-, Bohnen-, Zickzackstich, Satin 2 oder 4 mm. Den
    Skizzenstich gibt es auch als Linienart in den Eigenschaften (Streuung, Extra-Durchgänge)
  - **Stich-Editor** (Optimieren › Stiche, Doppelklick auf eine Stickdatei): Stich für Stich
    blättern, Stiche wählen (Klick, Umschalt+Klick, Rahmen), verschieben (Ziehen, Pfeiltasten),
    löschen, einfügen, Stichart (Stich/Sprung/Schnitt/Stopp), Farbwechsel setzen, Blockfarbe,
    kurze Stiche entfernen, lange teilen, Rückgängig. Formen und Schriften werden dafür beim
    Übernehmen in Stiche umgewandelt (Abbrechen lässt sie unverändert)
- **Malen & Druck-Applikation (ab 1.29, Verzieren › Zeichnen & Malen):**
  - **Mal-Atelier:** Pinsel, Radierer, Linie, Rechteck, Ellipse (gefüllt oder Kontur), Füllen,
    Pipette, Text; Stärke, Deckkraft, Farbpalette und eigene Farben; Bild laden, Größe in mm,
    weiß oder durchsichtig leeren, Rückgängig/Wiederholen
  - Das Bild wird **als Druck-Applikation** eingefügt (Bild zum Bedrucken von Stoff +
    Applikation mit Platzierungslinie, Heftstich und Satinrand – Umriss als abgerundetes
    Rechteck, Oval oder entlang des Motivs), **als Vorlage zum Nachzeichnen** benutzt oder
    **mit dem Bild-Assistenten gestickt**. Doppelklick auf ein Druckbild öffnet es wieder, die
    Applikation passt sich an
  - **Druckvorlage (PDF):** Bild in Originalgröße mit Platzierungs- und Schnittlinie und
    Prüfquadrat, auf Wunsch gespiegelt (Transferpapier)
- **Quiltblock & Stammbaum (ab 1.28, Verzieren › Assistenten):**
  - **Quiltblock:** Quadrat, Rechteck, Kreis oder Sechseck mit Motiv in der Mitte (als
    Quiltlinie oder gestickt) und Quiltmuster drumherum – Echo-Quilting, Stippling (Mäander),
    Kreuzschraffur (von Rand zu Rand, in wenigen durchgehenden Wegen), Konturlinien, Spirale;
    Blockrand mitquilten, Abstand zu Motiv und Rand, Stepp- oder Bohnenstich, ohne Unterlage.
    »Um die Auswahl quilten« legt den Block um eine vorhandene Stickerei
  - **Stammbaum:** Ahnentafel (Kinder, Eltern, Großeltern, optional Urgroßeltern – Namen in
    Rahmen, mittig über ihren Kindern, mit Verbindungslinien) oder Familienbaum (Stamm, Äste,
    bis zu 16 Namen in zwei versetzten Reihen, Blätter); »Name / 1950« ergibt eine zweite Zeile
- **Kreuzstich (ab 1.27, Verzieren › Kreuzstich):** Kreuzstich-Atelier mit Zählraster –
  volle, halbe (/ \) und Viertelkreuze, Rückstich zwischen Rasterpunkten, Füllen, Pipette,
  Radierer (Rechtsklick), Rückgängig; Farbpalette mit Garnfarben; Kästchengröße 1,5–6 mm und
  Fadenstärke einfach/kräftig; **Bild → Kreuzstich** (Raster und Garnfarben automatisch, helle
  Bereiche bleiben frei). Gestickt wird Reihe für Reihe nach der Zickzack-Methode (erst alle
  »/«-Schenkel hin, dann alle »\«-Schenkel zurück), Rückstiche zuletzt. Das Muster bleibt als
  Kreuzstich-Objekt bearbeitbar (Doppelklick)
- **Projekt im Rahmen (ab 1.26, Erstellen › Vorlagen & Bibliothek):** 10 Projekte komplett im
  Stickrahmen genäht – Untersetzer (rund, eckig, Sechseck, Herz), Schlüsselanhänger mit Öse,
  Gepäckanhänger, Baumschmuck mit Bandschlaufe (Kugel, Stern, Herz, Tannenbaum), Stoffkarte &
  Lesezeichen, Kartenetui mit Tasche, Handyhülle (Maß aus den Handymaßen, oben offen),
  Pass- & Buchhülle mit Einschubklappen, Reißverschluss-Etui (zum Wenden) und Kuschelfigur mit
  Füllöffnung, die im Rahmen geschlossen wird. Jedes Projekt besteht aus Arbeitsschritten
  (Platzierungslinie, Heftstich, Motiv, Rückseite, Satinrand) mit Maschinenstopp dazwischen;
  Text und Motiv frei wählbar. **Projekt-Anleitung (PDF):** Vorschau, Material, Zuschnitt,
  alle Schritte mit Garnfarbe und Fertigstellen – bleibt im Projekt gespeichert
- **Spirograph & Text in Form (ab 1.25, Reiter »Verzieren« › Muster):**
  - **Spirograph:** Innenrad und Außenrad (Zähne von Ring und Rad, Stiftabstand), Rosette und
    Guilloche-Ring; mehrere gedrehte Lagen in zwei Farben, als Stepp-, Bohnen- oder schmale
    Satinlinie
  - **Text in Form (Word Sculpt):** Wörter füllen ein Herz, einen Kreis, Stern, eine Wolke,
    ein Haus … oder die ausgewählte Form; Zeilen werden auf die Breite der Form gebracht –
    behutsam, damit die Stickschrift dicht bleibt (leicht gestaucht/gedehnt, sonst gesperrt bzw.
    kleiner); in schmale Spitzen springt ein kürzeres Wort ein; Wörter wiederholen, zwei Farben,
    Umriss (auch unter »Schrift«)
- **Verzieren (ab 1.24, neuer Reiter):**
  - **Encore:** Auswahl als Muster wiederholen – im Kreis, im Bogen (auch nach unten offen),
    als Linie/Bordüre mit Zickzack, als Rechteck-Rahmen (Ecken besetzt), auf dem Umriss einer
    Form (Herz, Stern, Oval, Raute, Sechseck, Tropfen, Wolke) oder entlang einer ausgewählten
    Linie; Kopien mitdrehen, jede zweite spiegeln, Größenverlauf; Live-Vorschau
  - **Rahmen & Schnörkel:** Zierrahmen mit Eckschnörkeln, Bogenkante, Wellenrahmen (doppelt),
    Rahmen mit Punkten/Motiven, Doppelrahmen, Schnörkel-Trenner, Eckschnörkel, Herz aus
    Schnörkeln, Ranke mit Blättern – Größe, Stichart (Satin, Bohnenstich, Steppstich, Zickzack)
    und Farben frei
  - **Strass & Perlen:** Steine (SS6–SS30, Kristall/Perle/Matt) entlang der Kontur, als
    Wabenfüllung oder beides; eigene Karte in den Eigenschaften; werden nicht gestickt
  - **Strass-Schablone:** SVG für den Schneideplotter oder PDF in Originalgröße (mit
    Prüfquadrat und Stückliste), Loch = Stein + 0,4 mm
- **Sprünge logisch verteilt (ab 1.23):** Teilflächen, gleichfarbige Objekte und die Teile
  importierter Stickdateien werden als ganzer Weg mit der kürzesten Summe aller Sprünge geordnet
  statt immer nur zum nächstgelegenen Teil – kein Rücksprung quer übers Motiv mehr (Kappe
  „Des is Passt“: Zeilen jetzt von oben nach unten, 14 → 13 Sprünge, längster 35 → 25 mm);
  beim Farbwechsel kein zusätzlicher Fadenschnitt mehr
- **AI / PDF öffnen (ab 1.22):** Illustrator- und PDF-Vektorgrafiken als Formen übernehmen
- **Bitmap nachzeichnen (ab 1.21):** Bilder wie in Inkscape genau in Pfade umwandeln – mit
  Kontur- und Knotenvorschau und Feinreglern (Details siehe oben unter „Bitmap nachzeichnen“)
- **Produktvorschau erweitert (ab 1.20):** freier Zoom, Motiv auf dem Produkt verschieben,
  drehen und skalieren (ins Design übernehmbar), Hilfslinien mit Abstand zum Kragen, neue Produkte
  T-Shirt-Rückseite, Kapuzenpulli, Polo, Schürze
- **Schriften verfeinert (ab 1.19):** Computerschriften als Satin-Lettering (Satin folgt der
  Buchstabenform), Stickschriften mit allen wichtigen Ink/Stitch-Parametern (Schienenrichtung,
  kurze Stiche in Kurven, Ripple, geführte Füllung, Kreuzstich, Stich für Stich), keine Stiche über 12,1 mm
- **Design-Werkzeuge (ab 1.18):** Hüllformen für Schrift (Bogen, Fass, Welle, Wimpel …), einzelne Buchstaben
  verschieben/drehen/skalieren, Motivstich-Linie (Herzen, Blätter-Ranke, Muschelkante …), Schatten-Effekt,
  Mehrfach-Rahmung mit Passmarken, Lineal und Messwerkzeug, Garnvorrat, Schneidedatei (SVG) für Applikationen
- **Automatisch aussparen** (Optimieren › Verbessern): Was später gestickte Objekte verdecken, wird darunter
  beim Berechnen der Stiche weggelassen – live: beim Verschieben eines Motivs über eine Fläche wandert die
  Aussparung mit, beim Wegschieben ist die Fläche wieder vollständig. Die Formen bleiben unverändert (anders
  als »Überlappung entfernen«), ein Rand folgt weiter der Originalkontur; gilt für Flächen und Schriftzüge in
  Computerschrift. Überlappung einstellbar (Pfeil am Knopf, Standard 1 mm), je Objekt abschaltbar
  (Eigenschaften › Füllstich › »Verdecktes aussparen«), wird im Projekt gespeichert; auch über die
  KI-Schnittstelle (`set_hoop` knockout/knockout_margin, Füllung `knockout`)

## Flatpak (Linux)

`./build_flatpak.sh` baut `dist/StichWizard-<version>.flatpak` (Laufzeit
`org.freedesktop.Platform//26.08` von Flathub, PySide6 und alle Schriften sind enthalten).

```
flatpak install --user dist/StichWizard-1.4.0.flatpak
flatpak run local.stichwizard.StichWizard
```

Das Flatpak darf auf den Home-Ordner zugreifen (Stickdateien öffnen/speichern, Design-Browser).
Einstellungen liegen dort getrennt unter `~/.var/app/local.stichwizard.StichWizard/`.
KI-Anbindung: `claude mcp add stichwizard -- flatpak run --command=stichwizard-mcp local.stichwizard.StichWizard`

## Windows

`dist/StichWizard-Setup-<version>.exe` installiert StichWizard unter Windows 10/11 (64 Bit) – ohne
Administratorrechte in `%LOCALAPPDATA%\Programs\StichWizard`, mit Startmenü-/Desktop-Verknüpfung,
Dateizuordnung für `.stickproj` und Deinstallation über „Apps & Features“.

Neu bauen (unter Linux, benötigt Wine): `./build_windows.sh` – lädt Python für Windows, die
Windows-Pakete (PySide6, NumPy, Shapely, pyembroidery) und Inno Setup in `build/` und legt das
Setup in `dist/` ab. Für die KI-Anbindung unter Windows den Befehl aus Hilfe › KI-Anbindung
verwenden (`python.exe -m stichwizard.mcp_server` im Installationsordner).

## KI-Anbindung (MCP)

StichWizard lässt sich von KI-Assistenten wie Claude per **Model Context Protocol** steuern
(Designs lesen, Text/Formen/Pfade anlegen, Farben und Füllmuster ändern, Bilder digitalisieren,
Vorschaubild ansehen, speichern und exportieren). Änderungen erscheinen live im Fenster und
lassen sich mit Strg+Z rückgängig machen.

```bash
claude mcp add stichwizard -- "/home/weidi/Claude Code Projekte/Software/StichWizard/stichwizard-mcp.sh"
```

Für Claude Desktop o. Ä.: `stichwizard-mcp.sh` als `command` eines MCP-Servers eintragen.
Läuft StichWizard nicht, startet der MCP-Server es selbst. Ein-/ausschalten unter
Einstellungen › Allgemein › KI-Schnittstelle; Einrichtungshilfe unter Hilfe › KI-Anbindung.

## Einstellungen & Hilfe

- **Einstellungen** (Strg+, oder Zahnrad oben rechts): Standard-Stickrahmen und -Stoff,
  vorausgewähltes Exportformat, Stickgeschwindigkeit, Rückgängig-Schritte, Darstellung,
  Raster, Mausrad (zoomen oder verschieben), Vorgaben für neue Formen und Schriftart
- **Tastenkürzel** (F1): durchsuchbare Übersicht aller Kürzel und Mausaktionen
- **Kurzanleitung**: Reiter „Hilfe“

## Bedienung

| Aktion | Maus / Taste |
|---|---|
| Zoomen | Mausrad |
| Ansicht verschieben | mittlere Maustaste oder Leertaste + Ziehen |
| Größe / Drehen | Eckgriffe / runder Griff oben (Umschalt = 15°-Schritte) |
| Feinverschieben | Pfeiltasten (Umschalt = 10 mm) |
| Werkzeuge | V Auswahl · R Rechteck · E Ellipse · P Vieleck · L Linie · F Freihand · T Text · N Punkte · X Radierer |
| Punkte bearbeiten | ziehen · Doppelklick auf Kante = neuer Punkt · Rechtsklick/Entf = löschen · Pfeiltasten = 0,1 mm |
| Zerlegen / Kombinieren | Strg+Umschalt+G / Strg+G |
| Vieleck/Linie beenden | Doppelklick, Enter oder Rechtsklick |
| Farbe setzen | Palette unten: Linksklick = Füllung, Rechtsklick = Rand |
| Vorlage laden | Reiter „Nachzeichnen“ oder Strg+Umschalt+B |
| Vorlage verschieben | „Fixiert“ abhaken, dann mit der Maus ziehen |

## Lizenzen der Stickschriften und Garnkarten

Die Stickschriften und Garnkarten stammen aus dem Open-Source-Projekt
[Ink/Stitch](https://inkstitch.org) (Schriften: github.com/inkstitch/embroidery-fonts).
Die meisten Schriften stehen unter der SIL Open Font License, einige unter Creative-Commons-
Lizenzen – Schriften mit „NC" dürfen nur privat, nicht kommerziell genutzt werden. Die Lizenz
jeder Schrift steht im Auswahlfenster; der Volltext ist in `stichwizard/fonts/<schrift>.json.gz`
(Feld `license_text`) enthalten. Neu erzeugen: `tools/convert_inkstitch_fonts.py`,
`tools/convert_thread_charts.py`, `tools/make_font_previews.py`.
