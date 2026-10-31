"""Seitenleisten: Eigenschaften, Objektreihenfolge, Motive, Garnpalette."""
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QColorDialog, QComboBox, QSpinBox, QDialog,
                               QDialogButtonBox,
                               QDoubleSpinBox, QFontComboBox, QFormLayout, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QToolButton, QVBoxLayout,
                               QWidget)

from . import engine, icons
from .engine import STITCH
from .render import geom_path
from .shapes import MOTIFS
from .threads import thread_name

FILL_TYPES = [("Tatami (Fläche)", "tatami"), ("Satin", "satin"), ("Wellenfüllung", "wave"),
              ("Geführte Füllung (folgt einer Linie)", "guided"),
              ("Konturfüllung", "contour"), ("Kreuzstich", "cross"), ("Motivfüllung", "motif"),
              ("Netz / Kreuzschraffur", "net"), ("Spiralfüllung", "circular"),
              ("Mäander (Quilt-Stil)", "meander"), ("Ripple / Konturlinien", "ripple"),
              ("Farbverlauf (2–5 Farben)", "gradient"), ("Schottenkaro (Tartan)", "tartan"),
              ("Applikation (Stoff aufnähen)", "applique"),
              ("Keine Füllung", "none")]
TATAMI_PATTERNS = [("Standard (feine Diagonale)", "standard"), ("Ziegel", "brick"),
                   ("Große Ziegel", "bigbrick"), ("Fischgrät", "herringbone"),
                   ("Zickzack", "zigzag"), ("Wellenlinien", "waves"), ("Große Wellen", "bigwaves"),
                   ("Steile Diagonale", "steps"), ("Flache Diagonale", "shallow"),
                   ("Köper", "twill"), ("Rauten", "diamond"), ("Karo", "check"),
                   ("Schuppen", "scales"), ("Gerade Einstichlinien", "straight"),
                   ("Gestreut (kein Muster)", "scatter")]
FILL_MOTIFS = [("Herz", "heart"), ("Stern", "star"), ("Kreis", "circle"), ("Raute", "diamond"),
               ("Blume", "flower")]
# Welche Felder bei welcher Füllart sinnvoll sind
FILL_FIELDS = {
    "tatami": {"angle", "density", "len", "pattern", "underlay", "ulfirst", "pull"},
    "satin": {"angle", "density", "underlay", "ulfirst", "pull"},
    "wave": {"angle", "density", "size", "underlay", "ulfirst", "pull"},
    "guided": {"density", "len", "pattern", "underlay", "ulfirst", "pull", "guide"},
    "contour": {"density", "underlay", "pull"},
    "cross": {"angle", "size"},
    "motif": {"angle", "pattern", "size", "len"},
    "net": {"angle", "size", "len"},
    "circular": {"density", "len", "underlay", "pull"},
    "meander": {"size", "len"},
    "ripple": {"size", "len"},
    "gradient": {"angle", "density", "len", "underlay", "ulfirst", "pull", "color2", "grev",
                 "gcolors"},
    "tartan": {"angle", "density", "len", "tartan"},
    "none": set(),
    "emb": {"underlay"},      # Stickschrift: Stiche kommen aus der Schrift
    "satincol": {"density", "pull", "underlay", "satintype", "short", "shortdist", "split",
                 "splitrand"},
    "applique": {"pattern"},
}
SIZE_LABELS = {"wave": "Wellengröße", "cross": "Kreuzgröße", "motif": "Motivgröße",
               "net": "Gitterabstand", "meander": "Mäandergröße", "ripple": "Ringabstand ×2"}
SATIN_TYPES = [("Satin", "satin"), ("Zickzack-Satin", "zigzag"), ("E-Stich (Applikation)", "estitch")]

_fill_icons = {}


def fill_icon(kind, extra=None):
    """Kleine gerenderte Vorschau einer Füllart (zwischengespeichert)."""
    key = (kind, str(extra))
    if key not in _fill_icons:
        from .model import Document, EmbObject
        from .render import render_document
        from .shapes import rounded_rect
        o = EmbObject("shape")
        o.set_geometry(rounded_rect(16, 16, 3.5))
        o.fill.update({"type": kind, "color": "#0B8A8A", "underlay": False, "size": 4.0,
                       "density": 0.7, "stitch_len": 2.5, **(extra or {})})
        if kind == "guided" and not o.fill.get("guide"):
            o.fill["guide"] = [[-8, 1], [-4, -4], [0, 0], [4, 4], [8, -1]]
        d = Document()
        d.objects = [o]
        img = render_document(d, 5, margin=0.4, transparent=True)
        _fill_icons[key] = QIcon(QPixmap.fromImage(img))
    return _fill_icons[key]
BORDER_TYPES = [("Kein Rand", "none"), ("Steppstich", "run"), ("Bohnenstich (mehrfach)", "triple"),
                ("Satinrand", "satin"), ("Zickzack", "zigzag"), ("E-Stich (Applikation)", "estitch"),
                ("Motivstich (Herzen, Bögen …)", "motif")]
LINE_TYPES = [("Steppstich", "run"), ("Bohnenstich (mehrfach)", "triple"), ("Satinstich", "satin"),
              ("Zickzack", "zigzag"), ("E-Stich", "estitch"), ("Manuell (jeder Punkt ein Stich)", "manual"),
              ("Motivstich (Herzen, Bögen …)", "motif"), ("Skizzenstich (Bleistift)", "sketch")]


# ---------------------------------------------------------------- Farbwahl
class PaletteGrid(QWidget):
    """Farbwahl aus der aktuellen Garnkarte. Passt sich der Bildschirmgröße an (alle Farben
    erreichbar, Bildlauf nur senkrecht); bei großen Karten mit Suche und Listenansicht."""
    picked = Signal(str)
    CELL = 28            # Kantenlänge eines Farbfelds in Pixel
    GAP = 3

    def __init__(self, cols=None, max_height=420):
        super().__init__()
        from .threads import CURRENT_CHART, palette
        self.colors = palette()
        n = len(self.colors)
        cols = cols or (10 if n <= 60 else 14 if n <= 200 else 16)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        head = QHBoxLayout()
        title = QLabel(f"{CURRENT_CHART or 'StichWizard-Standardfarben'}  ({n})")
        title.setObjectName("cardTitle")
        head.addWidget(title, 1)
        self.as_list = QToolButton()
        self.as_list.setText("Liste")
        self.as_list.setCheckable(True)
        self.as_list.setToolTip("Farben als Liste mit Nummer und Name anzeigen")
        head.addWidget(self.as_list)
        v.addLayout(head)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Nummer oder Name suchen …")
        self.search.setClearButtonEnabled(True)
        v.addWidget(self.search)
        # --- Raster
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        inner = QWidget()
        g = QGridLayout(inner)
        g.setSpacing(self.GAP)
        g.setContentsMargins(0, 0, 0, 0)
        g.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.buttons = []
        for i, (name, col) in enumerate(self.colors):
            b = QToolButton()
            b.setIcon(icons.swatch(col, 22))
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(self.CELL, self.CELL)
            b.setToolTip(name)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, c=col: self.picked.emit(c))
            g.addWidget(b, i // cols, i % cols)
            self.buttons.append((name.lower(), b))
        self.area.setWidget(inner)
        sb = self.style().pixelMetric(self.style().PixelMetric.PM_ScrollBarExtent)
        rows = (n + cols - 1) // cols
        step = self.CELL + self.GAP
        need = rows * step + 2
        head_h = 110 if n > 60 else 80
        self.area.setFixedHeight(max(step * 3, min(need, max_height - head_h)))
        self.area.setFixedWidth(cols * step + sb + 6)
        v.addWidget(self.area)
        # --- Liste (Nummer + Name)
        self.list = QListWidget()
        self.list.setIconSize(QSize(18, 18))
        for name, col in self.colors:
            it = QListWidgetItem(icons.swatch(col, 18), name)
            it.setData(Qt.UserRole, col)
            self.list.addItem(it)
        self.list.setFixedSize(self.area.width(), self.area.height())
        self.list.itemClicked.connect(lambda it: self.picked.emit(it.data(Qt.UserRole)))
        self.list.itemActivated.connect(lambda it: self.picked.emit(it.data(Qt.UserRole)))
        self.list.setVisible(False)
        v.addWidget(self.list)
        self.as_list.toggled.connect(self._mode)
        self.search.textChanged.connect(self._filter)
        self.search.setVisible(n > 60)
        self.as_list.setVisible(n > 60)
        more = QPushButton("Weitere Farben …")
        more.clicked.connect(self._more)
        v.addWidget(more)
        self._grid, self._cols = g, cols

    def _mode(self, as_list):
        self.area.setVisible(not as_list)
        self.list.setVisible(as_list)

    def _filter(self, text):
        q = text.strip().lower()
        shown = [b for n, b in self.buttons if not q or q in n]
        for _, b in self.buttons:
            self._grid.removeWidget(b)
            b.setVisible(False)
        for i, b in enumerate(shown):
            self._grid.addWidget(b, i // self._cols, i % self._cols)
            b.setVisible(True)
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(q) and q not in it.text().lower())

    def _more(self):
        c = QColorDialog.getColor(QColor("#E53935"), self, "Garnfarbe wählen")
        if c.isValid():
            self.picked.emit(c.name().upper())


class ColorPopup(QFrame):
    """Aufklappfenster mit der Farbwahl – immer vollständig auf dem Bildschirm."""

    def __init__(self, anchor):
        super().__init__(anchor, Qt.Popup)
        self.setObjectName("colorPopup")
        self.setFrameShape(QFrame.StyledPanel)
        screen = (anchor.screen() or QApplication.primaryScreen()).availableGeometry()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.grid = PaletteGrid(max_height=int(screen.height() * 0.8))
        v.addWidget(self.grid)
        self.adjustSize()
        below = anchor.mapToGlobal(anchor.rect().bottomLeft())
        above = anchor.mapToGlobal(anchor.rect().topLeft())
        w, h = self.width(), self.height()
        x = min(max(screen.left() + 4, below.x()), screen.right() - w - 4)
        if below.y() + h <= screen.bottom() - 4:
            y = below.y()
        elif above.y() - h >= screen.top() + 4:
            y = above.y() - h
        else:
            y = max(screen.top() + 4, screen.bottom() - h - 4)
        self.move(x, y)

    def showEvent(self, ev):
        super().showEvent(ev)
        if self.grid.search.isVisible():
            self.grid.search.setFocus()


class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color="#E53935"):
        super().__init__()
        self.setObjectName("colorButton")
        self.color = color
        self.popup = None
        self.clicked.connect(self._open)
        self.set_color(color)

    def _open(self):
        # jedes Mal neu bauen – die Garnkarte kann sich geändert haben
        self.popup = ColorPopup(self)
        self.popup.grid.picked.connect(self._picked)
        self.popup.show()

    def _picked(self, c):
        if self.popup:
            self.popup.close()
        self.set_color(c)
        self.colorChanged.emit(c)

    def set_color(self, c):
        self.color = c
        self.setIcon(icons.swatch(c, 18))
        self.setText("  " + thread_name(c))


def spin(lo, hi, step, dec=1, suffix=" mm", slider=False):
    """Zahlenfeld; slider=True: mit Schieberegler (für Werte, die man gern »ausprobiert«)."""
    if slider:
        from .controls import SliderSpin
        s = SliderSpin(lo, hi, step, dec, suffix)
        s.slider.setMinimumWidth(40)
        s.spin.setFixedWidth(86)
        return s
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(dec)
    s.setSuffix(suffix)
    s.setKeyboardTracking(False)
    s.setMinimumWidth(70)
    s.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return s


class Card(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        v = QVBoxLayout(self)
        v.setContentsMargins(11, 10, 10, 12)
        v.setSpacing(6)
        lab = QLabel(title)
        lab.setObjectName("cardTitle")
        v.addWidget(lab)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignLeft)
        self.form.setHorizontalSpacing(8)
        self.form.setVerticalSpacing(6)
        v.addLayout(self.form)


