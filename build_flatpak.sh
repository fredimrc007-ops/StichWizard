#!/bin/sh
# Baut StichWizard als Flatpak (Datei dist/StichWizard-<version>.flatpak).
# Benötigt: flatpak, krb5 + keyutils auf dem Host, die Laufzeit org.freedesktop.Platform//26.08 (Flathub) und python3 mit pip
# (.venv) zum Herunterladen der Python-Pakete. flatpak-builder wird nicht gebraucht.
#
# Installieren:  flatpak install --user dist/StichWizard-<version>.flatpak
# Starten:       flatpak run local.stichwizard.StichWizard
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APPID=local.stichwizard.StichWizard
RUNTIME=org.freedesktop.Platform
BRANCH=26.08
PYVER=3.14
VERSION=$("$DIR/.venv/bin/python" -c "import sys; sys.path.insert(0, '$DIR'); import stichwizard; print(stichwizard.__version__)")
B="$DIR/build/flatpak"
mkdir -p "$B/wheels" "$DIR/dist"
cd "$B"

echo "== 1/6 Laufzeit prüfen"
flatpak info "$RUNTIME//$BRANCH" >/dev/null 2>&1 || {
    echo "Laufzeit fehlt – bitte installieren: flatpak install flathub $RUNTIME//$BRANCH"; exit 1; }

echo "== 2/6 Python-Pakete für Linux (manylinux, Python $PYVER)"
PLAT=""
for v in $(seq 17 44); do PLAT="$PLAT --platform manylinux_2_${v}_x86_64"; done
"$DIR/.venv/bin/python" -m pip download -q --only-binary=:all: $PLAT --platform manylinux2014_x86_64 \
    --python-version "$PYVER" --implementation cp -d wheels \
    PySide6-Essentials shapely numpy pyembroidery pypdf

echo "== 3/6 App-Verzeichnis anlegen"
rm -rf app repo
flatpak build-init app "$APPID" "$RUNTIME" "$RUNTIME" "$BRANCH"
F=app/files
SP="$F/lib/python$PYVER/site-packages"
mkdir -p "$SP" "$F/share/stichwizard" "$F/bin"
for w in wheels/*.whl; do unzip -q -o "$w" -d "$SP"; done
# Nicht benötigte Qt-Teile entfernen (QML/Quick, PDF-Viewer, Designer-Werkzeuge)
Q="$SP/PySide6"
rm -rf "$Q/qml" "$Q/include" "$Q/typesystems" "$Q/glue" "$Q/scripts" "$Q/Qt/qml"
rm -f "$Q"/Qt/lib/libQt6Quick* "$Q"/Qt/lib/libQt6Qml* "$Q"/Qt/lib/libQt6Pdf* \
      "$Q"/Qt/lib/libQt6ShaderTools* "$Q"/Qt/lib/libQt6Designer* \
      "$Q"/QtQuick*.so "$Q"/QtQml*.so "$Q"/QtPdf*.so "$Q"/QtDesigner*.so \
      "$Q"/designer "$Q"/linguist "$Q"/assistant "$Q"/lupdate "$Q"/lrelease \
      "$Q"/qmlformat "$Q"/qmllint "$Q"/qmlls "$Q"/qmlcachegen "$Q"/qmltyperegistrar
rm -rf "$Q/Qt/plugins/qmltooling" "$Q/Qt/plugins/designer" "$SP/test"
find "$Q/Qt/translations" -type f ! -name "qt*_de.qm" ! -name "qt*_en.qm" -delete 2>/dev/null || true

# QtNetwork (Steuerverbindung für die KI) braucht Kerberos – fehlt in der Laufzeit, daher
# vom Hostsystem mitnehmen (gleiche glibc-Generation wie die Laufzeit)
for l in libgssapi_krb5.so.2 libkrb5.so.3 libk5crypto.so.3 libkrb5support.so.0 libkeyutils.so.1; do
    src=""
    for d in /usr/lib /usr/lib64 /usr/lib/x86_64-linux-gnu /lib/x86_64-linux-gnu; do
        [ -e "$d/$l" ] && { src="$d/$l"; break; }
    done
    [ -n "$src" ] || { echo "$l fehlt auf diesem System (Paket krb5 / keyutils installieren)"; exit 1; }
    cp -L "$src" "$F/lib/$l"
done

cp -r "$DIR/stichwizard" "$F/share/stichwizard/"
find "$F/share/stichwizard" -name "__pycache__" -type d -prune -exec rm -rf {} +
# Lizenztexte genau der mitgelieferten Pakete (Qt/PySide6, Shapely/GEOS, NumPy, pyembroidery …)
"$DIR/.venv/bin/python" "$DIR/tools/collect_licenses.py" "$SP" \
    "$F/share/stichwizard/stichwizard/licenses" "$PYVER (Flatpak-Laufzeit)"
cp "$DIR/README.md" "$F/share/stichwizard/"
mkdir -p "$F/share/stichwizard/docs"
cp "$DIR/docs/StichWizard-Anleitung.pdf" "$F/share/stichwizard/docs/"

cat > "$F/bin/stichwizard" <<'EOF'
#!/bin/sh
export PYTHONPATH=/app/share/stichwizard
exec python3 -m stichwizard "$@"
EOF
cat > "$F/bin/stichwizard-mcp" <<'EOF'
#!/bin/sh
# MCP-Server (stdin/stdout gehören dem Protokoll)
export PYTHONPATH=/app/share/stichwizard
exec python3 -m stichwizard.mcp_server "$@"
EOF
chmod +x "$F/bin/stichwizard" "$F/bin/stichwizard-mcp"

echo "== 4/6 Desktop-Eintrag, Symbol, Dateitypen, AppStream"
mkdir -p "$F/share/applications" "$F/share/metainfo" "$F/share/mime/packages" "$F/share/icons/hicolor"
sed "s/@APPID@/$APPID/g" "$DIR/tools/flatpak/stichwizard.desktop" > "$F/share/applications/$APPID.desktop"
sed -e "s/@APPID@/$APPID/g" -e "s/@VERSION@/$VERSION/g" -e "s/@DATE@/$(date +%F)/g" \
    "$DIR/tools/flatpak/metainfo.xml" > "$F/share/metainfo/$APPID.metainfo.xml"
cp "$DIR/tools/flatpak/mime.xml" "$F/share/mime/packages/$APPID.xml"
QT_QPA_PLATFORM=offscreen "$DIR/.venv/bin/python" "$DIR/tools/make_icon.py" --hicolor \
    "$F/share/icons/hicolor" "$APPID"
# Python-Dateien vorübersetzen (schnellerer Start), mit dem Python der Laufzeit
flatpak build app python3 -m compileall -q -j 0 /app/share/stichwizard "/app/lib/python$PYVER/site-packages" >/dev/null

echo "== 5/6 Berechtigungen"
flatpak build-finish app --command=stichwizard \
    --share=ipc --socket=wayland --socket=fallback-x11 --device=dri \
    --filesystem=home --filesystem=/run/media --filesystem=/media >/dev/null

echo "== 6/6 Paket bauen"
flatpak build-export repo app stable >/dev/null
flatpak build-bundle repo "$DIR/dist/StichWizard-$VERSION.flatpak" "$APPID" stable \
    --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
echo "Fertig: $DIR/dist/StichWizard-$VERSION.flatpak"
