import os
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QColor, QPalette, QPixmapCache
from PySide6.QtWidgets import QApplication

from .mainwindow import MainWindow


def apply_light_palette(app, theme="light"):
    """Feste Farben (hell oder dunkel), unabhängig vom System-Theme – sonst erscheint z. B.
    weiße Schrift auf den hellen Eingabefeldern."""
    from . import style
    acc = style.accent()
    pal = QPalette()
    if theme == "dark":
        colors = {
            QPalette.Window: "#1D1F27", QPalette.WindowText: "#E4E7EE",
            QPalette.Base: "#262934", QPalette.AlternateBase: "#2C2F3B",
            QPalette.Text: "#E4E7EE", QPalette.PlaceholderText: "#8F96A8",
            QPalette.Button: "#2D3040", QPalette.ButtonText: "#E4E7EE",
            QPalette.BrightText: "#FFFFFF", QPalette.ToolTipBase: "#14161C",
            QPalette.ToolTipText: "#FFFFFF", QPalette.Highlight: acc,
            QPalette.HighlightedText: "#FFFFFF", QPalette.Link: style.accent_light(),
            QPalette.Light: "#3A3E4C", QPalette.Midlight: "#30333F", QPalette.Mid: "#4A4F5E",
            QPalette.Dark: "#14161C", QPalette.Shadow: "#000000",
        }
        for role, c in colors.items():
            pal.setColor(role, QColor(c))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
            pal.setColor(QPalette.Disabled, role, QColor("#6B7180"))
        app.setPalette(pal)
        return
    colors = {
        QPalette.Window: "#F3F5F8", QPalette.WindowText: "#2B2D3A",
        QPalette.Base: "#FFFFFF", QPalette.AlternateBase: "#F1F4F7",
        QPalette.Text: "#2B2D3A", QPalette.PlaceholderText: "#8A90A0",
        QPalette.Button: "#FFFFFF", QPalette.ButtonText: "#2B2D3A",
        QPalette.BrightText: "#FFFFFF", QPalette.ToolTipBase: "#232634",
        QPalette.ToolTipText: "#FFFFFF", QPalette.Highlight: acc,
        QPalette.HighlightedText: "#FFFFFF", QPalette.Link: style._mix(acc, "#000000", 0.25),
        QPalette.Light: "#FFFFFF", QPalette.Midlight: "#E3E6EC", QPalette.Mid: "#C9CFD9",
        QPalette.Dark: "#9AA0AA", QPalette.Shadow: "#5B6070",
    }
    for role, c in colors.items():
        pal.setColor(role, QColor(c))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#B0B5C0"))
    app.setPalette(pal)


def install_translations(app):
    """Qt-eigene Texte (Abbrechen, Ja/Nein, Dateidialog) auf Deutsch."""
    tr = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    if tr.load(QLocale(QLocale.German), "qtbase", "_", path):
        app.installTranslator(tr)


def main():
    if sys.platform == "win32":
        try:   # eigenes Symbol/Gruppierung in der Windows-Taskleiste statt »pythonw«
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StichWizard.StichWizard")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("StickStudio")      # interner Name: Einstellungs- und Cache-Ordner bleiben
    app.setApplicationDisplayName("StichWizard")
    app.setDesktopFileName(os.environ.get("FLATPAK_ID") or "stickstudio")
    from . import style
    app.setStyle(style.app_style())
    QPixmapCache.setCacheLimit(256 * 1024)   # KB – Platz für zwischengespeicherte Stickobjekte
    apply_light_palette(app)
    install_translations(app)
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1:
        w.load_path(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
