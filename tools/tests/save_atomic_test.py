"""Projekt speichern darf die alte Datei nie zerstören (ohne Oberfläche lauffähig).

  .venv/bin/python tools/tests/save_atomic_test.py
"""
import os
import stat
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from stichwizard import fileio  # noqa: E402


def run():
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Design.stickproj")

        # 1. neue Datei anlegen, dann überschreiben
        fileio.write_text_atomic(path, '{"v": 1}')
        fileio.write_text_atomic(path, '{"v": 2, "ä": "ö"}')
        if open(path, encoding="utf-8").read() != '{"v": 2, "ä": "ö"}':
            fails.append("Inhalt nach dem Überschreiben falsch")

        # 2. Abbruch mitten im Schreiben: Original bleibt, keine Zwischendatei liegt herum

        def boom(fd):
            raise OSError(28, "Kein Platz mehr auf dem Gerät")
        with mock.patch.object(os, "fsync", boom):
            try:
                fileio.write_text_atomic(path, '{"v": 3, "halb": ')
                fails.append("Fehler beim Schreiben wurde verschluckt")
            except OSError:
                pass
        if open(path, encoding="utf-8").read() != '{"v": 2, "ä": "ö"}':
            fails.append("Original nach abgebrochenem Speichern beschädigt")
        if sorted(os.listdir(tmp)) != ["Design.stickproj"]:
            fails.append(f"Zwischendatei liegengeblieben: {os.listdir(tmp)}")

        # 3. Dateirechte der alten Datei bleiben erhalten
        os.chmod(path, 0o644)
        fileio.write_text_atomic(path, "{}")
        mode = stat.S_IMODE(os.stat(path).st_mode)
        if mode != 0o644:
            fails.append(f"Dateirechte geändert: {oct(mode)}")

        # 4. Verknüpfung: das Ziel wird ersetzt, der Link bleibt ein Link
        link = os.path.join(tmp, "Link.stickproj")
        os.symlink(path, link)
        fileio.write_text_atomic(link, '{"link": true}')
        if not os.path.islink(link) or open(path).read() != '{"link": true}':
            fails.append("Verknüpfung durch Datei ersetzt")
    for f in fails:
        print("FEHLER", f)
    print("OK" if not fails else f"{len(fails)} Fehler")
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
