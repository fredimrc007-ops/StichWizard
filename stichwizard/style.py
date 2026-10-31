ACCENT = "#0FA3A3"

QSS = """
* { font-family: "Adwaita Sans", "Cantarell", "Segoe UI", "DejaVu Sans"; font-size: 10pt; }
QMainWindow, QDialog { background: #F3F5F8; }
QWidget#panelBody, QWidget#rightPanel { background: #F3F5F8; }

/* ---------- Kopfzeile / Ribbon ---------- */
QFrame#header { background: #232634; }
QLabel#logo { color: white; font-size: 15pt; font-weight: 700; padding: 0 0 0 8px; }
QLabel#logoAccent { color: #3FD0C9; font-size: 15pt; font-weight: 300; }
QLabel#docTitle { color: #AEB4C4; font-size: 10pt; }
QToolButton#quick { color: white; border: none; border-radius: 6px; padding: 4px; }
QToolButton#quick:hover { background: #343849; }

QTabWidget#ribbon::pane { border: none; background: #FFFFFF; border-bottom: 1px solid #DDE1E8; }
QTabWidget#ribbon > QTabBar { background: #232634; }
QTabWidget#ribbon > QTabBar::tab { background: transparent; color: #C9CEDA; padding: 7px 18px;
    margin: 0 2px; border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 600; }
QTabWidget#ribbon > QTabBar::tab:selected { background: #FFFFFF; color: #232634; }
QTabWidget#ribbon > QTabBar::tab:hover:!selected { background: #343849; color: white; }
QWidget#ribbonPage { background: #FFFFFF; }
QLabel#groupLabel { color: #8A90A0; font-size: 8pt; }
QFrame#groupSep { background: #E3E6EC; max-width: 1px; min-width: 1px; margin: 6px 4px; }
QScrollArea#ribbonScroll, QScrollArea#ribbonScroll > QWidget > QWidget { background: transparent; }
QScrollArea#ribbonScroll QScrollBar:horizontal { height: 6px; background: transparent; margin: 0 8px; }
QScrollArea#ribbonScroll QScrollBar::handle:horizontal { background: #C9CFD9; border-radius: 3px; min-width: 40px; }
QScrollArea#ribbonScroll QScrollBar::add-line, QScrollArea#ribbonScroll QScrollBar::sub-line { width: 0; }
QToolButton#ribbonBtn { border: none; border-radius: 8px; padding: 4px 6px; color: #2B2D3A; }
QToolButton#ribbonBtn:hover { background: #E7F6F6; }
QToolButton#ribbonBtn:checked { background: #D3F0EF; color: #0B7D7D; }
QToolButton#ribbonBtn:pressed { background: #C2E9E8; }

/* ---------- Werkzeugleiste links ---------- */
QToolBar#tools { background: #FFFFFF; border: none; border-right: 1px solid #DDE1E8; padding: 6px 4px; spacing: 4px; }
QToolBar#tools QToolButton { border-radius: 10px; padding: 5px; margin: 0px 2px; }
QToolBar#tools QToolButton:hover { background: #EEF1F5; }
QToolBar#tools QToolButton:checked { background: #0FA3A3; }

/* ---------- Rechte Seitenleiste ---------- */
QTabWidget#side::pane { border: none; border-left: 1px solid #DDE1E8; background: #F3F5F8; }
QTabWidget#side > QTabBar::tab { background: #FFFFFF; color: #5B6070; padding: 8px 7px; border: none;
    border-bottom: 2px solid #E3E6EC; font-weight: 600; }
QTabWidget#side > QTabBar::tab:selected { color: #0B7D7D; border-bottom: 2px solid #0FA3A3; }
QFrame#card { background: #FFFFFF; border: 1px solid #E1E5EC; border-radius: 12px; }
QLabel#cardTitle { font-weight: 700; color: #232634; font-size: 10.5pt; }
QLabel#muted { color: #8A90A0; font-size: 8.5pt; }
QLabel#hint { color: #6B7180; padding: 16px; background: #FFFFFF; border: 1px dashed #CBD1DB; border-radius: 12px; }
QLabel#info { background: #FFFFFF; border: 1px solid #E1E5EC; border-radius: 12px; padding: 10px; color: #3A3F4E; }
QLabel#imgBox { background: #FFFFFF; border: 1px solid #E1E5EC; border-radius: 10px; }

QLineEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QComboBox, QFontComboBox {
    background: #F6F7FA; border: 1px solid #D9DEE6; border-radius: 7px; padding: 4px 6px; min-height: 20px; }
QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #0FA3A3; background: #FFFFFF; }
QComboBox QAbstractItemView { selection-background-color: #0FA3A3; selection-color: #FFFFFF;
    outline: 0; }
QDoubleSpinBox:disabled { color: #B0B5C0; }
QAbstractSpinBox { padding-right: 18px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { subcontrol-origin: border; width: 16px;
    border: none; background: transparent; }
QAbstractSpinBox::up-button { subcontrol-position: top right; }
QAbstractSpinBox::down-button { subcontrol-position: bottom right; }
QAbstractSpinBox::up-arrow { image: url(%UP%); width: 9px; height: 6px; }
QAbstractSpinBox::down-arrow { image: url(%DOWN%); width: 9px; height: 6px; }
QPushButton { background: #FFFFFF; border: 1px solid #D9DEE6; border-radius: 8px; padding: 6px 12px; }
QPushButton:hover { border-color: #0FA3A3; }
QPushButton#primary, QDialogButtonBox QPushButton:default { background: #0FA3A3; color: white; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #0C8E8E; }
QPushButton#colorButton { text-align: left; padding: 5px 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }

QListWidget#sequence { background: #FFFFFF; border: 1px solid #E1E5EC; border-radius: 12px; padding: 4px; }
QListWidget#sequence::item { border-radius: 8px; padding: 4px; color: #2B2D3A; }
QListWidget#sequence::item:selected { background: #D3F0EF; color: #0B5F5F; }
QListWidget#sequence::item:hover:!selected { background: #F1F4F7; }
QListWidget#motifs { background: #FFFFFF; border: 1px solid #E1E5EC; border-radius: 12px; }
QListWidget#motifs::item { border-radius: 10px; color: #3A3F4E; }
QListWidget#motifs::item:hover { background: #E7F6F6; }
QListWidget#motifs::item:selected { background: #D3F0EF; color: #0B5F5F; }

/* ---------- Palettenleiste & Status ---------- */
QFrame#paletteBar { background: #FFFFFF; border-top: 1px solid #DDE1E8; }
QLabel#paletteLabel { font-weight: 700; color: #232634; }
QToolButton#swatch { border-radius: 12px; padding: 1px; }
QToolButton#swatch:hover { background: #DDE1E8; }
QStatusBar { background: #232634; color: #C9CEDA; }
QStatusBar QLabel { color: #C9CEDA; padding: 0 10px; }
QMenu { background: white; border: 1px solid #D9DEE6; border-radius: 8px; padding: 4px; }
QScrollArea#paletteScroll QScrollBar:horizontal { height: 6px; background: transparent; }
QScrollArea#paletteScroll QScrollBar::handle:horizontal { background: #C9CFD9; border-radius: 3px; min-width: 40px; }
QScrollArea#paletteScroll QScrollBar::add-line, QScrollArea#paletteScroll QScrollBar::sub-line { width: 0; }
QFrame#optSide { background: #F3F5F8; border-left: 1px solid #DDE1E8; }
QFrame#colorPopup { background: white; border: 1px solid #D9DEE6; border-radius: 8px; }
QMenu::item { padding: 6px 20px; border-radius: 6px; }
QMenu::item:selected { background: #E7F6F6; color: #0B5F5F; }
QScrollBar:vertical { width: 10px; background: transparent; }
QScrollBar::handle:vertical { background: #C9CFD9; border-radius: 5px; min-height: 30px; }
QScrollBar:horizontal { height: 10px; background: transparent; }
QScrollBar::handle:horizontal { background: #C9CFD9; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QToolTip { background: #232634; color: white; border: none; padding: 6px; border-radius: 6px; }
"""


