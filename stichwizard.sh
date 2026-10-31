#!/bin/sh
# Startet StichWizard. Legt beim ersten Start eine venv mit pyembroidery an.
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$DIR/.venv/bin/python" ] || ! "$DIR/.venv/bin/python" -c "import pyembroidery, pypdf" 2>/dev/null; then
    echo "Richte Python-Umgebung ein …"
    rm -rf "$DIR/.venv"
    python3 -m venv --system-site-packages "$DIR/.venv" || exit 1
    "$DIR/.venv/bin/python" -m pip install -q pyembroidery pypdf || exit 1
fi
cd "$DIR" && exec "$DIR/.venv/bin/python" -m stichwizard "$@"
