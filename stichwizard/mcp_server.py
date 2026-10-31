"""MCP-Server für StichWizard (Transport: stdio, JSON-RPC 2.0).

Ein KI-Client (z. B. Claude Code oder Claude Desktop) startet dieses Programm. Es reicht die
Werkzeug-Aufrufe an das laufende StichWizard weiter (lokaler Unix-Socket, siehe api.py) und
startet StichWizard bei Bedarf selbst. Auf stdout darf ausschließlich das MCP-Protokoll stehen;
Meldungen gehen nach stderr.
"""
import json
import os
import socket
import subprocess
import sys
import time

from . import __version__
from .ipc import pipe_file, socket_path

WINDOWS = sys.platform == "win32"

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSTRUCTIONS = """StichWizard ist eine Sticksoftware. Mit diesen Werkzeugen steuerst du das geöffnete
Programm live; jede Änderung erscheint sofort im Fenster und kann vom Nutzer mit Strg+Z
rückgängig gemacht werden.
Koordinaten in Millimetern, Ursprung = Mitte des Stickrahmens, x nach rechts, y nach UNTEN.
Typischer Ablauf: get_design (Rahmengröße, vorhandene Objekte) → add_text / add_shape / add_path
→ update_object zum Feinschliff → render_preview, um das Ergebnis anzusehen → save_project bzw.
export_design. Bleib innerhalb des Stickfelds (outside_hoop in get_design muss false sein).
Schrift sollte mindestens 5–6 mm hoch sein. Farben: Hex (#E53935), Garnname aus get_options
oder CSS-Name."""

FILL_DOC = ("Weitere Füllangaben, alle Punkte in mm wie x/y: guide [[x, y], …] = Führungslinie "
            "der geführten Füllung (setzt fill type guided; null entfernt sie) oder guide_line = id "
            "einer Linie, die als Führungslinie übernommen wird (die Linie verschwindet); start / "
            "end [x, y] = Start-/Endpunkt des Stickwegs (Flächen, Schriftzüge in Computerschrift, "
            "Satinsäulen; null = automatisch); underlay, underlay_first, stitch_len, pull, color2. "
            "Nur Satinsäulen: satin_type satin|zigzag|estitch, short_inset (0–50 %, kurze Stiche "
            "in engen Kurven, 0 = aus), short_dist (mm), split_len (2–15 mm, längere Stiche "
            "werden geteilt), split_random (Teilungspunkte zufällig versetzen), satin_ul "
            "auto|none|center|contour|zigzag|center_zigzag|contour_zigzag|all (Unterlage), "
            "width_random / spacing_random (0–50 / 0–80 %). Feinheiten: ul_angle (° zum "
            "Deckstich, Standard 90), ul_spacing, ul_inset (mm), ul_layers 1|2, ul_contour "
            "(Randlinie), expand (mm, Füllfläche erweitern), len_random (0–50 %, zufällige "
            "Stichlänge; für Linien in border), tie auto|half|strong|backforth|arrow|star|"
            "triangle|zigzag|none (Vernähstich), tie_force (auch vor kurzen Sprüngen), "
            "underlay_auto (Unterlage nach Größe), auto_spacing (Satindichte nach Breite), puff "
            "(3D-Puff-Endkappen für Satinsäulen), knockout (Standard true: Verdecktes aussparen, "
            "wenn set_hoop knockout=true – false nimmt die Fläche aus).")

_text_path = {
    "path": {"type": "array", "items": {"type": "array"},
             "description": "Schriftzug entlang eines Pfads [[x, y], …] in mm (ersetzt Bogen, "
                            "Position und Drehung); null = wieder gerade"},
    "path_line": {"type": "string", "description": "id einer Linie, die als Pfad übernommen "
                                                   "wird (die Linie verschwindet)"},
    "path_align": {"type": "string", "enum": ["start", "center", "end"],
                   "description": "Lage des Schriftzugs auf dem Pfad"},
    "path_flip": {"type": "boolean", "description": "Text auf der anderen Seite der Linie"},
}

