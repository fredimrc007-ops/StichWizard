"""Gemeinsamer Ort der lokalen Steuerverbindung (ohne Qt, damit der MCP-Server schlank bleibt).

Linux/macOS: Unix-Socket im Laufzeitverzeichnis des Benutzers (im Flatpak: im App-Ordner darin).
Windows: Named Pipe \\\\.\\pipe\\stickstudio-<benutzer> (QLocalServer nutzt dort Pipes).
"""
import getpass
import os
import sys
import tempfile

SOCKET_NAME = "stickstudio.sock"


def socket_path():
    if sys.platform == "win32":
        user = "".join(c for c in getpass.getuser() if c.isalnum()) or "user"
        return f"stickstudio-{user}"
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "stickstudio")
    if os.environ.get("FLATPAK_ID") and os.environ.get("XDG_RUNTIME_DIR"):
        # Flatpak: dieser Ordner wird von allen Instanzen der App geteilt (Programm + MCP-Server)
        base = os.path.join(os.environ["XDG_RUNTIME_DIR"], "app", os.environ["FLATPAK_ID"])
    path = os.path.join(base, SOCKET_NAME)
    if len(path) > 100:   # Unix-Sockets erlauben nur ~107 Zeichen Pfadlänge
        base = os.path.join(tempfile.gettempdir(), f"stickstudio-{os.getuid()}")
        path = os.path.join(base, SOCKET_NAME)
    os.makedirs(base, mode=0o700, exist_ok=True)
    return path


def pipe_file(name):
    """Windows: Pfad der Named Pipe für open()."""
    return "\\\\.\\pipe\\" + name
