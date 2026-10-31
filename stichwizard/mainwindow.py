"""Hauptfenster von StichWizard."""
import math
import os
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSettings, QSize, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QIcon, QImage, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFrame, QGraphicsScene, QSlider,
                               QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu,
                               QMessageBox, QScrollArea, QSplitter, QTabWidget, QToolBar,
                               QToolButton,
                               QVBoxLayout, QWidget)
from shapely import affinity
from shapely.geometry import Point, Polygon
from shapely.ops import linemerge, unary_union

from . import curves, engine, fileio, icons
from .autodigitize import IMAGE_EXTS, DigitizeDialog, load_image
from .canvas import Canvas
from .engine import STITCH, lines_of, polygons_of
from .api import ApiServer
from .help import ABOUT, GuideDialog, McpDialog, ShortcutsDialog
from .model import Document, EmbObject
from .prefs import Prefs, SettingsDialog
from .render import HoopItem, ObjectItem, TemplateItem, ViewOptions, render_document
from .shapes import MOTIFS
from .style import build_qss
from .threads import FABRICS, HOOPS, thread_name
from .widgets import MotifPanel, PaletteBar, PropertiesPanel, SequencePanel

APP = "StichWizard"


class _Rect:
    """QRectF -> Objekt mit .bounds (für design.bounds_of)."""

    def __init__(self, r):
        self.bounds = (r.left(), r.top(), r.right(), r.bottom())
PROJECT_EXT = "stickproj"


def tool_icon(name):
    ic = QIcon()
    ic.addPixmap(icons.icon(name).pixmap(48), QIcon.Normal, QIcon.Off)
    ic.addPixmap(icons.icon(name, "#FFFFFF", "#FFFFFF").pixmap(48), QIcon.Normal, QIcon.On)
    return ic