# --------------------------------------------------------------- Farbschemata
# Dunkles Schema: Zuordnung der hellen Farben, getrennt nach Hintergrund, Schrift und Rahmen
DARK = {
    "bg": {"#F3F5F8": "#1D1F27", "#FFFFFF": "#262934", "white": "#262934", "#F6F7FA": "#2D3040",
           "#E7F6F6": "#1F3F42", "#D3F0EF": "#1C4A4C", "#C2E9E8": "#235659", "#EEF1F5": "#30333F",
           "#E3E6EC": "#383C4A", "#F1F4F7": "#2C2F3B", "#DDE1E8": "#3A3E4C", "#C9CFD9": "#4A4F5E",
           "#232634": "#14161C", "#343849": "#2A2D3A"},
    "fg": {"#2B2D3A": "#E4E7EE", "#232634": "#F0F2F6", "#5B6070": "#AEB4C4", "#8A90A0": "#8F96A8",
           "#6B7180": "#9AA0B0", "#3A3F4E": "#D0D4DE", "#0B7D7D": "#3FD0C9", "#0B5F5F": "#7FE3DD",
           "#B0B5C0": "#6B7180"},
    "bd": {"#DDE1E8": "#3A3E4C", "#E1E5EC": "#353948", "#D9DEE6": "#414657", "#CBD1DB": "#4A4F5E",
           "#E3E6EC": "#383C4A"},
}
CANVAS_BG = {"light": "#E6E9EF", "dark": "#2A2D38"}
CURRENT_THEME = "light"     # von MainWindow.apply_ui gesetzt