# ------------------------------------------------------------ Eigenschaften
class PropertiesPanel(QScrollArea):
    changed = Signal(object)   # EmbObject
    scaleRequested = Signal(float, float)   # Auswahl gemeinsam skalieren (Faktor x, y)
    action = Signal(str)       # Knopf, den das Hauptfenster ausführt (pick_start, detach, …)
    letter_selected = Signal(int)   # Buchstabe in »Einzelne Buchstaben« gewählt (-1 = keiner)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.obj = None
        self._shown = {}
        self._pattern_kind = None
        self._loading = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._apply)

        body = QWidget()
        body.setObjectName("panelBody")
        self.v = QVBoxLayout(body)
        self.v.setContentsMargins(8, 10, 6, 10)
        self.v.setSpacing(10)
        self.empty = QLabel("Kein Objekt ausgewählt.\n\nWähle ein Objekt auf der Arbeitsfläche "
                            "oder erstelle ein neues über die Werkzeugleiste, die Motive "
                            "oder »Erstellen« oben.")
        self.empty.setWordWrap(True)
        self.empty.setObjectName("hint")
        self.v.addWidget(self.empty)

        # Mehrere Objekte / Gruppe
        self.c_sel = Card("Auswahl")
        self.sel_info = QLabel()
        self.sel_info.setWordWrap(True)
        self.sel_info.setObjectName("muted")
        self.sel_w = spin(1, 1000, 1)
        self.sel_h = spin(1, 1000, 1)
        self.sel_lock = QCheckBox("Proportional")
        self.sel_lock.setChecked(True)
        self.sel_w.setToolTip("Gesamtbreite – alle Objekte werden gemeinsam um die Mitte skaliert "
                              "(Stichdichte bleibt erhalten, Stiche werden neu berechnet)")
        self.sel_h.setToolTip(self.sel_w.toolTip())
        gb = QHBoxLayout()
        gb.setContentsMargins(0, 0, 0, 0)
        self.sel_group = QPushButton("Gruppieren")
        self.sel_group.setIcon(icons.icon("group"))
        self.sel_group.clicked.connect(lambda: self.action.emit("group"))
        self.sel_ungroup = QPushButton("Auflösen")
        self.sel_ungroup.setIcon(icons.icon("ungroup"))
        self.sel_ungroup.clicked.connect(lambda: self.action.emit("ungroup"))
        gb.addWidget(self.sel_group)
        gb.addWidget(self.sel_ungroup)
        gbw = QWidget()
        gbw.setLayout(gb)
        self.c_sel.form.addRow(self.sel_info)
        self.c_sel.form.addRow("Breite", self.sel_w)
        self.c_sel.form.addRow("Höhe", self.sel_h)
        self.c_sel.form.addRow("", self.sel_lock)
        self.c_sel.form.addRow(gbw)
        self.v.addWidget(self.c_sel)
        self.c_sel.setVisible(False)
        self._sel = []
        self._sel_size = (0.0, 0.0)
        self.sel_w.valueChanged.connect(lambda v: self._sel_scale("w", v))
        self.sel_h.valueChanged.connect(lambda v: self._sel_scale("h", v))

        # Allgemein
        self.c_gen = Card("Objekt")
        self.name = QLineEdit()
        self.x, self.y = spin(-500, 500, 1), spin(-500, 500, 1)
        self.w, self.h = spin(1, 1000, 1), spin(1, 1000, 1)
        self.rot = spin(-360, 360, 5, 1, " °", slider=True)
        self.lock = QCheckBox("Proportional")
        self.lock.setChecked(True)
        pos = QHBoxLayout()
        pos.addWidget(self.x)
        pos.addWidget(self.y)
        size = QHBoxLayout()
        size.addWidget(self.w)
        size.addWidget(self.h)
        self.c_gen.form.addRow("Name", self.name)
        self.c_gen.form.addRow("Position X/Y", pos)
        self.c_gen.form.addRow("Breite/Höhe", size)
        self.c_gen.form.addRow("", self.lock)
        self.c_gen.form.addRow("Drehung", self.rot)
        self.smooth = QSpinBox()
        self.smooth.setRange(0, 5)
        self.smooth.setSpecialValueText("aus")
        self.smooth.setToolTip("Rundet Ecken ab – ideal für nachgezeichnete Formen")
        self.c_gen.form.addRow("Kurven glätten", self.smooth)
        self.trim_after = QComboBox()
        for label, key in (("Automatisch (Einstellungen › Sticken)", "auto"), ("Immer", "always"), ("Nie", "never"),
                           ("Schnitt + Stopp (Maschine hält an)", "stop")):
            self.trim_after.addItem(label, key)
        self.trim_after.setToolTip("Fadenschnitt nach diesem Objekt, wenn das nächste Objekt "
                                   "dieselbe Farbe hat. »Stopp« hält die Maschine zusätzlich an – "
                                   "z. B. um Applikationsstoff oder Puffschaum aufzulegen.")
        self.c_gen.form.addRow("Schnitt danach", self.trim_after)
        self.v.addWidget(self.c_gen)

        # Text
        self.c_text = Card("Schriftzug")
        self.t_text = QPlainTextEdit()
        self.t_text.setFixedHeight(64)
        self.t_font = QFontComboBox()
        self.t_font.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.t_font.setMinimumContentsLength(12)
        self.t_size = spin(3, 300, 1, slider=True)
        self.t_bold = QCheckBox("Fett")
        self.t_italic = QCheckBox("Kursiv")
        st = QHBoxLayout()
        st.addWidget(self.t_bold)
        st.addWidget(self.t_italic)
        st.addStretch()
        self.t_spacing = spin(-10, 30, 0.5, slider=True)
        self.t_arc = spin(-500, 500, 5, slider=True)
        self.t_arc.setToolTip("0 = gerade, positiv = Bogen nach oben, negativ = nach unten")
        self.t_emb = QPushButton()
        self.t_emb.setObjectName("colorButton")
        self.t_emb.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.t_emb.setMinimumWidth(120)
        self.t_emb.setToolTip("Professionell digitalisierte Stickschrift wählen")
        self.t_emb.clicked.connect(self._choose_embfont)
        self.t_info = QLabel()
        self.t_info.setWordWrap(True)
        self.t_info.setObjectName("muted")
        self.t_info.setTextFormat(Qt.RichText)
        self.t_density = spin(0.0, 1.5, 0.05, 2, slider=True)
        self.t_density.setSpecialValueText("Standard der Schrift")
        self.t_pull = spin(0.0, 1.0, 0.05, 2, slider=True)
        self.t_pull.setSpecialValueText("Standard der Schrift")
        self.c_text.form.addRow("Text", self.t_text)
        self.c_text.form.addRow("Stickschrift", self.t_emb)
        self.c_text.form.addRow("", self.t_info)
        self.c_text.form.addRow("Schriftart", self.t_font)
        self.c_text.form.addRow("Höhe", self.t_size)
        self.c_text.form.addRow("Stil", st)
        self.t_autosatin = QCheckBox("Schmale Striche als Satin")
        self.t_autosatin.setToolTip("Computerschrift wie in Profi-Programmen sticken: schmale "
                                    "Striche als Satin, der der Buchstabenform folgt, breite Teile "
                                    "als Tatami. Aus = ganze Schrift als Tatami-Fläche.")
        self.c_text.form.addRow("", self.t_autosatin)
        self.c_text.form.addRow("Laufweite", self.t_spacing)
        self.c_text.form.addRow("Bogenradius", self.t_arc)
        self.t_palign = QComboBox()
        for label, key in (("Am Anfang", "start"), ("Mittig", "center"), ("Am Ende", "end")):
            self.t_palign.addItem(label, key)
        self.t_palign.setToolTip("Wo der Schriftzug auf dem Pfad steht")
        self.t_pflip = QCheckBox("Andere Seite")
        self.t_pflip.setToolTip("Pfad andersherum: Text steht auf der anderen Seite der Linie")
        self.t_pdetach = QPushButton("Lösen")
        self.t_pdetach.setToolTip("Schriftzug wieder gerade setzen, der Pfad wird wieder eine Linie")
        self.t_pdetach.clicked.connect(lambda: self.action.emit("detach"))
        prow = QHBoxLayout()
        prow.addWidget(self.t_palign, 1)
        prow.addWidget(self.t_pflip)
        prow.addWidget(self.t_pdetach)
        self.t_prow = QWidget()
        self.t_prow.setLayout(prow)
        prow.setContentsMargins(0, 0, 0, 0)
        self.c_text.form.addRow("Am Pfad", self.t_prow)
        from .textfx import ENVELOPES
        self.t_env = QComboBox()
        for key, label, tip in ENVELOPES:
            self.t_env.addItem(label, key)
            self.t_env.setItemData(self.t_env.count() - 1, tip, Qt.ToolTipRole)
        self.t_env.setToolTip("Hüllform: den ganzen Schriftzug in eine Form biegen (Bogen, Fass, "
                              "Welle, Wimpel …) – die Stiche werden danach neu berechnet")
        self.t_envamt = spin(5, 100, 5, 0, " %", slider=True)
        self.t_envamt.setToolTip("Stärke der Hüllform in Prozent der Schrifthöhe")
        self.c_text.form.addRow("Hüllform", self.t_env)
        self.c_text.form.addRow("Stärke", self.t_envamt)
        self.c_text.form.addRow("Satindichte", self.t_density)
        self.c_text.form.addRow("Zugausgleich +", self.t_pull)
        self.v.addWidget(self.c_text)

        # Einzelne Buchstaben (Abstand, Höhe, Drehung je Buchstabe)
        self.c_letters = Card("Einzelne Buchstaben")
        self.l_pick = QComboBox()
        self.l_pick.setToolTip("Buchstaben wählen – oder im Punkte-Werkzeug (N) direkt am "
                               "Buchstaben ziehen")
        self.l_dx = spin(-200, 200, 0.5, 1, slider=True)
        self.l_dy = spin(-200, 200, 0.5, 1, slider=True)
        self.l_rot = spin(-180, 180, 1, 0, " °", slider=True)
        self.l_size = spin(20, 400, 5, 0, " %", slider=True)
        lrow = QHBoxLayout()
        lrow.setContentsMargins(0, 0, 0, 0)
        self.l_reset = QPushButton("Zurücksetzen")
        self.l_reset.setToolTip("Gewählten Buchstaben wieder an seinen Platz setzen")
        self.l_reset_all = QPushButton("Alle")
        self.l_reset_all.setToolTip("Alle Buchstaben zurücksetzen")
        lrow.addWidget(self.l_reset, 1)
        lrow.addWidget(self.l_reset_all)
        lw = QWidget()
        lw.setLayout(lrow)
        hint = QLabel("Tipp: Im Punkte-Werkzeug (N) erscheint an jedem Buchstaben ein Anfasser – "
                      "einfach ziehen. Laufweite zwischen zwei Buchstaben = Versatz waagerecht.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        self.c_letters.form.addRow("Buchstabe", self.l_pick)
        self.c_letters.form.addRow("Versatz →", self.l_dx)
        self.c_letters.form.addRow("Versatz ↓", self.l_dy)
        self.c_letters.form.addRow("Drehung", self.l_rot)
        self.c_letters.form.addRow("Größe", self.l_size)
        self.c_letters.form.addRow("", lw)
        self.c_letters.form.addRow(hint)
        self.l_pick.currentIndexChanged.connect(self._letter_picked)
        self.l_reset.clicked.connect(lambda: self._letter_reset(False))
        self.l_reset_all.clicked.connect(lambda: self._letter_reset(True))
        self.v.addWidget(self.c_letters)

        # Füllung
        self.c_fill = Card("Füllstich")
        self.f_type = QComboBox()
        self.f_type.setIconSize(QSize(36, 36))
        for label, key in FILL_TYPES:
            if key == "none":
                self.f_type.addItem(label, key)
            else:
                self.f_type.addItem(fill_icon(key), label, key)
        self.f_pattern = QComboBox()
        self.f_pattern.setIconSize(QSize(36, 36))
        self.f_size = spin(1.5, 30, 0.5, slider=True)
        self.f_color = ColorButton()
        self.f_angle = spin(-180, 180, 15, 0, " °", slider=True)
        self.f_density = spin(0.2, 2.0, 0.05, 2, slider=True)
        self.f_len = spin(1.0, 7.0, 0.5, slider=True)
        self.f_color2 = ColorButton("#1E88E5")
        self.f_grev = QCheckBox("Verlauf umkehren")
        self.f_gcount = QSpinBox()
        self.f_gcount.setRange(2, 5)
        self.f_gcount.setToolTip("Anzahl der Farben im Verlauf")
        self.f_gextra = [ColorButton(c) for c in ("#FDD835", "#43A047", "#8E24AA")]
        self.f_grow = self.f_gcount
        self.f_tartan = QComboBox()
        self.f_tartan.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.f_tartan_btn = QPushButton("…")
        self.f_tartan_btn.setFixedWidth(32)
        self.f_tartan_btn.setToolTip("Streifen selbst festlegen (Farben und Breiten)")
        self.f_tartan_btn.clicked.connect(self._edit_tartan)
        trow = QHBoxLayout()
        trow.setContentsMargins(0, 0, 0, 0)
        trow.addWidget(self.f_tartan, 1)
        trow.addWidget(self.f_tartan_btn)
        self.f_trow = QWidget()
        self.f_trow.setLayout(trow)
        self.f_tscale = spin(0.25, 4.0, 0.25, 2, " ×", slider=True)
        self.f_tscale.setToolTip("Alle Streifenbreiten vergrößern/verkleinern")
        self.f_tsym = QCheckBox("Gespiegelt wiederholen")
        self.f_tsym.setToolTip("Streifenfolge wie bei echten Tartans gespiegelt wiederholen "
                               "(A B C D C B …)")
        self.f_satintype = QComboBox()
        for label, key in SATIN_TYPES:
            self.f_satintype.addItem(label, key)
        self.f_underlay = QCheckBox("Unterlage sticken")
        self.f_ulfirst = QCheckBox("Unterlage zuerst für alle Teile")
        self.f_ulfirst.setToolTip(
            "Erst die Unterlage aller Teile dieser Form, danach der Füllstich.\n"
            "Stabilisiert große oder mehrteilige Flächen besser (weniger Verzug),\n"
            "kostet aber zusätzliche Sprünge. Ohne Haken: Teil für Teil\n"
            "(innerhalb einer zusammenhängenden Fläche kommt die Unterlage immer zuerst).")
        self.f_underlay.toggled.connect(self.f_ulfirst.setEnabled)
        self.f_pull = spin(0, 1.0, 0.05, 2, slider=True)
        self.f_guide = QLabel()
        self.f_guide.setObjectName("muted")
        self.f_guide.setWordWrap(True)
        self.f_guide_btn = QPushButton("Herauslösen")
        self.f_guide_btn.setToolTip("Führungslinie wieder als eigene Linie anlegen")
        self.f_guide_btn.clicked.connect(lambda: self.action.emit("detach"))
        grow = QHBoxLayout()
        grow.setContentsMargins(0, 0, 0, 0)
        grow.addWidget(self.f_guide, 1)
        grow.addWidget(self.f_guide_btn)
        self.f_guide_row = QWidget()
        self.f_guide_row.setLayout(grow)
        self.f_short = spin(0, 50, 5, 0, " %", slider=True)
        self.f_short.setSpecialValueText("aus")
        self.f_short.setToolTip("Kurze Stiche in engen Kurven: An der Innenseite wird jeder zweite "
                                "Stich um diesen Anteil der Säulenbreite eingerückt (wie Ink/Stitch "
                                "»short stitch inset«) – verhindert Garnhäufung und Fadenbruch.")
        self.f_shortdist = spin(0.05, 2.0, 0.05, 2, slider=True)
        self.f_shortdist.setToolTip("Kurze Stiche, sobald die Einstiche an einer Seite enger als "
                                    "dieser Abstand liegen")
        self.f_split = spin(2.0, 15.0, 0.5, slider=True)
        self.f_split.setToolTip("Satinstiche, die länger sind, werden geteilt (breite Säulen)")
        self.f_splitrand = QCheckBox("Zufällig teilen")
        self.f_splitrand.setToolTip("Teilungspunkte breiter Säulen zufällig versetzen – es entsteht "
                                    "keine sichtbare Linie in der Säulenmitte")
        self.f_knock = QCheckBox("Verdecktes aussparen")
        self.f_knock.setToolTip(
            "Bereiche, die später gestickte Objekte verdecken, werden in dieser Fläche nicht\n"
            "gestickt (schmaler Rand bleibt überlappend). Wirkt, wenn »Optimieren › Automatisch\n"
            "aussparen« für das Design eingeschaltet ist – live beim Verschieben, die Form selbst\n"
            "bleibt unverändert.")
        self.knockout_doc = False     # Dokument-Schalter (setzt das Hauptfenster)
        self.f_pts = QLabel()
        self.f_pts.setObjectName("muted")
        self.f_pts.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.f_pts.setMinimumWidth(60)
        prow = QHBoxLayout()
        prow.setContentsMargins(0, 0, 0, 0)
        prow.setSpacing(4)
        prow.addWidget(self.f_pts, 1)
        for text, act, tip in (("Start", "pick_start", "Startpunkt anklicken"),
                               ("Ende", "pick_end", "Endpunkt anklicken"),
                               ("✕", "clear_points", "Start- und Endpunkt entfernen")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=act: self.action.emit(a))
            prow.addWidget(b)
        self.f_pts_row = QWidget()
        self.f_pts_row.setLayout(prow)
        self.c_fill.form.addRow("Stichart", self.f_type)
        self.c_fill.form.addRow("Muster", self.f_pattern)
        self.c_fill.form.addRow("Mustergröße", self.f_size)
        self.c_fill.form.addRow("Garnfarbe", self.f_color)
        self.c_fill.form.addRow("Zweite Farbe", self.f_color2)
        self.c_fill.form.addRow("", self.f_grev)
        self.c_fill.form.addRow("Farbanzahl", self.f_gcount)
        for i, b in enumerate(self.f_gextra):
            self.c_fill.form.addRow(f"Farbe {i + 3}", b)
        self.c_fill.form.addRow("Tartan", self.f_trow)
        self.c_fill.form.addRow("Streifenbreite", self.f_tscale)
        self.c_fill.form.addRow("", self.f_tsym)
        self.c_fill.form.addRow("Satinart", self.f_satintype)
        self.c_fill.form.addRow("Stichwinkel", self.f_angle)
        self.c_fill.form.addRow("Reihenabstand", self.f_density)
        self.c_fill.form.addRow("Stichlänge", self.f_len)
        self.c_fill.form.addRow("Zugausgleich", self.f_pull)
        self.c_fill.form.addRow("", self.f_underlay)
        self.c_fill.form.addRow("", self.f_ulfirst)
        self.c_fill.form.addRow("Führungslinie", self.f_guide_row)
        self.c_fill.form.addRow("Kurze Stiche", self.f_short)
        self.c_fill.form.addRow("… ab Abstand", self.f_shortdist)
        self.c_fill.form.addRow("Max. Stichlänge", self.f_split)
        self.c_fill.form.addRow("", self.f_splitrand)
        self.c_fill.form.addRow("", self.f_knock)
        self.c_fill.form.addRow("Start / Ende", self.f_pts_row)
        self.v.addWidget(self.c_fill)

        # Rand / Linie
        self.c_border = Card("Rand")
        self.b_type = QComboBox()
        self.b_color = ColorButton("#1A1A1A")
        self.b_width = spin(0.8, 12, 0.5, slider=True)
        self.b_len = spin(1.0, 6.0, 0.5, slider=True)
        self.b_density = spin(0.2, 1.5, 0.05, 2, slider=True)
        self.b_repeats = QSpinBox()
        self.b_repeats.setRange(1, 4)
        self.b_repeats.setToolTip("1 = Dreifachstich, 2 = Fünffachstich …")
        self.b_bean = QLineEdit()
        self.b_bean.setPlaceholderText("z. B. 1 0  (leer = gleichmäßig)")
        self.b_bean.setToolTip("Bohnenstich-Muster: Wiederholungen Stich für Stich, der Reihe nach "
                               "(0 = einfacher Stich, 1 = dreifach, 2 = fünffach) – z. B. »1 0« "
                               "abwechselnd dreifach und einfach, »2 0 0« für ein Perlenmuster")
        self.b_corners = QCheckBox("Ecken genau einstechen")
        self.b_corners.setToolTip("Jede Ecke und jede Kreuzung wird genau getroffen – bei Redwork "
                                  "liegen Hin- und Rückweg so in denselben Einstichen")
        from .engine import LINE_MOTIFS
        self.b_motif = QComboBox()
        for key, label, _ in LINE_MOTIFS:
            self.b_motif.addItem(label, key)
        self.b_motif.setToolTip("Motiv, das entlang der Linie wiederholt wird")
        self.b_gap = spin(0.0, 30.0, 0.5, slider=True)
        self.b_gap.setToolTip("Abstand zwischen den Motiven (Bögen, Welle, Zacken laufen durch)")
        self.b_alt = QCheckBox("Abwechselnd oben/unten")
        self.b_mtriple = QCheckBox("Kräftig (Bohnenstich)")
        self.c_border.form.addRow("Stichart", self.b_type)
        self.c_border.form.addRow("Motiv", self.b_motif)
        self.c_border.form.addRow("Garnfarbe", self.b_color)
        self.c_border.form.addRow("Breite", self.b_width)
        self.c_border.form.addRow("Satindichte", self.b_density)
        self.c_border.form.addRow("Stichlänge", self.b_len)
        self.c_border.form.addRow("Wiederholungen", self.b_repeats)
        self.c_border.form.addRow("Muster", self.b_bean)
        self.c_border.form.addRow("", self.b_corners)
        self.c_border.form.addRow("Abstand", self.b_gap)
        mrow = QHBoxLayout()
        mrow.setContentsMargins(0, 0, 0, 0)
        mrow.addWidget(self.b_alt)
        mrow.addWidget(self.b_mtriple)
        mrow.addStretch()
        self.b_mrow = QWidget()
        self.b_mrow.setLayout(mrow)
        self.c_border.form.addRow("", self.b_mrow)
        self.v.addWidget(self.c_border)

        # Feinheiten (Ink/Stitch-Parameter)
        from .satin import SATIN_UNDERLAYS
        self.c_fine = Card("Feinheiten")
        self.c_fine.setToolTip("Feineinstellungen wie in Ink/Stitch – die Standardwerte passen "
                               "für die meisten Designs")
        self.x_ulangle = spin(-180, 180, 15, 0, " °", slider=True)
        self.x_ulangle.setToolTip("Richtung der Unterlage, bezogen auf den Stichwinkel "
                                  "(90° = quer zum Deckstich)")
        self.x_ulspacing = spin(0.8, 6.0, 0.2, slider=True)
        self.x_ulspacing.setToolTip("Abstand der Unterlagenreihen")
        self.x_ulinset = spin(0.0, 3.0, 0.1, slider=True)
        self.x_ulinset.setToolTip("So weit bleibt die Unterlage vom Rand weg")
        self.x_ullayers = QComboBox()
        self.x_ullayers.addItem("Eine Lage", 1)
        self.x_ullayers.addItem("Zwei Lagen (gekreuzt)", 2)
        self.x_ulcontour = QCheckBox("Randlinie unter der Füllung")
        self.x_expand = spin(-3.0, 3.0, 0.1, 2, slider=True)
        self.x_expand.setToolTip("Füllfläche nach außen erweitern (negativ: verkleinern) – z. B. "
                                 "damit die Füllung sicher unter den Satinrand reicht")
        self.x_lenrand = spin(0, 50, 5, 0, " %", slider=True)
        self.x_lenrand.setSpecialValueText("aus")
        self.x_lenrand.setToolTip("Stichlänge zufällig variieren – keine sichtbaren Einstichmuster "
                                  "(Steppstich und Füllung)")
        self.x_satinul = QComboBox()
        for label, key in SATIN_UNDERLAYS:
            self.x_satinul.addItem(label, key)
        self.x_satinul.setToolTip("Unterlage der Satinsäule: Mittellinie für schmale, Kontur und "
                                  "Zickzack für breite Säulen")
        self.x_widthrand = spin(0, 50, 5, 0, " %", slider=True)
        self.x_widthrand.setSpecialValueText("aus")
        self.x_widthrand.setToolTip("Satinstiche zufällig etwas breiter/schmaler – natürlicher "
                                    "Rand, z. B. für Fell oder Gras")
        self.x_spacerand = spin(0, 80, 10, 0, " %", slider=True)
        self.x_spacerand.setSpecialValueText("aus")
        self.x_spacerand.setToolTip("Abstand der Satinstiche zufällig variieren")
        self.x_tie = QComboBox()
        for label, key in engine.TIE_NAMES:
            self.x_tie.addItem(label, key)
        self.x_tie.setToolTip("Form der Vernähstiche am Anfang und Ende dieses Objekts")
        self.x_tieforce = QCheckBox("Vor jedem Sprung vernähen")
        self.x_tieforce.setToolTip("Vernäht vor jedem Sprung, nicht nur vor Fadenschnitten "
                                   "(sicherer, wenn die Maschine Sprünge später von Hand schneidet)")
        self.x_ulauto = QCheckBox("Unterlage nach Größe")
        self.x_ulauto.setToolTip("Schmale Teile bekommen weniger Unterlage (unter 2 mm keine, unter "
                                 "5 mm nur die Randlinie) – wie »Auto Underlay« in Profi-Programmen")
        self.x_autosp = QCheckBox("Satindichte nach Breite")
        self.x_autosp.setToolTip("Schmale Satinsäulen lockerer (nicht steif und wulstig), breite "
                                 "etwas dichter – wie »Auto Spacing« in Profi-Programmen")
        self.x_corner = QComboBox()
        self.x_corner.addItem("Gehrung (sauber)", "mitre")
        self.x_corner.addItem("Einfach", "none")
        self.x_corner.setToolTip("Spitze Ecken einer Satinlinie: Gehrung fächert die Stiche um die "
                                 "Ecke und verkürzt sie innen – keine Garnhäufung, keine Lücke außen")
        self.x_puff = QCheckBox("3D-Puff (Endkappen)")
        self.x_puff.setToolTip("Für Schaumstoff: dichte Stiche quer über die Enden schneiden den "
                               "Schaum sauber ab (am besten über »Sticken › Effekte › 3D-Puff« einrichten)")
        fm = self.c_fine.form
        fm.addRow("", self.x_ulauto)
        fm.addRow("", self.x_autosp)
        fm.addRow("Satin-Ecken", self.x_corner)
        fm.addRow("", self.x_puff)
        fm.addRow("Unterlage-Winkel", self.x_ulangle)
        fm.addRow("Unterlage-Abstand", self.x_ulspacing)
        fm.addRow("Unterlage-Einzug", self.x_ulinset)
        fm.addRow("Unterlage-Lagen", self.x_ullayers)
        fm.addRow("", self.x_ulcontour)
        fm.addRow("Satin-Unterlage", self.x_satinul)
        fm.addRow("Erweitern", self.x_expand)
        fm.addRow("Zufällige Stichlänge", self.x_lenrand)
        fm.addRow("Zufällige Breite", self.x_widthrand)
        fm.addRow("Zufälliger Abstand", self.x_spacerand)
        fm.addRow("Vernähen", self.x_tie)
        fm.addRow("", self.x_tieforce)
        self.v.addWidget(self.c_fine)

        # Stickdatei-Farben
        self.c_blocks = Card("Farben der Stickdatei")
        self.blocks_box = QVBoxLayout()
        self.c_blocks.form.addRow(self.blocks_box)
        self.v.addWidget(self.c_blocks)

        # Strass & Perlen (werden aufgebügelt, nicht gestickt)
        from .stones import SIZES, STYLES
        self.c_stones = Card("Strass & Perlen")
        self.s_size = QComboBox()
        for label, d in SIZES:
            self.s_size.addItem(label, d)
        self.s_style = QComboBox()
        for label, key in STYLES:
            self.s_style.addItem(label, key)
        self.s_color = ColorButton("#E8F4FF")
        self.s_info = QLabel()
        self.s_info.setWordWrap(True)
        self.s_info.setObjectName("muted")
        self.c_stones.form.addRow("Steingröße", self.s_size)
        self.c_stones.form.addRow("Art", self.s_style)
        self.c_stones.form.addRow("Farbe", self.s_color)
        self.c_stones.form.addRow(self.s_info)
        self.s_size.currentIndexChanged.connect(self._edited_now)
        self.s_style.currentIndexChanged.connect(self._edited_now)
        self.s_color.colorChanged.connect(self._edited_now)
        self.v.addWidget(self.c_stones)

        # Kreuzstich
        self.c_cross = Card("Kreuzstich")
        self.x_info = QLabel()
        self.x_info.setWordWrap(True)
        self.x_info.setObjectName("muted")
        self.x_edit = QPushButton("Im Kreuzstich-Atelier bearbeiten …")
        self.x_edit.clicked.connect(lambda: self.action.emit("cross_edit"))
        self.c_cross.form.addRow(self.x_info)
        self.c_cross.form.addRow(self.x_edit)
        self.v.addWidget(self.c_cross)

        # Druckbild (Druck-Applikation)
        self.c_print = Card("Druckbild")
        self.p_info = QLabel()
        self.p_info.setWordWrap(True)
        self.p_info.setObjectName("muted")
        self.p_edit = QPushButton("Im Mal-Atelier bearbeiten …")
        self.p_edit.clicked.connect(lambda: self.action.emit("print_edit"))
        self.p_sheet = QPushButton("Druckvorlage (PDF) speichern …")
        self.p_sheet.clicked.connect(lambda: self.action.emit("print_sheet"))
        for wdg in (self.p_info, self.p_edit, self.p_sheet):
            self.c_print.form.addRow(wdg)
        self.v.addWidget(self.c_print)

        self.v.addStretch()
        self.setWidget(body)
        # Auswahllisten dürfen schmaler als ihr längster Eintrag werden – die Leiste passt
        # so auch bei großer Schrift ohne abgeschnittene Felder
        for cb in body.findChildren(QComboBox):
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(8)

        for w in (self.x, self.y, self.w, self.h, self.rot, self.t_size, self.t_spacing,
                  self.t_envamt, self.l_dx, self.l_dy, self.l_rot, self.l_size,
                  self.t_arc, self.t_density, self.t_pull, self.f_angle, self.f_density, self.f_len, self.f_pull, self.f_size,
                  self.b_width, self.b_len, self.b_density, self.b_repeats, self.f_short,
                  self.b_gap,
                  self.f_shortdist, self.f_split, self.x_ulangle, self.x_ulspacing, self.x_ulinset,
                  self.x_expand, self.x_lenrand, self.x_widthrand, self.x_spacerand,
                  self.f_gcount, self.f_tscale):
            w.valueChanged.connect(self._edited)
        for w in (self.f_type, self.b_type, self.f_pattern, self.f_satintype, self.t_palign,
                  self.t_env, self.b_motif,
                  self.x_ullayers, self.x_satinul, self.x_tie, self.f_tartan, self.x_corner):
            w.currentIndexChanged.connect(self._edited)
        self.smooth.valueChanged.connect(self._edited)
        self.trim_after.currentIndexChanged.connect(self._edited)
        for w in (self.t_bold, self.t_italic, self.f_underlay, self.f_ulfirst, self.f_grev,
                  self.t_pflip, self.f_splitrand, self.b_corners, self.x_ulcontour,
                  self.x_tieforce, self.f_tsym, self.x_ulauto, self.x_autosp, self.x_puff,
                  self.b_alt, self.b_mtriple, self.f_knock, self.t_autosatin):
            w.toggled.connect(self._edited)
        for b in self.f_gextra:
            b.colorChanged.connect(self._edited_now)
        self.name.editingFinished.connect(self._edited)
        self.b_bean.editingFinished.connect(self._edited)
        self.t_text.textChanged.connect(self._edited)
        self.t_font.currentFontChanged.connect(self._edited)
        self.f_color.colorChanged.connect(self._edited_now)
        self.f_color2.colorChanged.connect(self._edited_now)
        self.b_color.colorChanged.connect(self._edited_now)
        self.w.valueChanged.connect(lambda v: self._keep_ratio("w", v))
        self.h.valueChanged.connect(lambda v: self._keep_ratio("h", v))
        self.set_object(None)

    def _keep_ratio(self, which, v):
        if self._loading or not self.lock.isChecked() or not self.obj:
            return
        lw, lh = self.obj.local_size()
        if lw <= 0 or lh <= 0:
            return
        self._loading = True
        if which == "w":
            self.h.setValue(v * lh / lw)
        else:
            self.w.setValue(v * lw / lh)
        self._loading = False

    def set_selection(self, objs):
        """Eine Auswahl anzeigen: ein Objekt = seine Eigenschaften, mehrere = Karte »Auswahl«."""
        objs = list(objs)
        self._sel = objs
        self.set_object(objs[0] if len(objs) == 1 else None)
        many = len(objs) > 1
        self.c_sel.setVisible(many)
        if many:
            self.empty.setVisible(False)
            self.refresh_selection()

    def refresh_selection(self):
        objs = self._sel
        if len(objs) < 2:
            return
        xs, ys = [], []
        for o in objs:
            for _, sts in o.world_blocks():
                xs.extend(p[0] for p in sts)
                ys.extend(p[1] for p in sts)
        w = (max(xs) - min(xs)) if xs else 0.0
        h = (max(ys) - min(ys)) if ys else 0.0
        self._sel_size = (w, h)
        groups = {o.group for o in objs}
        grouped = len(groups) == 1 and None not in groups
        self.c_sel.findChild(QLabel, "cardTitle").setText("Gruppe" if grouped else "Auswahl")
        self.sel_info.setText(f"{len(objs)} Objekte" + (" – gruppiert" if grouped else "") +
                              ". Mit den Eckgriffen oder hier gemeinsam skalieren.")
        self._loading = True
        self.sel_w.setValue(w)
        self.sel_h.setValue(h)
        self._loading = False
        free = all(abs(((o.rot + 45) % 90) - 45) < 0.01 for o in objs)
        self.sel_lock.setEnabled(free)
        if not free:
            self.sel_lock.setChecked(True)
            self.sel_lock.setToolTip("Gedrehte Objekte lassen sich nur proportional skalieren")
        self.sel_group.setEnabled(not grouped)
        self.sel_ungroup.setEnabled(any(o.group for o in objs))

    def _sel_scale(self, which, v):
        if self._loading or len(self._sel) < 2:
            return
        w, h = self._sel_size
        if w <= 0 or h <= 0:
            return
        f = v / (w if which == "w" else h)
        if self.sel_lock.isChecked():
            fx = fy = f
        else:
            fx, fy = (f, 1.0) if which == "w" else (1.0, f)
        self.scaleRequested.emit(fx, fy)

    def set_object(self, obj):
        if self._timer.isActive() and self.obj is not None and self.obj is not obj:
            self._timer.stop()
            self._apply()          # offene Eingabe nicht verlieren
        self.obj = obj
        self._timer.stop()
        has = obj is not None
        self.empty.setVisible(not has)
        for c in (self.c_gen, self.c_text, self.c_letters, self.c_fill, self.c_border, self.c_fine,
                  self.c_blocks, self.c_stones, self.c_cross, self.c_print):
            c.setVisible(has)
        if not has:
            return
        self.refresh()

    def refresh(self):
        obj = self.obj
        if obj is None:
            return
        self._loading = True
        kind = obj.kind
        self.c_text.setVisible(kind == "text")
        self.c_letters.setVisible(kind == "text")
        self.c_fill.setVisible(kind in ("shape", "text", "satin"))
        self.c_border.setVisible(kind not in ("stitches", "satin"))
        self.c_blocks.setVisible(kind == "stitches")
        self.name.setText(obj.name)
        self.x.setValue(obj.x)
        self.y.setValue(obj.y)
        lw, lh = obj.local_size()
        self.w.setValue(lw * abs(obj.sx))
        self.h.setValue(lh * abs(obj.sy))
        self.rot.setValue(((obj.rot + 180) % 360) - 180)
        self._shown = {k: getattr(self, k).value() for k in ("x", "y", "w", "h", "rot")}
        self.c_gen.form.setRowVisible(self.smooth, kind in ("shape", "line"))
        self.smooth.setValue(obj.smooth)
        self.trim_after.setCurrentIndex(max(0, self.trim_after.findData(obj.trim_after)))
        self.c_stones.setVisible(kind == "stones")
        self.c_cross.setVisible(kind == "cross")
        self.c_print.setVisible(kind == "print")
        if kind == "print":
            for c in (self.c_border, self.c_fine):
                c.setVisible(False)
            self.p_info.setText(f"{obj.fill.get('print_w', 0):.0f} × {obj.fill.get('print_h', 0):.0f} "
                                "mm · wird gedruckt, nicht gestickt. Auf bedruckbaren Stoff drucken "
                                "und mit der Applikation aufsticken.")
            self._loading = False
            return
        if kind == "cross":
            for c in (self.c_border, self.c_fine):
                c.setVisible(False)
            from .crossstitch import stats
            st = stats(obj.cross)
            self.x_info.setText(f"{obj.cross['cols']} × {obj.cross['rows']} Kästchen à "
                                f"{obj.cross['cell']:.1f} mm · {st['full']} volle, {st['half']} "
                                f"halbe, {st['quarter']} Viertelkreuze · {st['back']} Rückstiche "
                                f"· {st['colors']} Farben. Doppelklick öffnet das Atelier.")
            self._loading = False
            return
        if kind == "stones":
            for c in (self.c_border, self.c_fine):
                c.setVisible(False)
            f = obj.fill
            d = float(f.get("stone", 2.8))
            i = next((k for k in range(self.s_size.count())
                      if abs(self.s_size.itemData(k) - d) < 0.05), -1)
            if i < 0:
                self.s_size.addItem(f"{d:.1f} mm", d)
                i = self.s_size.count() - 1
            self.s_size.setCurrentIndex(i)
            self.s_style.setCurrentIndex(max(0, self.s_style.findData(f.get("stone_style", "crystal"))))
            self.s_color.set_color(f.get("color", "#E8F4FF"))
            self.s_info.setText(f"{len(obj.points)} Steine · werden nicht gestickt, sondern nach "
                                "dem Sticken aufgebügelt. Schablone: Export › Strass-Schablone.")
            self._loading = False
            return
        if kind == "text":
            t = obj.text
            if self.t_text.toPlainText() != t["text"]:
                self.t_text.setPlainText(t["text"])
            self.t_font.setCurrentFont(t["font"])
            self.t_size.setValue(t["size"])
            self.t_bold.setChecked(t["bold"])
            self.t_italic.setChecked(t["italic"])
            self.t_autosatin.setChecked(bool(t.get("auto_satin", True)))
            self.c_text.form.setRowVisible(self.t_autosatin, not t.get("embfont"))
            self.t_spacing.setValue(t["spacing"])
            self.t_arc.setValue(t["arc"])
            on_path = bool(t.get("path"))
            self.c_text.form.setRowVisible(self.t_prow, on_path)
            self.c_text.form.setRowVisible(self.t_arc, not on_path)
            self.t_palign.setCurrentIndex(max(0, self.t_palign.findData(t.get("path_align", "center"))))
            self.t_pflip.setChecked(bool(t.get("path_flip", False)))
            self.t_density.setValue(t.get("emb_density", 0.0))
            self.t_pull.setValue(t.get("emb_pull", 0.0))
            self.t_env.setCurrentIndex(max(0, self.t_env.findData(t.get("env", "none"))))
            self.t_envamt.setValue(round(float(t.get("env_amount", 0.3)) * 100))
            self.c_text.form.setRowVisible(self.t_envamt, t.get("env", "none") != "none")
            self._show_embfont(t)
            self._fill_letters(obj)
        f = obj.fill
        self.f_type.setCurrentIndex(max(0, self.f_type.findData(f["type"])))
        self.f_color.set_color(f["color"])
        self.f_color2.set_color(f.get("color2", "#1E88E5"))
        self.f_grev.setChecked(bool(f.get("gradient_reverse", False)))
        extra = list(f.get("gradient_colors") or [])
        self.f_gcount.setValue(2 + len(extra))
        for i, b in enumerate(self.f_gextra):
            if i < len(extra):
                b.set_color(extra[i])
        from .engine import TARTAN_PRESETS
        self.f_tartan.clear()
        cur = f.get("tartan")
        for name, sett in TARTAN_PRESETS.items():
            self.f_tartan.addItem(name, name)
        if cur and cur not in TARTAN_PRESETS.values():
            self.f_tartan.addItem("Eigene Streifen", "custom")
        idx = next((i for i, (n, st) in enumerate(TARTAN_PRESETS.items()) if st == cur), None)
        self.f_tartan.setCurrentIndex(0 if not cur else idx if idx is not None
                                      else self.f_tartan.count() - 1)
        self.f_tscale.setValue(f.get("tartan_scale", 1.0))
        self.f_tsym.setChecked(bool(f.get("tartan_symmetric", True)))
        self.f_satintype.setCurrentIndex(max(0, self.f_satintype.findData(f.get("satin_type", "satin"))))
        self.f_angle.setValue(f["angle"])
        self.f_density.setValue(f["density"])
        self.f_len.setValue(f["stitch_len"])
        self.f_size.setValue(f["size"])
        emb = kind == "text" and bool(obj.text.get("embfont"))
        self._fill_rows("emb" if emb else "satincol" if kind == "satin" else f["type"], f)
        self.c_fill.form.setRowVisible(self.f_type, not emb and kind != "satin")
        self.c_fill.findChild(QLabel, "cardTitle").setText("Satinstich" if kind == "satin" else "Füllstich")
        appl = kind in ("shape", "text") and f["type"] == "applique"
        lab = self.c_fill.form.labelForField(self.f_color)
        if lab:
            lab.setText("Stofffarbe" if appl else "Garnfarbe")
        self.c_border.form.setRowVisible(self.b_type, not appl)
        self.f_underlay.setChecked(f["underlay"])
        self.f_ulfirst.setChecked(bool(f.get("underlay_first", False)))
        self.f_ulfirst.setEnabled(f["underlay"])
        self.f_pull.setValue(f["pull"])
        self.f_short.setValue(f.get("short_inset", 15.0))
        self.f_shortdist.setValue(f.get("short_dist", 0.25))
        self.f_split.setValue(f.get("split_len", 8.0))
        self.f_splitrand.setChecked(bool(f.get("split_random", False)))
        self.f_shortdist.setEnabled(f.get("short_inset", 15.0) > 0)
        self.f_guide.setText("zugeordnet (lila gestrichelt)" if f.get("guide") else
                             "keine – Form und Linie wählen, dann »Geführte Füllung«")
        self.f_guide_btn.setEnabled(bool(f.get("guide")))
        pts_ok = (kind == "satin" or (kind in ("shape", "text") and not emb and
                                      f["type"] not in ("none", "applique")))
        self.c_fill.form.setRowVisible(self.f_pts_row, pts_ok)
        self.c_fill.form.setRowVisible(self.f_knock, kind in ("shape", "text") and not emb and
                                       f["type"] not in ("none", "applique"))
        self.f_knock.setChecked(bool(f.get("knockout", True)))
        tip = self.f_knock.toolTip().split("\n\n")[0]
        self.f_knock.setToolTip(tip + ("" if self.knockout_doc else
                                       "\n\nZurzeit im Design ausgeschaltet."))
        self.f_pts.setText("Start " + ("✓" if f.get("start") else "–") +
                           " · Ende " + ("✓" if f.get("end") else "–"))
        types = LINE_TYPES if kind == "line" else BORDER_TYPES
        self.b_type.clear()
        for label, key in types:
            self.b_type.addItem(label, key)
        b = obj.border
        appl = kind in ("shape", "text") and obj.fill["type"] == "applique"
        self.c_border.findChild(QLabel, "cardTitle").setText(
            "Applikationsrand (Satin)" if appl else ("Linie" if kind == "line" else "Rand"))
        self.b_type.setCurrentIndex(max(0, self.b_type.findData(b["type"])))
        self.b_color.set_color(b["color"])
        self.b_width.setValue(b["width"])
        self.b_len.setValue(b["stitch_len"])
        self.b_density.setValue(b["density"])
        self.b_repeats.setValue(int(b.get("repeats", 1)))
        satin = b["type"] == "satin" or appl
        motif = b["type"] == "motif"
        self.b_width.setEnabled(satin or b["type"] in ("zigzag", "estitch", "motif", "sketch"))
        self.b_density.setEnabled(satin)
        self.b_len.setEnabled(b["type"] in ("run", "triple", "zigzag", "estitch", "motif", "sketch"))
        wl = self.c_border.form.labelForField(self.b_width)
        if wl:
            wl.setText("Motivgröße" if motif else "Streuung" if b["type"] == "sketch" else "Breite")
        for row in (self.b_motif, self.b_gap, self.b_mrow):
            self.c_border.form.setRowVisible(row, motif)
        self.c_border.form.setRowVisible(self.b_density, not motif)
        self.b_motif.setCurrentIndex(max(0, self.b_motif.findData(b.get("motif", "heart"))))
        self.b_gap.setValue(float(b.get("gap", 1.0)))
        self.b_alt.setChecked(bool(b.get("motif_alt", False)))
        self.b_mtriple.setChecked(bool(b.get("motif_triple", False)))
        lab = self.c_border.form.labelForField(self.b_len)
        if lab:
            lab.setText("Abstand" if b["type"] in ("zigzag", "estitch") else "Stichlänge")
        self.c_border.form.setRowVisible(self.b_repeats, b["type"] in ("triple", "sketch"))
        rl = self.c_border.form.labelForField(self.b_repeats)
        if rl:
            rl.setText("Extra-Durchgänge" if b["type"] == "sketch" else "Wiederholungen")
        self.c_border.form.setRowVisible(self.b_bean, b["type"] == "triple")
        self.b_bean.setText(b.get("bean_pattern", ""))
        self.b_repeats.setEnabled(not engine.bean_pattern(b.get("bean_pattern")))
        self.c_border.form.setRowVisible(self.b_corners, b["type"] in ("run", "triple"))
        self.b_corners.setChecked(bool(b.get("corners", False)))
        self._show_fine(obj)
        if kind == "stitches":
            self._fill_blocks()
        self._loading = False

    def _show_fine(self, obj):
        """Karte »Feinheiten«: nur die Zeilen, die für dieses Objekt etwas bewirken."""
        kind, f, b = obj.kind, obj.fill, obj.border
        self.c_fine.setVisible(kind != "stitches")
        if kind == "stitches":
            return
        emb = kind == "text" and bool(obj.text.get("embfont"))
        ftype = f["type"] if kind in ("shape", "text") and not emb else None
        ul_fill = ftype in ("tatami", "satin", "wave", "guided", "gradient", "contour",
                            "circular") and f.get("underlay", True)
        rows_fill = ftype not in (None, "none", "applique")
        rand_len = (ftype in ("tatami", "guided", "gradient", "contour", "circular", "meander",
                              "ripple") or b.get("type") in ("run", "triple")) and kind != "satin"
        fm = self.c_fine.form
        for w in (self.x_ulangle, self.x_ulspacing, self.x_ulinset, self.x_ullayers,
                  self.x_ulcontour):
            fm.setRowVisible(w, ul_fill)
        fm.setRowVisible(self.x_satinul, kind == "satin")
        satin_line = b.get("type") == "satin" and kind in ("shape", "text", "line")
        fm.setRowVisible(self.x_ulauto, ul_fill)
        fm.setRowVisible(self.x_autosp, kind == "satin" or satin_line)
        fm.setRowVisible(self.x_corner, satin_line)
        fm.setRowVisible(self.x_puff, kind == "satin")
        self.x_ulauto.setChecked(bool(f.get("underlay_auto", False)))
        self.x_autosp.setChecked(bool(f.get("auto_spacing") if kind == "satin"
                                      else b.get("auto_spacing")))
        self.x_corner.setCurrentIndex(max(0, self.x_corner.findData(b.get("corner", "mitre"))))
        self.x_puff.setChecked(bool(f.get("puff", False)))
        fm.setRowVisible(self.x_expand, rows_fill)
        fm.setRowVisible(self.x_lenrand, rand_len)
        fm.setRowVisible(self.x_widthrand, kind == "satin")
        fm.setRowVisible(self.x_spacerand, kind == "satin")
        self.x_ulangle.setValue(f.get("ul_angle", 90.0))
        self.x_ulspacing.setValue(f.get("ul_spacing", 2.2))
        self.x_ulinset.setValue(f.get("ul_inset", 0.6))
        self.x_ullayers.setCurrentIndex(max(0, self.x_ullayers.findData(int(f.get("ul_layers", 1)))))
        self.x_ulcontour.setChecked(bool(f.get("ul_contour", True)))
        self.x_satinul.setCurrentIndex(max(0, self.x_satinul.findData(f.get("satin_ul", "auto"))))
        self.x_satinul.setEnabled(bool(f.get("underlay", True)))
        self.x_expand.setValue(f.get("expand", 0.0))
        self.x_lenrand.setValue(max(f.get("len_random", 0.0), b.get("len_random", 0.0)))
        self.x_widthrand.setValue(f.get("width_random", 0.0))
        self.x_spacerand.setValue(f.get("spacing_random", 0.0))
        self.x_tie.setCurrentIndex(max(0, self.x_tie.findData(f.get("tie", "auto"))))
        self.x_tieforce.setChecked(bool(f.get("tie_force", False)))

    def _show_embfont(self, t):
        """Zeilen der Text-Karte je nach Computer- oder Stickschrift ein-/ausblenden."""
        from . import embfont
        fid = t.get("embfont") or ""
        info = next((f for f in embfont.font_index() if f["id"] == fid), None) if fid else None
        emb = info is not None
        self.t_emb.setText(("  " + info["name"]) if emb else "  Computerschrift – Stickschrift wählen …")
        self.t_emb.setIcon(icons.icon("text"))
        form = self.c_text.form
        form.setRowVisible(self.t_font, not emb)
        form.setRowVisible(self.t_info, True)
        form.setRowVisible(self.t_density, emb)
        form.setRowVisible(self.t_pull, emb)
        for i in range(form.rowCount()):
            lab = form.itemAt(i, QFormLayout.LabelRole)
            if lab and lab.widget() and lab.widget().text() == "Stil":
                form.setRowVisible(i, not emb)
        if emb:
            size = t["size"] * abs(self.obj.sy or 1)
            warn = ""
            if size < info["min"] - 0.05 or size > info["max"] + 0.05:
                warn = (f"<br><span style='color:#C62828'>⚠ Empfohlen sind {info['min']:.0f}–"
                        f"{info['max']:.0f} mm – sonst wird die Schrift zu dicht oder zu locker.</span>")
            nc = "<br>Nur private Nutzung (nicht kommerziell)." if info["noncommercial"] else ""
            self.t_info.setText(f"Empfohlene Höhe {info['min']:.0f}–{info['max']:.0f} mm · "
                                f"Lizenz {info['license']}{nc}{warn}")
        else:
            self.t_info.setText("Computerschriften werden automatisch digitalisiert. Für saubere "
                                "kleine Schrift besser eine Stickschrift wählen.")

    def _choose_embfont(self):
        if self.obj is None or self.obj.kind != "text":
            return
        from .fontdialog import EmbFontDialog
        dlg = EmbFontDialog(self.obj.text.get("embfont", ""), self.obj.text.get("text", "Abc"),
                            self.window())
        if not dlg.exec():
            return
        from . import embfont
        fid = dlg.selected or ""
        t = self.obj.text
        if fid and fid != t.get("embfont"):
            info = next(f for f in embfont.font_index() if f["id"] == fid)
            # Höhe in den empfohlenen Bereich bringen
            if not info["min"] <= t["size"] <= info["max"]:
                t["size"] = round(min(max(t["size"], info["min"]), info["max"]), 1)
        t["embfont"] = fid
        self.obj.sx = 1 if self.obj.sx >= 0 else -1
        self.obj.sy = 1 if self.obj.sy >= 0 else -1
        self.changed.emit(self.obj)
        self.refresh()

    def _fill_rows(self, kind, f):
        """Blendet nur die Felder ein, die zur gewählten Füllart passen."""
        fields = FILL_FIELDS.get(kind, set())
        form = self.c_fill.form
        for name, widget in (("angle", self.f_angle), ("density", self.f_density),
                             ("len", self.f_len), ("pattern", self.f_pattern),
                             ("size", self.f_size), ("pull", self.f_pull),
                             ("underlay", self.f_underlay), ("ulfirst", self.f_ulfirst),
                             ("color2", self.f_color2), ("grev", self.f_grev),
                             ("satintype", self.f_satintype), ("guide", self.f_guide_row),
                             ("short", self.f_short), ("shortdist", self.f_shortdist),
                             ("split", self.f_split), ("splitrand", self.f_splitrand),
                             ("gcolors", self.f_grow), ("tartan", self.f_trow),
                             ("tartan", self.f_tscale), ("tartan", self.f_tsym)):
            form.setRowVisible(widget, name in fields)
        ng = len(f.get("gradient_colors") or []) if "gcolors" in fields else -1
        for i, b in enumerate(self.f_gextra):
            form.setRowVisible(b, i < ng)
        form.setRowVisible(self.f_color, kind != "tartan")
        lab = form.labelForField(self.f_size)
        if lab:
            lab.setText(SIZE_LABELS.get(kind, "Mustergröße"))
        dl = form.labelForField(self.f_density)
        if dl:
            dl.setText("Linienabstand" if kind == "contour" else "Reihenabstand")
        self.f_pattern.blockSignals(True)
        self.f_pattern.clear()
        self._pattern_kind = kind
        if kind in ("tatami", "guided"):
            for label, key in TATAMI_PATTERNS:
                self.f_pattern.addItem(label, key)
            self.f_pattern.setCurrentIndex(max(0, self.f_pattern.findData(f.get("pattern"))))
        elif kind == "applique":
            for label, key in (("Heftstich: Zickzack", "zigzag"), ("Heftstich: Steppstich", "run")):
                self.f_pattern.addItem(label, key)
            self.f_pattern.setCurrentIndex(max(0, self.f_pattern.findData(f.get("pattern"))))
        elif kind == "motif":
            for label, key in FILL_MOTIFS:
                self.f_pattern.addItem(fill_icon("motif", {"motif": key, "size": 6.0}), label, key)
            self.f_pattern.setCurrentIndex(max(0, self.f_pattern.findData(f.get("motif"))))
        self.f_pattern.blockSignals(False)

    def _edit_tartan(self):
        if self.obj is None:
            return
        from .engine import TARTAN_PRESETS
        dlg = TartanDialog(self.obj.fill.get("tartan") or TARTAN_PRESETS["Royal Stewart"],
                           self.window())
        if dlg.exec():
            self.obj.fill["tartan"] = dlg.sett()
            self.obj.fill["type"] = "tartan"
            self.changed.emit(self.obj)
            self.refresh()

    def _fill_blocks(self):
        while self.blocks_box.count():
            w = self.blocks_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, b in enumerate(self.obj.blocks):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            lab = QLabel(f"{i + 1}.")
            lab.setFixedWidth(22)
            btn = ColorButton(b["color"])
            n = sum(1 for s in b["stitches"] if s[2] == STITCH)
            cnt = QLabel(f"{n:,}".replace(",", "."))
            cnt.setObjectName("muted")
            btn.colorChanged.connect(lambda c, i=i: self._block_color(i, c))
            h.addWidget(lab)
            h.addWidget(btn, 1)
            h.addWidget(cnt)
            self.blocks_box.addWidget(row)

    def _block_color(self, i, c):
        if self.obj and self.obj.kind == "stitches":
            self.obj.blocks[i]["color"] = c
            self.changed.emit(self.obj)

    # ---------------------------------------------------- einzelne Buchstaben
    def _fill_letters(self, obj):
        """Buchstabenliste des Schriftzugs füllen (Auswahl bleibt erhalten)."""
        try:
            centers = obj.letter_centers()
        except Exception:                          # Schrift fehlt o. Ä. – Karte einfach leer
            centers = []
        keep = self.l_pick.currentData()
        self.l_pick.blockSignals(True)
        self.l_pick.clear()
        for i, ch, _, _ in centers:
            mark = " •" if str(i) in (obj.text.get("letters") or {}) else ""
            self.l_pick.addItem(f"{i + 1}: {ch}{mark}", i)
        k = self.l_pick.findData(keep)
        self.l_pick.setCurrentIndex(k if k >= 0 else 0)
        self.l_pick.blockSignals(False)
        self._load_letter(obj)

    def _load_letter(self, obj):
        i = self.l_pick.currentData()
        v = (obj.text.get("letters") or {}).get(str(i), [0.0, 0.0, 0.0, 100.0]) if i is not None \
            else [0.0, 0.0, 0.0, 100.0]
        was = self._loading
        self._loading = True
        for w, val in zip((self.l_dx, self.l_dy, self.l_rot, self.l_size), v):
            w.setValue(float(val))
        self._loading = was

    def _letter_picked(self, *_):
        if self.obj is not None and self.obj.kind == "text":
            self._load_letter(self.obj)
            self.letter_selected.emit(self.l_pick.currentData()
                                      if self.l_pick.currentData() is not None else -1)

    def select_letter(self, i):
        """Vom Hauptfenster: Buchstabe i wurde auf der Arbeitsfläche angefasst."""
        k = self.l_pick.findData(i)
        if k >= 0 and k != self.l_pick.currentIndex():
            self.l_pick.blockSignals(True)
            self.l_pick.setCurrentIndex(k)
            self.l_pick.blockSignals(False)
        if self.obj is not None:
            self._load_letter(self.obj)

    def _letters_from_controls(self, o):
        letters = {k: list(v) for k, v in (o.text.get("letters") or {}).items()}
        i = self.l_pick.currentData()
        if i is None:
            return letters
        vals = [self.l_dx.value(), self.l_dy.value(), self.l_rot.value(), self.l_size.value()]
        if vals == [0.0, 0.0, 0.0, 100.0]:
            letters.pop(str(i), None)
        else:
            letters[str(i)] = vals
        return letters

    def _letter_reset(self, everything):
        o = self.obj
        if o is None or o.kind != "text":
            return
        if everything:
            o.text = dict(o.text, letters={})
            self._load_letter(o)
            self.changed.emit(o)
            return
        self._loading = True
        for w, val in zip((self.l_dx, self.l_dy, self.l_rot, self.l_size), (0, 0, 0, 100)):
            w.setValue(val)
        self._loading = False
        self._apply()

    def _edited(self, *_):
        if not self._loading and self.obj is not None:
            self._timer.start()

    def _edited_now(self, *_):
        if not self._loading and self.obj is not None:
            self._apply()

    def _apply(self):
        o = self.obj
        if o is None:
            return
        o.name = self.name.text() or o.name
        # Nur Felder übernehmen, die hier tatsächlich geändert wurden – sonst könnte ein
        # veralteter Wert das gerade mit der Maus verschobene Objekt zurücksetzen.
        changed = lambda k: abs(getattr(self, k).value() - self._shown.get(k, 1e9)) > 1e-6
        if changed("x"):
            o.x = self.x.value()
        if changed("y"):
            o.y = self.y.value()
        lw, lh = o.local_size()
        if changed("w") and lw > 0:
            o.sx = (1 if o.sx >= 0 else -1) * self.w.value() / lw
        if changed("h") and lh > 0:
            o.sy = (1 if o.sy >= 0 else -1) * self.h.value() / lh
        if changed("rot"):
            o.rot = self.rot.value() % 360
        o.trim_after = self.trim_after.currentData() or "auto"
        if o.kind in ("shape", "line") and self.smooth.value() != o.smooth:
            o.smooth = self.smooth.value()
        if o.kind == "text":
            new = dict(o.text, text=self.t_text.toPlainText() or " ",
                       font=self.t_font.currentFont().family(),
                       size=self.t_size.value(), bold=self.t_bold.isChecked(),
                       italic=self.t_italic.isChecked(), spacing=self.t_spacing.value(),
                       auto_satin=self.t_autosatin.isChecked(),
                       arc=self.t_arc.value(), emb_density=self.t_density.value(),
                       emb_pull=self.t_pull.value(),
                       path_align=self.t_palign.currentData() or "center",
                       path_flip=self.t_pflip.isChecked(),
                       env=self.t_env.currentData() or "none",
                       env_amount=self.t_envamt.value() / 100.0,
                       letters=self._letters_from_controls(o))
            if new != o.text:
                # Textänderung: Größe wieder über "Höhe" steuern
                o.text = new
                o.sx = 1 if o.sx >= 0 else -1
                o.sy = 1 if o.sy >= 0 else -1
        if o.kind in ("cross", "print"):
            self.changed.emit(o)
            self.refresh()
            return
        if o.kind == "stones":
            o.fill.update(stone=float(self.s_size.currentData()), color=self.s_color.color,
                          stone_style=self.s_style.currentData() or "crystal")
            self.changed.emit(o)
            self.refresh()
            return
        if o.kind == "satin":
            o.fill.update(color=self.f_color.color, density=self.f_density.value(),
                          pull=self.f_pull.value(), underlay=self.f_underlay.isChecked(),
                          satin_type=self.f_satintype.currentData() or "satin",
                          short_inset=self.f_short.value(), short_dist=self.f_shortdist.value(),
                          split_len=self.f_split.value(), split_random=self.f_splitrand.isChecked())
        elif o.kind in ("shape", "text"):
            kind = self.f_type.currentData()
            pat = self.f_pattern.currentData()
            o.fill.update(type=kind, color=self.f_color.color,
                          angle=self.f_angle.value(), density=self.f_density.value(),
                          stitch_len=self.f_len.value(), underlay=self.f_underlay.isChecked(),
                          underlay_first=self.f_ulfirst.isChecked(),
                          pull=self.f_pull.value(), size=self.f_size.value(),
                          color2=self.f_color2.color, gradient_reverse=self.f_grev.isChecked(),
                          knockout=self.f_knock.isChecked())
            if kind == "gradient":
                o.fill["gradient_colors"] = [b.color for b in self.f_gextra[:self.f_gcount.value() - 2]]
            if kind == "tartan":
                from .engine import TARTAN_PRESETS
                key = self.f_tartan.currentData()
                if key in TARTAN_PRESETS:
                    o.fill["tartan"] = [list(x) for x in TARTAN_PRESETS[key]]
                o.fill.update(tartan_scale=self.f_tscale.value(),
                              tartan_symmetric=self.f_tsym.isChecked())
            if pat and kind == "applique" and self._pattern_kind == "applique":
                o.fill["pattern"] = pat
            elif pat and kind in ("tatami", "guided") and self._pattern_kind == kind:
                o.fill["pattern"] = pat
            elif pat and kind == "motif" and self._pattern_kind == "motif":
                o.fill["motif"] = pat
        if o.kind != "stitches":
            o.border.update(type=self.b_type.currentData(), color=self.b_color.color,
                            width=self.b_width.value(), stitch_len=self.b_len.value(),
                            density=self.b_density.value(), repeats=self.b_repeats.value(),
                            corners=self.b_corners.isChecked(),
                            motif=self.b_motif.currentData() or "heart", gap=self.b_gap.value(),
                            motif_alt=self.b_alt.isChecked(),
                            motif_triple=self.b_mtriple.isChecked(),
                            len_random=self.x_lenrand.value(),
                            corner=self.x_corner.currentData() or "mitre",
                            auto_spacing=self.x_autosp.isChecked() if o.kind != "satin"
                            else o.border.get("auto_spacing", False),
                            bean_pattern=" ".join(map(str, engine.bean_pattern(self.b_bean.text())
                                                      or [])))
            o.fill.update(ul_angle=self.x_ulangle.value(), ul_spacing=self.x_ulspacing.value(),
                          ul_inset=self.x_ulinset.value(),
                          ul_layers=self.x_ullayers.currentData() or 1,
                          ul_contour=self.x_ulcontour.isChecked(),
                          satin_ul=self.x_satinul.currentData() or "auto",
                          expand=self.x_expand.value(), len_random=self.x_lenrand.value(),
                          width_random=self.x_widthrand.value(),
                          spacing_random=self.x_spacerand.value(),
                          tie=self.x_tie.currentData() or "auto",
                          underlay_auto=self.x_ulauto.isChecked(),
                          auto_spacing=self.x_autosp.isChecked() if o.kind == "satin"
                          else o.fill.get("auto_spacing", False),
                          puff=self.x_puff.isChecked() if o.kind == "satin"
                          else o.fill.get("puff", False),
                          tie_force=self.x_tieforce.isChecked())
        self.changed.emit(o)
        self.refresh()


# ------------------------------------------------------------ Reihenfolge
class SequencePanel(QWidget):
    selectionChanged = Signal(list)    # ids
    reordered = Signal(list)           # ids in neuer Reihenfolge
    visibilityToggled = Signal(str)
    renamed = Signal(str, str)
    action = Signal(str)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        title = QLabel("Stickreihenfolge")
        title.setObjectName("cardTitle")
        v.addWidget(title)
        hint = QLabel("Ziehen zum Umsortieren · Doppelklick zum Umbenennen")
        hint.setObjectName("muted")
        v.addWidget(hint)
        self.list = QListWidget()
        self.list.setObjectName("sequence")
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setIconSize(QSize(34, 34))
        self.list.setSpacing(2)
        self.list.itemSelectionChanged.connect(self._sel)
        self.list.model().rowsMoved.connect(self._moved)
        self.list.itemChanged.connect(self._item_changed)
        v.addWidget(self.list, 1)
        bar = QHBoxLayout()
        for name, tip, act in (("up", "Früher sticken", "up"), ("down", "Später sticken", "down"),
                               ("eye", "Ein-/Ausblenden", "toggle"),
                               ("lock", "Sperren/Entsperren (gesperrte Objekte sind auf der "
                                        "Arbeitsfläche nicht anklickbar)", "lock"),
                               ("duplicate", "Duplizieren", "duplicate"),
                               ("delete", "Löschen", "delete")):
            b = QToolButton()
            b.setIcon(icons.icon(name))
            b.setIconSize(QSize(20, 20))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=act: self.action.emit(a))
            bar.addWidget(b)
        bar.addStretch()
        v.addLayout(bar)

        info_t = QLabel("Design-Info")
        info_t.setObjectName("cardTitle")
        v.addWidget(info_t)
        self.info = QLabel()
        self.info.setObjectName("info")
        self.info.setTextFormat(Qt.RichText)
        self.info.setWordWrap(True)
        v.addWidget(self.info)
        self._updating = False

    def populate(self, objects, selected_ids):
        self._updating = True
        self.list.clear()
        gnum = {}
        for o in objects:
            if o.group:
                gnum.setdefault(o.group, len(gnum) + 1)
        for i, o in enumerate(objects):
            blocks = o.stitch_blocks()
            n = sum(1 for _, s in blocks for p in s if p[2] == STITCH)
            tag = (f"  ▣ Gruppe {gnum[o.group]}" if o.group else "") + \
                ("  🔒" if getattr(o, "locked", False) else "")
            it = QListWidgetItem(self._obj_icon(o), f"{o.name}\n{n:,} Stiche{tag}".replace(",", "."))
            it.setData(Qt.UserRole, o.id)
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            if not o.visible:
                it.setForeground(QColor("#9AA0AA"))
            self.list.addItem(it)
            it.setSelected(o.id in selected_ids)
        self._updating = False

    def _obj_icon(self, o):
        pm = QPixmap(68, 68)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#D5DAE3"), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(1, 1, 66, 66, 10, 10)
        geom = o.shaped_geometry()
        cols = o.colors() or ["#999999"]
        if geom is not None and not geom.is_empty:
            path = geom_path(geom)
            r = path.boundingRect()
            s = 48 / max(r.width(), r.height(), 1)
            p.translate(34, 34)
            p.scale(s, s)
            p.translate(-r.center())
            col = QColor(o.fill["color"] if o.fill["type"] != "none" else o.border["color"])
            p.setPen(QPen(QColor(o.border["color"]) if o.border["type"] != "none" else col.darker(130),
                          2.2 / s))
            p.setBrush(col if o.kind != "line" else Qt.NoBrush)
            p.drawPath(path)
        else:
            w = 48 / len(cols)
            for i, c in enumerate(cols[:12]):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(c))
                p.drawRoundedRect(10 + i * w, 20, max(w - 2, 3), 28, 3, 3)
        p.end()
        return QIcon(pm)

    def set_info(self, html):
        self.info.setText(html)

    def _sel(self):
        if not self._updating:
            self.selectionChanged.emit([it.data(Qt.UserRole) for it in self.list.selectedItems()])

    def _moved(self, *_):
        ids = [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]
        self.reordered.emit(ids)

    def _item_changed(self, it):
        if self._updating:
            return
        name = it.text().split("\n")[0].strip()
        if name:
            self.renamed.emit(it.data(Qt.UserRole), name)