_style = {
    "color": {"type": "string", "description": "Hauptfarbe (Füllung; bei Linien die Linienfarbe): "
                                               "Hex, Garnname oder CSS-Name"},
    "fill_type": {"type": "string", "enum": ["tatami", "satin", "wave", "guided", "contour",
                                             "cross", "motif", "net", "circular", "meander",
                                             "ripple", "gradient", "tartan", "applique", "none"],
                  "description": "Füllstich: tatami (Fläche), satin, wave (Wellen), guided "
                                 "(Reihen folgen einer Führungslinie – fill.guide oder "
                                 "fill.guide_line nötig), contour "
                                 "(parallel zum Umriss), cross (Kreuzstich), motif (kleine "
                                 "Motive), net (Gitter), circular (Spirale), meander (Quilt-"
                                 "Mäander), ripple (Konturlinien), gradient (Farbverlauf mit "
                                 "fill.color2 und bis zu 3 weiteren fill.gradient_colors), "
                                 "tartan (Schottenkaro: fill.tartan = Vorlagenname wie "
                                 "\"Royal Stewart\", \"Black Watch\", \"Buchanan\" oder "
                                 "[[farbe, breite_mm], …]; fill.tartan_scale, "
                                 "fill.tartan_symmetric), applique, none"},
    "pattern": {"type": "string", "enum": ["standard", "brick", "bigbrick", "herringbone", "zigzag",
                                           "waves", "bigwaves", "steps", "shallow", "twill",
                                           "diamond", "check", "scales", "straight", "scatter"],
                "description": "Tatami-Einstichmuster (diamond = Rauten, check = Karo, scales = "
                               "Schuppen, twill = Köper, scatter = gestreut ohne Muster)"},
    "motif": {"type": "string", "enum": ["heart", "star", "circle", "diamond", "flower"],
              "description": "Motiv für fill_type=motif"},
    "pattern_size": {"type": "number", "description": "Mustergröße in mm (Welle, Kreuz, Motiv, Netz)"},
    "angle": {"type": "number", "description": "Stichwinkel in Grad"},
    "density": {"type": "number", "description": "Reihenabstand in mm (0.3–0.6 dicht)"},
    "fill": {"type": "object", "description": FILL_DOC},
    "border": {"type": "object", "description": "Rand bzw. Linienstil: {type: none|run|triple|satin, "
                                                "color, width (mm, für satin), corners (bool: "
                                                "Steppstich trifft Ecken/Kreuzungen genau), "
                                                "repeats (Bohnenstich), bean_pattern (z. B. "
                                                "\"1 0\" = abwechselnd dreifach/einfach), "
                                                "len_random (0–50 %), corner mitre|none "
                                                "(Satin-Ecken), auto_spacing (bool)}"},
    "rotation": {"type": "number", "description": "Drehung in Grad"},
    "name": {"type": "string"},
}

