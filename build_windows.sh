#!/bin/sh
# Baut den Windows-Installer (StichWizard-Setup-<version>.exe) unter Linux.
# Benötigt: python3 mit pip (.venv), wine, curl, unzip. Ergebnis landet in dist/.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
B="$DIR/build/windows"
PYVER=3.12.10
PYTAG=312
VERSION=$("$DIR/.venv/bin/python" -c "import sys; sys.path.insert(0, '$DIR'); import stichwizard; print(stichwizard.__version__)")
export WINEPREFIX="$B/wineprefix" WINEDEBUG=-all WINEDLLOVERRIDES="mscoree=;mshtml=;winemenubuilder.exe=d"

mkdir -p "$B/downloads" "$B/wheels" "$DIR/dist"
cd "$B"

echo "== 1/6 Python $PYVER für Windows"
[ -f downloads/python-embed.zip ] || curl -fsSL -o downloads/python-embed.zip \
    "https://www.python.org/ftp/python/$PYVER/python-$PYVER-embed-amd64.zip"

echo "== 2/6 Windows-Pakete von PyPI"
"$DIR/.venv/bin/python" -m pip download -q --only-binary=:all: --platform win_amd64 \
    --python-version "$PYTAG" --implementation cp -d wheels \
    PySide6-Essentials shapely numpy pyembroidery pypdf

echo "== 3/6 Programmordner zusammenstellen"
rm -rf stage && mkdir -p stage/python stage/app
unzip -q downloads/python-embed.zip -d stage/python
mkdir -p stage/python/Lib/site-packages
for w in wheels/*.whl; do unzip -q -o "$w" -d stage/python/Lib/site-packages; done
cat > "stage/python/python$PYTAG._pth" <<EOF
python$PYTAG.zip
.
Lib\\site-packages
..\\app
import site
EOF
cp -r "$DIR/stichwizard" stage/app/
find stage/app -name "__pycache__" -type d -prune -exec rm -rf {} +
# Lizenztexte genau der mitgelieferten Pakete (Qt/PySide6, Shapely/GEOS, NumPy, pyembroidery …)
"$DIR/.venv/bin/python" "$DIR/tools/collect_licenses.py" stage/python/Lib/site-packages \
    stage/app/stichwizard/licenses "$PYVER"
cp "$DIR/README.md" stage/
mkdir -p stage/app/docs
cp "$DIR/docs/StichWizard-Anleitung.pdf" stage/app/docs/
# Nicht benötigte Qt-Teile entfernen (QML/Quick, Designer-Werkzeuge) – spart viel Platz
Q=stage/python/Lib/site-packages/PySide6
rm -rf "$Q/qml" "$Q/include" "$Q/typesystems" "$Q/glue" "$Q/scripts"
rm -f "$Q"/Qt6Quick*.dll "$Q"/Qt6Qml*.dll "$Q"/Qt6Pdf*.dll "$Q"/Qt6ShaderTools.dll \
      "$Q"/Qt6Designer*.dll "$Q"/designer.exe "$Q"/linguist.exe "$Q"/assistant.exe \
      "$Q"/lupdate.exe "$Q"/lrelease.exe "$Q"/qmlformat.exe "$Q"/qmllint.exe "$Q"/qmlls.exe \
      "$Q"/QtQuick*.pyd "$Q"/QtQml*.pyd "$Q"/QtPdf*.pyd "$Q"/QtDesigner.pyd
rm -rf stage/python/Lib/site-packages/test   # Testordner aus pyembroidery
find "$Q/translations" -type f ! -name "qt*_de.qm" ! -name "qt*_en.qm" -delete 2>/dev/null || true

echo "== 4/6 Programmsymbol"
QT_QPA_PLATFORM=offscreen "$DIR/.venv/bin/python" "$DIR/tools/make_icon.py" stage/stichwizard.ico

echo "== 5/6 Inno Setup (in eigener Wine-Umgebung)"
# Wine verknüpft Desktop/Dokumente … sonst mit den echten Linux-Ordnern – hier abkoppeln
[ -d "$WINEPREFIX/drive_c" ] || wineboot -i >/dev/null 2>&1
for l in "$WINEPREFIX"/drive_c/users/*/*; do
    if [ -L "$l" ]; then rm "$l" && mkdir "$l"; fi
done
if [ ! -f "$WINEPREFIX/drive_c/InnoSetup/ISCC.exe" ]; then
    [ -f downloads/innosetup.exe ] || curl -fsSL -o downloads/innosetup.exe \
        "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
    head -c 2 downloads/innosetup.exe | grep -q MZ || { echo "Inno-Setup-Download fehlerhaft"; exit 1; }
    wine downloads/innosetup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER \
        /DIR="C:\\InnoSetup" >/dev/null 2>&1
    wineserver -w
fi
[ -f "$WINEPREFIX/drive_c/InnoSetup/ISCC.exe" ] || { echo "Inno Setup wurde nicht installiert"; exit 1; }

echo "== 6/6 Installer bauen"
sed "s/@VERSION@/$VERSION/g" "$DIR/tools/stichwizard.iss" > stage/stichwizard.iss
wine "$WINEPREFIX/drive_c/InnoSetup/ISCC.exe" /Q "/O$(winepath -w "$DIR/dist")" \
    "$(winepath -w "$B/stage/stichwizard.iss")"
echo "Fertig: $DIR/dist/StichWizard-Setup-$VERSION.exe"
