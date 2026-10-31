GUI-Regressionstests (laufen ohne sichtbares Fenster, mit eigenen Einstellungen):

  T=$(mktemp -d); mkdir -p $T/rt; chmod 700 $T/rt
  XDG_CONFIG_HOME=$T XDG_CACHE_HOME=$T XDG_DATA_HOME=$T XDG_RUNTIME_DIR=$T/rt QT_QPA_PLATFORM=offscreen \
      .venv/bin/python tools/tests/regress_gui.py $T
  ... ebenso tools/tests/nodes_gui.py $T, inkstitch_gui.py, pfade_gui.py (1.4: Text an Pfad,
      geführte Füllung, Redwork/Auto-Route, Start/Ende, Satin), api_gui.py (KI-Schnittstelle:
      dieselben 1.4-Funktionen über api.py/mcp_server.py), knockout_gui.py (Automatisch aussparen:
      Motiv über Fläche schieben/wegschieben, je Objekt, Rand, Schrift, Speichern/Laden, Rückgängig),
      trace_gui.py (Bitmap nachzeichnen: Modi, Feinregler, Vorlage deckungsgleich),
      vector_gui.py (AI/PDF öffnen: erzeugt sich seine Testdatei selbst),
      jumporder_gui.py (Sprünge logisch verteilt: geplante Reihenfolge, tour.py),
      verzieren_gui.py (1.24: Encore, Rahmen & Schnörkel, Strass samt Schablone SVG/PDF),
      muster_gui.py (1.25: Spirograph, Text in Form / Word Sculpt),
      ith_gui.py (1.26: Projekt im Rahmen, Stopps, PDF-Anleitung),
      kreuzstich_gui.py (1.27: Kreuzstich-Atelier, Stichfolge, Bild → Kreuzstich),
      quilt_gui.py (1.28: Quiltblock- und Stammbaum-Assistent),
      malen_gui.py (1.29: Mal-Atelier, Druck-Applikation, Druckvorlage),
      sketch_gui.py (1.30: Skizzenstich, Sketch-Werkzeug, Stich-Editor),
      senden_gui.py (1.31: Simulationsvideo, An Maschine senden, USB-Erkennung) usw.

Beispieldateien kommen aus »~/Nextcloud/04 Hobby & Werkstatt/Sticken« (nur lesend, anderer Ordner
per STICK_TESTDATA=…). Fehlt dort das Hafnerei-Projekt, legen die Tests im Testordner ein Ersatzprojekt
aus der DST-Datei an. Die Optimierer-Tests (regress_gui, order_gui) erzeugen sich ihre Stickdatei
mit vielen Sprüngen selbst (jumpy_dst in tools/tests/testdata.py).

Rauchtest im installierten Flatpak (setzt seine XDG-Ordner selbst – »flatpak run --env=XDG_…«
würde von Flatpak überschrieben und die echten Nutzerdaten treffen). Der Testordner muss im
Home-Verzeichnis liegen, /tmp ist im Flatpak ein anderer Ordner:

  T="$PWD/build/flatpak-test"; mkdir -p "$T" /tmp/fprt; chmod 700 /tmp/fprt
  flatpak run --env=XDG_RUNTIME_DIR=/tmp/fprt --command=python3 local.stichwizard.StichWizard \
      "$PWD/tools/tests/flatpak_smoke.py" "$T"

Danach prüfen, dass unter ~/.var/app/local.stichwizard.StichWizard/data nichts Neues entstanden ist.