class RibbonButton(QToolButton):
    """Menüband-Knopf, der nie schmaler als seine Beschriftung wird (sonst kürzt Qt sie zu
    »Punkte bea…ten«). Passt ein Reiter nicht ins Fenster, lässt er sich seitlich verschieben."""

    def minimumSizeHint(self):
        s = self.sizeHint()
        return QSize(max(64, s.width()), s.height())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(build_qss())
        self.setWindowIcon(QIcon(icons.app_logo(256)))
        self.prefs = Prefs()
        self.prefs.apply_model_defaults()
        from .threads import load_custom_hoops
        load_custom_hoops(self.prefs.get("custom_hoops"))
        self.doc = self._new_document()
        self.opts = ViewOptions()
        self.opts.mode = self.prefs.get("view_mode")
        self.opts.show_grid = self.prefs.get("show_grid")
        self.opts.grid_step = self.prefs.get("grid_step")
        self.opts.wheel = self.prefs.get("wheel")
        self.path = None
        self.dirty = False
        self.undo_stack, self.redo_stack = [], []
        self.items = {}
        self.clipboard = []
        self._syncing = False

        self.scene = QGraphicsScene(-3000, -3000, 6000, 6000, self)
        self.hoop_item = HoopItem(self.opts)
        self.scene.addItem(self.hoop_item)
        self.template_item = TemplateItem()
        self.template_item.on_moved = self._template_moved
        self.scene.addItem(self.template_item)
        self.canvas = Canvas(self.scene, self.opts)

        self._make_actions()
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_header())
        root.addWidget(self._make_ribbon())

        self.props = PropertiesPanel()
        self.seq = SequencePanel()
        self.motifs = MotifPanel()
        self.side = QTabWidget()
        self.side.setObjectName("side")
        self.side.addTab(self.props, "Eigenschaften")
        self.side.addTab(self.seq, "Objekte")
        from .widgets import LayerPanel
        self.layers_panel = LayerPanel()
        self.side.addTab(self.layers_panel, "Ebenen")
        self.side.addTab(self.motifs, "Motive")
        from .widgets import LibraryPanel
        self.library_panel = LibraryPanel()
        self.side.addTab(self.library_panel, "Bibliothek")
        self.side.setMinimumWidth(380)

        mid = QSplitter(Qt.Horizontal)
        mid.setHandleWidth(1)
        self.toolstrip = self._make_toolstrip()
        mid.addWidget(self.toolstrip)
        mid.addWidget(self.canvas)
        mid.addWidget(self.side)
        mid.setStretchFactor(1, 1)
        mid.setSizes([56, 900, 400])
        mid.setCollapsible(0, False)
        mid.setCollapsible(1, False)
        self.mid = mid
        root.addWidget(mid, 1)
        self.palette_bar = PaletteBar()
        root.addWidget(self.palette_bar)
        self.setCentralWidget(central)
        self._make_status()
        self.apply_ui()
        self._update_machine_label()

        # Signale
        self.canvas.objectCreated.connect(self.on_created)
        self.canvas.itemsTransformed.connect(self.on_transformed)
        self.canvas.textRequested.connect(self.on_text_requested)
        self.canvas.crossRequested.connect(       # Doppelklick: passender Editor je Objektart
            lambda o: self.open_paint(o) if o.kind == "print" else
            self.open_stitch_editor(o) if o.kind == "stitches" else self.open_cross(o))
        self.canvas.cursorMoved.connect(lambda x, y: self.lbl_pos.setText(f"X {x:6.1f}  Y {y:6.1f} mm"))
        self.canvas.zoomChanged.connect(lambda z: self.lbl_zoom.setText(f"Zoom {z / 4 * 100:.0f} %"))
        self.canvas.toolFinished.connect(self._tool_finished)
        self.canvas.escapePressed.connect(lambda: self.set_tool("select"))
        self.canvas.nodesEdited.connect(self.on_nodes_edited)
        self.canvas.joinRequested.connect(self.join_nodes)
        self.canvas.breakRequested.connect(self.break_nodes)
        self.canvas.connectNodesRequested.connect(self.connect_selected_nodes)
        self.canvas.eraseRequested.connect(self.erase)
        self.canvas.jumpClicked.connect(self.on_jump_clicked)
        self.canvas.pointPicked.connect(self.on_point_picked)
        self.canvas.letterPicked.connect(self.props.select_letter)
        self.canvas.letterMoved.connect(self.on_letter_moved)
        self.canvas.measured.connect(lambda t: self.lbl_tip.setText("Gemessen: " + t))
        self.props.letter_selected.connect(self._letter_selected_in_panel)
        self._pick = None
        self.align_ref = "selection"      # Ausrichten an der Auswahl oder am Rahmen ("hoop")
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.canvas_menu)
        self.scene.selectionChanged.connect(self.on_scene_selection)
        self.props.changed.connect(self.on_prop_changed)
        self.props.action.connect(self.on_props_action)
        self.props.scaleRequested.connect(self.scale_selection)
        self.seq.selectionChanged.connect(self.on_seq_selection)
        self.seq.reordered.connect(self.on_reordered)
        self.seq.renamed.connect(self.on_renamed)
        self.seq.action.connect(self.on_seq_action)
        self.layers_panel.action.connect(self.on_layer_action)
        self.layers_panel.renamed.connect(self.rename_layer)
        self.library_panel.action.connect(self.on_library_action)
        self.motifs.chosen.connect(self.add_motif)
        self.palette_bar.picked.connect(self.apply_color)
        self.palette_bar.chartChanged.connect(self.set_thread_chart)
        self.palette_bar.snapRequested.connect(self.snap_colors)
        self.palette_bar.stockSnapRequested.connect(self.snap_to_stock)
        self.palette_bar.stockRequested.connect(self.edit_thread_stock)
        from . import threads as _threads
        _threads.set_chart(self.prefs.get("thread_chart"))
        self.palette_bar.set_chart(_threads.CURRENT_CHART)

        self.settings = QSettings("StickStudio", "StickStudio")
        try:
            self.canvas.eraser_size = max(0.3, min(50.0, float(self.settings.value("eraserSize", 3.0))))
        except (TypeError, ValueError):
            pass
        self.canvas.eraserSizeChanged.connect(self._eraser_size_changed)
        self.apply_hoop()
        self.commit(initial=True)
        self.update_title()
        self.resize(1440, 900)
        self.api_server = ApiServer(self, self._ai_activity)
        self.update_api_server()
        self._update_checker = None
        # Update-Hinweis: nicht in den Tests (offscreen) und nur, wenn eingeschaltet
        if self.prefs.get("update_check") and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            from PySide6.QtCore import QTimer
            QTimer.singleShot(4000, lambda: self.check_updates(manual=False))

    # ---------------------------------------------------------- Updates
    def check_updates(self, manual=True):
        """Bei GitHub nach einer neueren Version fragen. Lädt nichts herunter: neuere Version →
        Hinweis in der Statusleiste (beim Start) bzw. Dialog mit Link (über das Menü)."""
        from .update import UpdateChecker
        if self._update_checker is not None:
            return
        self._update_checker = UpdateChecker(self)
        self._update_checker.finished.connect(lambda res: self._update_result(res, manual))
        self._update_checker.start()
        if manual:
            self.lbl_tip.setText("Suche nach Updates …")

    def _update_result(self, res, manual):
        from . import __version__
        from .update import RELEASES_URL, is_newer
        self._update_checker = None
        if res and is_newer(res["version"]):
            self._update_info = res
            self.lbl_update.setText(f"<a href='#'>⬆ Version {res['version']} verfügbar</a>")
            self.lbl_update.show()
            if manual:
                self.show_update()
        elif manual:
            self.lbl_tip.setText("")
            if res:
                QMessageBox.information(self, APP, f"StichWizard {__version__} ist aktuell.")
            else:
                QMessageBox.information(
                    self, APP, "Es konnte nicht nach Updates gesucht werden (keine Internet-"
                    f"verbindung oder noch keine veröffentlichte Version).<br><br>Releases: "
                    f"<a href='{RELEASES_URL}'>{RELEASES_URL}</a>")

    def show_update(self):
        from . import __version__
        res = getattr(self, "_update_info", None)
        if not res:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Neue Version")
        box.setTextFormat(Qt.RichText)
        notes = res["notes"].strip()
        if len(notes) > 600:
            notes = notes[:600].rsplit("\n", 1)[0] + "\n…"
        box.setText(f"<b>StichWizard {res['version']}</b> ist erschienen (installiert: "
                    f"{__version__}).<br><br>Die neue Version wird nicht automatisch installiert. "
                    "Lade sie herunter und installiere sie wie gewohnt.")
        if notes:
            box.setDetailedText(notes)
        dl = box.addButton("Herunterladen …", QMessageBox.AcceptRole)
        page = box.addButton("Release-Seite", QMessageBox.ActionRole)
        box.addButton("Später", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is dl:
            QDesktopServices.openUrl(QUrl(res["url"]))
        elif box.clickedButton() is page:
            QDesktopServices.openUrl(QUrl(res["page"]))

    # ---------------------------------------------------------- KI / MCP
    def update_api_server(self):
        want = self.prefs.get("mcp_enabled")
        if want and not self.api_server.running():
            ok = self.api_server.start()
            self.lbl_ai.setText("✦ KI bereit" if ok else "✦ KI-Schnittstelle belegt")
        elif not want and self.api_server.running():
            self.api_server.stop()
        if not want:
            self.lbl_ai.setText("")

    def _ai_activity(self, method):
        self.lbl_ai.setText(f"✦ KI: {method}")

    def show_mcp(self):
        if sys.platform == "win32":
            exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
            command = [exe, "-m", "stichwizard.mcp_server"]
        elif os.environ.get("FLATPAK_ID"):
            command = ["flatpak", "run", "--command=stichwizard-mcp", os.environ["FLATPAK_ID"]]
        else:
            command = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "stichwizard-mcp.sh")]
        status = ("aktiv – StichWizard wartet auf Befehle" if self.api_server.running()
                  else "ausgeschaltet (Einstellungen › Allgemein › KI-Schnittstelle)")
        McpDialog(command, status, self).exec()

    # ================================================================= UI
    def _act(self, text, icon_name=None, slot=None, shortcut=None, checkable=False, tip=None):
        a = QAction(text, self)
        if "&" in text:      # sonst liest Qt »&« als Tastenkürzel-Markierung und blendet es aus
            a.setIconText(text.replace("&", "&&"))
        if icon_name:
            a.setIcon(icons.icon(icon_name))
            a.setProperty("icon_name", icon_name)
        if slot:
            if checkable:
                a.triggered.connect(slot)
            else:
                # triggered(bool) liefert »checked« mit – Methoden mit optionalem Parameter
                # (z. B. export_worksheet(path=None)) hielten das sonst für ihr Argument
                a.triggered.connect(lambda _checked=False, s=slot: s())
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        a.setToolTip(f"{tip or text}" + (f"  ({QKeySequence(shortcut).toString()})" if shortcut else ""))
        self.addAction(a)
        return a

    def _make_actions(self):
        A = self._act
        self.a_new = A("Neu", "new", self.new_doc, "Ctrl+N")
        self.a_open = A("Öffnen", "open", self.open_doc, "Ctrl+O")
        self.a_save = A("Speichern", "save", self.save_doc, "Ctrl+S")
        self.a_saveas = A("Speichern\nunter", "save", self.save_doc_as, "Ctrl+Shift+S")
        self.a_undo = A("Rückgängig", "undo", self.undo, "Ctrl+Z")
        self.a_redo = A("Wieder-\nholen", "redo", self.redo, "Ctrl+Y")
        self.a_redo2 = A("", None, self.redo, "Ctrl+Shift+Z")
        self.a_dup = A("Duplizieren", "duplicate", self.duplicate, "Ctrl+D")
        self.a_del = A("Löschen", "delete", self.delete_selected, "Delete")
        self.a_copy = A("Kopieren", None, self.copy, "Ctrl+C")
        self.a_paste = A("Einfügen", None, self.paste, "Ctrl+V")
        self.a_all = A("Alles auswählen", None, self.select_all, "Ctrl+A")
        self.a_up = A("Früher\nsticken", "up", lambda: self.move_seq(-1), "Ctrl+Up")
        self.a_down = A("Später\nsticken", "down", lambda: self.move_seq(1), "Ctrl+Down")
        self.a_center = A("Zentrieren", "center", self.center_selected, "Ctrl+M")
        # Gestalten wie in Inkscape
        self.a_intersect = A("Schnitt-\nmenge", "intersect", lambda: self.path_op("intersect"),
                             tip="Nur die Fläche behalten, die alle ausgewählten Formen gemeinsam "
                                 "haben (Inkscape: Überschneidung)")
        self.a_exclude = A("Exklusion", "exclude", lambda: self.path_op("exclude"),
                           tip="Überlappende Bereiche entfernen, der Rest bleibt (Inkscape: "
                               "Exklusiv-Oder)")
        self.a_divide = A("Teilen", "divide", lambda: self.path_op("divide"),
                          tip="Die unterste Form an den Umrissen der oberen in Stücke schneiden – "
                              "jedes Stück lässt sich einzeln färben (Inkscape: Division)")
        self.a_grow = A("Erweitern", "grow", lambda: self.offset_selected(True),
                        tip="Form rundum um einen Abstand vergrößern (Inkscape: Erweitern)")
        self.a_shrink = A("Schrumpfen", "shrink", lambda: self.offset_selected(False),
                          tip="Form rundum um einen Abstand verkleinern (Inkscape: Schrumpfen)")
        self.a_outline = A("Umriss", "outline_ring", self.outline_selected,
                           tip="Geschlossene Linie im Abstand um die Auswahl – z. B. als Satinrand "
                               "für einen Aufnäher")
        self.a_shadow = A("Schatten", "shadow", self.shadow_selected,
                          tip="Versetzten Schatten hinter Schrift oder Formen legen – als Fläche "
                              "oder Satinkontur, verdeckte Teile werden ausgespart")
        self.a_copygrid = A("Raster-\nkopien", "copygrid", self.copies_grid,
                            tip="Auswahl als Raster wiederholen (Spalten × Zeilen)")
        self.a_copycircle = A("Kreis-\nkopien", "copycircle", self.copies_circle,
                              tip="Auswahl im Kreis wiederholen, auf Wunsch mitgedreht")
        self.a_encore = A("Encore", "encore", self.open_encore,
                          tip="Auswahl als Muster wiederholen – im Kreis, im Bogen, als Linie, "
                              "Rechteck- oder Formrahmen oder entlang einer ausgewählten Linie")
        self.a_ornaments = A("Rahmen &\nSchnörkel", "ornament", self.open_ornaments,
                             tip="Zierrahmen, Bogenkanten, Wellenrahmen, Schnörkel-Trenner, "
                                 "Eckschnörkel und Ranken – frei in Größe, Stichart und Farbe")
        self.a_stones = A("Strass &\nPerlen", "stones", self.open_stones,
                          tip="Strass-Steine oder Perlen entlang der Kontur oder als Füllung "
                              "der ausgewählten Form, Linie oder Schrift setzen")
        self.a_stones_export = A("Strass-\nSchablone", "stonesheet", self.export_stones,
                                 tip="Schablone für Strassfolie oder Schneideplotter in "
                                     "Originalgröße speichern (SVG oder PDF mit Stückliste)")
        self.a_spiro = A("Spirograph", "spiro", self.open_spiro,
                         tip="Spirograph-Muster wie mit dem Zahnrad-Spielzeug: Innenrad, Außenrad, "
                             "Rosette, Guilloche-Ring – mehrere Lagen, zwei Farben")
        self.a_wordsculpt = A("Text in\nForm", "wordsculpt", self.open_wordsculpt,
                              tip="Word Sculpt: Wörter füllen eine Form (Herz, Kreis, Stern … oder "
                                  "die ausgewählte Form)")
        self.a_ith = A("Projekt im\nRahmen", "ith", self.open_ith,
                       tip="Projekte komplett im Stickrahmen nähen: Untersetzer, Schlüsselanhänger, "
                           "Gepäckanhänger, Baumschmuck, Karte, Kartenetui, Handyhülle, Pass-/"
                           "Buchhülle, Reißverschluss-Etui, Kuschelfigur – mit Anleitung")
        self.a_ith_pdf = A("Projekt-\nAnleitung", "sheet", self.export_ith_instructions,
                           tip="Anleitung zum Projekt im Rahmen als PDF: Material, Zuschnitt und "
                               "alle Arbeitsschritte mit Garnfarben")
        self.a_cross = A("Kreuzstich", "cross", self.open_cross,
                         tip="Kreuzstich-Atelier: Zählmuster mit vollen, halben und Viertelkreuzen "
                             "und Rückstich zeichnen oder aus einem Bild erzeugen – ein "
                             "ausgewähltes Kreuzstich-Objekt wird bearbeitet (auch Doppelklick)")
        self.a_quilt = A("Quiltblock", "quilt", self.open_quilt,
                         tip="Quiltblock-Assistent: Block mit Motiv und Quiltmuster – Echo, "
                             "Stippling, Kreuzschraffur, Konturlinien, Spirale; auch um eine "
                             "ausgewählte Stickerei herum")
        self.a_family = A("Stammbaum", "family", self.open_family,
                          tip="Stammbaum-Assistent: Ahnentafel (Kind, Eltern, Großeltern, "
                              "Urgroßeltern) oder Familienbaum mit Namen in der Krone")
        self.a_paint = A("Mal-\nAtelier", "paint", self.open_paint,
                         tip="Malen und zeichnen – als Druck-Applikation (Bild auf Stoff drucken, "
                             "Rand aufsticken), als Vorlage zum Nachzeichnen oder mit dem "
                             "Bild-Assistenten sticken")
        self.a_printsheet = A("Druck-\nvorlage", "printsheet", self.export_print_sheet,
                              tip="Druckvorlage für die Druck-Applikation als PDF in "
                                  "Originalgröße – mit Platzierungs- und Schnittlinie")
        self.a_stitchedit = A("Stich-\nEditor", "stitchedit", self.open_stitch_editor,
                              tip="Einzelne Stiche bearbeiten: wählen, verschieben, einfügen, "
                                  "löschen, Farbwechsel setzen, kurze Stiche entfernen, lange "
                                  "teilen – für Stickdateien und umgewandelte Objekte")
        self.a_send = A("An Maschine\nsenden", "usb", self.send_to_machine,
                        tip="Design im Format der eingestellten Maschine direkt auf den "
                            "USB-Stick (wird erkannt) oder in einen gemerkten Ordner speichern")
        self.a_video = A("Simulations-\nvideo", "video", self.export_sim_video,
                         tip="Video (MP4), wie das Design Stich für Stich entsteht – zum Zeigen "
                             "oder Teilen")
        self.a_templates = A("Design-\nVorlagen", "templates", self.open_templates,
                             tip="Fertige, anpassbare Layouts: Namensschild, Wappen, Rund-Emblem, "
                                 "Kranz, Monogramm, Aufnäher")
        self.a_layers = A("Ebenen", "layers", lambda: self.side.setCurrentWidget(self.layers_panel),
                          tip="Ebenen anzeigen: anlegen, ein-/ausblenden, sperren, umsortieren")
        self.a_newlayer = A("Neue\nEbene", "layer", lambda: self.on_layer_action(
            "add", self.doc.active_layer), tip="Neue Ebene über der aktiven anlegen")
        self.a_libsave = A("In Biblio-\nthek", "star", lambda: self.on_library_action(
            "save_sel", ""), tip="Ausgewählte Objekte als eigenes Element speichern")
        self.a_library = A("Bibliothek", "browse", lambda: self.side.setCurrentWidget(self.library_panel),
                           tip="Eigene Elemente und Designs anzeigen und einfügen")
        self.a_fontshop = A("Schrift-\nWerkstatt", "fontshop", self.open_font_workshop,
                            tip="Eigene Stickschriften: aus einer Computerschrift erzeugen oder "
                                "selbst gezeichnete Zeichen übernehmen")
        self.a_star = A("Stern /\nVieleck", "staricon", self.make_star,
                        tip="Stern oder regelmäßiges Vieleck mit Ecken, Spitzen und Rundung")
        self.a_spiral = A("Spirale", "spiral", self.make_spiral,
                          tip="Spirale als Linie (Windungen, Durchmesser)")
        self.a_lock = A("Sperren", "lock", self.lock_selected, "Ctrl+Alt+L",
                        tip="Ausgewählte Objekte sperren – nicht mehr anklickbar oder verschiebbar")
        self.a_unlock = A("Alle ent-\nsperren", "unlock", self.unlock_all, "Ctrl+Alt+Shift+L",
                          tip="Alle gesperrten Objekte wieder freigeben (einzeln: Objektliste)")
        self.a_pipette = A("Farbe\naufnehmen", "pipette", self.pick_color,
                           tip="Farbpipette: Farbe in der Vorlage anklicken – die ausgewählten "
                               "Objekte bekommen die nächstliegende Garnfarbe")
        self.a_snap = A("Einrasten ein/aus", "snap", self.toggle_snap, "%", checkable=True,
                        tip="Beim Verschieben an Raster, Rahmenmitte und anderen Objekten "
                            "einrasten (Alt beim Ziehen = ohne Einrasten)")
        self.a_snap.setChecked(bool(self.prefs.get("snap")))
        self.a_group = A("Grup-\npieren", "group", self.group_selected, "Ctrl+Alt+G",
                         tip="Ausgewählte Objekte zu einer Gruppe zusammenfassen – sie werden "
                             "gemeinsam ausgewählt, verschoben, skaliert und gedreht "
                             "(Alt+Klick wählt ein einzelnes Objekt der Gruppe)")
        self.a_ungroup = A("Gruppe\nauflösen", "ungroup", self.ungroup_selected, "Ctrl+Alt+Shift+G",
                           tip="Gruppierung der ausgewählten Objekte aufheben")
        self.a_mh = A("Spiegeln\n↔", "mirror_h", lambda: self.mirror(True),
                      tip="Horizontal spiegeln (links ↔ rechts)")
        self.a_mv = A("Spiegeln\n↕", "mirror_v", lambda: self.mirror(False),
                      tip="Vertikal spiegeln (oben ↕ unten)")
        self.a_import = A("Stickdatei\nimportieren", "import", self.import_design, "Ctrl+I")
        self.a_vector = A("AI / PDF\nöffnen", "vector", self.import_vector, "Ctrl+Shift+I",
                          tip="Vektorgrafik aus Illustrator (.ai) oder PDF als bearbeitbare Formen "
                              "und Linien übernehmen – Farben, Kurven und Löcher bleiben erhalten")
        self.a_browser = A("Design-\nBrowser", "browse", self.open_browser, "Ctrl+Shift+O",
                           tip="Alle Stickdateien eines Ordners mit Vorschaubildern durchsehen")
        self.a_photo = A("Fotostich", "photo", self.photo_stitch,
                         tip="Foto als Stickerei: farbig mit mehreren Garnen oder als einfarbige "
                             "Linienschraffur – mit Live-Vorschau")
        self.a_digit = A("Bild-\nAssistent", "wand", self.digitize_image, "Ctrl+B")
        self.a_trace = A("Bitmap\nnachzeichnen", "trace", self.trace_bitmap, "Ctrl+Alt+B",
                         tip="Bild genau in Pfade umwandeln wie in Inkscape: Helligkeitsschwelle, "
                             "Kanten, Mittellinie, Helligkeitsstufen, Farben oder Graustufen – mit "
                             "Feinreglern (Flecken, Ecken glätten, Toleranz) und Kontur-Vorschau")
        self.a_tpl = A("Vorlage\nladen", "image", self.load_template, "Ctrl+Shift+B",
                       tip="Bild als Vorlage zum Nachzeichnen in den Rahmen legen")
        self.a_tpl_del = A("Vorlage\nentfernen", "delete", self.remove_template)
        self.a_split = A("Zerlegen", "split", self.split_selected, "Ctrl+Shift+G",
                         tip="Form in einzelne Teile zerlegen (z. B. einzelne Buchstaben)")
        self.a_merge = A("Kombi-\nnieren", "merge", self.merge_selected, "Ctrl+G",
                         tip="Ausgewählte Formen zu einer Form vereinen")
        self.a_convert = A("In Form\numwandeln", "convert", self.convert_to_shape,
                           tip="Schriftzug in eine bearbeitbare Form umwandeln")
        self.a_addnode = A("Punkt\neinfügen", "addnode", self.insert_nodes, "Ins",
                           tip="Neue Punkte einfügen: zwischen den ausgewählten Punkten (bzw. nach "
                               "einem ausgewählten Punkt). Im Punkte-Werkzeug geht es auch per "
                               "Klick auf die Kante.")
        self.a_joinnode = A("Punkte\nverbinden", "joinnode", self.join_nodes, "Ctrl+J",
                            tip="Beide Endpunkte einer Linie gewählt: Linie schließen. Benachbarte "
                                "Punkte gewählt: zu einem Punkt zusammenfassen. Zwei oder mehr Linien "
                                "ausgewählt: zu einer Linie verbinden.")
        self.a_breaknode = A("Auf-\ntrennen", "breaknode", self.break_nodes, "Ctrl+Shift+J",
                             tip="Linie am gewählten Punkt auftrennen: geschlossene Linie wird "
                                 "geöffnet, offene Linie in zwei Linien geteilt")
        self.a_corner = A("Ecke", "corner", lambda: self.set_node_type(curves.CORNER),
                          tip="Ausgewählte Punkte zu spitzen Eckpunkten machen")
        self.a_curvept = A("Rundung", "curvept", lambda: self.set_node_type(curves.CURVE),
                           tip="Ausgewählte Punkte zu fließenden Rundungspunkten machen")
        self.a_auto = A("Rundungen\nerkennen", "autocurve", self.auto_curves,
                        tip="Eckige Konturen (z. B. digitalisiert) in wenige Ecken und Rundungen umwandeln")
        self.a_cut = A("Aus-\nschneiden", "cut", self.cut_selected,
                       tip="Obere ausgewählte Form aus der unteren herausschneiden (Loch)")
        self.a_tostitch = A("In Stiche\numwandeln", "stitchview", self.convert_to_stitches,
                            tip="Form/Schriftzug in feste Stiche umwandeln, um einzelne Sprünge "
                                "und Stiche von Hand zu bearbeiten")
        self.a_tosatin = A("In Säulen-\nSatin", "tosatin", self.line_to_satin,
                           tip="Linie in eine Satinsäule umwandeln (Breite wie der Satinrand bzw. 3 mm)")
        self.a_toline = A("In Linie\numwandeln", "toline", self.satin_to_line,
                          tip="Satinsäule in eine Linie entlang ihrer Mitte umwandeln")
        self.a_flip = A("Richtung\numkehren", "flip", self.reverse_direction,
                        tip="Linie bzw. Satinsäule von der anderen Seite her sticken")
        self.a_cutsatin = A("Satin\nteilen", "cutsatin", self.cut_satin,
                            tip="Satinsäule am gewählten Punktepaar in zwei Säulen teilen "
                                "(im Punkte-Werkzeug ein Paar wählen)")
        self.a_autosatin = A("Auto-\nSatin", "autosatin", self.auto_satin,
                             tip="Ausgewählte Satinsäulen/-linien in kürzester Reihenfolge und "
                                 "passender Richtung sticken, Verbindungen als Steppstich verdeckt "
                                 "unter den Säulen statt Sprüngen (wie Ink/Stitch »Auto-Satin«)")
        self.a_multisatin = A("Mehrfarbiger\nSatin", "multisatin", self.multicolor_satin,
                              tip="Satinsäule der Länge nach in Streifen mehrerer Farben teilen "
                                  "(wie Ink/Stitch »Satin multicolor«)")
        self.a_centerline = A("Mittel-\nlinie", "centerline", self.to_centerline,
                              tip="Mittellinie einer schmalen Fläche (z. B. digitalisierte Schrift) "
                                  "als Linie erzeugen – zum Sticken mit Stepp- oder Satinstich")
        self.a_outline_emb = A("Umriss aus\nStickdatei", "outline", self.outline_from_stitches,
                           tip="Aus einer importierten Stickdatei bearbeitbare Formen je Farbe "
                               "rekonstruieren (zum Neu-Digitalisieren)")
        self.a_knockdown = A("Knockdown", "knockdown", self.add_knockdown,
                             tip="Lockere Unterlagsfläche unter den ausgewählten Objekten – drückt "
                                 "Flor bei Frottee, Fleece oder Samt nieder")
        self.a_textpath = A("Text an\nPfad", "textpath", self.text_to_path,
                            tip="Schriftzug entlang einer Linie setzen: Schriftzug und Linie auswählen "
                                "(Umschalt+Klick) – geht mit Computer- und Stickschriften")
        self.a_guided = A("Geführte\nFüllung", "guided", self.assign_guide,
                          tip="Füllreihen folgen einer Führungslinie: Fläche(n) und eine Linie auswählen")
        self.a_detach = A("Pfad\nlösen", "detach", self.detach_path,
                          tip="Schriftzug vom Pfad lösen bzw. die Führungslinie einer geführten Füllung "
                              "wieder als Linie herauslösen")
        self.a_redwork = A("Redwork", "redwork", lambda: self.route_lines("redwork"),
                           tip="Ausgewählte Steppstichlinien ohne Sprung sticken: jede Strecke genau "
                               "zweimal (hin und zurück), Ende am Anfang")
        self.a_autoroute = A("Auto-\nRoute", "autoroute", lambda: self.route_lines("autoroute"),
                             tip="Ausgewählte Steppstichlinien als ein durchgehender Weg: jede Strecke "
                                 "einmal, nur wo nötig ein zweites Mal")
        self.a_startpt = A("Start-\npunkt", "startpt", lambda: self.pick_point("start"),
                           tip="Startpunkt der ausgewählten Fläche oder Satinsäule anklicken")
        self.a_endpt = A("End-\npunkt", "endpt", lambda: self.pick_point("end"),
                         tip="Endpunkt der ausgewählten Fläche oder Satinsäule anklicken")
        self.a_clearpts = A("Start/Ende\nentfernen", "delete", self.clear_points,
                            tip="Start- und Endpunkt der ausgewählten Objekte entfernen (automatisch)")
        self.a_density = A("Dichte\nprüfen", "density", self.toggle_density,
                           tip="Zu dicht gestickte Stellen anzeigen (gelb = dicht, rot = zu dicht)")
        self.a_density.setCheckable(True)
        self.a_mockup = A("Produkt-\nvorschau", "tshirt", self.open_mockup, "F7",
                          tip="Den Entwurf in Originalgröße auf T-Shirt, Kappe, Tasche, Handtuch, "
                              "Kissen oder Lätzchen ansehen – aktualisiert sich beim Weiterarbeiten")
        self.a_cutfile = A("Schneide-\ndatei", "cutfile", self.export_cutfile,
                           tip="Applikationsformen als SVG für Schneideplotter (Cricut, Brother "
                               "ScanNCut, Silhouette …) – der Stoff wird exakt passend zugeschnitten")
        self.a_multihoop = A("Mehrfach-\nRahmung", "multihoop", self.open_multihoop,
                             tip="Design größer als der Rahmen: in überlappende Rahmungen mit "
                                 "Passmarken teilen und jeden Teil als Stickdatei ausgeben")
        self.a_multiexport = A("Mehrfach-\nExport", "multiexport", self.multi_export,
                               tip="In mehrere Formate auf einmal exportieren – auch als Namensliste "
                                   "(eine Datei je Name)")
        self.a_puff = A("3D-Puff", "puff", self.puff_selected,
                        tip="Ausgewählte Objekte für 3D-Puff (Schaumstoff) einrichten: dichter "
                            "Satin ohne Unterlage, Endkappen, Maschinenstopp zum Auflegen des "
                            "Schaumstoffs, Puff-Objekte zuletzt")
        self.a_overlap = A("Überlappung\nentfernen", "overlap", self.remove_overlaps,
                           tip="Flächen, die von später gestickten Objekten verdeckt werden, nicht "
                               "doppelt sticken (wie »Remove overlaps« in Wilcom/Hatch) – weniger "
                               "Stiche, weichere und flachere Stickerei. Ein schmaler Rand bleibt "
                               "überlappend, damit keine Lücken entstehen.")
        self.a_knockout = A("Automatisch\naussparen", "knockout", self.toggle_knockout,
                            checkable=True,
                            tip="Was später gestickte Objekte verdecken, wird darunter beim "
                                "Berechnen der Stiche ausgespart – live: die Aussparung wandert "
                                "beim Verschieben mit und verschwindet beim Wegschieben. Die Formen "
                                "selbst bleiben unverändert, ein Rand folgt weiter der Kontur. "
                                "Pfeil: Überlappung einstellen; je Objekt abschaltbar (Eigenschaften "
                                "› Füllstich).")
        self.a_cleanup = A("Kleinteile\nentfernen", "cleanup", self.cleanup_small,
                           tip="Winzige Flächenstücke, Löcher und Linien entfernen (z. B. nach dem "
                               "Digitalisieren) – sie ergeben nur Sprünge und Fadensalat")
        self.a_simplify = A("Punkte\nreduzieren", "simplify", self.simplify_selected,
                            tip="Weniger Punkte – macht das Bearbeiten übersichtlicher")
        self.a_text = A("Schriftzug", "text", lambda: self.set_tool("text"))
        self.a_export = A("Für Maschine\nexportieren", "export", self.export_design, "Ctrl+E")
        self.a_png = A("Als Bild\nspeichern", "png", self.export_png)
        self.a_sheet = A("Arbeitsblatt\n(PDF)", "sheet", self.export_worksheet, "Ctrl+P",
                         tip="Arbeitsblatt mit Vorschau, Farbfolge und 1:1-Schablone als PDF")
        # Simulator und Optimierer sind ein Fenster – F6 bleibt als zweites Tastenkürzel
        self.a_optimizer = A("Simulator &\nOptimierer", "play", self.simulate, "F6")
        self.a_colorsort = A("Farben zusam-\nmenfassen", "colorsort", self.toggle_colorsort,
                             checkable=True,
                             tip="Gleiche Garnfarben nacheinander sticken (weniger Farbwechsel); "
                                 "Überlappungen behalten ihre Reihenfolge")
        self.a_optjumps = A("Sprungstiche\noptimieren", "jumps", self.optimize_jumps,
                            tip="Importierte Stickdateien mit möglichst wenigen Sprüngen und "
                                "Fadenschnitten neu ordnen (Verbindungen unter späteren Stichen)")
        self.a_sim = A("Simulator &\nOptimierer", "play", self.simulate, "F5",
                       tip="Realistische Sticksimulation mit nummerierten Sprüngen – Reihenfolge, "
                           "Fadenschnitte und Verbindungen direkt bearbeiten, automatisch optimieren "
                           "(auch F6)")
        self.a_zin = A("Vergrößern", "zoomin", lambda: self.canvas.zoom_by(1.25), "Ctrl++")
        self.a_zout = A("Verkleinern", "zoomout", lambda: self.canvas.zoom_by(0.8), "Ctrl+-")
        self.a_fit = A("Rahmen\neinpassen", "fit", self.fit_hoop, "Ctrl+0")
        self.a_real = A("Realistisch", "realview", lambda: self.set_mode("real"), checkable=True)
        self.a_rulers = A("Lineal", "ruler", self.toggle_rulers, checkable=True,
                          tip="Lineale oben und links ein-/ausblenden (mm ab Rahmenmitte)")
        self.a_stitch = A("Stich-\nansicht", "stitchview", lambda: self.set_mode("stitch"), checkable=True)
        g = QActionGroup(self)
        g.addAction(self.a_real)
        g.addAction(self.a_stitch)
        (self.a_stitch if self.opts.mode == "stitch" else self.a_real).setChecked(True)
        self.a_jumps = A("Sprünge\nzeigen", "jumps", self.toggle_jumps, checkable=True)
        self.a_grid = A("Raster", "grid", self.toggle_grid, checkable=True)
        self.a_grid.setChecked(self.opts.show_grid)
        self.a_settings = A("Einstel-\nlungen", "gear", self.open_settings, "Ctrl+,")
        self.a_ui = A("Oberfläche\nanpassen", "layout", lambda: self.open_settings("Oberfläche"),
                      tip="Farbschema (hell/dunkel), Schriftgröße, Menüband, Lage von Werkzeugleiste "
                          "und Seitenleiste sowie einen eigenen Favoriten-Reiter einstellen")
        self.a_keys = A("Tasten-\nkürzel", "keyboard", self.show_shortcuts, "F1")
        self.a_guide = A("Kurz-\nanleitung", "help", self.show_guide)
        self.a_manual = A("Anleitung\n(PDF)", "pdf", self.show_manual,
                          tip="Ausführliche Funktionsanleitung mit Bildern und Beispielen öffnen")
        self.a_about = A("Über\nStichWizard", "info", self.show_about)
        self.a_update = A("Nach Updates\nsuchen", "import", self.check_updates,
                          tip="Bei GitHub nachsehen, ob es eine neuere StichWizard-Version gibt "
                              "(installiert nichts selbst)")
        self.a_mcp = A("KI-Anbindung\n(MCP)", "ai", self.show_mcp,
                       tip="KI-Assistenten wie Claude per MCP mit StichWizard verbinden")
        self.a_info = A("Design-\nInfo", "info", lambda: self.side.setCurrentWidget(self.seq))
        # Pfeiltasten & Entf nur auf der Arbeitsfläche
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            for mod, f in (("", 1), ("Shift+", 10)):
                a = QAction(self)
                a.setShortcut(QKeySequence(mod + key))
                a.setShortcutContext(Qt.WidgetShortcut)
                a.triggered.connect(lambda _=False, dx=dx * f, dy=dy * f: self.nudge(dx, dy))
                self.canvas.addAction(a)
        self.a_del.setShortcutContext(Qt.WidgetShortcut)
        self.canvas.addAction(self.a_del)
        self.a_addnode.setShortcutContext(Qt.WidgetShortcut)
        self.canvas.addAction(self.a_addnode)
        # Werkzeuge
        self.tool_group = QActionGroup(self)
        self.tool_actions = {}
        for key, label, ic, sc in (("select", "Auswählen", "select", "V"),
                                   ("rect", "Rechteck", "rect", "R"),
                                   ("ellipse", "Ellipse / Kreis", "ellipse", "E"),
                                   ("polygon", "Vieleck (Klicks, Doppelklick beendet)", "polygon", "P"),
                                   ("line", "Linie (Klicks, Doppelklick beendet)", "line", "L"),
                                   ("pen", "Bézier-Stift: Klick = Ecke, Klicken+Ziehen = Kurve mit "
                                           "Anfassern, Klick auf den Start = schließen, Enter = "
                                           "offene Linie", "pen", "B"),
                                   ("freehand", "Freihand-Linie", "freehand", "F"),
                                   ("sketch", "Sketch: frei mit Stichen zeichnen (Stil im Menüband "
                                              "unter Verzieren)", "sketch", "D"),
                                   ("text", "Schriftzug", "text", "T"),
                                   ("nodes", "Punkte bearbeiten", "nodes", "N"),
                                   ("connect", "Zwei Punkte mit einer Linie verbinden", "connectline", "K"),
                                   ("eraser", "Radierer: über Formen wischen ([ / ] = Größe)", "eraser", "X"),
                                   ("jumps", "Sprünge & Fadenschnitte bearbeiten", "jumps", "J"),
                                   ("measure", "Messen: Abstand und Winkel ziehen (Umschalt = 45°)",
                                    "measure", "M"),
                                   ("satin", "Säulen-Satin (abwechselnd links/rechts klicken)", "satin", "S")):
            a = QAction(tool_icon(ic), label, self)
            a.setProperty("tool_icon", ic)
            a.setCheckable(True)
            a.setShortcut(QKeySequence(sc))
            a.setToolTip(f"{label}  ({sc})")
            a.triggered.connect(lambda _=False, k=key: self.set_tool(k))
            self.tool_group.addAction(a)
            self.tool_actions[key] = a
            self.addAction(a)
        self.tool_actions["select"].setChecked(True)

    def _make_header(self):
        f = QFrame()
        f.setObjectName("header")
        h = QHBoxLayout(f)
        h.setContentsMargins(12, 6, 12, 2)
        logo_ic = QLabel()
        logo_ic.setPixmap(icons.app_logo(30))
        h.addWidget(logo_ic)
        l1 = QLabel("Stich")
        l1.setObjectName("logo")
        l2 = QLabel("Wizard")
        l2.setObjectName("logoAccent")
        name = QHBoxLayout()                 # »Stich« und »Wizard« ohne Lücke
        name.setSpacing(0)
        name.addWidget(l1)
        name.addWidget(l2)
        h.addLayout(name)
        h.addSpacing(20)
        for a, name in ((self.a_save, "save"), (self.a_undo, "undo"), (self.a_redo, "redo")):
            b = QToolButton()
            b.setObjectName("quick")
            b.setProperty("head_icon", name)
            b.setIcon(icons.icon(name, "#FFFFFF", "#3FD0C9"))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(a.toolTip().replace("\n", ""))
            b.clicked.connect(a.trigger)
            h.addWidget(b)
        h.addStretch()
        self.doc_title = QLabel()
        self.doc_title.setObjectName("docTitle")
        h.addWidget(self.doc_title)
        h.addStretch()
        for a, name in ((self.a_keys, "keyboard"), (self.a_settings, "gear")):
            b = QToolButton()
            b.setObjectName("quick")
            b.setProperty("head_icon", name)
            b.setIcon(icons.icon(name, "#FFFFFF", "#3FD0C9"))
            b.setIconSize(QSize(20, 20))
            b.setToolTip(a.toolTip().replace("\n", ""))
            b.clicked.connect(a.trigger)
            h.addWidget(b)
        return f

    def _rbtn(self, action, big=True):
        b = RibbonButton()
        b.setObjectName("ribbonBtn")
        b.setDefaultAction(action)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(28, 28) if big else QSize(20, 20))
        return b

    def _group(self, title, widgets):
        g = QWidget()
        v = QVBoxLayout(g)
        v.setContentsMargins(4, 4, 4, 2)
        v.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(2)
        for w in widgets:
            row.addWidget(w)
        v.addLayout(row, 1)
        if title:
            lab = QLabel(title)
            lab.setObjectName("groupLabel")
            lab.setAlignment(Qt.AlignCenter)
            v.addWidget(lab)
        return g

    def _page(self, groups):
        p = QWidget()
        p.setObjectName("ribbonPage")
        h = QHBoxLayout(p)
        h.setContentsMargins(8, 2, 8, 2)
        h.setSpacing(4)
        for i, g in enumerate(groups):
            if i:
                sep = QFrame()
                sep.setObjectName("groupSep")
                h.addWidget(sep)
            h.addWidget(g)
        h.addStretch()
        # passt der Reiter nicht ins Fenster, lässt er sich seitlich verschieben (auch per Mausrad)
        sa = QScrollArea()
        sa.setObjectName("ribbonScroll")
        sa.setWidget(p)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        return sa

    def _make_ribbon(self):
        r = QTabWidget()
        self.ribbon = r
        r.setObjectName("ribbon")
        r.setFixedHeight(138)
        B = self._rbtn
        self.a_merge.setToolTip("Formen zu einer verbinden (Inkscape: Vereinigung)  (Strg+G)")
        self.a_cut.setToolTip("Obere Form aus der unteren herausschneiden (Inkscape: Differenz)")
        # Hoop / Stoff
        self.hoop_combo = QComboBox()
        self.hoop_combo.setToolTip("Stickrahmen – ganz unten »Eigener Rahmen …« für eine "
                                   "eigene Größe")
        self.hoop_combo.setMaxVisibleItems(24)
        self._fill_hoop_combo()
        self.hoop_combo.currentIndexChanged.connect(self._hoop_chosen)
        self.fabric_combo = QComboBox()
        for name, col in FABRICS:
            self.fabric_combo.addItem(icons.swatch(col, 16), name, col)
        self.fabric_combo.currentIndexChanged.connect(
            lambda i: self.set_fabric(self.fabric_combo.itemData(i)))
        self.fabtype_combo = QComboBox()
        for key, p in engine.FABRIC_PROFILES.items():
            self.fabtype_combo.addItem(p["name"], key)
            self.fabtype_combo.setItemData(self.fabtype_combo.count() - 1, p["hint"], Qt.ToolTipRole)
        self.fabtype_combo.setToolTip("Stoffart: passt Dichte, Zugausgleich und Unterlage aller "
                                      "Objekte an den Stoff an (wie in Profi-Sticksoftware)")
        self.fabtype_combo.currentIndexChanged.connect(
            lambda i: self.set_fabric_type(self.fabtype_combo.itemData(i)))
        for cb in (self.hoop_combo, self.fabric_combo, self.fabtype_combo):
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(10)
            cb.view().setMinimumWidth(260)
            cb.setFixedHeight(26)
        hoop_box = QWidget()
        hv = QVBoxLayout(hoop_box)
        hv.setContentsMargins(0, 2, 0, 0)
        hv.setSpacing(1)
        for lab, w in (("Rahmen", self.hoop_combo), ("Farbe", self.fabric_combo),
                       ("Stoffart", self.fabtype_combo)):
            row = QHBoxLayout()
            l = QLabel(lab)
            l.setFixedWidth(50)
            row.addWidget(l)
            row.addWidget(w)
            hv.addLayout(row)

        r.addTab(self._page([
            self._group("Datei", [B(self.a_new), B(self.a_open), B(self.a_import), B(self.a_vector),
                                  B(self.a_browser), B(self.a_save), B(self.a_saveas)]),
            self._group("Bearbeiten", [B(self.a_undo), B(self.a_redo), B(self.a_dup), B(self.a_del)]),
            self._group("", [hoop_box]),       # Felder sind beschriftet – kein Gruppentitel
        ]), "Start")

        shape_btns = []
        for key, label in (("rect", "Rechteck"), ("ellipse", "Ellipse"), ("polygon", "Vieleck")):
            shape_btns.append(B(self.tool_actions[key]))
        motif_btn = QToolButton()
        motif_btn.setObjectName("ribbonBtn")
        motif_btn.setText("Motive")
        motif_btn.setIcon(icons.icon("fabric"))
        motif_btn.setIconSize(QSize(30, 30))
        motif_btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        motif_btn.setPopupMode(QToolButton.InstantPopup)
        mm = QMenu(motif_btn)
        for name, _ in MOTIFS:
            mm.addAction(name, lambda n=name: self.add_motif(n))
        motif_btn.setMenu(mm)
        shape_btns.append(motif_btn)
        for b in shape_btns[:3]:
            b.defaultAction().setIconText(b.defaultAction().text().split(" (")[0].split(" /")[0])
        self.tool_actions["satin"].setIconText("Säulen-\nSatin")
        line_btns = [B(self.tool_actions["pen"]), B(self.tool_actions["line"]),
                     B(self.tool_actions["freehand"]), B(self.tool_actions["satin"])]
        self.tool_actions["pen"].setIconText("Bézier-\nStift")
        self.tool_actions["line"].setIconText("Linie")
        self.tool_actions["freehand"].setIconText("Freihand")
        self.tool_actions["text"].setIconText("Schriftzug")
        # Erstellen: neue Objekte zeichnen oder automatisch erzeugen
        r.addTab(self._page([
            self._group("Formen", shape_btns[:3] + [B(self.a_star)] + shape_btns[3:]),
            self._group("Linien", line_btns + [B(self.a_spiral)]),
            self._group("Automatisch", [B(self.a_digit), B(self.a_photo), B(self.a_outline_emb)]),
            self._group("Vorlagen & Bibliothek", [B(self.a_templates), B(self.a_ith),
                                                  B(self.a_library), B(self.a_libsave)]),
        ]), "Erstellen")

        # Verzieren: Wiederholungen, Rahmen und Schnörkel, Strass (wie »Embellish«/»Encore«)
        r.addTab(self._page([
            self._group("Wiederholen", [B(self.a_encore)]),
            self._group("Muster", [B(self.a_spiro), B(self.a_wordsculpt)]),
            self._group("Kreuzstich", [B(self.a_cross)]),
            self._group("Assistenten", [B(self.a_quilt), B(self.a_family)]),
            self._group("Zeichnen & Malen", [self._sketch_btn(), B(self.a_paint),
                                             B(self.a_printsheet)]),
            self._group("Rahmen", [B(self.a_ornaments)]),
            self._group("Strass & Perlen", [B(self.a_stones), B(self.a_stones_export)]),
        ]), "Verzieren")

        # Schrift: alles rund um Schriftzüge (wie »Lettering« in Profiprogrammen)
        r.addTab(self._page([
            self._group("Text", [B(self.tool_actions["text"]), B(self.a_textpath),
                                 B(self.a_detach),
                                 self._menu_btn("Hüllform", "envelope", self.envelope_menu()),
                                 B(self.a_shadow), B(self.a_wordsculpt)]),
            self._group("Umwandeln", [B(self.a_convert), B(self.a_centerline)]),
            self._group("Eigene Schriften", [B(self.a_fontshop)]),
        ]), "Schrift")

        # Vorlage zum Nachzeichnen
        self.tpl_opacity = QSlider(Qt.Horizontal)
        self.tpl_opacity.setRange(10, 100)
        self.tpl_opacity.setFixedWidth(110)
        self.tpl_width = QDoubleSpinBox()
        self.tpl_width.setRange(5, 600)
        self.tpl_width.setSuffix(" mm")
        self.tpl_width.setKeyboardTracking(False)
        self.tpl_width.setFixedWidth(110)
        self.tpl_show = QCheckBox("Anzeigen")
        self.tpl_lock = QCheckBox("Fixiert")
        self.tpl_lock.setToolTip("Abhaken, um die Vorlage mit der Maus zu verschieben")
        tpl_box = QWidget()
        tv = QVBoxLayout(tpl_box)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(4)
        for lab, w, cb in (("Deckkraft", self.tpl_opacity, self.tpl_show),
                           ("Breite", self.tpl_width, self.tpl_lock)):
            row = QHBoxLayout()
            l = QLabel(lab)
            l.setFixedWidth(64)
            row.addWidget(l)
            row.addWidget(w)
            row.addSpacing(8)
            row.addWidget(cb)
            tv.addLayout(row)
        self.tpl_controls = [self.tpl_opacity, self.tpl_width, self.tpl_show, self.tpl_lock]
        self.tpl_opacity.valueChanged.connect(self.template_changed)
        self.tpl_width.valueChanged.connect(self.template_changed)
        self.tpl_show.toggled.connect(self.template_changed)
        self.tpl_lock.toggled.connect(self.template_changed)
        r.addTab(self._page([
            self._group("Bild als Vorlage", [B(self.a_tpl), B(self.a_tpl_del), B(self.a_pipette),
                                             B(self.a_trace)]),
            self._group("Vorlage einstellen", [tpl_box]),
            self._group("Nachzeichnen mit", [B(self.tool_actions["polygon"]), B(self.tool_actions["satin"]),
                                             B(self.tool_actions["line"]),
                                             B(self.tool_actions["freehand"])]),
            self._group("So geht's", [self._hint_label(
                "Links = Ecke · Rechts = Rundung\n"
                "Startpunkt / Enter = fertig\n"
                "Strg beim Schließen = Loch")]),
            self._group("Nacharbeiten", [B(self.a_auto), B(self.tool_actions["nodes"])]),
        ]), "Nachzeichnen")

        for key, label in (("nodes", "Punkte\nbearbeiten"), ("eraser", "Radierer"),
                           ("jumps", "Sprünge\nbearbeiten"), ("connect", "Mit Linie\nverbinden")):
            self.tool_actions[key].setIconText(label)
        # Bearbeiten: die Kontur eines einzelnen Objekts formen
        r.addTab(self._page([
            self._group("Werkzeuge", [B(self.tool_actions["nodes"]), B(self.tool_actions["connect"]),
                                      self._eraser_btn()]),
            self._group("Punkte", [B(self.a_addnode), B(self.a_joinnode), B(self.a_breaknode),
                                   B(self.a_corner), B(self.a_curvept), B(self.a_auto),
                                   B(self.a_simplify)]),
            self._group("Versatz", [B(self.a_grow), B(self.a_shrink), B(self.a_outline),
                                    B(self.a_shadow)]),
            self._group("Kopien", [B(self.a_copygrid), B(self.a_copycircle)]),
        ]), "Form bearbeiten")

        # Anordnen: mehrere Objekte zueinander (Gruppen, Pfade, Lage, Ebenen)
        r.addTab(self._page([
            self._group("Gruppe", [B(self.a_group), B(self.a_ungroup)]),
            self._group("Pfad-Operationen", [B(self.a_merge), B(self.a_cut), B(self.a_intersect),
                                             B(self.a_exclude), B(self.a_divide), B(self.a_split)]),
            self._group("Ausrichten", [self._menu_btn("Ausrichten", "align", self.align_menu()),
                                       self._menu_btn("Verteilen", "distribute",
                                                      self.distribute_menu()),
                                       B(self.a_center), B(self.a_mh), B(self.a_mv)]),
            self._group("Ebenen", [B(self.a_layers), B(self.a_newlayer), B(self.a_lock),
                                   B(self.a_unlock)]),
        ]), "Anordnen")

        # Sticken: Stichart-spezifische Werkzeuge (Satin, Linien, Füllung, Effekte)
        r.addTab(self._page([
            self._group("Satin", [B(self.a_tosatin), B(self.a_toline), B(self.a_flip),
                                  B(self.a_cutsatin), B(self.a_autosatin), B(self.a_multisatin)]),
            self._group("Linien führen", [B(self.a_redwork), B(self.a_autoroute)]),
            self._group("Füllung", [B(self.a_guided)]),
            self._group("Effekte", [B(self.a_puff), B(self.a_knockdown)]),
            self._group("Start & Ende", [B(self.a_startpt), B(self.a_endpt), B(self.a_clearpts)]),
        ]), "Sticken")

        # Optimieren: Stickreihenfolge, Sprünge und Prüfen vor dem Export
        r.addTab(self._page([
            self._group("Verbessern", [B(self.a_overlap), self._knockout_btn(),
                                       B(self.a_cleanup)]),
            self._group("Reihenfolge", [B(self.a_up), B(self.a_down), B(self.a_colorsort)]),
            self._group("Sprünge", [B(self.a_optjumps), B(self.tool_actions["jumps"]),
                                    B(self.a_tostitch)]),
            self._group("Stiche", [B(self.a_stitchedit)]),
            self._group("Prüfen", [B(self.a_sim), B(self.a_density)]),
        ]), "Optimieren")

        r.addTab(self._page([
            self._group("Messen", [B(self.a_rulers), B(self.tool_actions["measure"])]),
            self._group("Darstellung", [B(self.a_real), B(self.a_stitch), B(self.a_jumps),
                                        self._grid_btn()]),
            self._group("Zoom", [B(self.a_zin), B(self.a_zout), B(self.a_fit)]),
            self._group("Vorschau", [B(self.a_mockup)]),
            self._group("Oberfläche", [self._theme_btn(), B(self.a_ui)]),
        ]), "Ansicht")

        exp_btn = B(self.a_export)
        r.addTab(self._page([
            self._group("Maschine", [self._machine_btn(), B(self.a_send), exp_btn,
                                     B(self.a_multiexport), B(self.a_multihoop)]),
            self._group("Drucken & Bild", [B(self.a_sheet), B(self.a_png), B(self.a_mockup),
                                           B(self.a_cutfile), B(self.a_stones_export),
                                           B(self.a_ith_pdf), B(self.a_printsheet),
                                           B(self.a_video)]),
            self._group("Information", [B(self.a_info)]),
        ]), "Export")
        r.addTab(self._page([
            self._group("Hilfe", [B(self.a_keys), B(self.a_guide), B(self.a_manual)]),
            self._group("KI", [B(self.a_mcp)]),
            self._group("Programm", [B(self.a_settings), B(self.a_update), B(self.a_about)]),
        ]), "Hilfe")
        r.setCurrentIndex(0)
        return r

    # ------------------------------------------------------------ Maschinenprofil
    def machine(self):
        from . import machines
        return machines.get(self.prefs.get("machine"), self.prefs.get("custom_machines"))

    def _machine_btn(self):
        b = QToolButton()
        b.setObjectName("ribbonBtn")
        b.setText("Stick-\nmaschine")
        b.setIcon(icons.icon("machine"))
        b.setProperty("icon_name", "machine")
        b.setIconSize(QSize(28, 28))
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setPopupMode(QToolButton.InstantPopup)
        b.setToolTip("Stickmaschine wählen: stellt Rahmen, Exportformat, Tempo, Stopps und "
                     "Nadelempfehlung passend ein")
        m = QMenu(b)
        m.aboutToShow.connect(lambda: self._fill_machine_menu(m))
        b.setMenu(m)
        self.machine_btn = b
        return b

    def _fill_machine_menu(self, m):
        from . import machines
        m.clear()
        cur = self.prefs.get("machine")
        grp = QActionGroup(m)
        a = m.addAction("Keine Maschine gewählt", lambda: self.set_machine(machines.NEUTRAL))
        a.setCheckable(True)
        a.setChecked(cur in (None, "", machines.NEUTRAL))
        grp.addAction(a)
        m.addSeparator()
        for mc in machines.all_machines(self.prefs.get("custom_machines")):
            label = f"{mc['name']}  ·  {mc['needles']} Nadel{'n' if mc['needles'] > 1 else ''}, " \
                    f"{mc['field'][0]:g} × {mc['field'][1]:g} mm"
            a = m.addAction(label, lambda k=mc["id"]: self.set_machine(k))
            a.setCheckable(True)
            a.setChecked(cur == mc["id"])
            grp.addAction(a)
        m.addSeparator()
        m.addAction("Eigene Maschine anlegen …", self.add_custom_machine)
        if self.prefs.get("custom_machines"):
            m.addAction("Eigene Maschine löschen …", self.delete_custom_machine)
        m.addSeparator()
        m.addAction("Maschinen-Info und Nadel …", self.show_machine_info)

    def _update_machine_label(self):
        mc = self.machine()
        self.lbl_machine.setText(f"⚙ {mc['name']}" if mc else "")
        self.lbl_machine.setVisible(bool(mc))

    def set_machine(self, machine_id, apply_hoop=True):
        """Maschinenprofil wählen und alles Passende einstellen."""
        from . import machines, model
        from .threads import hoop_for_size, custom_hoops
        self.prefs.set("machine", machine_id)
        mc = self.machine()
        engine.EXPLICIT_STOPS = bool(mc and mc.get("auto_color"))
        self._update_machine_label()
        if not mc:
            self.rebuild(list(self.doc.objects))
            self.commit()
            self.lbl_tip.setText("Keine Maschine gewählt – Standardeinstellungen.")
            return
        # Rahmen der Maschine in die Liste, Standardrahmen wählen
        for name, w, h in mc.get("hoops", []):
            try:
                hoop_for_size(w, h, name)
            except ValueError:
                pass
        self.prefs.set("custom_hoops", custom_hoops())
        self._fill_hoop_combo()
        if apply_hoop and mc.get("default_hoop"):
            i = hoop_for_size(*mc["default_hoop"])
            self.prefs.set("hoop", i)
            if not self.doc.objects:
                self.set_hoop(i)
        # Exportformat und Tempo für die Zeitschätzung
        self.prefs.set("export_format", mc["format"])
        self.prefs.set("speed", int(mc["speed"]))
        model.STITCHES_PER_MINUTE = int(mc["speed"])
        self.rebuild(list(self.doc.objects))
        self.commit()
        parts = [f"Maschine: {mc['name']}", f"Format {mc['format'].upper()}",
                 f"Tempo {mc['speed']} Stiche/min (Zeitschätzung)",
                 f"Nadel {machines.needle_for(mc, self.doc.fabric_type)}"]
        if mc.get("auto_color"):
            parts.append("Stopps (Applikation, Puff) werden ausdrücklich in die Datei geschrieben")
        self.lbl_tip.setText(" · ".join(parts) + ".")

    def add_custom_machine(self):
        from .controls import ask_values
        from .fileio import EXPORT_FORMATS
        import re
        v = ask_values(self, "Eigene Stickmaschine", [
            ("name", "Name", "text", "Meine Maschine"),
            ("needles", "Nadeln", "int", 1, 20, 1),
            ("w", "Stickfeld Breite", "num", 50.0, 1500.0, 1.0, 0, " mm", 260.0),
            ("h", "Stickfeld Höhe", "num", 50.0, 1500.0, 1.0, 0, " mm", 160.0),
            ("format", "Dateiformat", "choice",
             [(label, ext) for label, ext in EXPORT_FORMATS if ext not in ("zip", "svg")], "dst"),
            ("speed", "Tempo (für die Stickzeit)", "int", 200, 1500, 700),
            ("system", "Nadelsystem", "editcombo",
             ["DBxK5", "130/705 H-E (Sticknadel)", "laut Handbuch"], "DBxK5"),
            ("auto", "Wechselt die Farben selbst (Mehrnadel)", "check", True)],
            "Die Angaben stehen im Handbuch deiner Maschine. Mehrnadel-Maschinen halten beim "
            "Farbwechsel nicht an – StichWizard schreibt dann nötige Stopps ausdrücklich in die Datei.")
        if not v or not str(v["name"]).strip():
            return
        name = str(v["name"]).strip()
        mid = "custom_" + (re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "maschine")
        lst = [m for m in self.prefs.get("custom_machines") if m.get("id") != mid]
        lst.append(dict(id=mid, name=name, needles=int(v["needles"]),
                        field=[float(v["w"]), float(v["h"])], hoops=[], default_hoop=None,
                        format=v["format"], speed_max=int(v["speed"]), speed=int(v["speed"]),
                        needle_system=str(v["system"]), auto_color=bool(v["auto"]) and
                        int(v["needles"]) > 1, trimmer=True, note="Eigene Maschine."))
        self.prefs.set("custom_machines", lst)
        self.set_machine(mid)

    def delete_custom_machine(self):
        from .controls import ask_values
        from . import machines
        lst = self.prefs.get("custom_machines")
        if not lst:
            return
        v = ask_values(self, "Eigene Maschine löschen", [
            ("id", "Maschine", "choice", [(m["name"], m["id"]) for m in lst], lst[0]["id"])])
        if not v:
            return
        self.prefs.set("custom_machines", [m for m in lst if m["id"] != v["id"]])
        if self.prefs.get("machine") == v["id"]:
            self.set_machine(machines.NEUTRAL)

    def show_machine_info(self):
        from . import machines
        mc = self.machine()
        if not mc:
            QMessageBox.information(self, APP, "Noch keine Stickmaschine gewählt – unter "
                                    "Export › Stickmaschine eine auswählen.")
            return
        needle = machines.needle_for(mc, self.doc.fabric_type)
        fab = engine.FABRIC_PROFILES.get(self.doc.fabric_type, {}).get("name", "")
        w, h = self.doc.hoop_size
        fw, fh = mc["field"]
        fits = (w <= fw and h <= fh) or (w <= fh and h <= fw)
        QMessageBox.information(self, APP, (
            f"<h3>{mc['name']}</h3>"
            f"<p>{mc.get('note', '')}</p><table>"
            f"<tr><td>Nadeln</td><td><b>{mc['needles']}</b></td></tr>"
            f"<tr><td>Stickfeld</td><td><b>{fw:g} × {fh:g} mm</b></td></tr>"
            f"<tr><td>Format</td><td><b>{mc['format'].upper()}</b></td></tr>"
            f"<tr><td>Tempo</td><td><b>bis {mc['speed_max']} Stiche/min</b> "
            f"(Zeitschätzung mit {mc['speed']})</td></tr>"
            f"<tr><td>Nadelsystem</td><td><b>{mc['needle_system']}</b></td></tr>"
            f"<tr><td>Nadel für {fab}</td><td><b>{needle}</b></td></tr>"
            f"<tr><td>Farbwechsel</td><td><b>{'automatisch' if mc.get('auto_color') else 'von Hand (Maschine hält an)'}</b></td></tr>"
            f"<tr><td>Rahmen {w:g} × {h:g} mm</td><td><b>{'passt' if fits else 'GRÖSSER als das Stickfeld!'}</b></td></tr>"
            "</table><p><small>Angaben laut Hersteller/Händler – bitte mit dem Handbuch "
            "abgleichen.</small></p>"))

    ERASER_SIZES = (0.5, 1, 2, 3, 5, 8, 12, 20)

    def _eraser_btn(self):
        """Radierer: Klick schaltet das Werkzeug ein, der Pfeil wählt Größe bzw. Lasso."""
        b = self._rbtn(self.tool_actions["eraser"])
        b.setPopupMode(QToolButton.MenuButtonPopup)
        m = QMenu(self)
        m.aboutToShow.connect(lambda: self._fill_eraser_menu(m))
        b.setMenu(m)
        return b

    def _fill_eraser_menu(self, m):
        m.clear()
        cur = self.canvas.eraser_size
        for mm in self.ERASER_SIZES:
            a = m.addAction(f"Pinsel {mm:g} mm", lambda v=mm: self.set_eraser(v, False))
            a.setCheckable(True)
            a.setChecked(not self.canvas.eraser_lasso and abs(cur - mm) < 1e-6)
        m.addSeparator()
        a = m.addAction("Lasso: Bereich umfahren", lambda: self.set_eraser(None, True))
        a.setCheckable(True)
        a.setChecked(self.canvas.eraser_lasso)

    def set_eraser(self, size=None, lasso=False):
        self.canvas.eraser_lasso = bool(lasso)
        if size is not None:
            self.canvas.set_eraser_size(size)
        self.set_tool("eraser")

    def _eraser_size_changed(self, mm):
        self.settings.setValue("eraserSize", mm)
        if self.canvas.tool == "eraser":
            self.lbl_tip.setText(self._eraser_tip())

    def _eraser_tip(self):
        if self.canvas.eraser_lasso:
            return ("Radierer (Lasso): Bereich umfahren, der weggeschnitten werden soll · "
                    "Pinsel-Radierer über den Pfeil am Knopf")
        return (f"Radierer {self.canvas.eraser_size:g} mm: mit gedrückter Maustaste über die Form "
                "wischen · [ / ] = kleiner/größer · Umschalt+Ziehen = Bereich umfahren (Lasso) · "
                "wirkt auf die ausgewählten Formen, sonst auf alle darunter")

    def _sketch_btn(self):
        """Sketch: Klick schaltet das Werkzeug ein, der Pfeil wählt den Stil."""
        b = self._rbtn(self.tool_actions["sketch"])
        self.tool_actions["sketch"].setIconText("Sketch")
        b.setPopupMode(QToolButton.MenuButtonPopup)
        b.setMenu(self.sketch_menu())
        return b

    def _menu_btn(self, text, icon_name, menu):
        b = QToolButton()
        b.setObjectName("ribbonBtn")
        b.setText(text)
        b.setIcon(icons.icon(icon_name))
        b.setProperty("icon_name", icon_name)
        b.setIconSize(QSize(28, 28))
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setPopupMode(QToolButton.InstantPopup)
        b.setMenu(menu)
        return b

    def envelope_menu(self):
        from .textfx import ENVELOPES
        m = QMenu(self)
        for key, label, tip in ENVELOPES:
            a = m.addAction(label, lambda k=key: self.set_envelope(k))
            a.setToolTip(tip)
        m.setToolTipsVisible(True)
        return m

    def set_envelope(self, key):
        """Hüllform für die gewählten Schriftzüge setzen (Stärke rechts in den Eigenschaften)."""
        texts = [o for o in self.selected_objects() if o.kind == "text"]
        if not texts:
            self.lbl_tip.setText("Hüllform: zuerst einen Schriftzug auswählen.")
            return
        for o in texts:
            amt = o.text.get("env_amount", 0.3) if o.text.get("env", "none") != "none" else 0.35
            o.text = dict(o.text, env=key, env_amount=amt)
        self.rebuild(texts)
        self.commit()
        self.props.refresh()
        from .textfx import ENVELOPES
        name = next(l for k, l, _ in ENVELOPES if k == key)
        self.lbl_tip.setText(f"Hüllform »{name}« – Stärke rechts unter »Schriftzug« einstellen."
                             if key != "none" else "Hüllform entfernt.")

    def align_menu(self):
        from . import design
        m = QMenu(self)
        for key, label in design.ALIGN_MODES:
            m.addAction(label, lambda k=key: self.align_selected(k))
        m.addSeparator()
        ref = m.addMenu("Bezug")
        grp = QActionGroup(m)
        for key, label in (("selection", "Auswahl (äußere Kanten)"), ("hoop", "Stickrahmen")):
            a = ref.addAction(label, lambda k=key: self.set_align_ref(k))
            a.setCheckable(True)
            a.setChecked(key == "selection")
            grp.addAction(a)
        return m

    def distribute_menu(self):
        m = QMenu(self)
        m.addAction("Waagerecht gleichmäßig verteilen", lambda: self.distribute_selected("x"))
        m.addAction("Senkrecht gleichmäßig verteilen", lambda: self.distribute_selected("y"))
        return m

    def _knockout_btn(self):
        """Knopf »Automatisch aussparen«: Klick = ein/aus, Pfeil = Überlappung einstellen."""
        b = self._rbtn(self.a_knockout)
        b.setPopupMode(QToolButton.MenuButtonPopup)
        m = QMenu(b)
        self.a_knockout.setIconVisibleInMenu(False)
        m.addAction(self.a_knockout)
        m.addSeparator()
        m.addAction("Überlappung einstellen …", self.set_knockout_margin)
        b.setMenu(m)
        return b

    def toggle_knockout(self):
        """Automatisches Aussparen für das Dokument ein-/ausschalten."""
        before = self.doc.stats()["stitches"]
        self.doc.knockout = self.props.knockout_doc = self.a_knockout.isChecked()
        self.commit()
        self.props.refresh()
        after = self.doc.stats()["stitches"]
        if self.doc.knockout:
            self.lbl_tip.setText(
                f"Automatisch aussparen: an – {before:,} → {after:,} Stiche. Verdecktes wird "
                f"darunter nicht gestickt ({self.doc.knockout_margin:.1f} mm bleiben überlappend); "
                "beim Verschieben wandert die Aussparung mit.".replace(",", "."))
        else:
            self.lbl_tip.setText(f"Automatisch aussparen: aus – wieder alles vollständig "
                                 f"({after:,} Stiche).".replace(",", "."))

    def set_knockout_margin(self):
        v, ok = QInputDialog.getDouble(
            self, "Automatisch aussparen",
            "So weit reicht die untere Fläche unter das obere Objekt (gegen Lücken durch "
            "Verzug):", self.doc.knockout_margin, 0.0, 5.0, 1)
        if not ok or abs(v - self.doc.knockout_margin) < 1e-6:
            return
        self.doc.knockout_margin = v
        if not self.doc.knockout:
            self.doc.knockout = self.props.knockout_doc = True
            self.a_knockout.setChecked(True)
        self.commit()
        self.props.refresh()
        self.lbl_tip.setText(f"Automatisch aussparen: {v:.1f} mm Überlappung.")

    def _sync_knockouts(self, extra=()):
        """Aussparungen aktualisieren und betroffene Objekte neu zeichnen."""
        self.doc.update_knockouts()
        ids = {id(o) for o in extra}
        todo = [it for it in self.items.values()
                if id(it.obj) in ids or getattr(it, "_knock", None) != it.obj._knock_key]
        if not todo:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for it in todo:
                it.rebuild()
        finally:
            QApplication.restoreOverrideCursor()
        self.canvas.viewport().update()

    def _grid_btn(self):
        """Raster-Knopf: Klick = Raster ein/aus, Pfeil = Einrasten und Rasterweite."""
        b = self._rbtn(self.a_grid)
        b.setPopupMode(QToolButton.MenuButtonPopup)
        m = QMenu(b)
        for a in (self.a_grid, self.a_snap):
            a.setIconVisibleInMenu(False)        # Häkchen statt Symbol zeigt den Zustand
        m.addAction(self.a_grid)
        m.addSeparator()
        m.addAction(self.a_snap)
        targets = m.addMenu("Einrasten an")
        for key, label in (("snap_grid", "Raster"), ("snap_objects", "Anderen Objekten (Kanten und Mitte)"),
                           ("snap_center", "Rahmenmitte")):
            a = targets.addAction(label)
            a.setCheckable(True)
            a.setChecked(bool(self.prefs.get(key)))
            a.toggled.connect(lambda on, k=key: self._set_snap_target(k, on))
            setattr(self, "a_" + key, a)
        step = m.addMenu("Rasterweite")
        grp = QActionGroup(step)
        for mm in (5, 10, 20, 25):
            a = step.addAction(f"{mm} mm")
            a.setCheckable(True)
            a.setChecked(self.opts.grid_step == mm)
            a.triggered.connect(lambda _=False, v=mm: self._set_grid_step(v))
            grp.addAction(a)
        b.setMenu(m)
        b.setToolTip("Raster ein/aus · Pfeil: Einrasten ein/aus, Einrast-Ziele, Rasterweite")
        self.grid_btn = b
        self._apply_snap_prefs()
        return b

    def _theme_btn(self):
        """Farbschema-Knopf: Hell/Dunkel und Akzentfarbe sofort umschalten."""
        from . import style
        b = QToolButton()
        b.setObjectName("ribbonBtn")
        b.setText("Farb-\nschema")
        b.setIcon(icons.icon("palette"))
        b.setProperty("icon_name", "palette")
        b.setIconSize(QSize(28, 28))
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setPopupMode(QToolButton.InstantPopup)
        m = QMenu(b)
        g1 = QActionGroup(m)
        for key, label in (("light", "Hell"), ("dark", "Dunkel")):
            a = m.addAction(label, lambda k=key: self.set_theme(theme=k))
            a.setCheckable(True)
            a.setChecked(self.prefs.get("ui_theme") == key)
            g1.addAction(a)
        m.addSeparator()
        g2 = QActionGroup(m)
        for key, (label, col) in style.ACCENTS.items():
            a = m.addAction(icons.swatch(col, 16), label, lambda k=key: self.set_theme(accent=k))
            a.setCheckable(True)
            a.setChecked(self.prefs.get("ui_accent") == key)
            g2.addAction(a)
        b.setMenu(m)
        b.setToolTip("Farbschema: hell oder dunkel, dazu eine Akzentfarbe")
        self.theme_menu = m
        return b

    def set_theme(self, theme=None, accent=None):
        if theme:
            self.prefs.set("ui_theme", theme)
        if accent:
            self.prefs.set("ui_accent", accent)
        self.apply_ui()
        from . import style
        self.lbl_tip.setText(f"Farbschema: {'Dunkel' if self.prefs.get('ui_theme') == 'dark' else 'Hell'}"
                             f", Akzent {style.ACCENTS[style.CURRENT_ACCENT][0]}.")

    def _apply_snap_prefs(self):
        c = self.canvas
        c.snap = bool(self.prefs.get("snap"))
        c.snap_grid = bool(self.prefs.get("snap_grid"))
        c.snap_objects = bool(self.prefs.get("snap_objects"))
        c.snap_center = bool(self.prefs.get("snap_center"))

    def _set_snap_target(self, key, on):
        self.prefs.set(key, bool(on))
        self._apply_snap_prefs()

    def _set_grid_step(self, mm):
        self.prefs.set("grid_step", mm)
        self.opts.grid_step = mm
        self.hoop_item.update()
        self.lbl_tip.setText(f"Rasterweite {mm} mm.")

    def toggle_snap(self):
        self.prefs.set("snap", self.a_snap.isChecked())
        self.canvas.snap = self.a_snap.isChecked()
        self.lbl_tip.setText("Einrasten " + ("an (Alt beim Ziehen = ohne)." if self.canvas.snap
                                             else "aus."))

    def _hint_label(self, text):
        l = QLabel(text)
        l.setObjectName("muted")
        return l

    def _make_toolstrip(self):
        tb = QToolBar()
        tb.setObjectName("tools")
        tb.setOrientation(Qt.Vertical)
        tb.setIconSize(QSize(26, 26))
        tb.setMovable(False)
        for key in ("select", "rect", "ellipse", "polygon", "pen", "line", "freehand", "satin", "text",
                    "nodes", "connect", "eraser", "jumps"):
            tb.addAction(self.tool_actions[key])
            if key in ("select", "text"):
                tb.addSeparator()
        tb.addSeparator()
        for a in (self.a_digit, self.a_sim):
            tb.addAction(a)
        tb.setFixedWidth(56)
        return tb

    def _make_status(self):
        sb = self.statusBar()
        self.lbl_pos = QLabel("X 0.0  Y 0.0 mm")
        self.lbl_stats = QLabel()
        self.lbl_zoom = QLabel()
        self.lbl_tip = QLabel()
        sb.addWidget(self.lbl_tip, 1)
        self.lbl_ai = QLabel()
        self.lbl_ai.setToolTip("KI-Schnittstelle (MCP) – Einrichtung unter Hilfe › KI-Anbindung")
        sb.addPermanentWidget(self.lbl_ai)
        self.lbl_update = QLabel()
        self.lbl_update.setToolTip("Eine neuere StichWizard-Version ist erschienen – klicken für Details")
        self.lbl_update.linkActivated.connect(lambda _: self.show_update())
        self.lbl_update.hide()
        sb.addPermanentWidget(self.lbl_update)
        self.lbl_machine = QLabel()
        self.lbl_machine.setToolTip("Gewählte Stickmaschine – ändern unter Export › Maschine")
        sb.addPermanentWidget(self.lbl_machine)
        sb.addPermanentWidget(self.lbl_stats)
        sb.addPermanentWidget(self.lbl_pos)
        sb.addPermanentWidget(self.lbl_zoom)

    # =========================================================== Dokument
    # ======================================================= Einstellungen & Hilfe
    def _new_document(self):
        d = Document()
        d.hoop = min(max(0, self.prefs.get("hoop")), len(HOOPS) - 1)
        d.fabric = self.prefs.get("fabric")
        return d

    # ------------------------------------------------------------ Oberfläche
    def action_catalog(self):
        """Alle Funktionen für den Favoriten-Reiter: [(schlüssel, bezeichnung, symbol)]."""
        out, seen = [], set()
        for key, a in sorted(self.tool_actions.items(), key=lambda kv: kv[1].text()):
            out.append((f"tool:{key}", a.text().split("(")[0].strip(), a.icon()))
            seen.add(id(a))
        for name, a in sorted(vars(self).items()):
            if name.startswith("a_") and isinstance(a, QAction) and id(a) not in seen and a.icon() \
                    and not a.icon().isNull():
                seen.add(id(a))
                out.append((name, a.text().replace("-\n", "").replace("\n", " "), a.icon()))
        out.sort(key=lambda t: t[1].lower())
        return out

    def _favorite_actions(self):
        acts = []
        for key in [k for k in self.prefs.get("ui_favorites").split(",") if k]:
            a = self.tool_actions.get(key[5:]) if key.startswith("tool:") else getattr(self, key, None)
            if isinstance(a, QAction):
                acts.append(a)
        return acts

    def apply_ui(self):
        """Oberflächen-Einstellungen sofort anwenden (Farbschema, Schrift, Menüband, Anordnung)."""
        from . import style
        from .__main__ import apply_light_palette
        P = self.prefs.get
        self.canvas.show_rulers = bool(P("rulers"))
        self.a_rulers.setChecked(bool(P("rulers")))
        theme = P("ui_theme")
        style.CURRENT_THEME = theme
        style.CURRENT_ACCENT = P("ui_accent") if P("ui_accent") in style.ACCENTS else "tuerkis"
        icons.FG = "#E4E7EE" if theme == "dark" else "#2B2D3A"
        icons.ACCENT = style.accent()
        from . import canvas as _canvas
        _canvas.ACCENT = QColor(style.accent())
        apply_light_palette(QApplication.instance(), theme)
        self.setStyleSheet(build_qss(theme, P("ui_font")))
        for b in self.findChildren(QToolButton):
            if b.property("head_icon"):
                b.setIcon(icons.icon(b.property("head_icon"), "#FFFFFF", style.accent_light()))
        self.hoop_item.update()
        for it in getattr(self, "items", {}).values():
            it.update()
        self.canvas.setBackgroundBrush(QColor(style.CANVAS_BG[theme]))
        for a in self.findChildren(QAction):
            if a.property("icon_name"):
                a.setIcon(icons.icon(a.property("icon_name")))
            elif a.property("tool_icon"):
                a.setIcon(tool_icon(a.property("tool_icon")))
        # Favoriten-Reiter
        r = self.ribbon
        for i in range(r.count()):
            if r.tabText(i).startswith("★"):
                r.removeTab(i)
                break
        favs = self._favorite_actions()
        if favs:
            r.insertTab(0, self._page([self._group("Meine Werkzeuge", [self._rbtn(a) for a in favs])]),
                        "★ Favoriten")
            r.setCurrentIndex(0)
        # Menüband: Größe der Knöpfe
        mode = P("ui_ribbon")
        big = {"large": 28, "compact": 20, "icons": 26}[mode]
        for b in self.findChildren(RibbonButton):
            b.setIconSize(QSize(big, big))
            b.setToolButtonStyle(Qt.ToolButtonIconOnly if mode == "icons" else Qt.ToolButtonTextUnderIcon)
            b.updateGeometry()
        f = P("ui_font") / 10.0
        r.setFixedHeight(int({"large": 138, "compact": 118, "icons": 96}[mode] * (0.75 + 0.25 * f)))
        ch = int({"large": 26, "compact": 24, "icons": 18}[mode] * (0.75 + 0.25 * f))
        for cb in (self.hoop_combo, self.fabric_combo, self.fabtype_combo):
            cb.setFixedHeight(ch)
        # Werkzeugleiste und Seitenleiste
        pos = P("ui_toolbar")
        self.toolstrip.setVisible(pos != "hidden")
        side_left = P("ui_side") == "left"
        widgets = []
        if side_left:
            widgets.append(self.side)
        if pos == "left":
            widgets.append(self.toolstrip)
        widgets.append(self.canvas)
        if pos == "right":
            widgets.append(self.toolstrip)
        if not side_left:
            widgets.append(self.side)
        if pos == "hidden":
            widgets.append(self.toolstrip)
        for k, wdg in enumerate(widgets):
            self.mid.insertWidget(k, wdg)
        self.mid.setStretchFactor(self.mid.indexOf(self.canvas), 1)
        for wdg in (self.toolstrip, self.side):
            self.mid.setStretchFactor(self.mid.indexOf(wdg), 0)
        self.palette_bar.setVisible(P("ui_palette"))
        self.toolstrip.setIconSize(QSize(20, 20) if mode == "compact" else QSize(24, 24))

    def open_settings(self, tab=None):
        dlg = SettingsDialog(self.prefs, self, self.action_catalog(), tab)
        before = (self.prefs.get("tie_mode"), self.prefs.get("trim_distance"))
        machine_before = self.prefs.get("machine")
        if not dlg.exec():
            return
        chosen = dlg.machine.currentData()
        if chosen != machine_before:                # Profil gewechselt: Format/Tempo/Rahmen setzen
            self.set_machine(chosen)
        self.prefs.apply_model_defaults()
        if (self.prefs.get("tie_mode"), self.prefs.get("trim_distance")) != before:
            # Vernähen bzw. Schnittlänge geändert: alles neu berechnen
            from . import embfont
            embfont.render.cache_clear()
            for o in self.doc.objects:
                if o.kind != "stitches":
                    o._skey = o._okey = None
            self.rebuild(self.doc.objects)
        self.doc.optimize = self.prefs.get("optimize_export")
        self.opts.grid_step = self.prefs.get("grid_step")
        self.opts.wheel = self.prefs.get("wheel")
        self.opts.show_grid = self.prefs.get("show_grid")
        self.a_grid.setChecked(self.opts.show_grid)
        self.hoop_item.update()
        self.refresh_panels()     # Stickzeit mit neuer Geschwindigkeit
        self.update_api_server()
        self.apply_ui()
        self.statusBar().showMessage("Einstellungen gespeichert. Rahmen und Stoff gelten für "
                                     "neue Designs.", 5000)

    def _keys(self, action):
        return action.shortcut().toString(QKeySequence.NativeText)

    def shortcut_groups(self):
        k = self._keys
        T = self.tool_actions
        return [
            ("Datei", [("Neues Design", k(self.a_new)), ("Öffnen", k(self.a_open)),
                       ("Design-Browser", k(self.a_browser)),
                       ("Speichern", k(self.a_save)), ("Speichern unter", k(self.a_saveas)),
                       ("Für Maschine exportieren", k(self.a_export)),
                       ("Stickdatei importieren", k(self.a_import))]),
            ("Werkzeuge", [("Auswählen", k(T["select"])), ("Rechteck", k(T["rect"])),
                           ("Ellipse / Kreis", k(T["ellipse"])), ("Vieleck", k(T["polygon"])),
                           ("Linie", k(T["line"])), ("Freihand-Linie", k(T["freehand"])),
                           ("Säulen-Satin", k(T["satin"])),
                           ("Schriftzug", k(T["text"])), ("Punkte bearbeiten", k(T["nodes"])), ("Mit Linie verbinden", k(T["connect"])),
                           ("Radierer", k(T["eraser"])),
                           ("Radierer kleiner / größer", "[  /  ]"),
                           ("Radierer: Bereich umfahren (Lasso)", "Umschalt + Ziehen"),
                           ("Sprünge & Fadenschnitte bearbeiten", k(T["jumps"])),
                           ("Zurück zum Auswählen", "Esc")]),
            ("Bearbeiten", [("Rückgängig", k(self.a_undo)),
                            ("Wiederholen", f"{k(self.a_redo)}  /  {k(self.a_redo2)}"),
                            ("Kopieren", k(self.a_copy)), ("Einfügen", k(self.a_paste)),
                            ("Duplizieren", k(self.a_dup)), ("Löschen", "Entf"),
                            ("Alles auswählen", k(self.a_all)),
                            ("Früher / später sticken", f"{k(self.a_up)}  /  {k(self.a_down)}"),
                            ("Im Rahmen zentrieren", k(self.a_center)),
                            ("Zerlegen", k(self.a_split)), ("Kombinieren", k(self.a_merge))]),
            ("Verschieben & Formen", [
                ("Objekt verschieben", "Ziehen  /  Pfeiltasten"),
                ("In 10-mm-Schritten", "Umschalt + Pfeiltasten"),
                ("Größe ändern", "Eckgriff ziehen"),
                ("Drehen (15°-Schritte)", "Runder Griff  (+ Umschalt)"),
                ("Quadrat / Kreis zeichnen", "Umschalt beim Aufziehen"),
                ("Eckpunkt setzen (Vieleck/Linie)", "Linksklick"),
                ("Rundungspunkt setzen (Vieleck/Linie)", "Rechtsklick"),
                ("Form schließen", "Klick auf Startpunkt  /  Enter  /  Doppelklick"),
                ("Als Loch in gewählte Form", "Strg beim Abschließen"),
                ("Letzten Punkt entfernen", "Rücktaste"),
                ("Punkt einfügen (Punkte-Werkzeug)", "Klick auf Kante  /  Einfg"),
                ("Linie verlängern (Punkte-Werkzeug)", "Strg+Klick neben dem Ende"),
                ("Punkte / Linien verbinden", "Strg+J"),
                ("Linie am Punkt auftrennen", "Strg+Umschalt+J"),
                ("Zwei Punkte mit Linie verbinden", "K, dann zwei Punkte anklicken"),
                ("Ecke/Rundung/Löschen (Punkte-Werkzeug)", "Rechtsklick auf Punkt"),
                ("Punkt löschen (Punkte-Werkzeug)", "Entf"),
                ("Punkte fein verschieben", "Pfeiltasten (0,1 mm)")]),
            ("Ansicht", [("Vergrößern / Verkleinern", f"{k(self.a_zin)}  /  {k(self.a_zout)}"),
                         ("Zoomen", "Mausrad" if self.opts.wheel == "zoom" else "Strg + Mausrad"),
                         ("Ansicht verschieben", "Mittlere Maustaste  /  Leertaste + Ziehen"),
                         ("Touchpad", "2 Finger wischen = verschieben, spreizen = zoomen"),
                         ("Rahmen einpassen", k(self.a_fit)),
                         ("Simulator & Optimierer", f"{k(self.a_sim)}  /  {k(self.a_optimizer)}"),
                         ("Produktvorschau", k(self.a_mockup))]),
            ("Bilder", [("Bild-Assistent", k(self.a_digit)),
                        ("Bitmap nachzeichnen", k(self.a_trace)),
                        ("AI / PDF öffnen", k(self.a_vector)),
                        ("Vorlage zum Nachzeichnen", k(self.a_tpl))]),
            ("Farben", [("Füllfarbe setzen", "Linksklick auf Garnfarbe"),
                        ("Rand-/Linienfarbe setzen", "Rechtsklick auf Garnfarbe")]),
            ("Programm", [("Einstellungen", k(self.a_settings)),
                          ("Diese Übersicht", k(self.a_keys))]),
        ]

    def show_shortcuts(self):
        ShortcutsDialog(self.shortcut_groups(), self).exec()

    def manual_path(self):
        """Pfad der PDF-Anleitung (Projektordner, Flatpak und Windows: <basis>/docs)."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(base, "docs", "StichWizard-Anleitung.pdf")
        return p if os.path.exists(p) else None

    def show_manual(self):
        src = self.manual_path()
        if not src:
            QMessageBox.information(self, APP, "Die Anleitung (StichWizard-Anleitung.pdf) wurde "
                                    "nicht gefunden.")
            return
        path = src
        if os.environ.get("FLATPAK_ID"):
            # Dateien in /app sieht der PDF-Betrachter außerhalb der Sandbox nicht –
            # daher in den eigenen Datenordner kopieren (liegt unter ~/.var/app/…)
            import shutil
            d = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, os.path.basename(src))
            if not os.path.exists(path) or os.path.getmtime(path) < os.path.getmtime(src) or \
                    os.path.getsize(path) != os.path.getsize(src):
                shutil.copy2(src, path)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.information(self, APP, f"Kein PDF-Betrachter gefunden. Die Anleitung liegt "
                                    f"hier:\n{path}")

    def show_guide(self):
        GuideDialog(self).exec()

    def show_about(self):
        from .help import LicensesDialog
        box = QMessageBox(self)
        box.setWindowTitle("Über StichWizard")
        box.setIconPixmap(icons.app_logo(96))
        box.setText(ABOUT)
        lic = box.addButton("Lizenzen Dritter …", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is lic:
            LicensesDialog(self).exec()

    def update_title(self):
        name = os.path.basename(self.path) if self.path else "Unbenannt"
        star = " •" if self.dirty else ""
        self.setWindowTitle(f"{name}{star} – {APP}")
        self.doc_title.setText(f"{name}{star}")

    def commit(self, initial=False):
        self._sync_knockouts()
        snap = self.doc.to_json()
        if not self.undo_stack or self.undo_stack[-1] != snap:
            self.undo_stack.append(snap)
            self.undo_stack = self.undo_stack[-self.prefs.get("undo_steps"):]
            self.redo_stack.clear()
            if not initial:
                self.dirty = True
        self.refresh_panels()
        self.update_title()
        if getattr(self, "_mockup", None) is not None:
            self._mockup.schedule()

    def open_mockup(self):
        """Produktvorschau öffnen (nicht modal – bleibt beim Weiterarbeiten offen)."""
        from .mockup import MockupDialog, default_product
        if getattr(self, "_mockup", None) is None:
            self._mockup = MockupDialog(self)
        else:
            dlg = self._mockup
            if not dlg.isVisible():                # bei erneutem Öffnen zum Rahmen passend
                dlg.product = default_product(self.doc)
                dlg.color = self.doc.fabric
                dlg.place = 0
                dlg._sync_controls()
        self._mockup.show()
        self._mockup.raise_()
        self._mockup.activateWindow()
        self._mockup.view.update()

    def refresh_panels(self):
        if self.canvas.tool == "jumps":
            self._refresh_jumps()
        if getattr(self, "a_density", None) is not None and self.a_density.isChecked():
            self._update_density()
        sel = [o.id for o in self.selected_objects()]
        self.seq.populate(self.doc.objects, sel)
        self._refresh_layers()
        st = self.doc.stats()
        w, h = self.doc.hoop_size
        hrs = int(st["minutes"] // 60)
        mins = int(round(st["minutes"] % 60))
        tstr = f"{hrs} h {mins} min" if hrs else f"{mins} min"
        self.lbl_stats.setText(f"{st['stitches']:,} Stiche · {st['colors']} Farben · "
                               f"{st['width']:.0f} × {st['height']:.0f} mm · ca. {tstr}".replace(",", "."))
        b = st["bounds"]
        outside = st["stitches"] and (b[0] < -w / 2 or b[2] > w / 2 or b[1] < -h / 2 or b[3] > h / 2)
        rows = "".join(
            f"<tr><td><span style='color:{c}; font-size:14pt'>■</span></td>"
            f"<td>{i + 1}. {thread_name(c)}</td><td style='color:#8A90A0'>&nbsp;{c}</td></tr>"
            for i, (c, _) in enumerate(self.doc.machine_blocks()))
        warn = ("<p style='color:#C62828'><b>⚠ Das Design ragt über das Stickfeld hinaus!</b></p>"
                if outside else "")
        self.seq.set_info(
            f"{warn}<table cellspacing=3>"
            f"<tr><td>Stiche</td><td><b>{st['stitches']:,}</b></td></tr>".replace(",", ".") +
            f"<tr><td>Größe</td><td><b>{st['width']:.1f} × {st['height']:.1f} mm</b></td></tr>"
            f"<tr><td>Farbwechsel</td><td><b>{max(0, st['colors'] - 1)}</b></td></tr>"
            f"<tr><td>Fadenschnitte</td><td><b>{st['trims']}</b></td></tr>"
            f"<tr><td>Stickzeit&nbsp;</td><td><b>ca. {tstr}</b></td></tr>"
            f"<tr><td>Rahmen</td><td><b>{HOOPS[self.doc.hoop][0]}</b></td></tr></table>"
            f"<p><b>Farbfolge</b></p><table cellspacing=2>{rows}</table>")

    def sync_items(self, keep_selection=None):
        keep = set(keep_selection or [])
        self.doc.apply_layer_flags()
        self.doc.sort_by_layers()
        self.doc.update_knockouts()
        self._syncing = True
        for it in self.items.values():
            self.scene.removeItem(it)
        self.items = {}
        for i, o in enumerate(self.doc.objects):
            it = ObjectItem(o, self.opts)
            it.setZValue(i)
            self.scene.addItem(it)
            self.items[o.id] = it
            if o.id in keep:
                it.setSelected(True)
        self._syncing = False
        self.on_scene_selection()

    # ------------------------------------------------------------- Ebenen
    def on_layer_action(self, act, lid):
        from .model import new_layer
        d = self.doc
        ids = [L["id"] for L in d.layers]
        if lid not in ids:
            lid = d.active_layer
        L = next(x for x in d.layers if x["id"] == lid)
        k = d.layers.index(L)
        if act == "activate":
            d.active_layer = lid
            self.lbl_tip.setText(f"Aktive Ebene: {L['name']} – neue Objekte landen hier.")
            self._refresh_layers()
            return
        if act == "add":
            n = new_layer(f"Ebene {len(d.layers) + 1}")
            d.layers.insert(k + 1, n)
            d.active_layer = n["id"]
        elif act in ("up", "down"):
            j = k + (1 if act == "up" else -1)
            if not 0 <= j < len(d.layers):
                return
            d.layers[k], d.layers[j] = d.layers[j], d.layers[k]
        elif act == "toggle":
            L["visible"] = not L["visible"]
            if not L["visible"]:
                self.scene.clearSelection()
        elif act == "lock":
            L["locked"] = not L["locked"]
            if L["locked"]:
                self.scene.clearSelection()
        elif act == "delete":
            if len(d.layers) == 1:
                self.lbl_tip.setText("Die letzte Ebene lässt sich nicht löschen.")
                return
            target = d.layers[k - 1] if k > 0 else d.layers[k + 1]
            for o in d.objects:
                if o.layer == lid:
                    o.layer = target["id"]
            d.layers.remove(L)
            d.active_layer = target["id"]
        elif act == "move_here":
            sel = self.selected_objects()
            if not sel:
                self.lbl_tip.setText("Zuerst Objekte auswählen, die in diese Ebene sollen.")
                return
            for o in sel:
                o.layer = lid
            # wie in Inkscape: oben in der Ziel-Ebene einordnen
            d.objects = [o for o in d.objects if o not in sel] + sorted(sel, key=d.objects.index)
            self.lbl_tip.setText(f"{len(sel)} Objekt(e) in »{L['name']}« verschoben.")
        elif act == "select":
            if not L["visible"] or L["locked"]:
                self.lbl_tip.setText("Die Ebene ist ausgeblendet oder gesperrt.")
                return
            self.sync_items([o.id for o in d.objects if o.layer == lid])
            self._refresh_layers()
            return
        self.sync_items([o.id for o in self.selected_objects()] if act == "move_here" else [])
        self.commit()
        self._refresh_layers()

    # ------------------------------------------------------------- Bibliothek
    def on_library_action(self, act, path):
        from . import library
        from .controls import ask_values
        if act in ("save_sel", "save_all"):
            objs = self.selected_objects() if act == "save_sel" else list(self.doc.objects)
            if not objs:
                self.lbl_tip.setText("Zuerst Objekte auswählen, die in die Bibliothek sollen."
                                     if act == "save_sel" else "Das Design ist leer.")
                return
            default = objs[0].name if act == "save_sel" and len(objs) == 1 else (
                os.path.splitext(os.path.basename(self.path))[0] if self.path else "Mein Design")
            v = ask_values(self, "In die Bibliothek speichern", [
                ("name", "Name", "text", default),
                ("cat", "Kategorie", "editcombo", library.categories() or ["Eigene Elemente"],
                 "Designs" if act == "save_all" else (library.categories() or ["Eigene Elemente"])[0])],
                "Das Element steht danach im Reiter »Bibliothek« bereit – Doppelklick fügt es "
                "in jedes Design ein.")
            if not v or not v["name"]:
                return
            library.save(v["name"], v["cat"] or "Eigene Elemente", objs)
            self.library_panel.refresh()
            self.side.setCurrentWidget(self.library_panel)
            self.lbl_tip.setText(f"»{v['name']}« in der Bibliothek gespeichert ({v['cat']}).")
        elif act == "insert":
            objs = library.load_objects(path)
            if not objs:
                return
            self.add_objects(objs)
            self.lbl_tip.setText(f"»{os.path.basename(path)[:-len(library.EXT)]}« eingefügt.")
        elif act == "rename":
            data = library.load(path)
            v = ask_values(self, "Element umbenennen", [
                ("name", "Name", "text", data.get("name", "")),
                ("cat", "Kategorie", "editcombo", library.categories(), data.get("category", ""))])
            if v and v["name"]:
                library.rename(path, v["name"], v["cat"] or data.get("category"))
                self.library_panel.refresh()
        elif act == "delete":
            r = QMessageBox.question(self, APP, f"»{os.path.basename(path)[:-len(library.EXT)]}« "
                                     "aus der Bibliothek löschen?")
            if r == QMessageBox.Yes:
                library.delete(path)
                self.library_panel.refresh()

    def rename_layer(self, lid, name):
        for L in self.doc.layers:
            if L["id"] == lid and L["name"] != name:
                L["name"] = name
                self.commit()
        self._refresh_layers()

    def _refresh_layers(self):
        if hasattr(self, "layers_panel"):
            self.layers_panel.populate(self.doc)

    def restack(self):
        for i, o in enumerate(self.doc.objects):
            if o.id in self.items:
                self.items[o.id].setZValue(i)

    def selected_objects(self):
        return [it.obj for it in self.scene.selectedItems() if isinstance(it, ObjectItem)]

    def add_objects(self, objs, select=True):
        self._syncing = True
        if select:
            self.scene.clearSelection()
        for o in objs:
            self.doc.objects.append(o)
        self.doc.apply_layer_flags()          # neue Objekte kommen in die aktive Ebene
        self.doc.sort_by_layers()
        for o in objs:
            it = ObjectItem(o, self.opts)
            self.scene.addItem(it)
            self.items[o.id] = it
            if select:
                it.setSelected(True)
        self.restack()
        self._syncing = False
        self.on_scene_selection()
        self.commit()

    def rebuild(self, objs):
        # verdeckte Bereiche zuerst: ein verschobenes Objekt spart andere aus (und umgekehrt)
        self._sync_knockouts(extra=list(objs))

    # ========================================================== Ereignisse
    def set_tool(self, tool):
        self._pick = None
        if tool == "connect" and self.canvas.tool == "nodes" and len(self.canvas._node_sel) == 2 \
                and self.canvas.has_node_selection():
            # zwei Punkte schon gewählt: gleich verbinden und im Punkte-Werkzeug bleiben
            self.tool_actions["nodes"].setChecked(True)
            self.connect_selected_nodes()
            return
        self.tool_actions[tool].setChecked(True)
        self.canvas.set_tool(tool)
        tips = {
            "select": "Klicken zum Auswählen · Ziehen zum Verschieben · Ecken: Größe · Kreis oben: Drehen (Umschalt = 15°)",
            "rect": "Rechteck aufziehen · Umschalt = Quadrat",
            "ellipse": "Ellipse aufziehen · Umschalt = Kreis",
            "polygon": "Linksklick = Eckpunkt · Rechtsklick = Rundungspunkt · Klick auf Startpunkt, Enter oder "
                       "Doppelklick = fertig · Strg beim Abschließen = Loch · Rücktaste = Punkt zurück",
            "line": "Linksklick = Eckpunkt · Rechtsklick = Rundungspunkt · Enter oder Doppelklick = fertig",
            "satin": "Säulen-Satin: abwechselnd links und rechts der Säule klicken (jedes Paar legt die "
                     "Stichrichtung fest) · Linksklick = Ecke, Rechtsklick = Rundung · Enter = fertig",
            "freehand": "Linie frei zeichnen (gedrückt halten)",
            "sketch": "Sketch: mit gedrückter Maustaste zeichnen – jeder Strich wird gleich zu "
                      "Stichen, das Werkzeug bleibt für weitere Striche aktiv (Esc beendet)",
            "text": "Klicken, wo der Schriftzug stehen soll",
            "connect": "Ersten Punkt anklicken, dann den zweiten – dazwischen entsteht eine Linie · rastet "
                       "auf vorhandenen Punkten ein · Linienenden werden verlängert, verbunden oder "
                       "geschlossen · Umschalt = 15°-Winkel · Esc/Rechtsklick = abbrechen",
            "nodes": "Punkte ziehen · Klick auf Kante (+): Punkt einfügen · Rechtsklick: Ecke/Rundung/"
                     "Löschen · Einfg: Punkt nach Auswahl · Strg+Klick: Linie verlängern · "
                     "Rahmen ziehen: mehrere wählen",
            "jumps": "Orange = Sprung, Rot mit ✕ = Sprung mit Fadenschnitt · Klick auf einen Sprung: "
                     "Fadenschnitt setzen/entfernen oder mit Stichen verbinden · Klick auf einen Stich "
                     "einer Stickdatei: in Sprung umwandeln",
            "eraser": self._eraser_tip(),
            "measure": "Messen: von Punkt zu Punkt ziehen – Abstand, waagerecht/senkrecht und Winkel "
                       "erscheinen an der Linie · Umschalt = in 45°-Schritten",
        }
        self.lbl_tip.setText(tips.get(tool, ""))
        if tool == "jumps":
            self._refresh_jumps()
        else:
            self.canvas.jump_records = []
        self.canvas.setFocus()

    # ------------------------------------------------------- Sprung-Editor
    def _refresh_jumps(self):
        from . import jumps
        recs = jumps.jump_list(self.doc)
        self.canvas.jump_records = recs
        self.canvas._jump_hover = None
        self.canvas.viewport().update()
        n_trim = sum(r["trim"] for r in recs)
        self.statusBar().showMessage(f"{len(recs)} Sprünge, davon {n_trim} mit Fadenschnitt", 6000)
        return recs

    def _name(self, oid):
        o = self.doc.find(oid)
        return o.name if o else "?"

    def _confirm_convert(self, o):
        if o.kind == "stitches":
            return True
        r = QMessageBox.question(
            self, APP, f"»{o.name}« ist eine berechnete Form. Um einzelne Sprünge zu bearbeiten, "
            "wird sie in feste Stiche umgewandelt (wie sie gestickt würde). Form, Füllart und "
            "Größe lassen sich danach nicht mehr verändern – Rückgängig (Strg+Z) geht aber.\n\n"
            "Jetzt umwandeln?", QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return False
        from . import jumps
        jumps.to_stitches(o, self.doc.optimize)
        return True

    def _edit_inside(self, rec, action):
        """Sprung innerhalb eines Objekts bearbeiten (wandelt bei Bedarf in Stiche um)."""
        from . import jumps
        o = self.doc.find(rec["obj"])
        if not self._confirm_convert(o):
            return
        rec = self._refind_jump(rec) or rec
        if action == "trim_on":
            jumps.set_trim(self.doc, rec, True)
        elif action == "trim_off":
            jumps.set_trim(self.doc, rec, False)
        elif action == "connect":
            jumps.connect(self.doc, rec)
        self.sync_items([o.id])
        self.commit()

    def _refind_jump(self, rec):
        """Denselben Sprung (gleiche Start-/Endpunkte) in der aktuellen Liste suchen –
        nötig, wenn das Objekt gerade in Stiche umgewandelt wurde."""
        from . import jumps
        kinds = {rec["kind"], "inside"} if rec.get("same") else {rec["kind"]}
        for r in jumps.jump_list(self.doc):
            if r["kind"] in kinds and r["obj"] == rec["obj"] and \
                    math.hypot(r["a"][0] - rec["a"][0], r["a"][1] - rec["a"][1]) < 0.05 and \
                    math.hypot(r["b"][0] - rec["b"][0], r["b"][1] - rec["b"][1]) < 0.05:
                return r
        return None

    def on_jump_clicked(self, x, y, gpos):
        from . import jumps
        idx = self.canvas.hit_jump(x, y)
        m = QMenu(self)
        if idx is not None:
            rec = self.canvas.jump_records[idx]
            state = "mit Fadenschnitt" if rec["trim"] else "ohne Fadenschnitt"
            head = m.addAction(f"Sprung {rec['length']:.1f} mm · {state}")
            head.setEnabled(False)
            if rec["kind"] == "between" and not rec["same"]:
                info = m.addAction(f"zwischen »{self._name(rec['obj'])}« und »{self._name(rec['obj_b'])}«")
                info.setEnabled(False)
                m.addSeparator()
                o = self.doc.find(rec["obj"])
                for mode, label in (("auto", "Fadenschnitt automatisch (laut Einstellungen)"),
                                    ("always", "Hier immer schneiden"),
                                    ("never", "Hier nie schneiden")):
                    a = m.addAction(label, lambda md=mode: (jumps.set_trim_mode(self.doc, rec, md),
                                                            self.rebuild([o]), self.commit(),
                                                            self.props.refresh()))
                    a.setCheckable(True)
                    a.setChecked(o.trim_after == mode)
            else:
                o = self.doc.find(rec["obj"])
                if o.kind != "stitches":
                    note = m.addAction(f"in »{o.name}« – wird dafür in Stiche umgewandelt")
                    note.setEnabled(False)
                m.addSeparator()
                if rec["trim"]:
                    m.addAction("Fadenschnitt entfernen", lambda: self._edit_inside(rec, "trim_off"))
                else:
                    m.addAction("Fadenschnitt setzen", lambda: self._edit_inside(rec, "trim_on"))
                covered = jumps.is_covered(self.doc, rec)
                label = ("Mit Stichen verbinden (verdeckt – wird später überstickt)" if covered
                         else "Mit Stichen verbinden (⚠ Faden bleibt sichtbar)")
                m.addAction(label, lambda: self._edit_inside(rec, "connect"))
        else:
            hit = jumps.find_stitch(self.doc, x, y, 6 / self.canvas.zoom())
            if hit is None:
                return
            head = m.addAction(f"Stich {hit['length']:.1f} mm in »{self._name(hit['obj'])}«")
            head.setEnabled(False)
            m.addSeparator()
            for trim, label in ((False, "In Sprung umwandeln"),
                                (True, "In Sprung mit Fadenschnitt umwandeln")):
                m.addAction(label, lambda t=trim: (jumps.split_stitch(self.doc, hit, t),
                                                   self.sync_items([hit["obj"]]), self.commit()))
        m.exec(gpos)

    def toggle_colorsort(self):
        before = len(self.doc.machine_blocks())
        self.doc.color_sort = self.a_colorsort.isChecked()
        after = len(self.doc.machine_blocks())
        self.commit()
        self.statusBar().showMessage(f"Farbwechsel: {max(0, before - 1)} → {max(0, after - 1)}", 6000)

    def open_browser(self):
        from .browser import DesignBrowser, load_design
        folder = self.settings.value("browserDir", "") or self._dir()
        dlg = DesignBrowser(folder, self)
        ok = dlg.exec()
        self.settings.setValue("browserDir", dlg.folder)
        if not ok or not dlg.selected_path:
            return
        path = dlg.selected_path
        if dlg.action == "open":
            if self.maybe_save():
                self.load_path(path)
            return
        try:
            doc = load_design(path)
        except Exception as e:
            QMessageBox.critical(self, APP, f"Datei konnte nicht gelesen werden:\n{e}")
            return
        objs = [o.clone() for o in doc.objects]
        self.center_group(objs)
        self.add_objects(objs)

    def open_optimizer(self):
        """Stick-Optimierer = Stick-Simulator (ein gemeinsames Fenster)."""
        self.simulate()

    def convert_to_stitches(self, objs=None):
        from . import jumps
        objs = objs or [o for o in self.selected_objects() if o.kind != "stitches"]
        if not objs:
            self.lbl_tip.setText("Eine Form oder einen Schriftzug auswählen, der in Stiche "
                                 "umgewandelt werden soll.")
            return
        for o in objs:
            jumps.to_stitches(o, self.doc.optimize)
        self.sync_items([o.id for o in objs])
        self.commit()
        self.lbl_tip.setText("In Stiche umgewandelt – Sprünge und Stiche lassen sich jetzt mit "
                             "»Sprünge bearbeiten« (J) einzeln ändern.")

    def _tool_finished(self):
        # Beim Nachzeichnen bleibt das Werkzeug aktiv, damit Form um Form entstehen kann
        t = self.doc.template
        if not (t and t["visible"] and self.canvas.tool == "polygon"):
            self.set_tool("select")

    SKETCH_STYLES = [("Bleistift (Skizzenstich)", {"type": "sketch", "width": 1.2, "repeats": 2,
                                                   "stitch_len": 2.0}),
                     ("Steppstich", {"type": "run", "stitch_len": 2.0}),
                     ("Bohnenstich", {"type": "triple", "repeats": 1, "stitch_len": 2.2}),
                     ("Zickzack", {"type": "zigzag", "width": 2.0, "stitch_len": 0.8}),
                     ("Satin 2 mm", {"type": "satin", "width": 2.0}),
                     ("Satin 4 mm", {"type": "satin", "width": 4.0})]

    def sketch_menu(self):
        from PySide6.QtGui import QActionGroup as _AG
        m = QMenu(self)
        grp = _AG(m)
        for i, (label, style) in enumerate(self.SKETCH_STYLES):
            a = m.addAction(label, lambda s=style, l=label: self.set_sketch_style(s, l))
            a.setCheckable(True)
            a.setChecked(i == 0)
            grp.addAction(a)
        return m

    def set_sketch_style(self, style, label=None):
        self.sketch_style = dict(style)
        self.set_tool("sketch")
        if label:
            self.lbl_tip.setText(f"Sketch-Stil: {label} – jetzt mit gedrückter Maustaste zeichnen.")

    def on_created(self, kind, data):
        if kind == "sketch":                 # Sketch: Strich sofort als Stichlinie, Werkzeug bleibt
            o = EmbObject("line", "Sketch")
            o.set_points(data)
            o.smooth = 1
            o.border.update(getattr(self, "sketch_style", None) or self.SKETCH_STYLES[0][1])
            o.border["auto_spacing"] = o.border.get("type") == "satin"
            self.add_objects([o], select=False)
            return
        if kind == "connect":
            self.connect_points(data["a"], data["b"])
            return
        if kind == "curve":
            sel = [o for o in self.selected_objects() if o.kind in ("shape", "text")]
            if data["add"] and len(sel) == 1:
                self._add_ring(sel[0], data["rings"][0])
                return
            o = EmbObject("shape", "Form")
            self._set_world_curve(o, data["rings"])
        elif kind == "satin":
            o = EmbObject("satin", "Satinsäule")
            allp = data["a"] + data["b"]
            xs, ys = [p[0] for p in allp], [p[1] for p in allp]
            o.x, o.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            o.set_satin([[x - o.x, y - o.y, t] for x, y, t in data["a"]],
                        [[x - o.x, y - o.y, t] for x, y, t in data["b"]])
            o.fill.update(density=0.4, pull=0.2, underlay=True)
        elif kind == "curveline":
            o = EmbObject("line", "Linie")
            xs, ys = [p[0] for p in data], [p[1] for p in data]
            o.x, o.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            o.set_line_nodes([[x - o.x, y - o.y, t] for x, y, t in data])
        elif kind == "shape":
            o = EmbObject("shape", "Form")
            o.set_geometry(data)
        else:
            o = EmbObject("line", "Linie")
            o.set_points(data)
        self.add_objects([o])
        self.side.setCurrentWidget(self.props)

    def _set_world_curve(self, o, rings):
        """Setzt Pfade aus Weltkoordinaten; Drehpunkt in die Mitte, ohne Drehung/Skalierung."""
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        o.x, o.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        o.rot, o.sx, o.sy = 0.0, 1.0, 1.0
        o.set_curve([[[x - o.x, y - o.y, t] for x, y, t in r] for r in rings])

    def _curve_rings(self, o):
        """Pfade einer Form in Objektkoordinaten (Polygone werden zu Eckpunkten)."""
        if o.kind == "text":
            self._text_to_shape(o)
        return [list(map(list, r)) for r in (o.curve or curves.polygon_rings(o.raw_geometry()))]

    def _add_ring(self, target, world_nodes):
        """Mit Strg abgeschlossene Form: als Loch (innen) bzw. weiteres Teil zur Auswahl."""
        rings = self._curve_rings(target)
        rings.append([[*target.to_local(x, y), t] for x, y, t in world_nodes])
        target.set_curve(rings)
        self.sync_items([target.id])
        self.commit()
        self.lbl_tip.setText("Zur ausgewählten Form hinzugefügt – innen liegende Pfade werden zu Löchern.")

    def on_text_requested(self, x, y):
        text, ok = QInputDialog.getMultiLineText(self, "Schriftzug", "Text eingeben:", "Hallo")
        self.set_tool("select")
        if not ok or not text.strip():
            return
        o = EmbObject("text", text.split("\n")[0][:24])
        o.text["text"] = text
        o.fill.update(type="satin", angle=0, color="#1565C0")
        o.x, o.y = x, y
        self.add_objects([o])
        self.side.setCurrentWidget(self.props)

    # ------------------------------------------------------ Form bearbeiten
    def on_nodes_edited(self, obj):
        self.rebuild([obj])
        self.props.refresh()
        if self.canvas.merge_undo and len(self.undo_stack) > 1:
            self.undo_stack.pop()       # eingefügten Punkt gleich weitergezogen: ein Schritt
        self.commit()

    def _replace(self, old, new, select=True):
        """Ersetzt Objekte in der Reihenfolge (neue an der Stelle des ersten alten)."""
        objs = self.doc.objects
        idx = min(objs.index(o) for o in old) if old else len(objs)
        ids = {o.id for o in old}
        self.doc.objects = [o for o in objs[:idx] if o.id not in ids] + list(new) + \
                           [o for o in objs[idx:] if o.id not in ids]
        self.sync_items([o.id for o in new] if select else [])
        self.commit()

    def split_selected(self):
        out, old = [], []
        for o in self.selected_objects():
            if o.kind == "text":
                self._text_to_shape(o)
            if o.kind != "shape":
                continue
            polys = polygons_of(o.raw_geometry())
            if len(polys) < 2:
                continue
            old.append(o)
            polys.sort(key=lambda p: (round(p.bounds[1] / 5), p.bounds[0]))  # Lesereihenfolge
            # Bei Eck-/Rundungspfaden jeden Pfad dem kleinsten Teil zuordnen, das ihn umschließt
            owner = {}
            if o.curve:
                outlines = [Polygon(p.exterior) for p in polys]
                for ri, r in enumerate(o.curve):
                    pt = Point(r[0][0], r[0][1])
                    hits = [k for k, ol in enumerate(outlines) if ol.buffer(1e-6).covers(pt)]
                    if hits:
                        owner.setdefault(min(hits, key=lambda k: outlines[k].area), []).append(r)
            for i, p in enumerate(polys):
                c = o.clone()
                c.name = f"{o.name} – Teil {i + 1}"
                minx, miny, maxx, maxy = p.bounds
                cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
                if owner.get(i):
                    c.set_curve([[[x - cx, y - cy, t] for x, y, t in r] for r in owner[i]])
                else:
                    c.set_raw_geometry(affinity.translate(p, -cx, -cy))
                c.x, c.y = o.to_world(cx, cy)
                out.append(c)
        if not old:
            self.lbl_tip.setText("Zum Zerlegen eine Form mit mehreren Teilen auswählen.")
            return
        self._replace(old, out)
        self.lbl_tip.setText(f"In {len(out)} Teile zerlegt – jetzt einzeln verschieben, umfärben oder löschen.")

    def merge_selected(self):
        sel = [o for o in self.selected_objects() if o.kind in ("shape", "text")]
        if len(sel) < 2:
            self.lbl_tip.setText("Zum Kombinieren mindestens zwei Formen auswählen.")
            return
        sel.sort(key=self.doc.objects.index)
        geoms = [o.world_geometry() for o in sel]
        geom = unary_union(geoms)
        new = EmbObject("shape", sel[0].name.split(" – Teil")[0])
        if abs(sum(g.area for g in geoms) - geom.area) < 0.5 and not any(o.smooth for o in sel):
            # Teile überlappen nicht: Ecken und Rundungen bleiben erhalten
            rings = [[[*o.to_world(x, y), t] for x, y, t in r]
                     for o in sel for r in self._curve_rings(o)]
            self._set_world_curve(new, rings)
        else:
            new.set_geometry(geom)
        new.fill = dict(sel[0].fill, angle=sel[0].fill["angle"] + sel[0].rot)
        new.border = dict(sel[0].border)
        self._replace(sel, [new])

    def _text_to_shape(self, o):
        o.geom_wkt = o.local_geometry().wkt
        o.kind = "shape"
        o._gkey = o._skey = None

    def convert_to_shape(self):
        sel = [o for o in self.selected_objects() if o.kind == "text"]
        if not sel:
            self.lbl_tip.setText("Einen Schriftzug auswählen, um ihn in eine Form umzuwandeln.")
            return
        for o in sel:
            self._text_to_shape(o)
        self.sync_items([o.id for o in sel])
        self.commit()

    def simplify_selected(self):
        sel = [o for o in self.selected_objects() if o.kind in ("shape", "line")]
        for o in sel:
            if o.curve or o.ptypes:
                self._auto_curve(o, tolerance=0.6)      # Rundungen dabei erhalten
            else:
                o.set_raw_geometry(o.raw_geometry().simplify(0.3, preserve_topology=True))
        if sel:
            self.rebuild(sel)
            self.commit()
            self.canvas.viewport().update()

    def _auto_curve(self, o, tolerance=0.35):
        if o.kind == "text":
            self._text_to_shape(o)
        if o.kind == "line":
            g = o.raw_geometry()
            coords = list(g.coords)
            nodes = curves.auto_ring(coords, o.closed, tolerance)
            if o.closed and len(nodes) > 1 and nodes[0][:2] == nodes[-1][:2]:
                nodes = nodes[:-1]
            o.set_line_nodes(nodes)
        else:
            rings = curves.auto_geometry_rings(o.raw_geometry(), tolerance)
            if rings:
                o.set_curve(rings)
                o.smooth = 0

    def auto_curves(self):
        sel = [o for o in self.selected_objects() if o.kind in ("shape", "line", "text")]
        if not sel:
            self.lbl_tip.setText("Eine Form auswählen – z. B. eine digitalisierte Fläche mit eckigen Kanten.")
            return
        for o in sel:
            self._auto_curve(o)
        self.sync_items([o.id for o in sel])
        self.commit()
        self.lbl_tip.setText("Rundungen erkannt. Mit »Punkte bearbeiten« (N) kannst du einzelne Punkte "
                             "nachträglich zu Ecke oder Rundung machen.")

    def insert_nodes(self):
        if self.canvas.has_node_selection() and self.canvas.insert_nodes():
            return
        if self.canvas.tool != "nodes":
            self.set_tool("nodes")
        self.lbl_tip.setText("Punkt einfügen: mit der Maus über die Kante fahren (es erscheint ein »+«) "
                             "und klicken – oder Punkte wählen und »Punkt einfügen« (Einfg) drücken. "
                             "Linien verlängern: Strg+Klick neben dem Linienende.")

    def join_nodes(self):
        """Punkte verbinden (Punkte-Werkzeug) bzw. ausgewählte Linien zu einer verbinden."""
        lines = [o for o in self.selected_objects() if o.kind == "line"]
        if len(lines) >= 2:
            self.join_lines(lines)
            return
        if self.canvas.has_node_selection():
            msg = self.canvas.join_nodes()
            if msg:
                self.lbl_tip.setText(msg)
                return
        if self.canvas.tool != "nodes":
            self.set_tool("nodes")
        self.lbl_tip.setText("Punkte verbinden: im Punkte-Werkzeug die beiden Endpunkte einer Linie "
                             "(schließt sie) oder benachbarte Punkte (fasst sie zusammen) mit Umschalt "
                             "wählen. Mehrere Linien verbinden: Linien auswählen, dann »Punkte verbinden«.")

    def _line_from_world(self, template, chain, closed=False):
        """Neue Linie aus Weltpunkten [[x, y, typ], …] (Stil von `template`, falls angegeben)."""
        o = template.clone() if template is not None else EmbObject("line", "Linie")
        o.rot, o.sx, o.sy = 0.0, 1.0, 1.0
        xs, ys = [p[0] for p in chain], [p[1] for p in chain]
        o.x, o.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        o.closed = closed
        o.set_line_nodes([[x - o.x, y - o.y, t] for x, y, t in chain])
        return o

    def connect_selected_nodes(self):
        t = self.canvas.selected_node_targets()
        if len(t) != 2:
            self.lbl_tip.setText("Genau zwei Punkte wählen (Umschalt+Klick) – oder das Werkzeug "
                                 "»Mit Linie verbinden« (K) nehmen und zwei Punkte anklicken.")
            return
        self.connect_points(*t)

    def connect_points(self, a, b):
        """Zwei Punkte mit einer Linie verbinden. Sind es Linienenden, wird die Linie geschlossen,
        verlängert bzw. mit der anderen Linie zusammengeführt – sonst entsteht eine neue Linie."""
        objs = {o.id: o for o in self.doc.objects}
        la = objs.get(a["obj"]) if a.get("end") else None
        lb = objs.get(b["obj"]) if b.get("end") else None
        world = lambda o: [[*o.to_world(x, y), t] for x, y, t in o.line_nodes()]

        def oriented(o, end, at_back):
            nodes = world(o)
            return nodes if (end == "end") == at_back else nodes[::-1]

        if la is not None and la is lb:
            nodes = oriented(la, a["end"], True)
            new = self._line_from_world(la, nodes, closed=True)
            new.id = la.id
            self._replace([la], [new])
            msg = "Linie geschlossen."
        elif la is not None and lb is not None:
            chain = oriented(la, a["end"], True) + oriented(lb, b["end"], False)
            new = self._line_from_world(la, chain)
            self._replace([la, lb], [new])
            msg = "Die beiden Linien wurden zu einer verbunden."
        elif la is not None or lb is not None:
            line, end, other = (la, a["end"], b) if la is not None else (lb, b["end"], a)
            chain = oriented(line, end, True) + [[*other["pt"], curves.CORNER]]
            new = self._line_from_world(line, chain)
            new.id = line.id
            self._replace([line], [new])
            msg = "Linie bis zum Punkt verlängert."
        else:
            src = objs.get(a.get("obj")) or objs.get(b.get("obj"))
            new = self._line_from_world(None, [[*a["pt"], curves.CORNER], [*b["pt"], curves.CORNER]])
            if src is not None:
                if src.kind == "line":
                    new.border = dict(src.border)
                else:
                    new.border["color"] = src.border["color"] if src.border["type"] != "none" \
                        else src.fill["color"]
            self._replace([], [new])
            msg = "Verbindungslinie erstellt."
        self.rebuild([new])
        self.commit()
        self.lbl_tip.setText(msg + " Nächste zwei Punkte anklicken – oder Esc.")

    # ------------------------------------------------------------------ Dichteprüfung
    DENSITY_WARN = 5.8     # mm Faden je mm² (≈ zwei volle Stichlagen übereinander) – gelb
    DENSITY_HIGH = 8.5     # ≈ drei Lagen übereinander: zu dicht (hart, Nadel-/Fadenbruch) – rot

    def toggle_density(self):
        if self.a_density.isChecked():
            self._update_density()
            self.lbl_tip.setText("Dichteprüfung: gelb = sehr dicht (etwa zwei Stichlagen übereinander), rot = zu "
                                 "dicht (drei Lagen und mehr, z. B. übereinanderliegende Flächen). "
                                 "Knopf erneut drücken zum Ausblenden.")
        else:
            self._remove_density()

    def _remove_density(self):
        it = getattr(self, "_density_item", None)
        if it is not None:
            self.scene.removeItem(it)
            self._density_item = None

    def density_grid(self, cell=0.25, half=6):
        """Fadenmenge (mm Faden je mm², gemittelt über ~3 mm) als Raster: (werte, minx, miny, zelle)."""
        import numpy as np
        segs = []
        for _, sts in self.doc.machine_blocks():
            last = None
            for x, y, f in sts:
                if f == STITCH:
                    if last is not None:
                        segs.append((last[0], last[1], x, y))
                    last = (x, y)
                elif f in (1, 2, 3):          # Sprung, Schnitt, Stopp: kein Faden auf dem Stoff
                    last = None
        if not segs:
            return None
        a = np.array(segs, dtype=float)
        ln = np.hypot(a[:, 2] - a[:, 0], a[:, 3] - a[:, 1])
        n = np.maximum(1, np.ceil(ln / cell)).astype(int)
        idx = np.repeat(np.arange(len(a)), n)
        t = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n) + 0.5) / np.repeat(n, n)
        px = a[idx, 0] + (a[idx, 2] - a[idx, 0]) * t
        py = a[idx, 1] + (a[idx, 3] - a[idx, 1]) * t
        w = np.repeat(ln / n, n)                       # Fadenlänge je Abtastpunkt
        minx, miny = px.min() - 3, py.min() - 3
        nx, ny = int((px.max() + 3 - minx) / cell) + 1, int((py.max() + 3 - miny) / cell) + 1
        H, _, _ = np.histogram2d(py, px, bins=[ny, nx], weights=w,
                                 range=[[miny, miny + ny * cell], [minx, minx + nx * cell]])
        k = half
        hp = np.pad(H, k)
        I = np.zeros((hp.shape[0] + 1, hp.shape[1] + 1))
        I[1:, 1:] = hp.cumsum(0).cumsum(1)
        m = 2 * k + 1
        S = I[m:, m:] - I[:-m, m:] - I[m:, :-m] + I[:-m, :-m]
        return S / (m * cell) ** 2, minx, miny, cell

    def _update_density(self):
        import numpy as np
        from PySide6.QtGui import QImage, QPixmap
        from PySide6.QtWidgets import QGraphicsPixmapItem
        self._remove_density()
        res = self.density_grid()
        if res is None:
            return
        dens, minx, miny, cell = res
        rgba = np.zeros(dens.shape + (4,), dtype=np.uint8)
        warn = dens >= self.DENSITY_WARN
        high = dens >= self.DENSITY_HIGH
        rgba[warn] = (251, 192, 45, 150)
        rgba[high] = (229, 57, 53, 180)
        img = QImage(rgba.tobytes(), dens.shape[1], dens.shape[0], dens.shape[1] * 4,
                     QImage.Format_RGBA8888).copy()
        it = QGraphicsPixmapItem(QPixmap.fromImage(img))
        it.setTransformationMode(Qt.SmoothTransformation)
        it.setPos(minx, miny)
        it.setScale(cell)
        it.setZValue(50_000)
        it.setAcceptedMouseButtons(Qt.NoButton)
        self.scene.addItem(it)
        self._density_item = it
        n_warn, n_high = int(warn.sum() * cell * cell), int(high.sum() * cell * cell)
        self.statusBar().showMessage(
            f"Dichteprüfung: {n_high} mm² zu dicht (rot), {n_warn} mm² sehr dicht (gelb)"
            if n_warn else "Dichteprüfung: keine zu dichten Stellen gefunden", 8000)

    def export_cutfile(self, path=None, offset=None):
        """Schneidedatei (SVG, Millimeter) für die Applikationsstoffe."""
        from shapely.geometry.polygon import orient
        from .controls import ask_values
        app = [o for o in self.doc.objects if o.visible and o.kind in ("shape", "text")
               and o.fill.get("type") == "applique"]
        sel = [o for o in self.selected_objects() if o.kind in ("shape", "text")]
        objs = app or sel
        if not objs:
            QMessageBox.information(self, APP, "Keine Applikation im Design. Wähle Formen aus oder "
                                    "stelle bei einer Form die Füllart »Applikation« ein.")
            return None
        if offset is None:
            v = ask_values(self, "Schneidedatei", [
                ("off", "Zugabe rundum", "num", -2.0, 5.0, 0.1, 1, " mm", 0.0,
                 "0 = genau die Form (der Satinrand deckt die Kante). Größer = etwas mehr Stoff, "
                 "z. B. für ausfransende Stoffe")],
                f"{len(objs)} Form(en) werden als Schneidelinien gespeichert – in Originalgröße "
                "(Millimeter), für Cricut, Brother ScanNCut, Silhouette & Co.")
            if not v:
                return None
            offset = v["off"]
        if path is None:
            base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "Design"
            path, _ = QFileDialog.getSaveFileName(self, "Schneidedatei speichern",
                                                  os.path.join(self._dir(), f"{base} Schneidedatei.svg"),
                                                  "SVG (*.svg)")
            if not path:
                return None
            if not path.lower().endswith(".svg"):
                path += ".svg"
        geoms = []
        for o in objs:
            g = o.world_geometry()
            if g is not None and not g.is_empty:
                geoms.append((o, g.buffer(offset, join_style=1) if offset else g))
        minx = min(g.bounds[0] for _, g in geoms) - 5
        miny = min(g.bounds[1] for _, g in geoms) - 5
        maxx = max(g.bounds[2] for _, g in geoms) + 5
        maxy = max(g.bounds[3] for _, g in geoms) + 5
        W, H = maxx - minx, maxy - miny
        paths = []
        for o, g in geoms:
            polys = list(g.geoms) if hasattr(g, "geoms") else [g]
            for poly in polys:
                if poly.geom_type != "Polygon":
                    continue
                poly = orient(poly)
                d = ""
                for ring in [poly.exterior] + list(poly.interiors):
                    pts = list(ring.coords)
                    d += "M" + " L".join(f"{x - minx:.2f},{y - miny:.2f}" for x, y in pts) + " Z "
                col = o.fill.get("color", "#000000")
                paths.append(f'  <path d="{d.strip()}" fill="none" stroke="{col}" '
                             f'stroke-width="0.3"><title>{o.name}</title></path>')
        svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
               f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" '
               f'viewBox="0 0 {W:.2f} {H:.2f}">\n'
               f'  <!-- StichWizard Schneidedatei: 1 Einheit = 1 mm, Zugabe {offset:g} mm -->\n'
               + "\n".join(paths) + "\n</svg>\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        self.lbl_tip.setText(f"Schneidedatei gespeichert ({len(paths)} Form(en), Originalgröße): {path}")
        return path

    def toggle_rulers(self):
        on = self.a_rulers.isChecked()
        self.prefs.set("rulers", on)
        self.canvas.show_rulers = on
        self.canvas.viewport().update()

    def open_multihoop(self):
        if not self.doc.objects:
            QMessageBox.information(self, APP, "Das Design ist noch leer.")
            return
        from .multihoop import MultiHoopDialog
        MultiHoopDialog(self).exec()

    def multi_export(self):
        from .multiexport import MultiExportDialog
        base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "Design"
        last = self.settings.value("lastFormat", "pes")
        dlg = MultiExportDialog(self.doc, self._dir(), base, (last, "dst"), self)
        if dlg.exec() and dlg.written:
            self.rebuild([o for o in self.doc.objects if o.kind == "text"])
            QMessageBox.information(self, "Mehrfach-Export",
                                    f"{len(dlg.written)} Datei(en) gespeichert in:\n"
                                    f"{os.path.dirname(dlg.written[0])}")

    # ------------------------------------------------ Satin-/Linienwerkzeuge (wie Ink/Stitch)
    def _sel_kind(self, *kinds):
        return [o for o in self.selected_objects() if o.kind in kinds]

    def line_to_satin(self):
        lines = self._sel_kind("line")
        if not lines:
            self.lbl_tip.setText("Zuerst eine oder mehrere Linien auswählen.")
            return
        new = []
        for o in lines:
            nodes = [[*o.to_world(x, y), t] for x, y, t in o.line_nodes()]
            if o.closed and nodes:
                nodes.append(list(nodes[0]))
            if len(nodes) < 2:
                continue
            w = o.border["width"] if o.border["type"] in ("satin", "zigzag", "estitch") else 3.0
            a, b = [], []
            n = len(nodes)
            for i, (x, y, t) in enumerate(nodes):
                p = nodes[i - 1] if i > 0 else (nodes[-2] if o.closed and n > 2 else nodes[i])
                q = nodes[i + 1] if i < n - 1 else (nodes[1] if o.closed and n > 2 else nodes[i])
                tx, ty = q[0] - p[0], q[1] - p[1]
                ln = math.hypot(tx, ty) or 1.0
                nx, ny = -ty / ln * w / 2, tx / ln * w / 2
                a.append([x + nx, y + ny, t])
                b.append([x - nx, y - ny, t])
            s = EmbObject("satin", "Satinsäule")
            allp = a + b
            s.x = (min(p[0] for p in allp) + max(p[0] for p in allp)) / 2
            s.y = (min(p[1] for p in allp) + max(p[1] for p in allp)) / 2
            s.set_satin([[x - s.x, y - s.y, t] for x, y, t in a], [[x - s.x, y - s.y, t] for x, y, t in b])
            s.fill.update(color=o.border["color"], density=o.border.get("density", 0.4), pull=0.2,
                          underlay=True)
            s.trim_after = o.trim_after
            new.append((o, s))
        for o, s in new:
            self._replace([o], [s], select=False)
        self.sync_items([s.id for _, s in new])
        self.rebuild([s for _, s in new])
        self.commit()
        self.lbl_tip.setText(f"{len(new)} Linie(n) in Säulen-Satin umgewandelt. Breite und Verlauf "
                             "lassen sich im Punkte-Werkzeug (N) anpassen.")

    def satin_to_line(self):
        sats = self._sel_kind("satin")
        if not sats:
            self.lbl_tip.setText("Zuerst eine Satinsäule auswählen.")
            return
        new = []
        for o in sats:
            a, b = o.curve
            mid = [[*o.to_world((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), p[2]] for p, q in zip(a, b)]
            ln = self._line_from_world(None, mid)
            ln.border.update(type="run", color=o.fill["color"])
            ln.trim_after = o.trim_after
            new.append((o, ln))
        for o, ln in new:
            self._replace([o], [ln], select=False)
        self.sync_items([ln.id for _, ln in new])
        self.rebuild([ln for _, ln in new])
        self.commit()
        self.lbl_tip.setText("In Linie umgewandelt (Steppstich). Stichart rechts unter »Linie« ändern.")

    def reverse_direction(self):
        objs = self._sel_kind("line", "satin")
        if not objs:
            self.lbl_tip.setText("Zuerst eine Linie oder Satinsäule auswählen.")
            return
        for o in objs:
            if o.kind == "line":
                o.set_line_nodes(o.line_nodes()[::-1])
            else:
                a, b = o.curve
                o.set_satin(a[::-1], b[::-1])
        self.rebuild(objs)
        self.commit()
        self.canvas.viewport().update()
        self.lbl_tip.setText("Stickrichtung umgekehrt – Start und Ende sind vertauscht.")

    def auto_satin(self):
        """Satinsäulen (und Satinlinien) einer Farbe zu einem durchgehenden Weg ordnen: jeweils
        das nächstgelegene Säulenende anschließen, Richtung passend drehen, Verbindungen laufen
        beim Sticken als Steppstich unter den Säulen (model.autosatin_link)."""
        objs = [o for o in self.selected_objects() if o.kind == "satin" or
                (o.kind == "line" and o.border.get("type") == "satin")]
        if len(objs) < 2:
            self.lbl_tip.setText("Auto-Satin: mindestens zwei Satinsäulen oder Satinlinien auswählen.")
            return

        def ends(o):
            if o.kind == "satin":
                a, b = o.curve
                h = o.to_world((a[0][0] + b[0][0]) / 2, (a[0][1] + b[0][1]) / 2)
                t = o.to_world((a[-1][0] + b[-1][0]) / 2, (a[-1][1] + b[-1][1]) / 2)
            else:
                n = o.line_nodes()
                h, t = o.to_world(n[0][0], n[0][1]), o.to_world(n[-1][0], n[-1][1])
                if o.border.get("underlay", True) and o.border.get("width", 3.0) >= 1.2:
                    t = h          # Satinlinie mit Unterlage: hin Unterlage, zurück Satin
            return h, t

        def flip(o):
            if o.kind == "satin":
                a, b = o.curve
                o.set_satin(a[::-1], b[::-1])
            else:
                o.set_line_nodes(o.line_nodes()[::-1])

        import uuid
        order = []
        for color in dict.fromkeys((o.fill["color"] if o.kind == "satin" else o.border["color"]).upper()
                                   for o in objs):
            rest = [o for o in objs if (o.fill["color"] if o.kind == "satin"
                                        else o.border["color"]).upper() == color]
            gid = uuid.uuid4().hex[:8]
            # Start: das Säulenende ganz links
            first = min(rest, key=lambda o: min(ends(o)[0][0], ends(o)[1][0]))
            h, t = ends(first)
            if t[0] < h[0]:
                flip(first)
            rest.remove(first)
            chain = [first]
            while rest:
                pos = ends(chain[-1])[1]
                nxt = min(rest, key=lambda o: min(engine.dist(pos, e) for e in ends(o)))
                h, t = ends(nxt)
                if engine.dist(pos, t) < engine.dist(pos, h):
                    flip(nxt)
                rest.remove(nxt)
                chain.append(nxt)
            for o in chain:
                o.fill["autosatin"] = gid
                o.fill["start"] = o.fill["end"] = None
                o.trim_after = "auto"
            order += chain
        # zusammenhängend an der Stelle der ersten Säule einordnen
        self._replace(order, order)
        self.rebuild(order)
        self.commit()
        before = len(objs) - 1
        self.lbl_tip.setText(f"Auto-Satin: {len(order)} Säulen verbunden – Wege laufen verdeckt "
                             f"unter den Säulen, wo es geht (sonst Sprung). Vorher bis zu {before} "
                             "Sprünge.")

    def multicolor_satin(self):
        objs = self._sel_kind("satin")
        if len(objs) != 1:
            self.lbl_tip.setText("Mehrfarbiger Satin: genau eine Satinsäule auswählen.")
            return
        from .widgets import MultiSatinDialog
        o = objs[0]
        dlg = MultiSatinDialog(o.fill["color"], self)
        if not dlg.exec():
            return
        colors, overlap = dlg.values()
        a, b = o.curve
        n = len(colors)
        new = []
        for i, col in enumerate(colors):
            t0 = max(0.0, i / n - (overlap / 2 if i else 0))
            t1 = min(1.0, (i + 1) / n + (overlap / 2 if i < n - 1 else 0))
            lerp = lambda p, q, t: [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t, p[2]]
            c = o.clone()
            c.set_satin([lerp(p, q, t0) for p, q in zip(a, b)], [lerp(p, q, t1) for p, q in zip(a, b)])
            c.fill["color"] = col
            c.fill["underlay"] = o.fill.get("underlay", True) and i == 0
            c.name = f"{o.name} {i + 1}"
            new.append(c)
        self._replace([o], new)
        self.rebuild(new)
        self.commit()
        self.lbl_tip.setText(f"Satinsäule in {n} farbige Streifen geteilt (Überlappung "
                             f"{overlap * 100:.0f} %).")

    def cut_satin(self):
        st = self.canvas._node_state() if self.canvas.tool == "nodes" else None
        if not st or st["obj"].kind != "satin" or len({i for _, i in self.canvas._node_sel}) != 1:
            if self.canvas.tool != "nodes":
                self.set_tool("nodes")
            self.lbl_tip.setText("Satin teilen: im Punkte-Werkzeug einen Punkt (ein Paar) in der Mitte "
                                 "der Satinsäule anklicken, dann »Satin teilen«.")
            return
        o = st["obj"]
        i = next(iter({i for _, i in self.canvas._node_sel}))
        a, b = o.curve
        if i <= 0 or i >= len(a) - 1:
            self.lbl_tip.setText("Am Ende der Säule gibt es nichts zu teilen – ein Paar in der Mitte wählen.")
            return
        o2 = o.clone()
        o.set_satin(a[:i + 1], b[:i + 1])
        o2.set_satin([list(p) for p in a[i:]], [list(p) for p in b[i:]])
        self._replace([o], [o, o2])
        self.rebuild([o, o2])
        self.commit()
        self.lbl_tip.setText("Satinsäule in zwei Säulen geteilt.")

    def to_centerline(self):
        from .centerline import centerlines
        objs = self._sel_kind("shape", "text")
        if not objs:
            self.lbl_tip.setText("Zuerst eine (schmale) Fläche oder einen Schriftzug auswählen.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            new = []
            for o in objs:
                for pts in centerlines(o.world_geometry()):
                    ln = self._line_from_world(None, [[x, y, curves.CORNER] for x, y in pts])
                    ln.border.update(type="run", color=o.fill["color"] if o.fill["type"] != "none"
                                     else o.border["color"])
                    new.append(ln)
        finally:
            QApplication.restoreOverrideCursor()
        if not new:
            self.lbl_tip.setText("Keine Mittellinie gefunden – die Fläche ist zu klein oder zu breit.")
            return
        for o in objs:
            o.visible = False                     # Original ausblenden (nicht löschen)
        self._replace([], new)
        self.rebuild(new)
        self.commit()
        self.lbl_tip.setText(f"{len(new)} Mittellinie(n) erzeugt, Original ausgeblendet (rechts unter "
                             "»Objekte« wieder einblendbar). Stichart z. B. auf Satin stellen.")

    def outline_from_stitches(self):
        objs = self._sel_kind("stitches")
        if not objs:
            self.lbl_tip.setText("Zuerst eine importierte Stickdatei auswählen.")
            return
        from shapely.geometry import MultiLineString
        new = []
        for o in objs:
            for col, sts in o.world_blocks():
                runs, cur = [], []
                for x, y, f in sts:
                    if f == STITCH:
                        cur.append((x, y))
                    elif cur:
                        runs.append(cur)
                        cur = []
                if cur:
                    runs.append(cur)
                runs = [r for r in runs if len(r) >= 2]
                if not runs:
                    continue
                g = MultiLineString(runs).buffer(0.35, quad_segs=2).buffer(-0.1)
                g = g.simplify(0.15, preserve_topology=True)
                parts = [p for p in engine.polygons_of(g) if p.area > 2.0]
                if not parts:
                    continue
                from shapely.ops import unary_union as _uu
                s = EmbObject("shape", f"Umriss {thread_name(col)}")
                s.set_geometry(_uu(parts))
                s.fill.update(type="tatami", color=col)
                new.append(s)
            o.visible = False
        if not new:
            self.lbl_tip.setText("Aus dieser Stickdatei ließ sich kein Umriss gewinnen.")
            return
        self._replace([], new)
        self.rebuild(new)
        self.commit()
        self.lbl_tip.setText(f"{len(new)} Form(en) aus der Stickdatei erzeugt, Stickdatei ausgeblendet. "
                             "Mit »Rundungen erkennen« werden die Konturen glatter.")

    def add_knockdown(self):
        objs = [o for o in self.selected_objects() if o.kind != "stitches"] or \
            [o for o in self.selected_objects()]
        if not objs:
            self.lbl_tip.setText("Zuerst die Objekte auswählen, unter die der Knockdown soll.")
            return
        from shapely.ops import unary_union as _uu
        geoms = []
        for o in objs:
            g = o.world_geometry()
            if g is not None and not g.is_empty:
                geoms.append(g.buffer(0.3) if g.geom_type in ("LineString", "MultiLineString") else g)
        if not geoms:
            return
        area = _uu(geoms).buffer(1.5, join_style=1).buffer(-0.5)
        k = EmbObject("shape", "Knockdown")
        k.set_geometry(area)
        k.fill.update(type="tatami", color=self.doc.fabric, density=1.4, stitch_len=4.5,
                      underlay=False, pull=0.0, angle=135.0, pattern="standard")
        idx = min(self.doc.objects.index(o) for o in objs)
        self.doc.objects.insert(idx, k)
        self.sync_items([k.id])
        self.rebuild([k])
        self.commit()
        self.lbl_tip.setText("Knockdown-Fläche in Stofffarbe unter den Objekten angelegt – sie wird "
                             "zuerst gestickt und drückt den Flor nieder.")

    # ------------------------------------- Pfade, Redwork, Start/Ende (wie Ink/Stitch)
    def _world_polyline(self, o):
        g = o.world_geometry()
        return [tuple(p[:2]) for p in g.coords] if g is not None and not g.is_empty else []

    def text_to_path(self):
        texts, lines = self._sel_kind("text"), self._sel_kind("line")
        if len(texts) != 1 or len(lines) != 1:
            self.lbl_tip.setText("Text an Pfad: genau einen Schriftzug und eine Linie auswählen "
                                 "(Umschalt+Klick), dann »Text an Pfad«.")
            return
        t, ln = texts[0], lines[0]
        pts = self._world_polyline(ln)
        if len(pts) < 2:
            return
        self.set_text_path(t, pts)
        self.doc.objects.remove(ln)
        self.sync_items([t.id])
        self.rebuild([t])
        self.commit()
        self.lbl_tip.setText("Schriftzug steht auf dem Pfad. Rechts unter »Am Pfad«: Ausrichtung und "
                             "Seite · »Pfad lösen« macht die Linie wieder frei.")

    @staticmethod
    def set_text_path(t, pts):
        """Schriftzug auf den Pfad `pts` (Weltkoordinaten) setzen."""
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        t.x, t.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        t.rot, t.sx, t.sy = 0.0, 1.0, 1.0
        t.text = dict(t.text, path=[[x - t.x, y - t.y] for x, y in pts], arc=0.0)

    @staticmethod
    def set_guide(o, pts):
        """Geführte Füllung mit der Führungslinie `pts` (Weltkoordinaten)."""
        o.fill.update(type="guided", guide=[list(o.to_local(x, y)) for x, y in pts])

    def assign_guide(self):
        areas = [o for o in self.selected_objects() if o.kind in ("shape", "text")
                 and not (o.kind == "text" and o.text.get("embfont"))]
        lines = self._sel_kind("line")
        if not areas or len(lines) != 1:
            self.lbl_tip.setText("Geführte Füllung: eine oder mehrere Flächen und genau eine Linie "
                                 "(die Führungslinie) auswählen, dann »Geführte Füllung«.")
            return
        ln = lines[0]
        pts = self._world_polyline(ln)
        for o in areas:
            self.set_guide(o, pts)
        self.doc.objects.remove(ln)
        self.sync_items([o.id for o in areas])
        self.rebuild(areas)
        self.commit()
        self.lbl_tip.setText("Geführte Füllung: die Reihen folgen jetzt der Linie (lila gestrichelt, "
                             "wenn ausgewählt). »Pfad lösen« macht sie wieder zur Linie.")

    def detach_path(self):
        new, changed = [], []
        for o in self.selected_objects():
            pts, label = None, "Führungslinie"
            if o.kind == "text" and o.text.get("path"):
                pts, label = [o.to_world(*p) for p in o.text["path"]], "Pfad"
                o.text = dict(o.text, path=None)
                o.sx, o.sy = (1 if o.sx >= 0 else -1), (1 if o.sy >= 0 else -1)
            elif o.kind in ("shape", "text") and o.fill.get("guide"):
                pts = [o.to_world(*p) for p in o.fill["guide"]]
                o.fill.update(guide=None, type="tatami" if o.fill["type"] == "guided" else o.fill["type"])
            if not pts:
                continue
            ln = self._line_from_world(None, [[x, y, curves.CORNER] for x, y in pts])
            ln.border.update(type="run", color="#7E57C2")
            ln.name = label
            new.append(ln)
            changed.append(o)
        if not new:
            self.lbl_tip.setText("Pfad lösen: einen Schriftzug am Pfad oder eine Fläche mit geführter "
                                 "Füllung auswählen.")
            return
        idx = min(self.doc.objects.index(o) for o in changed)
        self.doc.objects[idx:idx] = new
        self.sync_items([o.id for o in changed])
        self.rebuild(changed)
        self.commit()
        self.lbl_tip.setText(f"{len(new)} Linie(n) wiederhergestellt – sie werden als Steppstich "
                             "gestickt, bis du sie wieder zuordnest oder löschst.")

    def route_lines(self, mode):
        lines = sorted(self._sel_kind("line"), key=self.doc.objects.index)
        if not lines:
            self.lbl_tip.setText(("Redwork" if mode == "redwork" else "Auto-Route") +
                                 ": zuerst die Linien auswählen (Strg+A oder Rahmen ziehen).")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            paths, info = self.route_objects(lines, mode)
        finally:
            QApplication.restoreOverrideCursor()
        title = "Redwork" if mode == "redwork" else "Auto-Route"
        jumps = max(0, len(paths) - 1)
        what = "jede Strecke zweimal" if mode == "redwork" else \
            f"{info['doubled']} von {info['edges']} Strecken doppelt"
        self.lbl_tip.setText(f"{title}: {len(lines)} Linie(n) → {len(paths)} durchgehende(r) Weg(e), "
                             f"{what}" + (f", {jumps} Sprung/Sprünge zwischen getrennten Teilen."
                                          if jumps else ", ohne Sprung."))

    def route_objects(self, lines, mode):
        """Linien (in Stickreihenfolge) durch durchgehende Wege ersetzen -> (neue Linien, info)."""
        from . import redwork
        polys = [self._world_polyline(o) for o in lines]
        polys = [p for p in polys if len(p) >= 2]
        paths, info = redwork.route(polys, mode, start=polys[0][0] if polys else None)
        tpl = lines[0]
        title = "Redwork" if mode == "redwork" else "Auto-Route"
        new = []
        for i, pts in enumerate(paths):
            ln = self._line_from_world(tpl, [[x, y, curves.CORNER] for x, y in pts])
            ln.smooth = 0
            ln.name = title + (f" {i + 1}" if len(paths) > 1 else "")
            if ln.border["type"] not in ("run", "triple"):
                ln.border["type"] = "run"
            ln.border["corners"] = True
            new.append(ln)
        self._replace(lines, new)
        self.rebuild(new)
        self.commit()
        return new, info

    def _point_targets(self):
        return [o for o in self.selected_objects()
                if o.kind == "satin" or (o.kind in ("shape", "text") and
                                         not (o.kind == "text" and o.text.get("embfont")))]

    def pick_point(self, kind):
        objs = self._point_targets()
        if len(objs) != 1:
            self.lbl_tip.setText("Start-/Endpunkt: zuerst genau eine Fläche oder Satinsäule auswählen.")
            return
        self.set_tool("select")
        self._pick = (kind, objs[0].id)
        self.canvas.set_tool("pick")
        self.canvas.setFocus()
        self.lbl_tip.setText(("Startpunkt" if kind == "start" else "Endpunkt") +
                             " anklicken (auf oder nahe der Form) · Esc/Rechtsklick = abbrechen")

    def on_point_picked(self, x, y):
        pick, self._pick = self._pick, None
        if pick and pick[0] == "color":
            self.set_tool("select")
            self._pick_template_color(x, y)
            return
        o = self.doc.find(pick[1]) if pick else None
        if o is not None:
            o.fill[pick[0]] = [round(v, 3) for v in o.to_local(x, y)]
            self.rebuild([o])
            self.commit()
            self.props.refresh()
        self.set_tool("select")
        if o is not None:
            self.lbl_tip.setText(("Startpunkt" if pick[0] == "start" else "Endpunkt") +
                                 " gesetzt (grün S / rot E, wenn ausgewählt).")

    def clear_points(self):
        objs = [o for o in self._point_targets() if o.fill.get("start") or o.fill.get("end")]
        for o in objs:
            o.fill.update(start=None, end=None)
        if objs:
            self.rebuild(objs)
            self.commit()
            self.props.refresh()
        self.lbl_tip.setText("Start- und Endpunkt entfernt – die Reihenfolge wird wieder "
                             "automatisch gewählt." if objs else "Keine Start-/Endpunkte gesetzt.")

    def on_letter_moved(self, o, i, dx, dy):
        """Buchstabe im Punkte-Werkzeug gezogen: Versatz zum gespeicherten Wert addieren."""
        letters = {k: list(v) for k, v in (o.text.get("letters") or {}).items()}
        v = letters.get(str(i), [0.0, 0.0, 0.0, 100.0])
        v[0] = round(v[0] + dx, 2)
        v[1] = round(v[1] + dy, 2)
        if v == [0.0, 0.0, 0.0, 100.0]:
            letters.pop(str(i), None)
        else:
            letters[str(i)] = v
        o.text = dict(o.text, letters=letters)
        self.rebuild([o])
        self.commit()
        self.props.refresh()
        self.props.select_letter(i)
        self.lbl_tip.setText(f"Buchstabe {i + 1} verschoben – Umschalt beim Ziehen = nur waagerecht "
                             "(Laufweite). Feinwerte rechts unter »Einzelne Buchstaben«.")

    def _letter_selected_in_panel(self, i):
        self.canvas.letter_sel = i
        self.canvas.viewport().update()

    def on_props_action(self, act):
        {"pick_start": lambda: self.pick_point("start"), "pick_end": lambda: self.pick_point("end"),
         "clear_points": self.clear_points, "detach": self.detach_path,
         "group": self.group_selected, "ungroup": self.ungroup_selected,
         "cross_edit": self.open_cross, "print_edit": self.open_paint,
         "print_sheet": self.export_print_sheet}[act]()

    def join_lines(self, lines):
        """Offene Linien zu einer Linie verketten – immer das nächstgelegene Ende anhängen."""
        lines = [o for o in lines if not o.closed]
        if len(lines) < 2:
            self.lbl_tip.setText("Zum Verbinden mindestens zwei offene Linien auswählen.")
            return
        order = sorted(lines, key=self.doc.objects.index)
        world = lambda o: [[*o.to_world(x, y), t] for x, y, t in o.line_nodes()]
        chain = world(order[0])
        rest = [world(o) for o in order[1:]]
        while rest:
            best = None
            for k, nodes in enumerate(rest):
                for flip_chain in (False, True):
                    for flip in (False, True):
                        end = chain[0] if flip_chain else chain[-1]
                        start = nodes[-1] if flip else nodes[0]
                        d = math.hypot(end[0] - start[0], end[1] - start[1])
                        if best is None or d < best[0]:
                            best = (d, k, flip_chain, flip)
            d, k, flip_chain, flip = best
            nodes = rest.pop(k)
            if flip_chain:
                chain.reverse()
            if flip:
                nodes = nodes[::-1]
            if d < 0.3:                      # Enden liegen aufeinander: Punkt nur einmal
                nodes = nodes[1:]
            chain += nodes
        closed = len(chain) > 3 and math.hypot(chain[0][0] - chain[-1][0], chain[0][1] - chain[-1][1]) < 0.3
        if closed:
            chain.pop()
        o = order[0].clone()
        o.rot, o.sx, o.sy = 0.0, 1.0, 1.0
        xs, ys = [p[0] for p in chain], [p[1] for p in chain]
        o.x, o.y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        o.closed = closed
        o.set_line_nodes([[x - o.x, y - o.y, t] for x, y, t in chain])
        self._replace(order, [o])
        self.rebuild([o])
        self.commit()
        self.lbl_tip.setText(f"{len(order)} Linien zu einer verbunden" + (" (geschlossen)." if closed else "."))

    def break_nodes(self):
        """Linie am gewählten Punkt auftrennen."""
        st = self.canvas._node_state() if self.canvas.has_node_selection() else None
        if not st or st["obj"].kind != "line" or len(self.canvas._node_sel) != 1:
            if self.canvas.tool != "nodes":
                self.set_tool("nodes")
            self.lbl_tip.setText("Auftrennen: im Punkte-Werkzeug genau einen Punkt einer Linie wählen. "
                                 "Flächen-Formen lassen sich nicht auftrennen.")
            return
        o = st["obj"]
        (_, i), = self.canvas._node_sel
        nodes = o.line_nodes()
        if o.closed:
            o.closed = False
            o.set_line_nodes(nodes[i:] + nodes[:i] + [list(nodes[i])])
            new = [o]
            msg = "Linie am Punkt geöffnet."
        else:
            if i == 0 or i == len(nodes) - 1:
                self.lbl_tip.setText("Am Endpunkt gibt es nichts aufzutrennen – einen Punkt in der "
                                     "Linie wählen.")
                return
            b = o.clone()
            o.set_line_nodes(nodes[:i + 1])
            b.set_line_nodes([list(p) for p in nodes[i:]])
            new = [o, b]
            msg = "Linie in zwei Linien geteilt."
        self._replace([o], new)
        self.rebuild(new)
        self.commit()
        self.lbl_tip.setText(msg)

    def set_node_type(self, t):
        if self.canvas.has_node_selection():
            self.canvas.set_node_type(t)
        else:
            self.set_tool("nodes")
            self.lbl_tip.setText("Punkte anklicken (Umschalt = mehrere) und dann »Ecke« oder "
                                 "»Rundung« wählen – oder Rechtsklick auf einen Punkt.")

    def cut_selected(self):
        """Obere Formen (später in der Reihenfolge) aus der untersten ausschneiden."""
        sel = [o for o in self.selected_objects() if o.kind in ("shape", "text")]
        if len(sel) < 2:
            self.lbl_tip.setText("Zum Ausschneiden zwei Formen auswählen: die Form und das, was "
                                 "herausgeschnitten werden soll (darüber liegend).")
            return
        sel.sort(key=self.doc.objects.index)
        target, cutters = sel[0], sel[1:]
        tw = target.world_geometry()
        inside = all(tw.buffer(1e-6).contains(c.world_geometry()) and not c.smooth for c in cutters)
        if inside and not target.smooth:
            # Loch komplett innen: als Pfad anhängen, Ecken und Rundungen bleiben erhalten
            rings = self._curve_rings(target)
            for c in cutters:
                for r in self._curve_rings(c):
                    rings.append([[*target.to_local(*c.to_world(x, y)), t] for x, y, t in r])
            target.set_curve(rings)
        else:
            cut = unary_union([c.world_geometry() for c in cutters])
            local = affinity.affine_transform(cut, self._inverse_matrix(target))
            rest = target.raw_geometry().difference(local)
            if rest.is_empty:
                return
            target.set_raw_geometry(rest)
        ids = {c.id for c in cutters}
        self.doc.objects = [o for o in self.doc.objects if o.id not in ids]
        self.sync_items([target.id])
        self.commit()

    @staticmethod
    def _cover_area(o):
        """Fläche, die ein Objekt mit Stichen deckt (für »Überlappung entfernen«) oder None."""
        if not o.visible:
            return None
        g = o.world_geometry()
        if g is None or g.is_empty:
            return None
        if o.kind in ("shape", "text"):
            return g if o.fill.get("type", "none") not in ("none",) else None
        if o.kind == "satin":
            return g
        if o.kind == "line" and o.border.get("type") == "satin":
            return g.buffer(o.border.get("width", 3.0) / 2, cap_style=2)
        return None

    def puff_selected(self):
        """3D-Puff einrichten (wie die Puff-Voreinstellung in Profi-Programmen)."""
        sel = [o for o in self.selected_objects() if o.kind in ("satin", "line", "shape", "text")]
        if not sel:
            self.lbl_tip.setText("3D-Puff: zuerst Satinsäulen, Satinlinien oder Schriftzüge auswählen.")
            return
        narrow = 0
        for o in sel:
            if o.kind == "satin":
                o.fill.update(puff=True, satin_ul="center", density=0.25, pull=0.0, split_len=15.0,
                              short_inset=0.0, auto_spacing=False, width_random=0.0,
                              spacing_random=0.0, underlay=True)
                ra, rb, _ = o.satin_rails()
                w = min(engine.dist(a, b) for a, b in zip(ra[::3], rb[::3])) * abs(o.sx)
                narrow += w < 3.0
            elif o.kind == "line":
                o.border.update(type="satin", density=0.25, underlay=False, auto_spacing=False,
                                width=max(3.0, o.border.get("width", 3.0)))
                o.fill["puff"] = True
            else:
                if o.kind == "text" and o.text.get("embfont"):
                    o.text["emb_density"] = 0.25
                elif o.fill.get("type") not in ("none", "applique"):
                    o.fill.update(type="satin", density=0.25, underlay=False)
                o.fill.update(puff=True, auto_spacing=False, underlay=False)
            o.trim_after = "auto"
        # Puff zuletzt sticken; davor hält die Maschine an (Schaumstoff auflegen)
        rest = [o for o in self.doc.objects if o not in sel]
        self.doc.objects = rest + sorted(sel, key=self.doc.objects.index)
        flat = [o for o in rest if o.visible and not o.fill.get("puff")]
        if flat:
            flat[-1].trim_after = "stop"
        self.sync_items([o.id for o in sel])
        self.rebuild(sel)
        self.commit()
        msg = (f"3D-Puff für {len(sel)} Objekt(e): " +
               (f"Nach »{flat[-1].name}« stoppt die Maschine – " if flat else "Vor dem Sticken ") +
               "Schaumstoff (2–3 mm, in Garnfarbe) auflegen, weitersticken, dann den Schaum "
               "abreißen und Reste kurz mit Heißluft schrumpfen.")
        if narrow:
            msg += f" Achtung: {narrow} Säule(n) schmaler als 3 mm – Puff wirkt erst ab ~3 mm."
        self.lbl_tip.setText(msg)

    def remove_overlaps(self):
        """Verdeckte Bereiche aus Flächen herausnehmen: Was ein später gesticktes Objekt
        überdeckt, muss darunter nicht gestickt werden. `keep` mm bleiben überlappend."""
        objs = self.selected_objects() or list(self.doc.objects)
        keep, ok = QInputDialog.getDouble(
            self, "Überlappung entfernen",
            "Verdeckte Bereiche unter später gestickten Objekten werden nicht mehr doppelt "
            "gestickt.\nSo viel bleibt am Rand überlappend (gegen Lücken durch Verzug):",
            1.0, 0.3, 4.0, 1)
        if not ok:
            return
        order = self.doc.objects
        changed, skipped, saved, small = [], 0, 0, 0
        for o in objs:
            if o.kind != "shape" or o.fill.get("type") in ("none", "applique") or not o.visible:
                continue
            later = [self._cover_area(x) for x in order[order.index(o) + 1:]]
            later = [g for g in later if g is not None]
            if not later:
                continue
            cover = unary_union(later).buffer(-keep)
            if cover.is_empty:
                continue
            world = o.world_geometry()
            if not world.intersects(cover):
                continue
            if o.border.get("type", "none") != "none":
                skipped += 1        # Rand würde sonst der neuen Kontur folgen
                continue
            rest = world.difference(cover)
            rest = unary_union([p for p in engine.polygons_of(rest) if p.area > 0.5])
            if rest.is_empty:
                continue
            before = sum(len(b) for _, b in o.stitch_blocks())
            old = (o.geom_wkt, o.curve)
            o.set_raw_geometry(affinity.affine_transform(rest, self._inverse_matrix(o)))
            after = sum(len(b) for _, b in o.stitch_blocks())
            if after > before * 0.97:       # lohnt nicht (kleine Überdeckung, mehr Wege)
                o.geom_wkt, o.curve = old
                o._gkey = o._skey = None
                small += 1
                continue
            saved += before - after
            changed.append(o)
        if changed:
            self.rebuild(changed)
            self.commit()
        msg = (f"{len(changed)} Fläche(n) angepasst – {max(0, saved):,} Stiche weniger."
               .replace(",", ".") if changed else "Keine verdeckten Bereiche gefunden.")
        if skipped:
            msg += (f" {skipped} Form(en) mit Rand übersprungen (der Rand würde sonst der neuen "
                    "Kontur folgen).")
        if small:
            msg += (f" {small} Form(en) unverändert – dort spart das Aussparen kaum Stiche "
                    "(kleine Überdeckung, mehr Wege).")
        self.lbl_tip.setText(msg)

    def cleanup_small(self):
        """Winzige Teile entfernen: Flächenstücke und Löcher unter `area` mm², Linien unter
        2 mm, Objekte, von denen nichts übrig bleibt."""
        objs = self.selected_objects() or list(self.doc.objects)
        area, ok = QInputDialog.getDouble(
            self, "Kleinteile entfernen", "Flächenstücke und Löcher kleiner als (mm²) entfernen:",
            2.0, 0.2, 50.0, 1)
        if not ok:
            return
        from shapely.geometry import Polygon as _Poly
        changed, removed, parts = [], [], 0
        for o in objs:
            if o.kind == "shape":
                g = o.raw_geometry()
                polys = engine.polygons_of(g)
                keep = []
                for p in polys:
                    if p.area * abs(o.sx * o.sy) < area:
                        parts += 1
                        continue
                    holes = [r for r in p.interiors if _Poly(r).area * abs(o.sx * o.sy) >= area]
                    parts += len(p.interiors) - len(holes)
                    keep.append(_Poly(p.exterior, holes))
                if not keep:
                    removed.append(o)
                elif len(keep) != len(polys) or sum(len(p.interiors) for p in keep) != \
                        sum(len(p.interiors) for p in polys):
                    o.set_raw_geometry(unary_union(keep))
                    changed.append(o)
            elif o.kind == "line":
                g = o.world_geometry()
                if g is not None and g.length < 2.0:
                    removed.append(o)
        if removed:
            ids = {o.id for o in removed}
            self.doc.objects = [o for o in self.doc.objects if o.id not in ids]
            self.sync_items()
        if changed:
            self.rebuild(changed)
        if changed or removed:
            self.commit()
            self.lbl_tip.setText(f"Aufgeräumt: {parts} Kleinteil(e) aus {len(changed)} Form(en) "
                                 f"entfernt, {len(removed)} winzige(s) Objekt(e) gelöscht.")
        else:
            self.lbl_tip.setText("Nichts zu entfernen – keine Teile unter dieser Größe.")

    # ============================================================ Gestalten (wie Inkscape)
    def _shapes_sel(self, n=2, what="Formen"):
        sel = [o for o in self.selected_objects() if o.kind in ("shape", "text") and
               not (o.kind == "text" and o.text.get("embfont"))]
        if len(sel) < n:
            self.lbl_tip.setText(f"Dafür mindestens {n} {what} auswählen "
                                 "(Stickschriften vorher »In Form umwandeln«).")
            return None
        return sorted(sel, key=self.doc.objects.index)

    @staticmethod
    def _shape_like(geom, template, name=None):
        """Neue Form aus Weltgeometrie mit dem Stil von `template`."""
        o = EmbObject("shape", name or template.name)
        o.layer = template.layer
        o.set_geometry(geom)
        o.fill = dict(template.fill, angle=template.fill["angle"] + template.rot,
                      start=None, end=None, guide=None)
        o.border = dict(template.border)
        o.trim_after = template.trim_after
        return o

    def shadow_selected(self):
        """Schatten-Effekt: versetzte Kopie der Auswahl dahinter (wie »Drop Shadow« in Hatch)."""
        from shapely import affinity
        from shapely.ops import unary_union
        from .controls import ask_values
        sel = [o for o in self.selected_objects() if o.visible and o.kind != "stitches"
               and o.world_geometry() is not None]
        if not sel:
            self.lbl_tip.setText("Schatten: zuerst Schriftzüge oder Formen auswählen.")
            return
        v = ask_values(self, "Schatten", [
            ("dx", "Versatz nach rechts", "num", -20.0, 20.0, 0.1, 1, " mm", 1.2),
            ("dy", "Versatz nach unten", "num", -20.0, 20.0, 0.1, 1, " mm", 1.2),
            ("kind", "Art", "choice", [("Fläche (Satin/Tatami)", "fill"),
                                       ("Nur Kontur (Satin)", "outline")], "fill"),
            ("color", "Farbe", "choice", [("Dunkelgrau", "#3A3A3A"), ("Schwarz", "#111111"),
                                          ("Mittelgrau", "#8A8A8A"), ("Dunkelblau", "#1A237E"),
                                          ("Gold", "#C9A227")], "#3A3A3A"),
            ("cut", "Verdeckten Teil aussparen (weniger Stiche)", "check", True)],
            "Der Schatten wird vor der Auswahl gestickt und liegt dahinter. Kleine Versätze "
            "(1–2 mm) wirken am besten.")
        if not v:
            return
        geoms = []
        for o in sel:
            g = o.world_geometry()
            if g.area <= 0:
                g = g.buffer(max(0.4, o.border.get("width", 1.0) / 2))
            geoms.append(g)
        base = unary_union(geoms)
        sh = affinity.translate(base, v["dx"], v["dy"])
        if v["cut"]:
            sh = sh.difference(base.buffer(-0.4))        # 0,4 mm Überlappung gegen Lücken
        sh = sh.buffer(0)
        if sh.is_empty or sh.area < 0.5:
            self.lbl_tip.setText("Schatten: der Versatz ist zu klein – nichts sichtbar.")
            return
        o = EmbObject("shape", "Schatten")
        o.layer = sel[0].layer
        o.set_geometry(sh)
        if v["kind"] == "outline":
            o.fill.update(type="none")
            o.border.update(type="satin", width=1.2, color=v["color"])
        else:
            # schmale Schattenränder als Satin, breite als Tatami (wie bei Schriften üblich)
            o.fill.update(type="satin" if max(abs(v["dx"]), abs(v["dy"])) <= 3 else "tatami",
                          color=v["color"], angle=45.0)
            o.border.update(type="none")
        if len({x.group for x in sel}) == 1 and sel[0].group:
            o.group = sel[0].group
        idx = min(self.doc.objects.index(x) for x in sel)
        self.doc.objects.insert(idx, o)
        self.sync_items([x.id for x in sel])
        self.rebuild([o])
        self.commit()
        self.lbl_tip.setText("Schatten erzeugt – er wird vor der Auswahl gestickt. Farbe und "
                             "Stichart lassen sich wie bei jeder Form ändern.")

    def path_op(self, op):
        """Pfad-Operationen: »intersect« Schnittmenge, »exclude« Exklusion, »divide« Teilen."""
        from . import design
        sel = self._shapes_sel(2)
        if not sel:
            return
        geoms = [o.world_geometry() for o in sel]
        if op == "divide":
            pieces = design.division(geoms[0], geoms[1:])
            if len(pieces) < 2:
                self.lbl_tip.setText("Teilen: die oberen Formen schneiden die unterste nicht.")
                return
            new = [self._shape_like(p, sel[0], f"{sel[0].name} – Stück {i + 1}")
                   for i, p in enumerate(pieces)]
            msg = f"In {len(new)} Stücke geteilt – jedes lässt sich einzeln färben."
        else:
            g = design.intersection(geoms) if op == "intersect" else design.exclusion(geoms)
            if g is None:
                self.lbl_tip.setText("Die Formen überlappen sich nicht – es bleibt nichts übrig."
                                     if op == "intersect" else "Es bleibt keine Fläche übrig.")
                return
            new = [self._shape_like(g, sel[0])]
            msg = "Schnittmenge gebildet." if op == "intersect" else "Exklusion gebildet."
        self._replace(sel, new)
        self.rebuild(new)
        self.commit()
        self.lbl_tip.setText(msg)

    def _units(self, objs):
        """Gruppen zählen beim Ausrichten als eine Einheit: [(objekte, rechteck)]."""
        from . import design
        units, seen = [], {}
        for o in objs:
            key = o.group or o.id
            seen.setdefault(key, []).append(o)
        for members in seen.values():
            rects = [self.items[o.id].mapRectToScene(self.items[o.id].stitch_rect()) for o in members]
            units.append((members, design.bounds_of([_Rect(r) for r in rects])))
        return units

    def align_selected(self, mode):
        from . import design
        objs = [o for o in self.selected_objects() if o.visible]
        if not objs:
            self.lbl_tip.setText("Ausrichten: zuerst Objekte auswählen.")
            return
        units = self._units(objs)
        hw, hh = self.doc.hoop_size
        if self.align_ref == "hoop" or len(units) == 1:
            ref, where = (-hw / 2, -hh / 2, hw / 2, hh / 2), "am Rahmen"
        else:
            ref = (min(r[0] for _, r in units), min(r[1] for _, r in units),
                   max(r[2] for _, r in units), max(r[3] for _, r in units))
            where = "an der Auswahl"
        offs = design.align_offsets([r for _, r in units], mode, ref)
        for (members, _), (dx, dy) in zip(units, offs):
            for o in members:
                o.x += dx
                o.y += dy
                self.items[o.id].setPos(o.x, o.y)
        self.props.refresh()
        self.props.refresh_selection()
        self.commit()
        self.lbl_tip.setText(f"{dict(design.ALIGN_MODES)[mode]} {where} ausgerichtet.")

    def distribute_selected(self, axis):
        from . import design
        units = self._units([o for o in self.selected_objects() if o.visible])
        if len(units) < 3:
            self.lbl_tip.setText("Verteilen: mindestens drei Objekte (oder Gruppen) auswählen.")
            return
        offs = design.distribute_offsets([r for _, r in units], axis)
        for (members, _), (dx, dy) in zip(units, offs):
            for o in members:
                o.x += dx
                o.y += dy
                self.items[o.id].setPos(o.x, o.y)
        self.props.refresh_selection()
        self.commit()
        self.lbl_tip.setText("Gleichmäßig " + ("waagerecht" if axis == "x" else "senkrecht") +
                             " verteilt (gleiche Abstände).")

    def set_align_ref(self, ref):
        self.align_ref = ref
        self.lbl_tip.setText("Ausrichten bezieht sich jetzt auf " +
                             ("den Stickrahmen." if ref == "hoop" else "die Auswahl."))

    def offset_selected(self, grow):
        from . import design
        from .controls import ask_values
        sel = self._shapes_sel(1, "Form")
        if not sel:
            return
        v = ask_values(self, "Erweitern" if grow else "Schrumpfen", [
            ("d", "Abstand", "num", 0.1, 10.0, 0.1, 1, " mm", 1.0),
            ("round", "Runde Ecken", "check", True)],
            "Die Form wird rundum um diesen Abstand " + ("größer." if grow else "kleiner."))
        if not v:
            return
        new = []
        for o in sel:
            g = design.offset(o.world_geometry(), v["d"] if grow else -v["d"], v["round"])
            if g is not None:
                new.append((o, self._shape_like(g, o)))
        if not new:
            self.lbl_tip.setText("Nichts übrig – die Form ist dafür zu schmal.")
            return
        for old, n in new:
            self._replace([old], [n])
        self.rebuild([n for _, n in new])
        self.commit()
        self.lbl_tip.setText(("Erweitert" if grow else "Geschrumpft") + f" um {v['d']:.1f} mm.")

    def outline_selected(self):
        """Umriss (Patch-Rand): geschlossene Linie im Abstand um die Auswahl."""
        from . import design
        from .controls import ask_values
        sel = [o for o in self.selected_objects() if o.visible and o.world_geometry() is not None]
        if not sel:
            self.lbl_tip.setText("Umriss: zuerst Objekte auswählen.")
            return
        v = ask_values(self, "Umriss / Patch-Rand", [
            ("d", "Abstand", "num", 0.0, 20.0, 0.5, 1, " mm", 2.0,
             "Abstand des Umrisses zur Auswahl"),
            ("kind", "Stichart", "choice", [("Satin (Patch-Rand)", "satin"),
                                            ("Bohnenstich", "triple"), ("Steppstich", "run")], "satin"),
            ("w", "Satinbreite", "num", 1.0, 8.0, 0.5, 1, " mm", 3.0),
            ("round", "Runde Ecken", "check", True)],
            "Erzeugt eine geschlossene Linie rund um die Auswahl – z. B. als Rand für einen "
            "Aufnäher (Patch) oder als Kontur um eine Schrift.")
        if not v:
            return
        geoms = []
        for o in sel:
            g = o.world_geometry()
            geoms.append(g if g.area > 0 else g.buffer(o.border.get("width", 1.0) / 2))
        rings = design.outline_rings(geoms, v["d"], v["round"])
        if not rings:
            return
        from . import curves
        color = next((o.border["color"] for o in sel if o.border.get("type", "none") != "none"),
                     "#1A1A1A")
        new = []
        for k, ring in enumerate(rings):
            ln = self._line_from_world(None, [[x, y, curves.CORNER] for x, y in ring], closed=True)
            ln.name = "Umriss" + (f" {k + 1}" if len(rings) > 1 else "")
            ln.border.update(type=v["kind"], width=v["w"], color=color, stitch_len=2.5)
            new.append(ln)
        self.add_objects(new)
        self.lbl_tip.setText("Umriss erzeugt – er wird zuletzt gestickt (ggf. in der Objektliste "
                             "umsortieren).")

    def copies_grid(self):
        from . import design
        from .controls import ask_values
        sel = self.selected_objects()
        if not sel:
            self.lbl_tip.setText("Raster: zuerst ein Objekt oder eine Gruppe auswählen.")
            return
        r = self._selection_rect(sel)
        v = ask_values(self, "Kopien im Raster", [
            ("cols", "Spalten", "int", 1, 20, 3), ("rows", "Zeilen", "int", 1, 20, 2),
            ("gx", "Abstand waagerecht", "num", -20.0, 100.0, 0.5, 1, " mm", 5.0),
            ("gy", "Abstand senkrecht", "num", -20.0, 100.0, 0.5, 1, " mm", 5.0)],
            "Die Auswahl wird als Raster wiederholt (Abstand = Lücke zwischen den Kopien).")
        if not v:
            return
        offs = design.grid_offsets(r.width(), r.height(), int(v["cols"]), int(v["rows"]),
                                   v["gx"], v["gy"])
        self._add_copies(sel, [(dx, dy, 0.0, None) for dx, dy in offs])

    def copies_circle(self):
        from .controls import ask_values
        sel = self.selected_objects()
        if not sel:
            self.lbl_tip.setText("Kreis: zuerst ein Objekt oder eine Gruppe auswählen.")
            return
        r = self._selection_rect(sel)
        v = ask_values(self, "Kopien im Kreis", [
            ("n", "Anzahl (mit Original)", "int", 2, 36, 6),
            ("radius", "Radius", "num", 2.0, 150.0, 0.5, 1, " mm",
             round(max(10.0, r.height() * 1.2), 1), "Abstand der Objektmitte vom Kreismittelpunkt"),
            ("rotate", "Kopien mitdrehen (wie Blütenblätter)", "check", True)],
            "Das Original steht oben, die Kopien folgen im Uhrzeigersinn um den Mittelpunkt "
            "unterhalb.")
        if not v:
            return
        n = int(v["n"])
        c = (r.center().x(), r.center().y() + v["radius"])
        self._add_copies(sel, [(0.0, 0.0, 360.0 * k / n, c) for k in range(1, n)],
                         rotate=v["rotate"], radius=v["radius"])

    def _add_copies(self, sel, steps, rotate=True, radius=0.0):
        from .canvas import transform_objects
        new = []
        for dx, dy, ang, center in steps:
            clones = [o.clone() for o in sel]
            self._new_groups(clones)
            if center is not None:
                if rotate:
                    transform_objects(clones, center, angle=ang)
                else:
                    a = math.radians(ang)
                    for o in clones:
                        o.x += radius * math.sin(a)
                        o.y += radius - radius * math.cos(a)
            else:
                for o in clones:
                    o.x += dx
                    o.y += dy
            new += clones
        self.add_objects(new)
        self.lbl_tip.setText(f"{len(steps)} Kopie(n) erzeugt.")

    def replace_objects(self, old, new):
        """Objekte gegen neue tauschen – ein einziger Schritt zum Rückgängigmachen."""
        ids = {o.id for o in old}
        self._syncing = True
        for oid in ids:
            it = self.items.pop(oid, None)
            if it is not None:
                self.scene.removeItem(it)
        self.doc.objects = [o for o in self.doc.objects if o.id not in ids]
        self._syncing = False
        self.add_objects(new)

    def _insert_from_dialog(self, objs, group=True):
        """Ergebnis eines Vorschau-Fensters ohne die nur zur Ansicht gezeigten Teile."""
        import uuid
        objs = [o for o in objs if not getattr(o, "_context", False)]
        if group and len(objs) > 1:
            gid = uuid.uuid4().hex[:8]
            for o in objs:
                o.group = gid
        return objs

    def open_encore(self):
        from .encore import encore_templates
        from .templates import TemplateDialog
        sel = self.selected_objects()
        if not sel:
            self.lbl_tip.setText("Encore: zuerst ein Motiv (oder eine Gruppe) auswählen – für "
                                 "»Entlang der Linie« zusätzlich eine Linie mit Strg+Klick.")
            return
        tpls, motif = encore_templates(sel)
        dlg = TemplateDialog(self, tpls, "Encore – Muster wiederholen", "encore", "Übernehmen")
        if not dlg.exec() or not dlg.objects:
            return
        new = self._insert_from_dialog(dlg.objects, group=False)
        self.replace_objects(motif, new)
        self.lbl_tip.setText(f"Encore: {len(new)} Teile als Gruppe – Alt+Klick wählt ein "
                             "einzelnes Teil, Strg+Z stellt das Original wieder her.")

    def open_ornaments(self):
        from .ornaments import ORNAMENTS
        from .templates import TemplateDialog
        dlg = TemplateDialog(self, ORNAMENTS, "Rahmen & Schnörkel", "ornament")
        if not dlg.exec() or not dlg.objects:
            return
        self.add_objects(self._insert_from_dialog(dlg.objects))
        self.lbl_tip.setText("Rahmen eingefügt (als Gruppe) – Stichart und Farbe lassen sich je "
                             "Linie ändern, Alt+Klick wählt ein einzelnes Teil.")

    def open_spiro(self):
        from .spiro import SPIRO
        from .templates import TemplateDialog
        dlg = TemplateDialog(self, SPIRO, "Spirograph", "spiro")
        if not dlg.exec() or not dlg.objects:
            return
        self.add_objects(self._insert_from_dialog(dlg.objects))
        self.lbl_tip.setText("Spirograph eingefügt (als Gruppe) – mit Encore lässt er sich "
                             "wiederholen, Alt+Klick wählt eine einzelne Lage.")

    def open_wordsculpt(self):
        from .templates import TemplateDialog
        from .wordsculpt import sculpt_templates
        QApplication.setOverrideCursor(Qt.WaitCursor)     # Stickschrift wird beim ersten Mal geladen
        try:
            tpls = sculpt_templates(self.selected_objects())
            dlg = TemplateDialog(self, tpls, "Text in Form (Word Sculpt)", "wordsculpt")
        finally:
            QApplication.restoreOverrideCursor()
        if not dlg.exec() or not dlg.objects:
            return
        new = self._insert_from_dialog(dlg.objects)
        if not new:
            self.lbl_tip.setText("Text in Form: Die Form ist für diese Zeilenhöhe zu klein.")
            return
        self.add_objects(new)
        self.lbl_tip.setText(f"Text in Form: {len(new)} Teile als Gruppe – Texte und Farben "
                             "lassen sich einzeln ändern (Alt+Klick).")

    def open_ith(self):
        from .ith import PROJECTS
        from .templates import TemplateDialog
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            dlg = TemplateDialog(self, PROJECTS, "Projekt im Rahmen", "ith", thumbs=True)
        finally:
            QApplication.restoreOverrideCursor()
        if not dlg.exec() or not dlg.objects:
            return
        objs = self._insert_from_dialog(dlg.objects)
        old = []
        if self.doc.objects:
            r = QMessageBox.question(
                self, "Projekt im Rahmen",
                "Ein Projekt im Rahmen wird Schritt für Schritt gestickt und sollte allein im "
                "Design stehen.\n\nAktuelles Design durch das Projekt ersetzen?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Yes:
                old = list(self.doc.objects)
        # Arbeitsschritte in genau dieser Reihenfolge sticken (Farben nicht zusammenfassen)
        self.doc.color_sort = False
        self.a_colorsort.setChecked(False)
        self.replace_objects(old, objs)
        from .ith import project_info
        info, steps = project_info(objs)
        hw, hh = self.doc.hoop_size
        st = self.doc.stats()
        msg = (f"{info['title']}: {len(steps)} Arbeitsschritte, die Maschine hält nach jedem an. "
               "Anleitung: Export › Projekt-Anleitung.")
        if st["width"] > hw + 0.5 or st["height"] > hh + 0.5:
            msg = (f"Achtung: {st['width']:.0f} × {st['height']:.0f} mm passt nicht in den Rahmen "
                   f"({hw:.0f} × {hh:.0f} mm) – kleiner einstellen oder größeren Rahmen wählen. ")
            QMessageBox.warning(self, "Projekt im Rahmen", msg)
        self.lbl_tip.setText(msg)

    def export_ith_instructions(self, path=None):
        from . import ith
        info, _ = ith.project_info(self.doc.objects)
        if not info:
            QMessageBox.information(self, "Projekt-Anleitung",
                                    "Im Design ist kein Projekt im Rahmen. Erst »Erstellen › "
                                    "Projekt im Rahmen« wählen.")
            return
        if path is None:
            base = os.path.splitext(self.path)[0] if self.path else \
                os.path.join(self._dir(), info["title"])
            path, _ = QFileDialog.getSaveFileName(self, "Projekt-Anleitung speichern",
                                                  base + "-Anleitung.pdf", "PDF (*.pdf)")
            if not path:
                return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            n = ith.export_instructions(self.doc, path, render_document(self.doc, 6))
        except Exception as e:
            QMessageBox.warning(self, "Projekt-Anleitung", f"Speichern fehlgeschlagen:\n{e}")
            return
        self.lbl_tip.setText(f"Anleitung gespeichert ({n} Arbeitsschritte): {path}")

    def open_cross(self, obj=None):
        """Kreuzstich-Atelier: neues Muster oder das gewählte Kreuzstich-Objekt bearbeiten."""
        from .crossdialog import CrossDialog
        from .model import EmbObject
        if obj is None or not isinstance(obj, EmbObject):
            sel = self.selected_objects()
            obj = sel[0] if len(sel) == 1 and sel[0].kind == "cross" else None
        dlg = CrossDialog(self, obj.cross if obj else None, self.doc.fabric, self.doc.hoop_size)
        if not dlg.exec() or not dlg.result_data:
            return
        if obj is not None:
            obj.cross = dlg.result_data
            self.rebuild([obj])
            self.commit()
            self.props.set_object(obj)
            self.lbl_tip.setText("Kreuzstich aktualisiert.")
            return
        o = EmbObject("cross")
        o.cross = dlg.result_data
        self.add_objects([o])
        self.lbl_tip.setText("Kreuzstich eingefügt – Doppelklick öffnet das Atelier wieder.")

    def open_stitch_editor(self, obj=None):
        """Stich-Editor für eine Stickdatei; andere Objekte werden dabei in Stiche umgewandelt
        (erst beim Übernehmen – Abbrechen lässt sie unverändert)."""
        from . import jumps
        from .model import EmbObject
        from .stitcheditor import StitchEditor
        if obj is None or not isinstance(obj, EmbObject):
            sel = self.selected_objects()
            if len(sel) != 1:
                self.lbl_tip.setText("Stich-Editor: genau ein Objekt auswählen (Stickdatei, Form, "
                                     "Schriftzug …).")
                return
            obj = sel[0]
        if obj.kind in ("stones", "print"):
            self.lbl_tip.setText("Dieses Objekt wird nicht gestickt – es hat keine Stiche.")
            return
        work = obj
        if obj.kind != "stitches":
            r = QMessageBox.question(
                self, "Stich-Editor", f"»{obj.name}« wird für den Stich-Editor in feste Stiche "
                "umgewandelt – Form, Schrift und Sticheinstellungen lassen sich danach nicht mehr "
                "ändern (Strg+Z macht es rückgängig).\n\nUmwandeln und bearbeiten?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if r != QMessageBox.Yes:
                return
            work = obj.clone()
            jumps.to_stitches(work, self.doc.optimize)
        dlg = StitchEditor(self, work.blocks)
        if not dlg.exec():
            return
        if obj.kind != "stitches":
            jumps.to_stitches(obj, self.doc.optimize)
        obj.blocks = [b for b in dlg.blocks if b["stitches"]]
        obj._skey = obj._okey = None
        self.sync_items([obj.id])
        self.commit()
        self.lbl_tip.setText("Stiche übernommen.")

    def open_paint(self, obj=None):
        """Mal-Atelier: neues Bild oder das gewählte Druckbild bearbeiten."""
        from . import printapp
        from .model import EmbObject
        from .paintdialog import PaintDialog
        if obj is None or not isinstance(obj, EmbObject):
            sel = self.selected_objects()
            obj = next((o for o in sel if o.kind == "print"), None) if len(sel) <= 2 else None
        if obj is not None:
            dlg = PaintDialog(self, printapp.image_of(obj), printapp.size(obj), edit=True)
        else:
            w, h = self.doc.hoop_size
            side = round(min(w, h) * 0.6 / 10) * 10
            dlg = PaintDialog(self, None, (side, side))
        if not dlg.exec():
            return
        if obj is not None:                    # Druckbild ändern, Applikation anpassen
            obj.image = printapp.to_b64(dlg.img)
            obj.fill.update(print_w=dlg.w_mm, print_h=dlg.h_mm)
            changed = [obj]
            for a in self.doc.objects:
                if a.kind == "shape" and a.fill.get("print") and a.group and a.group == obj.group:
                    new = printapp.applique(obj, a.fill.get("print_outline", "rect"),
                                            a.border["color"], a.border.get("width", 3.0))
                    a.geom_wkt, a.curve, a.x, a.y = new.geom_wkt, None, new.x, new.y
                    a.sx = a.sy = 1.0
                    a.rot = 0.0
                    changed.append(a)
            self.rebuild(changed)
            self.commit()
            self.props.set_object(obj)
            self.lbl_tip.setText("Druckbild aktualisiert – die Applikation folgt dem neuen Bild.")
            return
        if dlg.use == "template":
            self.doc.template = {"png": printapp.to_b64(dlg.img), "x": 0.0, "y": 0.0,
                                 "width": float(dlg.w_mm), "opacity": 0.5, "visible": True,
                                 "locked": True}
            self.apply_template()
            self._template_moved()
            self.set_tool("polygon")
            self.lbl_tip.setText("Bild als Vorlage geladen – mit Vieleck, Linie oder Freihand "
                                 "nachzeichnen (Reiter »Nachzeichnen«).")
            return
        if dlg.use == "digitize":
            import tempfile
            fd, path = tempfile.mkstemp(suffix=".png", prefix="stichwizard-")
            os.close(fd)
            try:
                dlg.img.save(path, "PNG")
                self.digitize_image(path)
            finally:
                os.remove(path)
            return
        o = printapp.make(dlg.img, dlg.w_mm, dlg.h_mm)
        a = printapp.applique(o, dlg.outline.currentData(), dlg.edge_color, dlg.satin.value())
        self.add_objects([o, a])
        self.lbl_tip.setText("Druck-Applikation eingefügt: Bild mit »Druckvorlage« auf "
                             "bedruckbaren Stoff drucken, dann Platzierungslinie – Stoff auflegen – "
                             "Heftstich – zurückschneiden – Satinrand." + self._hoop_warning([o, a]))

    def export_print_sheet(self, path=None, mirror=None):
        from . import printapp
        if not printapp.prints_of(self.doc):
            QMessageBox.information(self, "Druckvorlage", "Im Design ist kein Druckbild. Erst "
                                    "»Verzieren › Mal-Atelier« benutzen.")
            return
        if path is None:
            base = os.path.splitext(self.path)[0] if self.path else \
                os.path.join(self._dir(), "Design")
            path, _ = QFileDialog.getSaveFileName(self, "Druckvorlage speichern",
                                                  base + "-Druckvorlage.pdf", "PDF (*.pdf)")
            if not path:
                return
            mirror = QMessageBox.question(
                self, "Druckvorlage", "Bild spiegeln?\n\nNur für Transfer- bzw. Bügelpapier – "
                "für bedruckbaren Stoff »Nein« wählen.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            n = printapp.export_sheet(self.doc, path, bool(mirror))
        except Exception as e:
            QMessageBox.warning(self, "Druckvorlage", f"Speichern fehlgeschlagen:\n{e}")
            return
        self.lbl_tip.setText(f"Druckvorlage gespeichert ({n} Seite(n)): {path} – in Originalgröße "
                             "(100 %) drucken.")

    def _hoop_warning(self, objs):
        """Hinweistext, wenn eingefügte Objekte nicht in den Rahmen passen (sonst leer)."""
        from .model import Document
        d = Document()
        d.objects = objs
        st = d.stats()
        hw, hh = self.doc.hoop_size
        if st["width"] > hw + 0.5 or st["height"] > hh + 0.5:
            return (f" Achtung: {st['width']:.0f} × {st['height']:.0f} mm ist größer als der "
                    f"Rahmen ({hw:.0f} × {hh:.0f} mm) – kleiner einstellen oder größeren Rahmen "
                    "wählen.")
        return ""

    def open_quilt(self):
        from .quilt import quilt_templates
        from .templates import TemplateDialog
        dlg = TemplateDialog(self, quilt_templates(self.selected_objects()), "Quiltblock", "quilt")
        if not dlg.exec() or not dlg.objects:
            return
        objs = self._insert_from_dialog(dlg.objects)
        self.add_objects(objs)
        self.lbl_tip.setText("Quiltblock eingefügt (als Gruppe) – gequiltet wird durch Oberstoff, "
                             "Vlies und Rückseite, ohne Unterlage." + self._hoop_warning(objs))

    def open_family(self):
        from .familytree import FAMILY
        from .templates import TemplateDialog
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            dlg = TemplateDialog(self, FAMILY, "Stammbaum", "family")
        finally:
            QApplication.restoreOverrideCursor()
        if not dlg.exec() or not dlg.objects:
            return
        objs = self._insert_from_dialog(dlg.objects)
        self.add_objects(objs)
        self.lbl_tip.setText("Stammbaum eingefügt (als Gruppe) – Namen lassen sich einzeln "
                             "ändern (Alt+Klick)." + self._hoop_warning(objs))

    def open_stones(self):
        from .stones import source_geometry, stone_templates
        from .templates import TemplateDialog
        sel = [o for o in self.selected_objects() if o.kind != "stones"]
        if not sel or source_geometry(sel) is None:
            self.lbl_tip.setText("Strass: zuerst eine Form, Linie oder einen Schriftzug auswählen.")
            return
        dlg = TemplateDialog(self, stone_templates(sel), "Strass & Perlen", "stones")
        if not dlg.exec():
            return
        new = self._insert_from_dialog(dlg.objects, group=False)
        if not new:
            self.lbl_tip.setText("Strass: In die Auswahl passen bei dieser Größe keine Steine.")
            return
        self.add_objects(new)
        self.lbl_tip.setText(f"{len(new[0].points)} Steine gesetzt – Größe, Art und Farbe "
                             "rechts unter »Strass & Perlen«.")

    def export_stones(self):
        from . import stones
        if not stones.collect(self.doc):
            QMessageBox.information(self, "Strass-Schablone",
                                    "Im Design sind keine Strass-Steine. Erst eine Form wählen "
                                    "und »Verzieren › Strass & Perlen« benutzen.")
            return
        base = os.path.splitext(self.path or "Design")[0] + "-Strass"
        path, filt = QFileDialog.getSaveFileName(
            self, "Strass-Schablone speichern", base + ".svg",
            "SVG für Schneideplotter (*.svg);;PDF zum Drucken (*.pdf)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".pdf" if "PDF" in filt else ".svg"
        try:
            n = (stones.export_pdf if path.lower().endswith(".pdf") else stones.export_svg)(
                self.doc, path)
        except Exception as e:
            QMessageBox.warning(self, "Strass-Schablone", f"Speichern fehlgeschlagen:\n{e}")
            return
        parts = ", ".join(f"{k} × {stones._size_name(d)}" for (d, _, _), k in
                          sorted(stones.summary(stones.collect(self.doc)).items()))
        self.lbl_tip.setText(f"Strass-Schablone gespeichert: {n} Steine ({parts}).")

    def open_templates(self):
        from .templates import TemplateDialog
        dlg = TemplateDialog(self)
        if not dlg.exec() or not dlg.objects:
            return
        objs = dlg.objects
        import uuid
        if len(objs) > 1:                       # als Gruppe einfügen – gemeinsam skalierbar
            gid = uuid.uuid4().hex[:8]
            for o in objs:
                o.group = gid
        self.add_objects(objs)
        self.lbl_tip.setText("Vorlage eingefügt (als Gruppe) – Texte und Farben lassen sich "
                             "weiter ändern, Alt+Klick wählt ein einzelnes Teil.")

    def open_font_workshop(self):
        from .fontmaker import FontWorkshop
        dlg = FontWorkshop(self, self.selected_objects())
        dlg.exec()
        if dlg.created:
            self.lbl_tip.setText("Eigene Schrift gespeichert – sie steht jetzt in der "
                                 "Stickschrift-Auswahl (Eigenschaften › Stickschrift wählen).")

    def make_star(self):
        from . import design
        from .controls import ask_values
        v = ask_values(self, "Stern / Vieleck", [
            ("polygon", "Vieleck statt Stern", "check", False),
            ("n", "Ecken", "int", 3, 24, 5),
            ("size", "Durchmesser", "num", 5.0, 200.0, 1.0, 0, " mm", 40.0),
            ("ratio", "Spitzen (innen/außen)", "num", 0.1, 0.95, 0.05, 2, "", 0.45,
             "Verhältnis von innerem zu äußerem Radius – klein = spitze Zacken"),
            ("rot", "Drehung", "num", -180.0, 180.0, 5.0, 0, " °", 0.0),
            ("round", "Abgerundet (Rundungspunkte)", "check", False)],
            "Wie das Stern-/Vieleck-Werkzeug in Inkscape. Die Punkte lassen sich danach "
            "einzeln bearbeiten.")
        if not v:
            return
        nodes = design.regular_shape_curve(v["n"], v["size"] / 2, v["ratio"], v["polygon"],
                                           v["rot"], v["round"])
        o = EmbObject("shape", "Vieleck" if v["polygon"] else "Stern")
        self._set_world_curve(o, [nodes])
        self.add_objects([o])

    def make_spiral(self):
        from . import design
        from .controls import ask_values
        from . import curves
        v = ask_values(self, "Spirale", [
            ("turns", "Windungen", "num", 0.5, 12.0, 0.5, 1, "", 3.0),
            ("size", "Durchmesser", "num", 5.0, 200.0, 1.0, 0, " mm", 40.0),
            ("inner", "Innenradius", "num", 0.0, 30.0, 0.5, 1, " mm", 1.0)],
            "Spirale als Linie (Stepp-, Bohnen- oder Satinstich wählbar).")
        if not v:
            return
        pts = design.spiral(v["turns"], v["inner"], v["size"] / 2)
        ln = self._line_from_world(None, [[x, y, curves.CORNER] for x, y in pts])
        ln.name = "Spirale"
        ln.border.update(type="triple", stitch_len=2.5)
        self.add_objects([ln])

    def lock_selected(self):
        sel = self.selected_objects()
        if not sel:
            self.lbl_tip.setText("Sperren: zuerst Objekte auswählen (entsperren über die "
                                 "Objektliste oder »Alle entsperren«).")
            return
        for o in sel:
            o.locked = True
        self.scene.clearSelection()
        self.sync_items([])
        self.commit()
        self.lbl_tip.setText(f"{len(sel)} Objekt(e) gesperrt – lassen sich nicht mehr anklicken "
                             "oder verschieben.")

    def unlock_all(self):
        n = 0
        for o in self.doc.objects:
            if o.locked:
                o.locked = False
                n += 1
        self.sync_items([])
        self.commit()
        self.lbl_tip.setText(f"{n} Objekt(e) entsperrt." if n else "Kein Objekt war gesperrt.")

    def pick_color(self):
        if not self.template_item.isVisible() or self.template_item.pixmap().isNull():
            self.lbl_tip.setText("Farbpipette: zuerst ein Bild als Vorlage laden (Nachzeichnen).")
            return
        if not self.selected_objects():
            self.lbl_tip.setText("Farbpipette: zuerst die Objekte auswählen, die die Farbe "
                                 "bekommen sollen.")
            return
        self._pick = ("color", None)
        self.canvas.set_tool("pick")
        self.canvas.setFocus()
        self.lbl_tip.setText("Farbe in der Vorlage anklicken – die nächstliegende Garnfarbe wird "
                             "übernommen · Esc = abbrechen")

    def _pick_template_color(self, x, y):
        it = self.template_item
        p = it.mapFromScene(x, y)
        img = it.pixmap().toImage()
        px, py = int(p.x() - it.offset().x()), int(p.y() - it.offset().y())
        if not (0 <= px < img.width() and 0 <= py < img.height()):
            self.lbl_tip.setText("Außerhalb der Vorlage geklickt.")
            return
        c = img.pixelColor(px, py).name().upper()
        from . import threads
        m = threads.chart_match(c) if threads.CURRENT_CHART else None
        color = m[2] if m else c
        self.apply_color(color, False)
        self.lbl_tip.setText(f"Farbe übernommen: {thread_name(color)}" +
                             (f" ({m[0]} {m[1]})" if m else ""))

    def _inverse_matrix(self, o):
        """Affine Matrix (shapely-Format) Arbeitsfläche -> Objektkoordinaten."""
        ox, oy = o.to_local(0, 0)
        ax, ay = o.to_local(1, 0)
        bx, by = o.to_local(0, 1)
        return [ax - ox, bx - ox, ay - oy, by - oy, ox, oy]

    def erase(self, cut):
        """Schneidet die Fläche `cut` (Pinselstrich oder Lasso, Arbeitsfläche) aus den ausgewählten
        Formen, sonst aus allen darunter – wie ein Radierer im Malprogramm. Durchgeschnittene
        Linien bleiben in allen Stücken erhalten."""
        if not hasattr(cut, "geom_type"):            # alte Aufrufer: Liste von Lasso-Punkten
            cut = Polygon(cut).buffer(0)
        if cut.is_empty:
            return
        targets = [o for o in self.selected_objects() if o.kind in ("shape", "text", "line")]
        if not targets:
            targets = [o for o in self.doc.objects if o.kind in ("shape", "text", "line") and o.visible
                       and o.world_geometry() is not None and o.world_geometry().intersects(cut)]
        changed, removed, added = [], [], []
        for o in targets:
            wg = o.world_geometry()
            if wg is None or not wg.intersects(cut):
                continue
            if o.kind == "text":
                self._text_to_shape(o)
            local_cut = affinity.affine_transform(cut, self._inverse_matrix(o))
            raw = o.raw_geometry()
            rest = raw.difference(local_cut)
            if o.kind == "line":
                if o.closed and rest.geom_type == "MultiLineString":
                    rest = linemerge(rest)               # Stücke am alten Startpunkt zusammenfügen
                parts = sorted((l for l in lines_of(rest) if l.length >= 1), key=lambda l: -l.length)
                if not parts:
                    removed.append(o)
                    continue
                if rest.length < raw.length - 1e-6:      # angeschnitten: ab jetzt offene Linie(n)
                    o.closed = False
                o.set_raw_geometry(parts[0])
                changed.append(o)
                for piece in parts[1:]:
                    c = o.clone()
                    c.set_raw_geometry(piece)
                    added.append((o, c))
                continue
            if rest.is_empty or rest.area < 0.3:
                removed.append(o)
                continue
            o.set_raw_geometry(rest)
            changed.append(o)
        if not changed and not removed:
            return
        for orig, c in added:                            # neue Stücke direkt hinter dem Original
            i = next(k for k, x in enumerate(self.doc.objects) if x is orig)
            self.doc.objects.insert(i + 1, c)
        if removed:
            ids = {o.id for o in removed}
            self.doc.objects = [o for o in self.doc.objects if o.id not in ids]
        self.sync_items([o.id for o in self.selected_objects() if o not in removed])
        self.commit()

    def on_transformed(self, objs):
        self.rebuild(objs)
        self.props.refresh()
        self.props.refresh_selection()
        self.commit()

    def on_prop_changed(self, obj):
        self.rebuild([obj])
        self.commit()

    def on_scene_selection(self):
        if self._syncing:
            return
        try:
            sel = self.selected_objects()
        except RuntimeError:   # Szene wird gerade beim Beenden abgebaut
            return
        # Gruppen immer ganz auswählen (Alt+Klick: nur das angeklickte Objekt)
        if not QApplication.keyboardModifiers() & Qt.AltModifier:
            groups = {o.group for o in sel if o.group}
            extra = [o for o in self.doc.objects if o.group in groups and o not in sel
                     and o.id in self.items]
            if extra:
                self._syncing = True
                for o in extra:
                    self.items[o.id].setSelected(True)
                self._syncing = False
                sel = self.selected_objects()
        self.props.set_selection(sel)
        ids = {o.id for o in sel}
        self.seq._updating = True
        for i in range(self.seq.list.count()):
            it = self.seq.list.item(i)
            it.setSelected(it.data(Qt.UserRole) in ids)
        self.seq._updating = False

    def on_seq_selection(self, ids):
        self._syncing = True
        self.scene.clearSelection()
        for oid in ids:
            if oid in self.items:
                self.items[oid].setSelected(True)
        self._syncing = False
        self.on_scene_selection()

    def on_reordered(self, ids):
        order = {oid: i for i, oid in enumerate(ids)}
        self.doc.objects.sort(key=lambda o: order.get(o.id, 0))
        self.restack()
        self.commit()

    def on_renamed(self, oid, name):
        o = self.doc.find(oid)
        if o and o.name != name:
            o.name = name
            self.props.refresh()
            self.commit()

    def on_seq_action(self, act):
        if act == "up":
            self.move_seq(-1)
        elif act == "down":
            self.move_seq(1)
        elif act == "toggle":
            for o in self.selected_objects():
                o.visible = not o.visible
                self.items[o.id].setVisible(o.visible)
            self.commit()
        elif act == "lock":
            # gesperrte Objekte sind auf der Arbeitsfläche nicht wählbar – hier über die Liste
            ids = [it.data(Qt.UserRole) for it in self.seq.list.selectedItems()]
            objs = [o for o in self.doc.objects if o.id in ids]
            if objs:
                lock = not all(o.locked for o in objs)
                for o in objs:
                    o.locked = lock
                self.sync_items([] if lock else ids)
                self.commit()
                self.lbl_tip.setText(f"{len(objs)} Objekt(e) " + ("gesperrt." if lock else "entsperrt."))
        elif act == "duplicate":
            self.duplicate()
        elif act == "delete":
            self.delete_selected()

    def canvas_menu(self, pos):
        if self.canvas.tool != "select":
            return
        item = self.canvas.itemAt(pos)
        if isinstance(item, ObjectItem) and not item.isSelected():
            self.scene.clearSelection()
            item.setSelected(True)
        m = QMenu(self)
        if self.selected_objects():
            for a in (self.a_dup, self.a_copy, self.a_del):
                m.addAction(a)
            m.addSeparator()
            m.addSeparator()
            if len(self.selected_objects()) > 1:
                m.addAction(self.a_group.text(), self.a_group.trigger)
            if any(o.group for o in self.selected_objects()):
                m.addAction(self.a_ungroup.text().replace("\n", " "), self.a_ungroup.trigger)
            m.addSeparator()
            for a in (self.a_up, self.a_down, self.a_center, self.a_mh, self.a_mv):
                m.addAction(a.text().replace("\n", " ").replace("- ", ""), a.trigger)
        if self.clipboard:
            m.addAction(self.a_paste)
        m.addSeparator()
        m.addAction(self.a_all)
        m.addAction(self.a_fit.text().replace("\n", " "), self.a_fit.trigger)
        m.exec(self.canvas.mapToGlobal(pos))

    # ============================================================ Befehle
    def add_motif(self, name):
        fn = dict(MOTIFS)[name]
        o = EmbObject("shape", name)
        o.set_geometry(fn())
        n = sum(1 for x in self.doc.objects if x.name == name)
        o.x = o.y = 6.0 * n
        o.fill["color"] = ["#E53935", "#EC407A", "#1E88E5", "#43A047", "#FB8C00", "#8E24AA"][n % 6]
        self.add_objects([o])

    def apply_color(self, color, border):
        sel = self.selected_objects()
        if not sel:
            self.lbl_tip.setText(f"{thread_name(color)}: zuerst ein Objekt auswählen.")
            return
        for o in sel:
            if o.kind == "stitches":
                if o.blocks:
                    o.blocks[0]["color"] = color
            elif border or o.kind == "line":
                o.border["color"] = color
                if o.border["type"] == "none":
                    o.border["type"] = "satin" if o.kind != "line" else o.border["type"]
            else:
                o.fill["color"] = color
                if o.fill["type"] == "none":
                    o.fill["type"] = "tatami"
        self.rebuild(sel)
        self.props.refresh()
        self.commit()

    def delete_selected(self):
        if self.canvas.has_node_selection():
            self.canvas.delete_nodes()
            return
        sel = self.selected_objects()
        if not sel:
            return
        ids = {o.id for o in sel}
        self._syncing = True
        for oid in ids:
            self.scene.removeItem(self.items.pop(oid))
        self.doc.objects = [o for o in self.doc.objects if o.id not in ids]
        self._syncing = False
        self.on_scene_selection()
        self.commit()

    @staticmethod
    def _new_groups(objs):
        """Kopien bekommen eigene Gruppen (gleich gruppiert wie die Originale)."""
        import uuid
        ids = {}
        for o in objs:
            if o.group:
                o.group = ids.setdefault(o.group, uuid.uuid4().hex[:8])

    def duplicate(self):
        sel = self.selected_objects()
        if not sel:
            return
        clones = []
        for o in sel:
            c = o.clone()
            c.x += 5
            c.y += 5
            c.name = o.name + " Kopie"
            clones.append(c)
        self._new_groups(clones)
        self.add_objects(clones)

    def group_selected(self):
        import uuid
        sel = self.selected_objects()
        if len(sel) < 2:
            self.lbl_tip.setText("Zum Gruppieren mindestens zwei Objekte auswählen "
                                 "(Umschalt+Klick oder Rahmen ziehen).")
            return
        gid = uuid.uuid4().hex[:8]
        for o in sel:
            o.group = gid
        self.commit()
        self.sync_items([o.id for o in sel])
        self.lbl_tip.setText(f"{len(sel)} Objekte gruppiert – sie werden jetzt gemeinsam gewählt, "
                             "verschoben und mit den Eckgriffen skaliert. Alt+Klick wählt ein "
                             "einzelnes Objekt.")

    def ungroup_selected(self):
        sel = [o for o in self.selected_objects() if o.group]
        if not sel:
            self.lbl_tip.setText("Die Auswahl ist nicht gruppiert.")
            return
        for o in sel:
            o.group = None
        self.commit()
        self.sync_items([o.id for o in sel])
        self.lbl_tip.setText("Gruppierung aufgehoben.")

    def scale_selection(self, fx, fy, angle=0.0):
        """Auswahl gemeinsam um ihre Mitte skalieren/drehen (Eigenschaften › Auswahl)."""
        from .canvas import transform_objects
        sel = self.selected_objects()
        if not sel:
            return
        r = self._selection_rect(sel)
        transform_objects(sel, (r.center().x(), r.center().y()), fx=fx, fy=fy, angle=angle)
        self.rebuild(sel)
        self.commit()
        self.props.set_selection(sel)

    def _selection_rect(self, sel):
        rects = [self.items[o.id].mapRectToScene(self.items[o.id].stitch_rect()) for o in sel]
        r = rects[0]
        for x in rects[1:]:
            r = r.united(x)
        return r

    def copy(self):
        self.clipboard = [o.to_dict() for o in self.selected_objects()]

    def paste(self):
        if not self.clipboard:
            return
        objs = []
        for d in self.clipboard:
            c = EmbObject.from_dict(d).clone()
            c.x += 5
            c.y += 5
            objs.append(c)
        self._new_groups(objs)
        self.clipboard = [o.to_dict() for o in objs]
        self.add_objects(objs)

    def select_all(self):
        self._syncing = True
        for it in self.items.values():
            it.setSelected(True)
        self._syncing = False
        self.on_scene_selection()

    def move_seq(self, d):
        sel = self.selected_objects()
        if not sel:
            return
        objs = self.doc.objects
        idx = sorted(objs.index(o) for o in sel)
        if d > 0:
            idx.reverse()
        for i in idx:
            j = i + d
            if 0 <= j < len(objs) and objs[j] not in sel:
                objs[i], objs[j] = objs[j], objs[i]
        self.restack()
        self.commit()

    def center_selected(self):
        sel = self.selected_objects() or list(self.doc.objects)
        if not sel:
            return
        rects = [self.items[o.id].sceneBoundingRect() for o in sel]
        r = rects[0]
        for x in rects[1:]:
            r = r.united(x)
        dx, dy = -r.center().x(), -r.center().y()
        for o in sel:
            o.x += dx
            o.y += dy
            self.items[o.id].setPos(o.x, o.y)
        self.props.refresh()
        self.commit()

    def mirror(self, horizontal):
        """Spiegeln an der Senkrechten bzw. Waagerechten durch die Mitte der Auswahl –
        mehrere Objekte (Gruppen) tauschen dabei auch ihre Plätze."""
        sel = self.selected_objects()
        c = self._selection_rect(sel).center() if len(sel) > 1 else None
        for o in sel:
            if horizontal:
                o.sx = -o.sx
                if c is not None:
                    o.x = 2 * c.x() - o.x
            else:
                o.sy = -o.sy
                if c is not None:
                    o.y = 2 * c.y() - o.y
            o.rot = (-o.rot) % 360            # Spiegelung in Weltachsen (auch bei Drehung)
        self.rebuild(sel)
        self.commit()

    def nudge(self, dx, dy):
        if self.canvas.has_node_selection():
            f = 0.1 if abs(dx) + abs(dy) < 5 else 1.0   # Punkte feiner verschieben
            self.canvas.move_nodes(dx * f, dy * f)
            return
        sel = self.selected_objects()
        for o in sel:
            o.x += dx
            o.y += dy
            self.items[o.id].setPos(o.x, o.y)
        if sel:
            self.props.refresh()
            self.commit()

    def undo(self):
        if len(self.undo_stack) < 2:
            return
        self.redo_stack.append(self.undo_stack.pop())
        self._restore(self.undo_stack[-1])

    def redo(self):
        if not self.redo_stack:
            return
        snap = self.redo_stack.pop()
        self.undo_stack.append(snap)
        self._restore(snap)

    def _restore(self, snap):
        sel = [o.id for o in self.selected_objects()]
        self.doc.load_json(snap)
        self.apply_hoop(fit=False)
        self.sync_items(sel)
        self.dirty = True
        self.refresh_panels()
        self.update_title()

    # ---------------------------------------------------- Rahmen & Ansicht
    def apply_hoop(self, fit=True):
        from .threads import is_cap_hoop
        w, h = self.doc.hoop_size
        self.hoop_item.set_hoop(w, h, self.doc.fabric, is_cap_hoop(self.doc.hoop))
        self.doc.optimize = self.prefs.get("optimize_export")
        self.a_colorsort.setChecked(self.doc.color_sort)
        self.a_knockout.setChecked(self.doc.knockout)
        self.props.knockout_doc = self.doc.knockout
        if engine.FABRIC != self.doc.fabric_type:
            engine.FABRIC = self.doc.fabric_type
            self.rebuild(list(self.doc.objects))
        for c in (self.hoop_combo, self.fabric_combo, self.fabtype_combo):
            c.blockSignals(True)
        self.fabtype_combo.setCurrentIndex(max(0, self.fabtype_combo.findData(self.doc.fabric_type)))
        if self.hoop_combo.findData(self.doc.hoop) < 0:     # neuer Rahmen aus Datei/KI
            self._fill_hoop_combo()
        self.hoop_combo.setCurrentIndex(self.doc.hoop)
        fi = self.fabric_combo.findData(self.doc.fabric)
        if fi >= 0:
            self.fabric_combo.setCurrentIndex(fi)
        for c in (self.hoop_combo, self.fabric_combo, self.fabtype_combo):
            c.blockSignals(False)
        self.apply_template()
        if fit:
            self.fit_hoop()

    # ---------------------------------------------------- Vorlage (Nachzeichnen)
    def load_template(self):
        exts = " ".join(f"*.{e} *.{e.upper()}" for e in IMAGE_EXTS)
        path, _ = QFileDialog.getOpenFileName(self, "Vorlage zum Nachzeichnen", self._dir(),
                                              f"Bilder und Vektorgrafiken ({exts})")
        if not path:
            return
        self._remember(path)
        img = load_image(path, 2000)
        if img is None or img.isNull():
            QMessageBox.critical(self, APP, "Das Bild konnte nicht geladen werden.")
            return
        if max(img.width(), img.height()) > 2000:
            img = img.scaled(2000, 2000, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        w, h = self.doc.hoop_size
        aspect = img.height() / img.width()
        width = round(min(w * 0.9, h * 0.9 / aspect), 1)
        self.doc.template = {"png": bytes(ba.toBase64()).decode("ascii"), "x": 0.0, "y": 0.0,
                             "width": width, "opacity": 0.5, "visible": True, "locked": True}
        self.apply_template()
        self._template_moved()
        self.set_tool("polygon")
        self.lbl_tip.setText("Vorlage geladen – mit Vieleck (P), Linie (L) oder Freihand (F) "
                             "nachzeichnen. Zum Verschieben der Vorlage »Fixiert« abhaken.")

    def apply_template(self):
        t = self.doc.template
        self.template_item.apply(t)
        for w in self.tpl_controls:
            w.blockSignals(True)
            w.setEnabled(t is not None)
        self.a_tpl_del.setEnabled(t is not None)
        if t:
            self.tpl_opacity.setValue(int(t["opacity"] * 100))
            self.tpl_width.setValue(t["width"])
            self.tpl_show.setChecked(t["visible"])
            self.tpl_lock.setChecked(t["locked"])
        for w in self.tpl_controls:
            w.blockSignals(False)

    def template_changed(self, *_):
        t = self.doc.template
        if not t:
            return
        t.update(opacity=self.tpl_opacity.value() / 100, width=self.tpl_width.value(),
                 visible=self.tpl_show.isChecked(), locked=self.tpl_lock.isChecked())
        self.template_item.apply(t)
        self._template_moved()

    def remove_template(self):
        if self.doc.template:
            self.doc.template = None
            self.apply_template()
            self._template_moved()

    def _template_moved(self):
        self.dirty = True
        self.update_title()

    def set_hoop(self, i):
        from .threads import is_cap_hoop
        was_cap = is_cap_hoop(self.doc.hoop)
        self.doc.hoop = i
        cap = is_cap_hoop(i)
        if cap and self.doc.fabric_type != "cap":
            self._fabric_before_cap = self.doc.fabric_type
            self.doc.fabric_type = "cap"          # Kappen brauchen festere Unterlage, mehr Zug
        elif was_cap and not cap and self.doc.fabric_type == "cap":
            self.doc.fabric_type = getattr(self, "_fabric_before_cap", "standard")
        self.apply_hoop()
        self.commit()
        mc = self.machine()
        if mc:
            w, h = self.doc.hoop_size
            fw, fh = mc["field"]
            if not ((w <= fw and h <= fh) or (w <= fh and h <= fw)):
                self.lbl_tip.setText(f"Achtung: Der Rahmen {w:g} × {h:g} mm ist größer als das "
                                     f"Stickfeld der {mc['name']} ({fw:g} × {fh:g} mm).")
                return
        if cap:
            self.lbl_tip.setText(
                "Kappenrahmen: Stoffart »Kappe« ist gesetzt. Tipp: Auf Kappen von der Mitte nach "
                "außen und von unten nach oben sticken – Schriften ab 6 mm Höhe, keine großen "
                "Flächen über die Mittelnaht.")

    def _fill_hoop_combo(self):
        """Rahmenliste: feste Größen, eigene Rahmen, dann »Eigener Rahmen …« / »… löschen«."""
        from .threads import N_BUILTIN_HOOPS
        cb = self.hoop_combo
        cb.blockSignals(True)
        cb.clear()
        for i, (name, _, _) in enumerate(HOOPS):
            cb.addItem(icons.icon("hoop"), name, i)
        cb.insertSeparator(cb.count())
        cb.addItem(icons.icon("new"), "Eigener Rahmen …", "custom")
        if len(HOOPS) > N_BUILTIN_HOOPS:
            cb.addItem(icons.icon("delete"), "Eigenen Rahmen löschen …", "delete")
        cb.setCurrentIndex(min(self.doc.hoop, len(HOOPS) - 1))
        cb.blockSignals(False)

    def _hoop_chosen(self, idx):
        data = self.hoop_combo.itemData(idx)
        if isinstance(data, int):
            self.set_hoop(data)
            return
        # Sondereinträge: Auswahl erst einmal auf den aktuellen Rahmen zurücksetzen
        self.hoop_combo.blockSignals(True)
        self.hoop_combo.setCurrentIndex(self.doc.hoop)
        self.hoop_combo.blockSignals(False)
        if data == "custom":
            self.add_custom_hoop()
        elif data == "delete":
            self.delete_custom_hoop()

    def add_custom_hoop(self, w=None, h=None, name=None):
        """Eigene Rahmengröße anlegen, speichern und gleich verwenden."""
        from .controls import ask_values
        from .threads import HOOP_LIMITS, hoop_for_size, custom_hoops
        lo, hi = HOOP_LIMITS
        if w is None or h is None:
            cw, ch = self.doc.hoop_size
            v = ask_values(self, "Eigener Rahmen", [
                ("w", "Breite", "num", float(lo), float(hi), 1.0, 0, " mm", float(cw),
                 "Breite des Stickfelds (nicht des Rahmens außen) – steht in der "
                 "Anleitung deiner Maschine"),
                ("h", "Höhe", "num", float(lo), float(hi), 1.0, 0, " mm", float(ch)),
                ("name", "Name (optional)", "text", "")],
                "Gib die Größe des Stickfelds deines Rahmens ein, z. B. 180 × 300 mm. "
                "Der Rahmen wird gespeichert und steht dann immer in der Liste.")
            if not v:
                return None
            w, h, name = v["w"], v["h"], v.get("name", "")
        try:
            i = hoop_for_size(w, h, (name or "").strip())
        except ValueError as e:
            self.lbl_tip.setText(str(e) + ".")
            return None
        self.prefs.set("custom_hoops", custom_hoops())
        self._fill_hoop_combo()
        self.set_hoop(i)
        self.lbl_tip.setText(f"Rahmen {HOOPS[i][0]} gewählt.")
        return i

    def delete_custom_hoop(self, i=None):
        from .controls import ask_values
        from .threads import N_BUILTIN_HOOPS, custom_hoops, remove_custom_hoop
        if len(HOOPS) <= N_BUILTIN_HOOPS:
            return
        if i is None:
            choices = [(HOOPS[k][0], k) for k in range(N_BUILTIN_HOOPS, len(HOOPS))]
            default = self.doc.hoop if self.doc.hoop >= N_BUILTIN_HOOPS else choices[0][1]
            v = ask_values(self, "Eigenen Rahmen löschen", [
                ("i", "Rahmen", "choice", choices, default)],
                "Der Rahmen verschwindet aus der Liste. Designs, die ihn verwenden, bringen "
                "ihre Größe beim Öffnen wieder mit.")
            if not v:
                return
            i = v["i"]
        if not N_BUILTIN_HOOPS <= i < len(HOOPS):
            return
        old_name = HOOPS[i][0]
        cur_w, cur_h = self.doc.hoop_size
        using = self.doc.hoop == i
        remove_custom_hoop(i)
        self.prefs.set("custom_hoops", custom_hoops())
        if self.prefs.get("hoop") >= len(HOOPS):
            self.prefs.set("hoop", 1)
        if using:                                   # nächstgrößerer fester Rahmen
            from .threads import is_cap_hoop
            flat = [k for k in range(N_BUILTIN_HOOPS) if not is_cap_hoop(k)]
            fit = [k for k in flat if HOOPS[k][1] >= cur_w and HOOPS[k][2] >= cur_h]
            self.doc.hoop = fit[0] if fit else max(flat, key=lambda k: HOOPS[k][1] * HOOPS[k][2])
        elif self.doc.hoop > i:
            self.doc.hoop -= 1
        self._fill_hoop_combo()
        self.apply_hoop(fit=using)
        self.commit()
        self.lbl_tip.setText(f"Rahmen {old_name} gelöscht.")

    def set_fabric_type(self, key):
        if key not in engine.FABRIC_PROFILES or key == self.doc.fabric_type:
            return
        self.doc.fabric_type = key
        self.apply_hoop(fit=False)
        self.commit()
        from . import machines
        self.lbl_tip.setText(f"Stoffart: {engine.FABRIC_PROFILES[key]['name']} – "
                             f"{engine.FABRIC_PROFILES[key]['hint']} Nadel: "
                             f"{machines.needle_for(self.machine(), key)}.")

    def set_fabric(self, col):
        self.doc.fabric = col
        self.apply_hoop(fit=False)
        self.commit()

    def fit_hoop(self):
        self.canvas.fit_rect(self.hoop_item.boundingRect().adjusted(-8, -8, 8, 8))

    def showEvent(self, ev):
        super().showEvent(ev)
        self.fit_hoop()

    def _repaint_items(self):
        for it in self.items.values():
            it.update()       # Zwischenspeicher der Objekte erneuern

    def set_mode(self, mode):
        self.opts.mode = mode
        self._repaint_items()

    def toggle_jumps(self):
        self.opts.show_jumps = self.a_jumps.isChecked()
        self._repaint_items()

    def toggle_grid(self):
        self.opts.show_grid = self.a_grid.isChecked()
        self.hoop_item.update()

    # ============================================================== Dateien
    def maybe_save(self):
        if not self.dirty or not (self.doc.objects or self.doc.template):
            return True
        r = QMessageBox.question(self, APP, "Änderungen am Design speichern?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save_doc()
        return r == QMessageBox.Discard

    def _dir(self):
        return self.settings.value("lastDir", os.path.expanduser("~"))

    def _remember(self, path):
        self.settings.setValue("lastDir", os.path.dirname(path))

    def new_doc(self):
        if not self.maybe_save():
            return
        self.doc = self._new_document()
        self.path = None
        self.undo_stack, self.redo_stack = [], []
        self.apply_hoop()
        self.sync_items()
        self.commit(initial=True)
        self.dirty = False
        self.update_title()

    def open_doc(self):
        if not self.maybe_save():
            return
        exts = " ".join(f"*.{e}" for e in [PROJECT_EXT] + fileio.IMPORT_EXTS + IMAGE_EXTS)
        imgs = " ".join(f"*.{e} *.{e.upper()}" for e in IMAGE_EXTS)
        path, _ = QFileDialog.getOpenFileName(
            self, "Öffnen", self._dir(),
            f"Alle unterstützten Dateien ({exts} {exts.upper()});;"
            f"StichWizard-Projekt (*.{PROJECT_EXT});;"
            f"Vektorgrafiken – Illustrator, PDF (*.ai *.AI *.pdf *.PDF);;"
            f"Bilder & SVG – über Bild-Assistent ({imgs});;Alle Dateien (*)")
        if path:
            self.load_path(path)

    def load_path(self, path):
        self._remember(path)
        if path.lower().rsplit(".", 1)[-1] in ("ai", "pdf"):
            self.import_vector(path)
            return
        if path.lower().rsplit(".", 1)[-1] in IMAGE_EXTS:
            # Grafiken sind keine Stickdateien: über den Bild-Assistenten digitalisieren
            self.digitize_image(path)
            return
        try:
            self.open_document(path)
        except Exception as e:
            QMessageBox.critical(self, APP, f"Datei konnte nicht geöffnet werden:\n{e}")

    def open_document(self, path):
        """Öffnet Projekt oder Stickdatei als neues Dokument (wirft bei Fehlern)."""
        if path.lower().endswith("." + PROJECT_EXT):
            doc = Document()
            with open(path, encoding="utf-8") as f:
                doc.load_json(f.read())
            self.doc = doc
            self.path = path
        else:
            obj = fileio.import_file(path)
            self.doc = Document()
            self.doc.objects.append(obj)
            self._choose_hoop_for(obj)
            self.path = None
        self.undo_stack, self.redo_stack = [], []
        self.apply_hoop()
        self.sync_items()
        self.commit(initial=True)
        self.dirty = False
        self.update_title()

    def _choose_hoop_for(self, obj):
        w, h = obj.local_size()
        from .threads import N_BUILTIN_HOOPS, is_cap_hoop
        flat = [i for i in range(N_BUILTIN_HOOPS) if not is_cap_hoop(i)]
        for i in flat:
            _, hw, hh = HOOPS[i]
            if w <= hw and h <= hh:
                self.doc.hoop = i
                return
        self.doc.hoop = max(flat, key=lambda i: HOOPS[i][1] * HOOPS[i][2])

    def save_doc(self):
        if not self.path:
            return self.save_doc_as()
        try:
            fileio.write_text_atomic(self.path, self.doc.to_json(with_template=True))
        except OSError as e:
            QMessageBox.critical(self, APP, f"Speichern fehlgeschlagen:\n{e}")
            return False
        self.dirty = False
        self.update_title()
        self.statusBar().showMessage(f"Gespeichert: {self.path}", 4000)
        return True

    def save_doc_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Projekt speichern",
                                              os.path.join(self._dir(), f"Design.{PROJECT_EXT}"),
                                              f"StichWizard-Projekt (*.{PROJECT_EXT})")
        if not path:
            return False
        if not path.lower().endswith("." + PROJECT_EXT):
            path += "." + PROJECT_EXT
        self._remember(path)
        self.path = path
        return self.save_doc()

    def import_vector(self, path=None):
        """Illustrator-/PDF-Vektorgrafik als Formen und Linien ins Design übernehmen."""
        from .vectorimport import VectorError, VectorImportDialog
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Vektorgrafik öffnen", self._dir(),
                                                  "Illustrator und PDF (*.ai *.AI *.pdf *.PDF);;"
                                                  "Alle Dateien (*)")
            if not path:
                return
            self._remember(path)
        try:
            dlg = VectorImportDialog(path, self, self.doc.hoop_size)
        except VectorError as e:
            QMessageBox.warning(self, APP, str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, APP, f"Die Datei konnte nicht gelesen werden:\n{e}")
            return
        accepted = dlg.exec()
        objs = dlg.objects
        dlg.deleteLater()
        if not accepted or not objs:
            return
        self.center_group(objs)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.add_objects(objs)
        finally:
            QApplication.restoreOverrideCursor()
        self.lbl_tip.setText(f"{len(objs)} Objekt(e) aus der Vektorgrafik übernommen. Mit »Rundungen "
                             "erkennen« (Nachzeichnen) werden die Punkte zu wenigen Ecken und Rundungen.")

    def import_design(self):
        exts = " ".join(f"*.{e} *.{e.upper()}" for e in fileio.IMPORT_EXTS)
        path, _ = QFileDialog.getOpenFileName(self, "Stickdatei importieren", self._dir(),
                                              f"Stickdateien ({exts});;Alle Dateien (*)")
        if not path:
            return
        self._remember(path)
        try:
            obj = fileio.import_file(path)
        except Exception as e:
            QMessageBox.critical(self, APP, f"Import fehlgeschlagen:\n{e}")
            return
        self.add_objects([obj])

    def export_design(self):
        if not self.doc.objects:
            QMessageBox.information(self, APP, "Das Design ist noch leer.")
            return
        filters = ";;".join(f"{label} (*.{ext})" for label, ext in fileio.EXPORT_FORMATS)
        base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "Design"
        last = self.settings.value("lastFormat", "pes")
        if self.prefs.get("export_format") != "last":
            last = self.prefs.get("export_format")
        sel = next((f"{l} (*.{e})" for l, e in fileio.EXPORT_FORMATS if e == last), None)
        path, chosen = QFileDialog.getSaveFileName(self, "Für Stickmaschine exportieren",
                                                   os.path.join(self._dir(), f"{base}.{last}"),
                                                   filters, sel)
        if not path:
            return
        ext = chosen.split("*.")[-1].rstrip(")") if chosen else "pes"
        if not os.path.splitext(path)[1]:
            path += "." + ext
        self._remember(path)
        self.settings.setValue("lastFormat", os.path.splitext(path)[1].lstrip(".").lower())
        st = self.doc.stats()
        w, h = self.doc.hoop_size
        b = st["bounds"]
        if b[0] < -w / 2 or b[2] > w / 2 or b[1] < -h / 2 or b[3] > h / 2:
            if QMessageBox.warning(self, APP, "Das Design ragt über das Stickfeld des gewählten "
                                   "Rahmens hinaus. Trotzdem exportieren?",
                                   QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
        try:
            with self._progress("Sprungstiche werden optimiert …") as prog:
                res = fileio.export_file(self.doc, path, self.prefs.get("optimize_export"), prog)
        except Exception as e:
            QMessageBox.critical(self, APP, f"Export fehlgeschlagen:\n{e}")
            return
        extra = ""
        if res and res["jumps_before"] != res["jumps_after"]:
            extra = f" · Sprünge {res['jumps_before']} → {res['jumps_after']}"
        self.statusBar().showMessage(f"Exportiert: {path}  ({st['stitches']} Stiche{extra})", 8000)

    def send_to_machine(self, choose=None):
        """An Maschine senden. choose: Funktion(dialog) statt exec() (für Tests)."""
        from . import machinesend
        if not self.doc.objects:
            QMessageBox.information(self, APP, "Das Design ist noch leer.")
            return None
        m = self.machine()
        if not m:                          # noch keine Maschine gewählt: letztes Exportformat
            last = self.settings.value("lastFormat", "pes")
            if self.prefs.get("export_format") != "last":
                last = self.prefs.get("export_format")
            m = {"name": "keine gewählt (Export › Maschine)", "format": last or "pes"}
        st = self.doc.stats()
        info = (f"{st['width']:.0f} × {st['height']:.0f} mm · {st['stitches']:,} Stiche · "
                f"{st['colors']} Farben".replace(",", "."))
        folders = [f for f in (self.settings.value("sendFolders", []) or []) if f]
        if isinstance(folders, str):
            folders = [folders]
        base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "Design"
        dlg = machinesend.SendDialog(self, m, base, folders, info)
        ok = choose(dlg) if choose else dlg.exec()
        if not ok:
            return None
        folder, removable = dlg.target()
        if not folder:
            return None
        self.settings.setValue("sendFolders", dlg.extra)
        w, h = self.doc.hoop_size
        b = st["bounds"]
        if (b[0] < -w / 2 or b[2] > w / 2 or b[1] < -h / 2 or b[3] > h / 2) and not choose:
            if QMessageBox.warning(self, APP, "Das Design ragt über das Stickfeld des gewählten "
                                   "Rahmens hinaus. Trotzdem senden?",
                                   QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return None
        name, fmt = dlg.name.text().strip() or "Design", dlg.fmt.currentData()
        target = os.path.join(folder, f"{name}.{fmt}")
        if os.path.exists(target) and not choose and QMessageBox.question(
                self, APP, f"»{name}.{fmt}« gibt es dort schon. Ersetzen?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return None
        try:
            with self._progress("Wird gesendet …"):
                path = machinesend.send(self.doc, folder, name, fmt,
                                        self.prefs.get("optimize_export"),
                                        self.export_worksheet if dlg.sheet.isChecked() else None)
        except Exception as e:
            QMessageBox.critical(self, APP, f"Senden fehlgeschlagen:\n{e}")
            return None
        msg = f"Gesendet: {path}"
        if removable and dlg.eject.isChecked() and dlg.eject.isVisible():
            done, text = machinesend.eject(folder)
            msg += " · " + text
        elif removable:
            msg += " · Stick vor dem Abziehen auswerfen."
        self.lbl_tip.setText(msg)
        self.statusBar().showMessage(msg, 10000)
        return path

    def export_sim_video(self, path=None, opts=None):
        """Simulationsvideo (MP4) – ohne ffmpeg als Einzelbilder (PNG) in einen Ordner."""
        from PySide6.QtWidgets import QProgressDialog
        from . import video
        from .controls import ask_values
        from .threads import thread_name
        if not self.doc.objects:
            QMessageBox.information(self, APP, "Das Design ist noch leer.")
            return None
        st = self.doc.stats()
        auto = round(min(60.0, max(8.0, st["stitches"] / 500.0)))
        if opts is None:
            opts = ask_values(self, "Simulationsvideo", [
                ("seconds", "Dauer", "num", 3.0, 300.0, 1.0, 0, " s", float(auto)),
                ("size", "Größe", "choice", [(t, f"{s[0]}x{s[1]}") for t, s in video.SIZES],
                 "1280x720"),
                ("fps", "Bilder je Sekunde", "choice", [("25", 25), ("30", 30), ("60", 60)], 30),
                ("hoop", "Stickrahmen zeigen", "check", True),
                ("info", "Infoleiste (Farbe, Stich, Fortschritt)", "check", True)],
                "Das Design entsteht Stich für Stich – am Ende bleibt es 2 Sekunden stehen.")
            if not opts:
                return None
        has_ff = bool(video.ffmpeg())
        if path is None:
            base = os.path.splitext(self.path)[0] if self.path else os.path.join(self._dir(),
                                                                                 "Design")
            if has_ff:
                path, _ = QFileDialog.getSaveFileName(self, "Video speichern", base + ".mp4",
                                                      "MP4-Video (*.mp4)")
            else:
                QMessageBox.information(self, APP, "ffmpeg ist nicht installiert – das Video wird "
                                        "als Folge von Einzelbildern (PNG) gespeichert. Mit "
                                        "ffmpeg (Linux: Paket »ffmpeg«) entsteht direkt ein MP4.")
                path = QFileDialog.getExistingDirectory(self, "Ordner für die Einzelbilder")
            if not path:
                return None
        if has_ff and not path.lower().endswith(".mp4"):
            path += ".mp4"
        prog = QProgressDialog("Video wird erstellt …", "Abbrechen", 0, 100, self)
        prog.setWindowTitle(APP)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(300)

        def step(f):
            prog.setValue(int(f * 100))
            QApplication.processEvents()
            return not prog.wasCanceled()
        size = tuple(int(v) for v in str(opts.get("size", "1280x720")).split("x"))
        try:
            if has_ff:
                n = video.export_video(self.doc, path, opts["seconds"], size, int(opts["fps"]),
                                       opts["hoop"], opts["info"], progress=step,
                                       thread_name=thread_name)
            else:
                n = video.export_frames(self.doc, path, opts["seconds"], size, 10, opts["hoop"],
                                        opts["info"], progress=step, thread_name=thread_name)
        except InterruptedError:
            self.lbl_tip.setText("Video abgebrochen.")
            return None
        except Exception as e:
            QMessageBox.critical(self, APP, f"Video fehlgeschlagen:\n{e}")
            return None
        finally:
            prog.close()
        self.lbl_tip.setText(f"Video gespeichert ({n} Bilder): {path}")
        return path

    def export_png(self):
        if not self.doc.objects:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Als Bild speichern",
                                              os.path.join(self._dir(), "Design.png"), "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        img = render_document(self.doc, 12)
        img.save(path)
        self.statusBar().showMessage(f"Bild gespeichert: {path}", 5000)

    def export_worksheet(self, path=None):
        if not self.doc.objects:
            QMessageBox.information(self, APP, "Das Design ist noch leer.")
            return None
        from .worksheet import write_pdf
        base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "Design"
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Arbeitsblatt speichern",
                                                  os.path.join(self._dir(), f"{base} Arbeitsblatt.pdf"),
                                                  "PDF (*.pdf)")
            if not path:
                return None
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            interactive = True
        else:
            interactive = False
        write_pdf(self.doc, path, base, self.thread_chart_lookup(), self.machine())
        if interactive:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            self.statusBar().showMessage(f"Arbeitsblatt gespeichert: {path}", 6000)
        return path

    def thread_chart_lookup(self):
        """Funktion farbe -> (name, nummer) passend zur gewählten Garnkarte (oder None)."""
        from . import threads
        if not threads.CURRENT_CHART:
            return None

        def look(c):
            name, num, _, exact = threads.chart_match(c)
            return ("" if exact else "≈ ") + f"{threads.CURRENT_CHART} {name}", num
        return look

    def set_thread_chart(self, name):
        from . import threads
        threads.set_chart(name)
        self.prefs.set("thread_chart", threads.CURRENT_CHART)
        self.palette_bar.fill()
        self.props.refresh()
        self.refresh_panels()
        self.statusBar().showMessage(f"Garnkarte: {threads.CURRENT_CHART or 'StichWizard-Standard'}", 4000)

    def snap_colors(self):
        """Alle Farben auf die nächste Farbe der gewählten Garnkarte setzen."""
        from . import threads
        if not threads.CURRENT_CHART:
            self.lbl_tip.setText("Zuerst unten links eine Garnkarte wählen (z. B. Madeira Polyneon).")
            return
        snap = lambda c: threads.chart_match(c)[2]
        changed = 0
        for o in self.doc.objects:
            for d, key in ((o.fill, "color"), (o.border, "color")):
                new = snap(d[key])
                changed += new.upper() != d[key].upper()
                d[key] = new
            for b in o.blocks:
                new = snap(b["color"])
                changed += new.upper() != b["color"].upper()
                b["color"] = new
        self.sync_items([o.id for o in self.selected_objects()])
        self.props.refresh()
        self.commit()
        self.statusBar().showMessage(f"{changed} Farben an {threads.CURRENT_CHART} angepasst", 6000)

    def edit_thread_stock(self):
        from .threadstock import ThreadStockDialog
        dlg = ThreadStockDialog(self.prefs.get("thread_stock"), self)
        if dlg.exec():
            self.prefs.set("thread_stock", dlg.result_stock())
            self.lbl_tip.setText(f"Garnvorrat gespeichert: {len(dlg.result_stock())} Garne.")

    def snap_to_stock(self):
        """Alle Farben des Designs auf das nächste Garn aus dem eigenen Vorrat setzen."""
        from .threadstock import nearest
        stock = self.prefs.get("thread_stock")
        if not stock:
            self.lbl_tip.setText("Noch kein Garnvorrat – unten bei »Anpassen ▾ › Mein Garnvorrat …« "
                                 "die Garne anhaken, die du hast.")
            self.edit_thread_stock()
            stock = self.prefs.get("thread_stock")
            if not stock:
                return
        mapping, far = {}, []
        for o in self.doc.objects:
            for d, key in ((o.fill, "color"), (o.border, "color")):
                mapping.setdefault(d[key].upper(), None)
            for b in o.blocks:
                mapping.setdefault(b["color"].upper(), None)
        for col in mapping:
            it, dist = nearest(col, stock)
            mapping[col] = it
            if dist is not None and dist > 25:
                far.append(f"{col} → {(it.get('num') or '')} {it.get('name', '')}".strip())
        for o in self.doc.objects:
            for d, key in ((o.fill, "color"), (o.border, "color")):
                d[key] = mapping[d[key].upper()]["color"]
            for b in o.blocks:
                b["color"] = mapping[b["color"].upper()]["color"]
        self.sync_items([o.id for o in self.selected_objects()])
        self.props.refresh()
        self.commit()
        used = {it["color"] for it in mapping.values()}
        msg = f"Design auf deinen Garnvorrat umgestellt ({len(used)} Garne)."
        if far:
            msg += " Deutlich abweichend: " + "; ".join(far[:3]) + (" …" if len(far) > 3 else "")
        self.lbl_tip.setText(msg)

    def photo_stitch(self, path=None):
        """Fotostich-Assistent: Foto farbig oder als Linienschraffur sticken."""
        from .photostitch import PhotoStitchDialog
        dlg = PhotoStitchDialog(self, self.doc.hoop_size[0])
        if path:
            dlg.load(path)
        if dlg.exec() and dlg.objects:
            objs = dlg.objects
            self.center_group(objs)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.add_objects(objs)
            finally:
                QApplication.restoreOverrideCursor()
            self.commit()
            self.lbl_tip.setText("Fotostich eingefügt. Tipp: im Simulator (F5) ansehen; bei sehr vielen "
                                 "Stichen Breite oder Farbenzahl verringern.")

    def digitize_image(self, path=None):
        dlg = DigitizeDialog(self, self.doc.hoop_size[0])
        if path:
            dlg.load(path)
        if dlg.exec() and dlg.objects:
            objs = dlg.objects
            self.center_group(objs)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.add_objects(objs)
            finally:
                QApplication.restoreOverrideCursor()
            self.lbl_tip.setText("Tipp: Unter »Form bearbeiten« kannst du Punkte "
                                 "verschieben und mit dem Radierer Bereiche wegschneiden, unter »Anordnen« Flächen zerlegen.")

    def trace_bitmap(self, path=None):
        """Bitmap nachzeichnen (wie Inkscape). Ist eine Vorlage geladen, wird sie nachgezeichnet
        und das Ergebnis deckungsgleich daraufgelegt."""
        from .trace import TraceDialog
        t = self.doc.template
        tpl = None
        if t and not path:
            img = QImage.fromData(QByteArray.fromBase64(t["png"].encode("ascii")), "PNG")
            if not img.isNull():
                tpl = (img, t["width"])
        dlg = TraceDialog(self, self.doc.hoop_size[0], tpl)
        if path:
            dlg.load(path)
        accepted = dlg.exec()
        objs, res, aligned = dlg.objects, dlg.result, dlg.align.isChecked()
        dlg.deleteLater()
        if not accepted or not objs:
            return
        if tpl is not None and aligned:
            dx, dy = t["x"] - res["w"] / 2, t["y"] - res["h"] / 2
            for o in objs:
                o.x += dx
                o.y += dy
        else:
            self.center_group(objs)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.add_objects(objs)
        finally:
            QApplication.restoreOverrideCursor()
        self.lbl_tip.setText(f"{len(objs)} Objekt(e) nachgezeichnet. Feinschliff im Punkte-Werkzeug (N); "
                             "Stichart und Farbe rechts unter Eigenschaften.")

    def _progress(self, text):
        """Fortschrittsanzeige als Kontextmanager; liefert eine Rückruffunktion (0…1)."""
        from contextlib import contextmanager
        from PySide6.QtWidgets import QProgressDialog

        @contextmanager
        def cm():
            dlg = QProgressDialog(text, None, 0, 100, self)
            dlg.setWindowTitle(APP)
            dlg.setWindowModality(Qt.WindowModal)
            dlg.setMinimumDuration(400)
            QApplication.setOverrideCursor(Qt.WaitCursor)

            def step(f):
                dlg.setValue(int(f * 100))
                QApplication.processEvents()
            try:
                yield step
            finally:
                dlg.close()
                QApplication.restoreOverrideCursor()
        return cm()

    def optimize_jumps(self, objs=None):
        """Sprungstiche in importierten Stickdateien optimieren (rückgängig machbar)."""
        from .optimize import optimize_blocks
        if objs is None:
            sel = [o for o in self.selected_objects() if o.kind == "stitches"]
            objs = sel or [o for o in self.doc.objects if o.kind == "stitches"]
        if not objs:
            msg = ("Keine importierte Stickdatei im Design. Eigene Formen und Schriftzüge werden "
                   "beim Export automatisch optimiert (Einstellungen › Allgemein).")
            self.lbl_tip.setText(msg)
            return {"message": msg, "objects": []}
        report = []
        with self._progress("Sprungstiche werden optimiert …") as prog:
            for k, o in enumerate(objs):
                blocks = [(b["color"], [tuple(p) for p in b["stitches"]]) for b in o.blocks]
                trims0 = sum(1 for _, s in blocks for p in s if p[2] == 2)
                res, st = optimize_blocks(blocks, progress=lambda f, k=k: prog((k + f) / len(objs)))
                o.blocks = [{"color": c, "stitches": [list(p) for p in s]} for c, s in res]
                o._skey = None
                st["trims_before"] = trims0
                st["trims_after"] = sum(1 for _, s in res for p in s if p[2] == 2)
                st["id"], st["name"] = o.id, o.name
                report.append(st)
        self.sync_items([o.id for o in objs])
        self.commit()
        jb = sum(r["jumps_before"] for r in report)
        ja = sum(r["jumps_after"] for r in report)
        tb = sum(r["trims_before"] for r in report)
        ta = sum(r["trims_after"] for r in report)
        msg = (f"Optimiert: Sprünge {jb} → {ja}, Fadenschnitte {tb} → {ta}. Verbindungen laufen "
               f"nur dort, wo sie später überstickt werden.")
        self.lbl_tip.setText(msg)
        self.statusBar().showMessage(msg, 10000)
        return {"message": msg, "objects": report}

    @staticmethod
    def center_group(objs, cx0=0.0, cy0=0.0):
        """Verschiebt eine Gruppe von Objekten so, dass ihre Mitte bei (cx0, cy0) liegt."""
        rects = []
        for o in objs:
            bx = o.local_bounds()
            rects.append((bx[0] + o.x, bx[1] + o.y, bx[2] + o.x, bx[3] + o.y))
        if not rects:
            return
        cx = (min(r[0] for r in rects) + max(r[2] for r in rects)) / 2
        cy = (min(r[1] for r in rects) + max(r[3] for r in rects)) / 2
        for o in objs:
            o.x += cx0 - cx
            o.y += cy0 - cy

    def simulate(self):
        if not self.doc.objects:
            QMessageBox.information(self, APP, "Das Design ist noch leer.")
            return
        # Simulation mit nummerierten Sprüngen – Reihenfolge und Schnitte direkt bearbeitbar
        from .optimizer_dialog import OptimizerDialog
        OptimizerDialog(self, "Stick-Simulator & Optimierer").exec()
        self.refresh_panels()

    def closeEvent(self, ev):
        if self.maybe_save():
            self.scene.selectionChanged.disconnect(self.on_scene_selection)
            self.api_server.stop()
            ev.accept()
        else:
            ev.ignore()
