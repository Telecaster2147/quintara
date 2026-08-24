#!/usr/bin/env bash
set -euo pipefail
PREFIX="${QUINTARA_PREFIX:-$HOME/.local}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLE="$ROOT/dist/Quintara"
if [[ ! -x "$BUNDLE" ]]; then
  echo "dist/Quintara is missing; build the PyInstaller bundle first." >&2
  exit 2
fi
mkdir -p "$PREFIX/lib/quintara" "$PREFIX/bin" "$PREFIX/share/applications"
cp "$BUNDLE" "$PREFIX/lib/quintara/Quintara"
chmod +x "$PREFIX/lib/quintara/Quintara"
ln -sfn "$PREFIX/lib/quintara/Quintara" "$PREFIX/bin/quintara"
cat > "$PREFIX/share/applications/quintara.desktop" <<DESKTOP
[Desktop Entry]
Name=Quintara
Comment=Local A-share weekly research
Exec=$PREFIX/bin/quintara gui
Terminal=false
Type=Application
Categories=Finance;Science;
DESKTOP
echo "Installed Quintara to $PREFIX"