# ---------------------------------------------------------------- Motive
class MotifPanel(QWidget):
    chosen = Signal(str)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        title = QLabel("Motive")
        title.setObjectName("cardTitle")
        v.addWidget(title)
        hint = QLabel("Klicken, um ein Motiv mittig in den Rahmen zu setzen.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.list = QListWidget()
        self.list.setObjectName("motifs")
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(64, 64))
        self.list.setGridSize(QSize(92, 96))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(4)
        palette = ["#E53935", "#FB8C00", "#FFC107", "#43A047", "#26C6DA", "#1E88E5", "#8E24AA",
                   "#EC407A"]
        for i, (name, fn) in enumerate(MOTIFS):
            it = QListWidgetItem(self._thumb(fn(), palette[i % len(palette)]), name)
            it.setData(Qt.UserRole, name)
            self.list.addItem(it)
        self.list.itemClicked.connect(lambda it: self.chosen.emit(it.data(Qt.UserRole)))
        v.addWidget(self.list, 1)

    def _thumb(self, geom, color):
        pm = QPixmap(128, 128)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        path = geom_path(geom)
        r = path.boundingRect()
        s = 100 / max(r.width(), r.height())
        p.translate(64, 64)
        p.scale(s, s)
        p.translate(-r.center())
        c = QColor(color)
        p.setPen(QPen(c.darker(140), 3 / s))
        p.setBrush(c)
        p.drawPath(path)
        p.end()
        return QIcon(pm)


