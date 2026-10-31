# StichWizard – Sticksoftware für Linux und Windows

StichWizard ist eine Desktop-Sticksoftware (Python + Qt/PySide6) mit Menüband-Oberfläche,
realistischer Fadenansicht und Export für alle gängigen Stickmaschinen.

📖 **Ausführliche Anleitung mit Bildern:** [docs/StichWizard-Anleitung.pdf](docs/StichWizard-Anleitung.pdf)

## Download & Installation

Fertige Pakete gibt es auf der **[Release-Seite](https://github.com/fredimrc007-ops/StichWizard/releases/latest)**.

**Linux (Flatpak)**

```bash
flatpak install --user StichWizard-<version>.flatpak
flatpak run local.stichwizard.StichWizard
```

**Windows 10/11 (64 Bit):** `StichWizard-Setup-<version>.exe` ausführen. Die Installation braucht
keine Administratorrechte und legt Startmenü- und Desktop-Verknüpfung an.

**Aus dem Quellcode (Arch/CachyOS):**

```bash
sudo pacman -S pyside6 python-shapely python-numpy
./stichwizard.sh
```

Selbst bauen: `./build_flatpak.sh` bzw. `./build_windows.sh` (unter Linux mit Wine).

## Wichtigste Funktionen

- **Gestalten:** Formen, Linien, Bézier-Stift, Ebenen, Gruppieren, Ausrichten und Pfad-Operationen wie in Inkscape
- **Schrift:** 129 digitalisierte Stickschriften (Ink/Stitch) plus jede installierte Computerschrift, Bogentext, Text an Pfad
- **Stiche:** Tatami-, Satin-, Konturfüllung und viele weitere Füllarten, Säulen-Satin, Applikation, Kreuzstich, Fotostich
- **Digitalisieren:** Bild-Assistent, Bitmap nachzeichnen, AI/PDF/SVG als bearbeitbare Formen öffnen
- **Optimieren:** intelligente Stichreihenfolge mit wenigen Sprüngen, Simulator, Stich-Editor, automatisches Aussparen
- **Garn & Maschine:** 75 Garnkarten, Maschinenprofile, Stoffarten, Rahmen bis 360 × 200 mm
- **Öffnen & Exportieren:** PES, DST, JEF, EXP, VP3, XXX u. v. m., Arbeitsblatt (PDF), Simulationsvideo, direkt auf den USB-Stick senden
- **Extras:** Produktvorschau, Design-Vorlagen, Projekte im Stickrahmen, Quiltblock, Stammbaum, Mal-Atelier
- **KI-Anbindung (MCP):** StichWizard lässt sich von KI-Assistenten wie Claude steuern (Einrichtung unter Hilfe › KI-Anbindung)

## Updates

StichWizard prüft beim Start, ob auf GitHub eine neue Version erschienen ist, und zeigt dann einen
Hinweis mit Link zur Download-Seite. Es wird nichts automatisch heruntergeladen oder installiert.
Von Hand: Reiter „Hilfe“ › **Nach Updates suchen**; abschalten in den Einstellungen.

## Lizenzen

Die Stickschriften und Garnkarten stammen aus dem Open-Source-Projekt [Ink/Stitch](https://inkstitch.org).
Die meisten Schriften stehen unter der SIL Open Font License, einige unter Creative-Commons-Lizenzen.
Schriften mit „NC“ dürfen nur privat genutzt werden. Die Lizenz jeder Schrift steht im Auswahlfenster.
