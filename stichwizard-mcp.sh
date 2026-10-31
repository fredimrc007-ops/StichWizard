#!/bin/sh
# MCP-Server für KI-Assistenten (Claude Code, Claude Desktop …). Wird vom KI-Programm gestartet.
# Wichtig: stdout gehört dem MCP-Protokoll, alle Meldungen gehen nach stderr.
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$DIR/.venv/bin/python" ] || ! "$DIR/.venv/bin/python" -c "import pyembroidery, pypdf" 2>/dev/null; then
    echo "Richte Python-Umgebung ein …" >&2
    rm -rf "$DIR/.venv"
    python3 -m venv --system-site-packages "$DIR/.venv" >&2 || exit 1
    "$DIR/.venv/bin/python" -m pip install -q pyembroidery pypdf >&2 || exit 1
fi
cd "$DIR" && exec "$DIR/.venv/bin/python" -m stichwizard.mcp_server