# ------------------------------------------------------------ Palettenleiste
class HScrollArea(QScrollArea):
    """Waagerechter Bildlauf, der auch auf das normale Mausrad reagiert."""

    def wheelEvent(self, ev):
        d = ev.angleDelta()
        delta = d.x() if abs(d.x()) > abs(d.y()) else d.y()
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - delta)
        ev.accept()


class PaletteBar(QFrame):
    """Garnfarben der gewählten Garnkarte (Linksklick Füllung, Rechtsklick Rand)."""
    picked = Signal(str, bool)   # farbe, rand?
    chartChanged = Signal(str)
    snapRequested = Signal()
    stockSnapRequested = Signal()      # Design auf den eigenen Garnvorrat umstellen
    stockRequested = Signal()          # Garnvorrat bearbeiten

    def __init__(self):
        super().__init__()
        from .threads import chart_names
        self.setObjectName("paletteBar")
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 4, 12, 4)
        h.setSpacing(6)
        lab = QLabel("Garnfarben")
        lab.setObjectName("paletteLabel")
        lab.setToolTip("Linksklick: Füllfarbe · Rechtsklick: Rand-/Linienfarbe")
        h.addWidget(lab)
        self.chart = QComboBox()
        self.chart.addItem("StichWizard-Standard", "")
        for n in chart_names():
            self.chart.addItem(n, n)
        self.chart.setToolTip("Garnkarte: Farben mit echten Hersteller-Nummern")
        self.chart.setMaximumWidth(210)
        self.chart.currentIndexChanged.connect(lambda _: self.chartChanged.emit(self.chart.currentData()))
        h.addWidget(self.chart)
        snap = QToolButton()
        snap.setText("Anpassen")
        snap.setToolTip("Alle Farben des Designs auf die nächste Farbe dieser Garnkarte setzen – "
                        "Pfeil: auf deinen Garnvorrat anpassen oder den Vorrat bearbeiten")
        snap.setPopupMode(QToolButton.MenuButtonPopup)
        snap.clicked.connect(self.snapRequested.emit)
        sm = QMenu(snap)
        sm.addAction("An die Garnkarte anpassen", self.snapRequested.emit)
        sm.addAction("An meinen Garnvorrat anpassen", self.stockSnapRequested.emit)
        sm.addSeparator()
        sm.addAction("Mein Garnvorrat …", self.stockRequested.emit)
        snap.setMenu(sm)
        h.addWidget(snap)
        self.area = HScrollArea()
        self.area.setObjectName("paletteScroll")
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setWidgetResizable(True)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.area.setFixedHeight(42)
        self.area.setToolTip("Mausrad: durch die Farben blättern")
        h.addWidget(self.area, 1)
        self.all_btn = QToolButton()
        self.all_btn.setText("Alle …")
        self.all_btn.setToolTip("Alle Farben der Garnkarte in einem großen Fenster (mit Suche) – "
                                "gewählte Farbe wird zur Füllfarbe")
        self.all_btn.clicked.connect(self._open_all)
        h.addWidget(self.all_btn)
        self.fill()

    def _open_all(self):
        self.popup = ColorPopup(self.all_btn)
        self.popup.grid.picked.connect(self._picked_all)
        self.popup.show()

    def _picked_all(self, c):
        self.popup.close()
        self.picked.emit(c, False)

    def set_chart(self, name):
        self.chart.blockSignals(True)
        self.chart.setCurrentIndex(max(0, self.chart.findData(name)))
        self.chart.blockSignals(False)
        self.fill()

    def fill(self):
        from .threads import palette
        inner = QWidget()
        row = QHBoxLayout(inner)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        for name, col in palette():
            b = QToolButton()
            b.setObjectName("swatch")
            b.setIcon(icons.swatch(col, 20, radius=10))
            b.setIconSize(QSize(20, 20))
            b.setToolTip(f"{name}\nLinksklick: Füllung · Rechtsklick: Rand/Linie")
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, c=col: self.picked.emit(c, False))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _p, c=col: self.picked.emit(c, True))
            row.addWidget(b)
        row.addStretch()
        self.area.setWidget(inner)


