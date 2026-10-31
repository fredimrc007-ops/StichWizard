"""Programmeinstellungen (dauerhaft gespeichert) und Einstellungsdialog."""
from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFontComboBox, QFormLayout, QLabel, QListWidget, QListWidgetItem,
                               QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

from . import DEFAULT_FONT, icons, model
from .controls import SliderSpin
from .fileio import EXPORT_FORMATS
from .threads import FABRICS, HOOPS
from .widgets import ColorButton

DEFAULTS = {
    "hoop": 1,                  # Index in HOOPS
    "custom_hoops": [],         # eigene Rahmen: [[name, breite, höhe]]
    "machine": "none",          # Maschinenprofil (machines.py) oder "none"
    "rulers": True,             # Lineale an der Arbeitsfläche
    "thread_stock": [],         # eigener Garnvorrat: [{chart, num, name, color}]
    "custom_machines": [],      # eigene Maschinenprofile
    "fabric": "#FFFFFF",
    "export_format": "last",    # "last" oder Dateiendung
    "speed": 700,               # Stiche pro Minute (für die Stickzeit)
    "undo_steps": 80,
    "view_mode": "real",        # real | stitch
    "show_grid": True,
    "grid_step": 10,
    "snap": True,               # Einrasten beim Verschieben
    "snap_grid": True,          # … am Raster
    "snap_objects": True,       # … an Kanten/Mitten anderer Objekte
    "snap_center": True,        # … an der Rahmenmitte
    "wheel": "zoom",            # zoom | scroll
    "new_fill_type": "tatami",
    "new_color": "#E53935",
    "new_density": 0.4,
    "new_underlay": True,
    "text_font": DEFAULT_FONT,
    "mcp_enabled": True,        # KI-Schnittstelle (MCP)
    "optimize_export": True,    # Sprungstiche beim Export optimieren
    "thread_chart": "",         # gewählte Garnkarte (leer = Standardfarben)
    "tie_mode": "normal",       # Vernähen: none | normal | strong
    "min_stitch": 0.0,
    "curve_tol": 0.2,           # mm – Kurvenanpassung des Steppstichs (0 = aus)          # mm – kürzere Stiche beim Export zusammenfassen (0 = aus)
    "trim_distance": 3.0,       # mm – Sprünge ab dieser Länge werden geschnitten (0 = immer)
    # Oberfläche
    "ui_theme": "light",        # light | dark
    "ui_accent": "tuerkis",     # Akzentfarbe (style.ACCENTS)
    "ui_font": 10.0,            # Grundschrift in pt
    "ui_ribbon": "large",       # large (Symbol + Text) | compact | icons (nur Symbole)
    "ui_toolbar": "left",       # left | right | hidden
    "ui_side": "right",         # right | left
    "ui_palette": True,         # Garnfarben-Leiste unten
    "ui_favorites": "",         # Aktionen für den Reiter »Favoriten« (durch Komma getrennt)
}


class Prefs:
    def __init__(self):
        self.qs = QSettings("StickStudio", "StickStudio")

    def get(self, key):
        default = DEFAULTS[key]
        v = self.qs.value("prefs/" + key, default)
        if isinstance(default, bool):
            return v if isinstance(v, bool) else str(v).lower() in ("true", "1")
        try:
            return type(default)(v)
        except (TypeError, ValueError):
            return default

    def set(self, key, value):
        self.qs.setValue("prefs/" + key, value)

    def reset(self):
        self.qs.remove("prefs")

    def apply_model_defaults(self):
        """Voreinstellungen für neu erstellte Objekte und die Zeitschätzung."""
        model.DEFAULT_FILL.update(type=self.get("new_fill_type"), color=self.get("new_color"),
                                  density=self.get("new_density"),
                                  underlay=self.get("new_underlay"))
        model.DEFAULT_TEXT["font"] = self.get("text_font")
        model.STITCHES_PER_MINUTE = self.get("speed")
        from . import engine
        engine.TIE_MODE = self.get("tie_mode")
        engine.MIN_STITCH = self.get("min_stitch")
        engine.CURVE_TOL = self.get("curve_tol")
        engine.TRIM_DISTANCE = max(0.0, self.get("trim_distance"))
        from . import machines
        m = machines.get(self.get("machine"), self.get("custom_machines"))
        engine.EXPLICIT_STOPS = bool(m and m.get("auto_color"))