TOOLS = [
    ("get_design", "Aktuelles Design abfragen: Rahmen, Stoff, alle Objekte (id, Typ, Position, "
                   "Größe, Farben, Stiche), Farbfolge, Stichzahl, Stickzeit, ob etwas über den "
                   "Rahmen ragt.", {}, []),
    ("get_options", "Verfügbare Rahmen, Stoffe, Garnfarben, Füllarten, Formen und installierte "
                    "Schriftarten auflisten.", {}, []),
    ("new_design", "Neues, leeres Design beginnen.", {
        "hoop": {"type": "string", "description": "z. B. '130x180'"},
        "fabric": {"type": "string", "description": "Stofffarbe"},
        "fabric_type": {"type": "string", "enum": ["standard", "jersey", "pique", "towel", "fleece",
                                                    "denim", "cap", "leather", "silk"],
                        "description": "Stoffart: passt Dichte, Zugausgleich und Unterlage an "
                                       "(towel = Frottee, jersey = T-Shirt, cap = Kappe …)"},
        "discard_changes": {"type": "boolean", "description": "Ungespeicherte Änderungen verwerfen"}},
     []),
    ("set_hoop", "Stickrahmen, Stofffarbe, Stoffart, »Farben zusammenfassen« (weniger Farbwechsel) "
                 "und/oder »Automatisch aussparen« ändern.", {
        "hoop": {"type": "string", "description": "z. B. '200x200'"},
        "fabric": {"type": "string"},
        "fabric_type": {"type": "string", "enum": ["standard", "jersey", "pique", "towel", "fleece",
                                                    "denim", "cap", "leather", "silk"],
                        "description": "Stoffart: passt Dichte, Zugausgleich und Unterlage an "
                                       "(towel = Frottee, jersey = T-Shirt, cap = Kappe …)"},
        "color_sort": {"type": "boolean", "description": "Gleiche Farben nacheinander sticken"},
        "knockout": {"type": "boolean", "description": "Automatisch aussparen: was später gestickte "
                                                       "Objekte verdecken, wird darunter nicht gestickt "
                                                       "(Formen bleiben unverändert, wandert beim "
                                                       "Verschieben mit)"},
        "knockout_margin": {"type": "number", "description": "So weit (mm, 0–5, Standard 1) läuft die "
                                                             "untere Fläche unter dem oberen Objekt weiter"},
        "thread_chart": {"type": "string", "description": "Garnkarte (get_options › thread_charts), "
                                                          "danach Farben auch per Nummer angebbar"}}, []),
    ("add_text", "Schriftzug hinzufügen.", {
        "text": {"type": "string", "description": "Text, mehrzeilig mit \\n"},
        "x": {"type": "number"}, "y": {"type": "number"},
        "height": {"type": "number", "description": "Höhe der Großbuchstaben in mm (Standard 20)"},
        "font": {"type": "string", "description": "Computerschrift (siehe get_options › fonts)"},
        "embroidery_font": {"type": "string", "description": "ID einer Stickschrift (get_options › "
                                                             "embroidery_fonts) – sauberer als Computerschriften"},
        "bold": {"type": "boolean"}, "italic": {"type": "boolean"},
        "arc_radius": {"type": "number", "description": "Bogentext: Radius in mm, >0 Bogen nach "
                                                       "oben, <0 nach unten, 0 gerade"},
        "letter_spacing": {"type": "number", "description": "Laufweite in mm"},
        **_text_path, **_style}, ["text"]),
    ("add_shape", "Form hinzufügen: rect, ellipse oder ein Motiv (heart, star, circle, square, "
                  "rounded, triangle, hexagon, diamond, flower, cloud, moon, bolt, paw, leaf, ring, "
                  "drop, house, butterfly, anchor, star8).", {
        "shape": {"type": "string"},
        "width": {"type": "number", "description": "Breite in mm"},
        "height": {"type": "number", "description": "Höhe in mm (weglassen = proportional)"},
        "x": {"type": "number"}, "y": {"type": "number"}, **_style}, ["shape"]),
    ("add_path", "Eigene Form oder Linie aus Punkten zeichnen. Jeder Punkt [x, y, 'corner'|'curve']: "
                 "corner = spitze Ecke, curve = runde, fließende Kurve durch den Punkt.", {
        "points": {"type": "array", "items": {"type": "array"},
                   "description": "z. B. [[0,-20,'corner'],[15,5,'curve'],[0,18,'curve'],[-15,5,'curve']]"},
        "closed": {"type": "boolean", "description": "true = gefüllte Fläche, false = Linie"},
        **_style}, ["points"]),
    ("update_object", "Objekt ändern. changes kann enthalten: x, y, width, height, rotation, "
                      "visible, name, trim_after ('auto'|'always'|'never' – Fadenschnitt danach), color, fill_type, pattern, motif, pattern_size, angle, density, "
                      "fill {...} (z. B. {\"underlay\": true, \"underlay_first\": true} = erst Unterlage aller Teile, dann Füllstich), border {...}, smooth (0–5), mirror ('horizontal'|'vertical'), "
                      "text (neuer Text oder {text, font, height, bold, italic, arc_radius, "
                      "path, path_line, path_align, path_flip} – Text an Pfad wie bei add_text). "
                      "fill: " + FILL_DOC + " Punkte werden nach x/y/width/height/rotation derselben "
                      "Änderung umgerechnet.", {
        "id": {"type": "string"},
        "changes": {"type": "object"}}, ["id", "changes"]),
    ("route_lines", "Redwork / Auto-Route: Steppstichlinien zu durchgehenden Wegen ohne Sprung "
                    "verbinden (ersetzt die Linien). mode redwork = jede Strecke genau zweimal, hin "
                    "und zurück, Ende am Anfang; autoroute = jede Strecke einmal, nur wo nötig "
                    "doppelt. Getrennte Gruppen ergeben getrennte Wege.", {
        "ids": {"type": "array", "items": {"type": "string"},
                "description": "Linien-ids; leer = alle Linien des Designs"},
        "mode": {"type": "string", "enum": ["redwork", "autoroute"]}}, []),
    ("delete_objects", "Objekte löschen.", {
        "ids": {"type": "array", "items": {"type": "string"}}}, ["ids"]),
    ("duplicate_object", "Objekt kopieren (versetzt um dx/dy mm).", {
        "id": {"type": "string"}, "dx": {"type": "number"}, "dy": {"type": "number"}}, ["id"]),
    ("set_order", "Stickreihenfolge festlegen: alle Objekt-ids in neuer Reihenfolge (zuerst "
                  "gestickt zuerst).", {"ids": {"type": "array", "items": {"type": "string"}}}, ["ids"]),
    ("select_objects", "Objekte im Fenster auswählen/hervorheben, damit der Nutzer sie sieht.", {
        "ids": {"type": "array", "items": {"type": "string"}}}, ["ids"]),
    ("center_design", "Gesamtes Design im Rahmen zentrieren.", {}, []),
    ("digitize_image", "Bilddatei (PNG, JPG, SVG …) automatisch in Stickflächen umwandeln.", {
        "path": {"type": "string"}, "colors": {"type": "integer", "description": "Anzahl Garnfarben"},
        "width": {"type": "number", "description": "Breite im Rahmen in mm"},
        "remove_background": {"type": "boolean"},
        "smoothing": {"type": "number", "description": "Glättung in mm (0.1–2, Standard 0.4)"},
        "x": {"type": "number"}, "y": {"type": "number"}}, ["path"]),
    ("import_embroidery", "Fertige Stickdatei (PES, DST, JEF, EXP, VP3 …) ins Design einfügen.", {
        "path": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}}, ["path"]),
    ("open_file", "Projekt (.stickproj) oder Stickdatei als neues Design öffnen.", {
        "path": {"type": "string"}, "discard_changes": {"type": "boolean"}}, ["path"]),
    ("save_project", "Projekt speichern (.stickproj). Ohne path unter dem bisherigen Namen.", {
        "path": {"type": "string"}}, []),
    ("optimize_jumps", "Sprungstiche und Fadenschnitte in importierten Stickdateien minimieren: "
                       "Teile werden neu geordnet (Überlappungen behalten ihre Reihenfolge) und "
                       "Verbindungen als verdeckte Stiche unter später gestickten Bereichen geführt.", {
        "ids": {"type": "array", "items": {"type": "string"},
                "description": "Objekt-ids (Typ stitches); leer = alle importierten Stickdateien"}}, []),
    ("get_jumps", "Alle Sprünge des Designs in Stickreihenfolge auflisten: Index, Start/Ende, "
                  "Länge, ob mit Fadenschnitt, ob innerhalb eines Objekts oder zwischen zwei "
                  "Objekten, und ob ein Verbindungsstich verdeckt wäre.", {}, []),
    ("edit_jump", "Einen Sprung bearbeiten: action trim_on / trim_off (Fadenschnitt setzen/"
                  "entfernen), trim_auto (nur zwischen Objekten) oder connect (durch "
                  "Verbindungsstiche ersetzen – nur sinnvoll, wenn get_jumps "
                  "connect_would_be_hidden=true meldet). Liegt der Sprung in einer berechneten Form, "
                  "convert=true setzen (Form wird in Stiche umgewandelt).", {
        "index": {"type": "integer"},
        "action": {"type": "string", "enum": ["trim_on", "trim_off", "trim_auto", "connect"]},
        "convert": {"type": "boolean"}}, ["index", "action"]),
    ("convert_to_stitches", "Formen/Schriftzüge in feste Stiche umwandeln (danach sind einzelne "
                            "Stiche und Sprünge bearbeitbar, die Form aber nicht mehr).", {
        "ids": {"type": "array", "items": {"type": "string"}}}, ["ids"]),
    ("export_design", "Für die Stickmaschine exportieren (Sprungstiche werden standardmäßig "
                      "optimiert).", {
        "path": {"type": "string"},
        "optimize": {"type": "boolean", "description": "Sprungstiche vor dem Export optimieren"},
        "format": {"type": "string", "enum": ["pes", "dst", "jef", "exp", "vp3", "xxx", "u01",
                                              "pec", "tbf", "pmv", "zip", "svg", "csv", "txt",
                                              "json", "gcode", "col", "edr", "inf"],
                   "description": "zip = PES, DST, JEF, EXP, VP3, XXX, U01 und Stichliste in "
                                  "einem Archiv"}}, ["path"]),
    ("export_worksheet", "Arbeitsblatt als PDF speichern: Vorschau, Maße, Farbfolge mit Garnnummern "
                         "und 1:1-Schablone zum Positionieren.", {"path": {"type": "string"}}, ["path"]),
    ("render_preview", "Vorschaubild des Designs (realistische Fadenansicht) als PNG. view='hoop' "
                       "zeigt den ganzen Rahmen mit Stoff.", {
        "view": {"type": "string", "enum": ["design", "hoop"]},
        "scale": {"type": "number", "description": "Pixel pro mm bei view=design (Standard 6)"}}, []),
    ("undo", "Letzte Änderung(en) rückgängig machen.", {"steps": {"type": "integer"}}, []),
    ("redo", "Rückgängig gemachte Änderung(en) wiederholen.", {"steps": {"type": "integer"}}, []),
]

