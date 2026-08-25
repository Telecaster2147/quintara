#!/usr/bin/env bash
set -euo pipefail
PREFIX="${QUINTARA_PREFIX:-$HOME/.local}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLE="$ROOT/dist/Quintara"
CLI_BUNDLE="$ROOT/dist/quintara-cli"
if [[ ! -x "$BUNDLE" || ! -x "$CLI_BUNDLE" ]]; then
  echo "dist/Quintara or dist/quintara-cli is missing; build both release bundles first." >&2
  exit 2
fi
mkdir -p "$PREFIX/lib/quintara/data/developer" "$PREFIX/bin" "$PREFIX/share/applications"
cp "$BUNDLE" "$PREFIX/lib/quintara/Quintara"
cp "$CLI_BUNDLE" "$PREFIX/lib/quintara/quintara-cli"
cp "$ROOT/packaging/developer_data/quintara-developer-data-v1.zip" "$PREFIX/lib/quintara/data/developer/"
cp "$ROOT/packaging/developer_data/README.txt" "$PREFIX/lib/quintara/data/developer/"
for size in 16 20 24 32 48 64 128 256; do
  icon_dir="$PREFIX/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$icon_dir"
  cp "$ROOT/src/quintara/assets/icons/quintara-${size}.png" "$icon_dir/quintara.png"
done
chmod +x "$PREFIX/lib/quintara/Quintara" "$PREFIX/lib/quintara/quintara-cli"
ln -sfn "$PREFIX/lib/quintara/Quintara" "$PREFIX/bin/quintara"
ln -sfn "$PREFIX/lib/quintara/quintara-cli" "$PREFIX/bin/quintara-cli"
cat > "$PREFIX/share/applications/quintara.desktop" <<DESKTOP
[Desktop Entry]
Name=Quintara
Comment=Local A-share weekly research
Exec=$PREFIX/bin/quintara
Icon=quintara
Terminal=false
Type=Application
Categories=Finance;Science;
DESKTOP
echo "Installed Quintara to $PREFIX"
