#!/usr/bin/env bash
set -euo pipefail
ENVLENS_SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENVLENS_DEST="$HOME/.local/share/envlens"
/usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); from gi.repository import Adw; assert Adw.get_minor_version() >= 5 or Adw.get_major_version() > 1' || {
  echo 'Install dependencies: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1'
  exit 1
}
mkdir -p "$ENVLENS_DEST" "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
cp -R "$ENVLENS_SOURCE/src" "$ENVLENS_SOURCE/bin" "$ENVLENS_DEST/"
install -m 755 "$ENVLENS_SOURCE/uninstall.sh" "$ENVLENS_DEST/uninstall.sh"
ln -sfn "$ENVLENS_DEST/bin/envlens" "$HOME/.local/bin/envlens"
ln -sfn "$ENVLENS_DEST/bin/envlens-gui" "$HOME/.local/bin/envlens-gui"
ln -sfn "$ENVLENS_DEST/bin/envlens-capture" "$HOME/.local/bin/envlens-capture"
sed "s|^Exec=.*|Exec=\"$ENVLENS_DEST/bin/envlens-gui\"|" "$ENVLENS_SOURCE/packaging/io.github.stevenmcsorley.EnvLens.desktop" > "$HOME/.local/share/applications/io.github.stevenmcsorley.EnvLens.desktop"
install -m 644 "$ENVLENS_SOURCE/src/envlens/data/icons/io.github.stevenmcsorley.EnvLens.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/"
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Installed. Launch from Applications, or run: $HOME/.local/bin/envlens-gui"