class MultiSatinDialog(QDialog):
    """Farben und Überlappung für »Mehrfarbiger Satin«."""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mehrfarbiger Satin")
        self.setWindowIcon(icons.icon("multisatin"))
        v = QVBoxLayout(self)
        lab = QLabel("Die Säule wird der Länge nach in Streifen geteilt – Streifen 1 liegt an der "
                     "ersten Schiene. Jeder Streifen wird eine eigene Satinsäule.")
        lab.setWordWrap(True)
        v.addWidget(lab)
        f = QFormLayout()
        self.count = QSpinBox()
        self.count.setRange(2, 6)
        self.count.setValue(3)
        f.addRow("Anzahl Farben", self.count)
        self.overlap = spin(0, 40, 5, 0, " %", slider=True)
        self.overlap.setValue(10)
        self.overlap.setToolTip("Benachbarte Streifen greifen so weit ineinander (keine Lücken)")
        f.addRow("Überlappung", self.overlap)
        v.addLayout(f)
        self.buttons = []
        defaults = [color, "#FDD835", "#1E88E5", "#43A047", "#8E24AA", "#F4511E"]
        grid = QFormLayout()
        for i in range(6):
            b = ColorButton(defaults[i])
            self.buttons.append(b)
            grid.addRow(f"Streifen {i + 1}", b)
        self.grid = grid
        v.addLayout(grid)
        self.count.valueChanged.connect(self._rows)
        self._rows()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _rows(self, *_):
        for i, b in enumerate(self.buttons):
            self.grid.setRowVisible(b, i < self.count.value())

    def values(self):
        return [b.color for b in self.buttons[:self.count.value()]], self.overlap.value() / 100.0


