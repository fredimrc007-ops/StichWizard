"""Update-Hinweis: Versionsvergleich, passende Datei je Paketart, Fehler werden verschluckt
(ohne Oberfläche und ohne Internet lauffähig).

  .venv/bin/python tools/tests/update_test.py
"""
import io
import json
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from stichwizard import update  # noqa: E402

RELEASE = {"tag_name": "v9.1.0", "html_url": "https://github.com/x/y/releases/tag/v9.1.0",
           "body": "Neu: …", "draft": False, "prerelease": False,
           "assets": [{"name": "StichWizard-Setup-9.1.0.exe", "browser_download_url": "https://dl/exe"},
                      {"name": "StichWizard-9.1.0.flatpak", "browser_download_url": "https://dl/flatpak"}]}


def answer(data):
    def urlopen(req, timeout=None):
        if isinstance(data, Exception):
            raise data
        return io.BytesIO(json.dumps(data).encode())
    return urlopen


def run():
    fails = []
    checks = [("v1.32.0", "1.31.0", True), ("1.31.0", "1.31.0", False), ("1.30.9", "1.31.0", False),
              ("1.31.1", "1.31", True), ("2.0", "1.99.99", True), ("Version 1.40.0", "1.31.0", True),
              ("nightly", "1.31.0", False), ("", "1.31.0", False)]
    for remote, local, want in checks:
        if update.is_newer(remote, local) != want:
            fails.append(f"is_newer({remote!r}, {local!r}) ≠ {want}")

    if update.pick_asset(RELEASE, "windows") != "https://dl/exe":
        fails.append("Windows bekommt nicht den Installer")
    if update.pick_asset(RELEASE, "flatpak") != "https://dl/flatpak":
        fails.append("Flatpak bekommt nicht die .flatpak-Datei")
    if update.pick_asset(RELEASE, "source") != RELEASE["html_url"]:
        fails.append("Quellcode-Start bekommt nicht die Release-Seite")
    if update.pick_asset(dict(RELEASE, assets=[]), "windows") != RELEASE["html_url"]:
        fails.append("ohne passende Datei keine Release-Seite")

    with mock.patch("urllib.request.urlopen", answer(RELEASE)):
        res = update.fetch_latest()
    if not res or res["version"] != "9.1.0":
        fails.append(f"fetch_latest liefert {res}")
    for bad in (OSError("offline"), {"message": "Not Found"}, dict(RELEASE, draft=True),
                dict(RELEASE, prerelease=True)):
        with mock.patch("urllib.request.urlopen", answer(bad)):
            if update.fetch_latest() is not None:
                fails.append(f"kein None bei {str(bad)[:40]}")
    for f in fails:
        print("FEHLER", f)
    print("OK" if not fails else f"{len(fails)} Fehler")
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
