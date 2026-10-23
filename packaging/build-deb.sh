#!/usr/bin/env bash
set -euo pipefail
ENVLENS_SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENVLENS_STAGE="$(mktemp -d)"
mkdir -p "$ENVLENS_STAGE/DEBIAN" "$ENVLENS_STAGE/opt/envlens" "$ENVLENS_STAGE/usr/bin" "$ENVLENS_STAGE/usr/share/applications" "$ENVLENS_STAGE/usr/share/icons/hicolor/scalable/apps" "$ENVLENS_SOURCE/dist"
cp -R "$ENVLENS_SOURCE/src" "$ENVLENS_SOURCE/bin" "$ENVLENS_STAGE/opt/envlens/"
find "$ENVLENS_STAGE/opt/envlens" -type d -name __pycache__ -exec rm -r -- {} +
ln -s /opt/envlens/bin/envlens "$ENVLENS_STAGE/usr/bin/envlens"
ln -s /opt/envlens/bin/envlens-gui "$ENVLENS_STAGE/usr/bin/envlens-gui"
ln -s /opt/envlens/bin/envlens-capture "$ENVLENS_STAGE/usr/bin/envlens-capture"
cp "$ENVLENS_SOURCE/packaging/io.github.stevenmcsorley.EnvLens.desktop" "$ENVLENS_STAGE/usr/share/applications/"
cp "$ENVLENS_SOURCE/src/envlens/data/icons/io.github.stevenmcsorley.EnvLens.svg" "$ENVLENS_STAGE/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$ENVLENS_SOURCE/packaging/control" "$ENVLENS_STAGE/DEBIAN/control"
dpkg-deb --root-owner-group --build "$ENVLENS_STAGE" "$ENVLENS_SOURCE/dist/envlens_1.0.0_all.deb"
echo "Built $ENVLENS_SOURCE/dist/envlens_1.0.0_all.deb"