class TartanDialog(QDialog):
    """Streifenfolge (Sett) eines Schottenkaros bearbeiten: Farbe und Breite je Streifen."""

    def __init__(self, sett, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tartan-Streifen")
        self.setWindowIcon(icons.icon("grid"))
        v = QVBoxLayout(self)
        lab = QLabel("Streifen von links nach rechts (bzw. oben nach unten). Die Folge gilt für "
                     "Längs- und Querrichtung.")
        lab.setWordWrap(True)
        v.addWidget(lab)
        self.rows = QVBoxLayout()
        v.addLayout(self.rows)
        self.items = []
        for c, w in sett:
            self._add(c, w)
        bar = QHBoxLayout()
        add = QPushButton("+ Streifen")
        add.clicked.connect(lambda: self._add("#FFFFFF", 2.0))
        bar.addWidget(add)
        bar.addStretch()
        v.addLayout(bar)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _add(self, color, width):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        b = ColorButton(color)
        w = spin(0.5, 30, 0.5, slider=True)
        w.setValue(float(width))
        rm = QToolButton()
        rm.setText("✕")
        rm.setToolTip("Streifen entfernen")
        item = (row, b, w)
        rm.clicked.connect(lambda: self._remove(item))
        h.addWidget(b, 1)
        h.addWidget(w)
        h.addWidget(rm)
        self.rows.addWidget(row)
        self.items.append(item)

    def _remove(self, item):
        if len(self.items) > 2:
            self.items.remove(item)
            item[0].deleteLater()

    def sett(self):
        return [[b.color, w.value()] for _, b, w in self.items]


# ---------------------------------------------------------------- Ebenen
class LayerPanel(QWidget):
    """Ebenen wie in Inkscape: oben steht die oberste Ebene (wird zuletzt gestickt).
    Auge = ein-/ausblenden (ausgeblendete Ebenen werden nicht gestickt), Schloss = sperren."""
    action = Signal(str, str)        # (befehl, ebenen-id)
    renamed = Signal(str, str)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        title = QLabel("Ebenen")
        title.setObjectName("cardTitle")
        v.addWidget(title)
        hint = QLabel("Klick = aktive Ebene (neue Objekte landen dort) · Doppelklick = umbenennen · "
                      "gestickt wird von unten nach oben")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.list = QListWidget()
        self.list.setObjectName("sequence")
        self.list.setSpacing(2)
        self.list.itemClicked.connect(lambda it: self.action.emit("activate", it.data(Qt.UserRole)))
        self.list.itemChanged.connect(self._changed)
        v.addWidget(self.list, 1)
        bar = QHBoxLayout()
        for icon, tip, act in (("new", "Neue Ebene über der aktiven", "add"),
                               ("up", "Ebene nach oben (später sticken)", "up"),
                               ("down", "Ebene nach unten (früher sticken)", "down"),
                               ("eye", "Aktive Ebene ein-/ausblenden", "toggle"),
                               ("lock", "Aktive Ebene sperren/entsperren", "lock"),
                               ("delete", "Aktive Ebene löschen (Objekte wandern in die Ebene "
                                          "darunter)", "delete")):
            b = QToolButton()
            b.setIcon(icons.icon(icon))
            b.setIconSize(QSize(20, 20))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=act: self.action.emit(a, self.current_id()))
            bar.addWidget(b)
        bar.addStretch()
        v.addLayout(bar)
        row = QHBoxLayout()
        mv = QPushButton("Auswahl hierher")
        mv.setToolTip("Ausgewählte Objekte in die aktive Ebene verschieben")
        mv.clicked.connect(lambda: self.action.emit("move_here", self.current_id()))
        sel = QPushButton("Alles darin wählen")
        sel.setToolTip("Alle Objekte der aktiven Ebene auswählen")
        sel.clicked.connect(lambda: self.action.emit("select", self.current_id()))
        row.addWidget(mv)
        row.addWidget(sel)
        v.addLayout(row)
        self._updating = False

    def current_id(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else ""

    def populate(self, doc):
        self._updating = True
        self.list.clear()
        counts = {}
        for o in doc.objects:
            counts[doc.layer_of(o)["id"]] = counts.get(doc.layer_of(o)["id"], 0) + 1
        for L in reversed(doc.layers):            # oberste Ebene oben
            state = ("" if L["visible"] else "  ⊘ ausgeblendet") + ("  🔒" if L["locked"] else "")
            it = QListWidgetItem(icons.icon("layers" if L["id"] == doc.active_layer else "layer"),
                                 f"{L['name']}\n{counts.get(L['id'], 0)} Objekt(e){state}")
            it.setData(Qt.UserRole, L["id"])
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            if not L["visible"]:
                it.setForeground(QColor("#9AA0AA"))
            f = it.font()
            f.setBold(L["id"] == doc.active_layer)
            it.setFont(f)
            self.list.addItem(it)
            if L["id"] == doc.active_layer:
                self.list.setCurrentItem(it)
        self._updating = False

    def _changed(self, it):
        if self._updating:
            return
        name = it.text().split("\n")[0].strip()
        if name:
            self.renamed.emit(it.data(Qt.UserRole), name)


# ---------------------------------------------------------------- Eigene Bibliothek
class LibraryPanel(QWidget):
    """Eigene Elemente und Designs: Vorschaubilder nach Kategorien, Doppelklick = einfügen."""
    action = Signal(str, str)        # (befehl, pfad)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        title = QLabel("Meine Bibliothek")
        title.setObjectName("cardTitle")
        v.addWidget(title)
        row = QHBoxLayout()
        self.cat = QComboBox()
        self.cat.currentIndexChanged.connect(lambda _: self.refresh())
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh())
        row.addWidget(self.cat, 1)
        row.addWidget(self.search, 1)
        v.addLayout(row)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(96, 96))
        self.list.setGridSize(QSize(118, 132))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(lambda it: self.action.emit("insert", it.data(Qt.UserRole)))
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        v.addWidget(self.list, 1)
        self.empty = QLabel("Noch leer. Objekte auswählen und »Auswahl speichern« – oder das ganze "
                            "Design speichern. Doppelklick auf ein Element fügt es ein.")
        self.empty.setObjectName("muted")
        self.empty.setWordWrap(True)
        v.addWidget(self.empty)
        bar = QHBoxLayout()
        for text, act, tip in (("Auswahl speichern …", "save_sel", "Ausgewählte Objekte als Element "
                                "speichern"),
                               ("Design speichern …", "save_all", "Das ganze Design als Element "
                                "speichern")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=act: self.action.emit(a, ""))
            bar.addWidget(b)
        v.addLayout(bar)
        self.refresh()

    def refresh(self):
        from . import library
        cur = self.cat.currentData()
        self.cat.blockSignals(True)
        self.cat.clear()
        self.cat.addItem("Alle Kategorien", "")
        for c in library.categories():
            self.cat.addItem(c, c)
        self.cat.setCurrentIndex(max(0, self.cat.findData(cur)))
        self.cat.blockSignals(False)
        self.list.clear()
        for path, name, cat in library.items(self.cat.currentData() or None, self.search.text()):
            img = library.thumbnail(path)
            ic = QIcon(QPixmap.fromImage(img)) if not img.isNull() else icons.icon("star")
            it = QListWidgetItem(ic, name)
            it.setData(Qt.UserRole, path)
            it.setToolTip(f"{name} ({cat}) – Doppelklick fügt ein")
            self.list.addItem(it)
        self.empty.setVisible(self.list.count() == 0)

    def _menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        path = it.data(Qt.UserRole)
        m = QMenu(self)
        m.addAction("Einfügen", lambda: self.action.emit("insert", path))
        m.addAction("Umbenennen / Kategorie …", lambda: self.action.emit("rename", path))
        m.addSeparator()
        m.addAction("Löschen", lambda: self.action.emit("delete", path))
        m.exec(self.list.mapToGlobal(pos))