READ_ONLY = {"get_design", "get_options", "render_preview"}


def log(*a):
    print("[stichwizard-mcp]", *a, file=sys.stderr, flush=True)


class AppLink:
    def __init__(self):
        self.sock = None
        self.file = None
        self.next_id = 1

    def _connect(self):
        if WINDOWS:
            f = open(pipe_file(socket_path()), "r+b", buffering=0)
            self.sock, self.file = f, f
            return
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(socket_path())
        s.settimeout(180)
        self.sock, self.file = s, s.makefile("rb")

    def _send(self, data):
        if WINDOWS:
            self.sock.write(data)
        else:
            self.sock.sendall(data)

    def ensure(self):
        if self.sock:
            return
        try:
            self._connect()
            return
        except OSError:
            pass
        log("StichWizard läuft nicht – wird gestartet")
        if WINDOWS:
            exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            subprocess.Popen([exe if os.path.exists(exe) else sys.executable, "-m", "stichwizard"],
                             cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             creationflags=0x00000008 | 0x00000200)   # DETACHED, NEW_GROUP
        elif os.environ.get("FLATPAK_ID"):
            # eigene Sandbox über das Flatpak-Portal, damit das Programm weiterläuft,
            # auch wenn der KI-Assistent die Verbindung beendet
            subprocess.Popen(["flatpak-spawn", "stichwizard"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        else:
            subprocess.Popen([sys.executable, "-m", "stichwizard"], cwd=ROOT,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.time() + 25
        while time.time() < deadline:
            time.sleep(0.5)
            try:
                self._connect()
                return
            except OSError:
                continue
        raise RuntimeError("StichWizard konnte nicht erreicht werden. Bitte StichWizard starten und "
                           "unter Einstellungen › Allgemein die KI-Schnittstelle aktivieren.")

    def call(self, method, params):
        for attempt in (1, 2):
            try:
                self.ensure()
                mid = self.next_id
                self.next_id += 1
                self._send(json.dumps({"id": mid, "method": method,
                                       "params": params}).encode() + b"\n")
                line = self.file.readline()
                if not line:
                    raise ConnectionError("Verbindung geschlossen")
                return json.loads(line)
            except (OSError, ConnectionError):
                self.sock = self.file = None
                if attempt == 2:
                    raise
        return None


def tool_list():
    tools = []
    for name, desc, props, required in TOOLS:
        t = {"name": name, "description": desc,
             "inputSchema": {"type": "object", "properties": props, "required": required}}
        t["annotations"] = {"readOnlyHint": name in READ_ONLY}
        tools.append(t)
    return tools


def handle(msg, link):
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        v = params.get("protocolVersion")
        return {"protocolVersion": v if v in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "stichwizard", "title": "StichWizard", "version": __version__},
                "instructions": INSTRUCTIONS}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": tool_list()}
    if method == "tools/call":
        name = params.get("name")
        if name not in {t[0] for t in TOOLS}:
            return {"content": [{"type": "text", "text": f"Unbekanntes Werkzeug: {name}"}],
                    "isError": True}
        try:
            resp = link.call(name, params.get("arguments") or {})
        except Exception as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        if "error" in resp:
            return {"content": [{"type": "text", "text": resp["error"]}], "isError": True}
        result = resp.get("result")
        if isinstance(result, dict) and "image_png_base64" in result:
            return {"content": [
                {"type": "image", "data": result["image_png_base64"], "mimeType": "image/png"},
                {"type": "text", "text": f"Vorschau {result['width']}×{result['height']} px"}]}
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)}]}
    raise LookupError(method)


def main():
    # MCP spricht UTF-8 – die Windows-Konsole würde sonst cp1252 verwenden (Umlaute, ✓ …)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    link = AppLink()
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
            continue
        if "id" not in msg:          # Benachrichtigung (z. B. notifications/initialized)
            continue
        try:
            out = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg, link)}
        except LookupError:
            out = {"jsonrpc": "2.0", "id": msg["id"],
                   "error": {"code": -32601, "message": f"Method not found: {msg.get('method')}"}}
        except Exception as e:
            log("Fehler:", e)
            out = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": str(e)}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
