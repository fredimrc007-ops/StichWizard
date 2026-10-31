"""Nach neuen Versionen sehen (GitHub-Releases). Lädt nichts herunter und installiert nichts –
StichWizard zeigt nur einen Hinweis mit Link zur Download-Seite."""
import json
import os
import re
import sys
import threading
import urllib.request

from PySide6.QtCore import QObject, Signal

from . import __version__

REPO = "fredimrc007-ops/StichWizard"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"


def parse_version(text):
    """»v1.31.0« / »1.31« → (1, 31, 0); None, wenn keine Versionsnummer drinsteht."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", str(text or ""))
    if not m:
        return None
    return tuple(int(g or 0) for g in m.groups())


def is_newer(remote, local=__version__):
    r, l = parse_version(remote), parse_version(local)
    return bool(r and l and r > l)


def package_kind():
    """Welche Paketart läuft gerade: »windows« (Installer), »flatpak« oder »source«."""
    if sys.platform == "win32":
        return "windows"
    if os.environ.get("FLATPAK_ID"):
        return "flatpak"
    return "source"


def pick_asset(release, kind=None):
    """Passende Datei aus dem Release: .exe für Windows, .flatpak für das Flatpak,
    sonst (oder wenn keine passt) die Release-Seite."""
    kind = kind or package_kind()
    ext = {"windows": ".exe", "flatpak": ".flatpak"}.get(kind)
    for a in release.get("assets") or []:
        if ext and str(a.get("name", "")).lower().endswith(ext):
            return a.get("browser_download_url") or release.get("html_url") or RELEASES_URL
    return release.get("html_url") or RELEASES_URL


def fetch_latest(timeout=8):
    """Neuestes Release von GitHub: {"version", "url", "notes"} oder None (offline, kein Release,
    privates Repository …). Fehler werden verschluckt – ein Update-Hinweis ist nie wichtig genug,
    um den Start zu stören."""
    req = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"StichWizard/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rel = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    if rel.get("draft") or rel.get("prerelease"):
        return None
    version = rel.get("tag_name") or rel.get("name")
    if not parse_version(version):
        return None
    return {"version": str(version).lstrip("vV"), "url": pick_asset(rel),
            "page": rel.get("html_url") or RELEASES_URL, "notes": rel.get("body") or ""}


class UpdateChecker(QObject):
    """Fragt im Hintergrund nach; »finished« liefert das Ergebnis von fetch_latest() im
    Hauptthread (Qt stellt Signale aus fremden Threads in die Warteschlange)."""
    finished = Signal(object)

    def start(self):
        threading.Thread(target=lambda: self.finished.emit(fetch_latest()), daemon=True).start()