def _combo(items, current):
    c = QComboBox()
    for label, data in items:
        c.addItem(label, data)
    i = c.findData(current)
    c.setCurrentIndex(max(0, i))
    return c


class SettingsDialog(QDialog):
    def __init__(self, prefs, parent=None, actions=None, start_tab=None):
        """actions: [(schlüssel, bezeichnung, QIcon)] für die Favoriten-Auswahl."""
        super().__init__(parent)
        self.prefs = prefs
        self.setWindowTitle("Einstellungen")
        self.setWindowIcon(icons.icon("gear"))
        self.resize(560, 560)
        v = QVBoxLayout(self)
        tabs = QTabWidget()
        self.tabs = tabs
        v.addWidget(tabs, 1)
        P = prefs.get

        # ---- Allgemein
        from . import machines
        self.machine = QComboBox()
        self.machine.addItem("Keine Maschine gewählt", machines.NEUTRAL)
        for mc in machines.all_machines(P("custom_machines")):
            self.machine.addItem(icons.icon("machine"), mc["name"], mc["id"])
        self.machine.setCurrentIndex(max(0, self.machine.findData(P("machine"))))
        self.machine.setToolTip("Stellt Rahmen, Exportformat, Tempo, Stopps und Nadelempfehlung "
                                "passend zur Maschine ein (eigene Maschinen: Export › Stickmaschine)")
        self.hoop = QComboBox()
        for name, _, _ in HOOPS:
            self.hoop.addItem(icons.icon("hoop"), name)
        self.hoop.setCurrentIndex(P("hoop"))
        self.fabric = QComboBox()
        for name, col in FABRICS:
            self.fabric.addItem(icons.swatch(col, 16), name, col)
        self.fabric.setCurrentIndex(max(0, self.fabric.findData(P("fabric"))))
        self.export = _combo([("Zuletzt verwendetes Format", "last")] +
                             [(label, ext) for label, ext in EXPORT_FORMATS], P("export_format"))
        self.speed = SliderSpin(200, 1500, 50, integer=True)
        self.speed.setRange(200, 1500)
        self.speed.setSingleStep(50)
        self.speed.setSuffix(" Stiche/min")
        self.speed.setValue(P("speed"))
        self.undo = QSpinBox()
        self.undo.setRange(10, 500)
        self.undo.setSuffix(" Schritte")
        self.undo.setValue(P("undo_steps"))
        self.optexp = QCheckBox("Sprungstiche beim Export automatisch optimieren")
        self.optexp.setChecked(P("optimize_export"))
        self.mcp = QCheckBox("KI-Assistenten (MCP) dürfen StichWizard steuern")
        self.mcp.setChecked(P("mcp_enabled"))
        tabs.addTab(self._page([
            ("Stickmaschine", self.machine),
            ("Standard-Stickrahmen", self.hoop),
            ("Standard-Stoff", self.fabric),
            ("Exportformat vorauswählen", self.export),
            ("Stickgeschwindigkeit", self.speed),
            ("Rückgängig bis zu", self.undo),
            ("Export", self.optexp),
            ("KI-Schnittstelle", self.mcp),
        ], "Rahmen und Stoff gelten für jedes neue Design. Die Stickgeschwindigkeit deiner "
           "Maschine wird für die geschätzte Stickzeit verwendet. Die KI-Schnittstelle ist nur "
           "für Programme deines eigenen Benutzers erreichbar; Einrichtung unter Hilfe › "
           "KI-Anbindung."), "Allgemein")

        # ---- Ansicht
        self.view_mode = _combo([("Realistisch (Fadenoptik)", "real"), ("Stichansicht", "stitch")],
                                P("view_mode"))
        self.grid = QCheckBox("Raster anzeigen")
        self.grid.setChecked(P("show_grid"))
        self.grid_step = _combo([("5 mm", 5), ("10 mm", 10), ("20 mm", 20), ("25 mm", 25)],
                                P("grid_step"))
        self.wheel = _combo([("Zoomen (Strg + Rad ebenfalls)", "zoom"),
                             ("Ansicht verschieben (Strg + Rad zoomt)", "scroll")], P("wheel"))
        tabs.addTab(self._page([
            ("Darstellung beim Start", self.view_mode),
            ("", self.grid),
            ("Rasterabstand", self.grid_step),
            ("Mausrad", self.wheel),
        ], "Mit dem Touchpad verschiebt Wischen mit zwei Fingern immer die Ansicht; "
           "Spreizen oder Strg + Wischen zoomt."), "Ansicht")

        # ---- Neue Objekte
        self.fill_type = _combo([("Tatami (Fläche)", "tatami"), ("Satin", "satin")],
                                P("new_fill_type"))
        self.color = ColorButton(P("new_color"))
        self.density = SliderSpin(0.2, 2.0, 0.05, 2)
        self.density.setRange(0.2, 2.0)
        self.density.setSingleStep(0.05)
        self.density.setSuffix(" mm")
        self.density.setValue(P("new_density"))
        self.underlay = QCheckBox("Unterlage sticken")
        self.underlay.setChecked(P("new_underlay"))
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(P("text_font")))
        tabs.addTab(self._page([
            ("Füllstich", self.fill_type),
            ("Garnfarbe", self.color),
            ("Reihenabstand", self.density),
            ("", self.underlay),
            ("Schriftart für Text", self.font),
        ], "Gilt für Formen und Schriftzüge, die du ab jetzt neu erstellst."), "Neue Objekte")

        # ---- Sticken
        self.tie = _combo([("Kurz vor- und zurück (Standard)", "normal"),
                           ("Kräftig (dreifach vor- und zurück)", "strong"),
                           ("Vor und zurück (ganzer Stich)", "backforth"), ("Pfeil", "arrow"),
                           ("Stern", "star"), ("Dreieck", "triangle"), ("Zickzack", "zigzag"),
                           ("Aus (z. B. bei Maschinen mit eigenem Vernähen)", "none")],
                          P("tie_mode"))
        self.min_stitch = SliderSpin(0.0, 1.0, 0.05, 2)
        self.min_stitch.setRange(0.0, 1.0)
        self.min_stitch.setSingleStep(0.05)
        self.min_stitch.setSpecialValueText("aus")
        self.min_stitch.setSuffix(" mm")
        self.min_stitch.setValue(P("min_stitch"))
        self.curve_tol = SliderSpin(0.0, 1.0, 0.05, 2)
        self.curve_tol.setRange(0.0, 1.0)
        self.curve_tol.setSingleStep(0.05)
        self.curve_tol.setSpecialValueText("aus")
        self.curve_tol.setSuffix(" mm")
        self.curve_tol.setValue(P("curve_tol"))
        self.curve_tol.setToolTip("Steppstich in Kurven: weicht ein Stich weiter als dieser Wert von "
                                  "der Linie ab, wird er geteilt – Rundungen bleiben rund, gerade "
                                  "Strecken behalten die volle Stichlänge")
        self.trim_dist = SliderSpin(0.0, 15.0, 0.5, 1)
        self.trim_dist.setRange(0.0, 15.0)
        self.trim_dist.setSingleStep(0.5)
        self.trim_dist.setSpecialValueText("jeden Sprung")
        self.trim_dist.setSuffix(" mm")
        self.trim_dist.setValue(P("trim_distance"))
        tabs.addTab(self._page([
            ("Fadenschnitt bei Sprüngen ab", self.trim_dist),
            ("Vernähen am Anfang/Ende", self.tie),
            ("Mindeststichlänge", self.min_stitch),
            ("Kurvenanpassung (Abweichung bis)", self.curve_tol),
        ], "Jede Fläche wird für sich fertig gestickt (Unterlage, Füllung, ihr Rand); gesprungen wird "
           "nur zwischen fertigen Elementen. Sprünge ab der eingestellten Länge werden geschnitten – "
           "dann bleibt kein Sprungfaden auf dem Stoff (kleiner = weniger sichtbare Fäden, aber mehr "
           "Schnitte). Vernähstiche sichern den Faden nach jedem Sprung und Schnitt. Sehr kurze "
           "Stiche können bei manchen Maschinen den Faden reißen lassen – mit einer "
           "Mindeststichlänge werden sie zusammengefasst."), "Sticken")

        # ---- Oberfläche
        self.ui_theme = _combo([("Hell", "light"), ("Dunkel", "dark")], P("ui_theme"))
        from . import style as _style
        self.ui_accent = _combo([(n, k) for k, (n, _c) in _style.ACCENTS.items()], P("ui_accent"))
        for i, (k, (n, c)) in enumerate(_style.ACCENTS.items()):
            self.ui_accent.setItemIcon(i, icons.swatch(c, 16))
        self.ui_font = _combo([("Klein (9 pt)", 9.0), ("Normal (10 pt)", 10.0), ("Groß (11 pt)", 11.0),
                               ("Sehr groß (12,5 pt)", 12.5)], P("ui_font"))
        self.ui_ribbon = _combo([("Groß – Symbole mit Text", "large"),
                                 ("Kompakt – kleine Symbole mit Text", "compact"),
                                 ("Nur Symbole (Text als Hinweis)", "icons")], P("ui_ribbon"))
        self.ui_toolbar = _combo([("Links", "left"), ("Rechts", "right"), ("Ausblenden", "hidden")],
                                 P("ui_toolbar"))
        self.ui_side = _combo([("Rechts", "right"), ("Links", "left")], P("ui_side"))
        self.ui_palette = QCheckBox("Garnfarben-Leiste unten anzeigen")
        self.ui_palette.setChecked(P("ui_palette"))
        self.fav_list = QListWidget()
        self.fav_list.setIconSize(QSize(20, 20))
        chosen = [k for k in P("ui_favorites").split(",") if k]
        for key, label, ic in (actions or []):
            it = QListWidgetItem(ic, label)
            it.setData(Qt.UserRole, key)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if key in chosen else Qt.Unchecked)
            self.fav_list.addItem(it)
        self.fav_list.setMinimumHeight(170)
        ui = self._page([
            ("Farbschema", self.ui_theme),
            ("Akzentfarbe", self.ui_accent),
            ("Schriftgröße", self.ui_font),
            ("Menüband", self.ui_ribbon),
            ("Werkzeugleiste", self.ui_toolbar),
            ("Seitenleiste (Eigenschaften)", self.ui_side),
            ("", self.ui_palette),
        ], "Alle Änderungen wirken sofort. Im Reiter »★ Favoriten« ganz vorn im Menüband stehen die "
           "Funktionen, die du unten anhakst – so hast du deine wichtigsten Werkzeuge immer griffbereit.")
        lay = ui.layout()
        head = QLabel("Favoriten (eigener Reiter im Menüband)")
        head.setObjectName("cardTitle")
        lay.insertWidget(lay.count() - 1, head)
        lay.insertWidget(lay.count() - 1, self.fav_list, 1)
        tabs.addTab(ui, "Oberfläche")
        if start_tab:
            for i in range(tabs.count()):
                if tabs.tabText(i) == start_tab:
                    tabs.setCurrentIndex(i)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel |
                              QDialogButtonBox.RestoreDefaults)
        bb.button(QDialogButtonBox.RestoreDefaults).setText("Standardwerte")
        bb.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._defaults)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _page(self, rows, hint):
        w = QWidget()
        v = QVBoxLayout(w)
        f = QFormLayout()
        f.setLabelAlignment(Qt.AlignLeft)
        f.setVerticalSpacing(10)
        for label, widget in rows:
            f.addRow(label, widget)
        v.addLayout(f)
        h = QLabel(hint)
        h.setWordWrap(True)
        h.setObjectName("muted")
        v.addSpacing(8)
        v.addWidget(h)
        v.addStretch()
        return w

    def _defaults(self):
        d = DEFAULTS
        self.hoop.setCurrentIndex(d["hoop"])
        self.fabric.setCurrentIndex(max(0, self.fabric.findData(d["fabric"])))
        self.export.setCurrentIndex(self.export.findData(d["export_format"]))
        self.speed.setValue(d["speed"])
        self.undo.setValue(d["undo_steps"])
        self.mcp.setChecked(d["mcp_enabled"])
        self.optexp.setChecked(d["optimize_export"])
        self.view_mode.setCurrentIndex(self.view_mode.findData(d["view_mode"]))
        self.grid.setChecked(d["show_grid"])
        self.grid_step.setCurrentIndex(self.grid_step.findData(d["grid_step"]))
        self.wheel.setCurrentIndex(self.wheel.findData(d["wheel"]))
        self.fill_type.setCurrentIndex(self.fill_type.findData(d["new_fill_type"]))
        self.color.set_color(d["new_color"])
        self.density.setValue(d["new_density"])
        self.underlay.setChecked(d["new_underlay"])
        self.font.setCurrentFont(QFont(d["text_font"]))
        self.tie.setCurrentIndex(self.tie.findData(d["tie_mode"]))
        self.min_stitch.setValue(d["min_stitch"])
        self.curve_tol.setValue(d["curve_tol"])
        self.trim_dist.setValue(d["trim_distance"])
        for key, w in (("ui_theme", self.ui_theme), ("ui_accent", self.ui_accent), ("ui_font", self.ui_font), ("ui_ribbon", self.ui_ribbon),
                       ("ui_toolbar", self.ui_toolbar), ("ui_side", self.ui_side)):
            w.setCurrentIndex(max(0, w.findData(d[key])))
        self.ui_palette.setChecked(d["ui_palette"])

    def accept(self):
        S = self.prefs.set
        S("hoop", self.hoop.currentIndex())
        S("fabric", self.fabric.currentData())
        S("export_format", self.export.currentData())
        S("speed", self.speed.value())
        S("undo_steps", self.undo.value())
        S("mcp_enabled", self.mcp.isChecked())
        S("optimize_export", self.optexp.isChecked())
        S("tie_mode", self.tie.currentData())
        S("min_stitch", self.min_stitch.value())
        S("curve_tol", self.curve_tol.value())
        S("trim_distance", self.trim_dist.value())
        for key, w in (("ui_theme", self.ui_theme), ("ui_accent", self.ui_accent), ("ui_font", self.ui_font), ("ui_ribbon", self.ui_ribbon),
                       ("ui_toolbar", self.ui_toolbar), ("ui_side", self.ui_side)):
            S(key, w.currentData())
        S("ui_palette", self.ui_palette.isChecked())
        favs = [self.fav_list.item(i).data(Qt.UserRole) for i in range(self.fav_list.count())
                if self.fav_list.item(i).checkState() == Qt.Checked]
        S("ui_favorites", ",".join(favs))
        S("view_mode", self.view_mode.currentData())
        S("show_grid", self.grid.isChecked())
        S("grid_step", self.grid_step.currentData())
        S("wheel", self.wheel.currentData())
        S("new_fill_type", self.fill_type.currentData())
        S("new_color", self.color.color)
        S("new_density", self.density.value())
        S("new_underlay", self.underlay.isChecked())
        S("text_font", self.font.currentFont().family())
        super().accept()
