#!/usr/bin/env bash
set -euo pipefail
rm -f -- "$HOME/.local/bin/envlens" "$HOME/.local/bin/envlens-gui" "$HOME/.local/bin/envlens-capture" "$HOME/.local/share/applications/io.github.stevenmcsorley.EnvLens.desktop" "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.stevenmcsorley.EnvLens.svg"
ENVLENS_INSTALLED="$HOME/.local/share/envlens"
if [[ -d "$ENVLENS_INSTALLED" ]]; then
  ENVLENS_RECOVERY="$(mktemp -d "$HOME/.local/share/envlens-uninstalled.XXXXXX")"
  mv -- "$ENVLENS_INSTALLED" "$ENVLENS_RECOVERY/app"
  echo "Application files moved to $ENVLENS_RECOVERY/app for recovery. Private captures and redaction key are retained in XDG data/state directories."
fi