# Akzentfarben (Knöpfe, Auswahl, Markierungen) – frei kombinierbar mit Hell/Dunkel
ACCENTS = {"tuerkis": ("Türkis", "#0FA3A3"), "violett": ("Zauberer-Violett", "#6A55D8"),
           "blau": ("Blau", "#1E7FD8"), "gruen": ("Grün", "#2E9E5B"),
           "orange": ("Orange", "#E2702B"), "rose": ("Rosé", "#D6457A"),
           "graphit": ("Graphit", "#5B6475")}
CURRENT_ACCENT = "tuerkis"


def accent(key=None):
    return ACCENTS.get(key or CURRENT_ACCENT, ACCENTS["tuerkis"])[1]


def _mix(a, b, t):
    """Farbe a zu t Anteilen mit b mischen (t = 0 -> a, t = 1 -> b)."""
    from PySide6.QtGui import QColor
    ca, cb = QColor(a), QColor(b)
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t),
                  round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t)).name().upper()


def accent_light(key=None):
    """Hellere Variante (auf dunklem Grund, z. B. Kopfzeile)."""
    return _mix(accent(key), "#FFFFFF", 0.3)


def _accent_map(key):
    """Türkistöne des Grund-Stylesheets -> Töne der gewählten Akzentfarbe."""
    a = accent(key)
    return {"#0FA3A3": a, "#0B7D7D": _mix(a, "#000000", 0.25), "#0B5F5F": _mix(a, "#000000", 0.42),
            "#3FD0C9": _mix(a, "#FFFFFF", 0.3), "#7FE3DD": _mix(a, "#FFFFFF", 0.5),
            "#E7F6F6": _mix(a, "#FFFFFF", 0.9), "#D3F0EF": _mix(a, "#FFFFFF", 0.82),
            "#C2E9E8": _mix(a, "#FFFFFF", 0.74),
            "#1F3F42": _mix(a, "#262934", 0.72), "#1C4A4C": _mix(a, "#262934", 0.62),
            "#235659": _mix(a, "#262934", 0.52)}


def canvas_bg():
    return CANVAS_BG.get(CURRENT_THEME, CANVAS_BG["light"])
PANEL_BG = {"light": "#F3F5F8", "dark": "#1D1F27"}


def _theme(qss, theme):
    """Stylesheet auf ein Farbschema umstellen (nur »dark« ändert etwas)."""
    import re
    if theme != "dark":
        return qss

    def repl(m):
        prop, val = m.group(1), m.group(2)
        kind = "fg" if prop == "color" else "bd" if prop.startswith("border") else "bg"
        out = val
        for k, v in DARK[kind].items():
            out = re.sub(rf"(?i){re.escape(k)}\b", v, out)
        return f"{prop}: {out}"
    return re.sub(r"(background(?:-color)?|color|border(?:-[a-z]+)?)\s*:\s*([^;}]+)", repl, qss)


def _scale_fonts(qss, base):
    """Alle Schriftgrößen im Verhältnis zur Grundschrift (Standard 10 pt) skalieren."""
    import re
    f = base / 10.0
    return re.sub(r"font-size:\s*([\d.]+)pt", lambda m: f"font-size: {float(m.group(1)) * f:.1f}pt", qss)


def build_qss(theme="light", font_pt=10.0, accent_key=None):
    """Erzeugt kleine Pfeilgrafiken im Cache und setzt sie ins Stylesheet ein."""
    import os

    from PySide6.QtCore import QPointF, QStandardPaths, Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap, QPolygonF

    d = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation) or "/tmp",
                     "stickstudio")
    os.makedirs(d, exist_ok=True)
    paths = {}
    for name, pts in (("up", ((1, 10), (8, 2), (15, 10))), ("down", ((1, 2), (8, 10), (15, 2)))):
        pm = QPixmap(16, 12)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#9AA0B0" if theme == "dark" else "#6B7180"))
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        p.end()
        path = os.path.join(d, f"arrow_{name}_{theme}.png")
        pm.save(path)
        paths[name] = path.replace("\\", "/")
    qss = QSS.replace("%UP%", paths["up"]).replace("%DOWN%", paths["down"])
    qss = _theme(qss, theme)
    key = accent_key or CURRENT_ACCENT
    if key != "tuerkis":
        import re
        amap = _accent_map(key)
        qss = re.sub(r"#[0-9A-Fa-f]{6}\b", lambda m: amap.get(m.group(0).upper(), m.group(0)), qss)
    return _scale_fonts(qss, font_pt)


def app_style():
    """Fusion, aber Auswahllisten als normale Liste: Fusions Menü-Darstellung zeichnet den
    gewählten Eintrag mit Stylesheet weiß auf weiß (unlesbar)."""
    from PySide6.QtWidgets import QProxyStyle, QStyle

    class _Style(QProxyStyle):
        def styleHint(self, hint, option=None, widget=None, returnData=None):
            if hint == QStyle.SH_ComboBox_Popup:
                return 0
            return super().styleHint(hint, option, widget, returnData)
    return _Style("Fusion")
