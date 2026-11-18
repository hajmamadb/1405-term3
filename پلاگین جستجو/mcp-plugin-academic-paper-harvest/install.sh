#!/usr/bin/env bash
# Installs the academic-paper-harvest plugin into your DSH user skills folder.
# Usage: ./install.sh   (from the package root)
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.agents/skills/academic-paper-harvest"

echo "Installing academic-paper-harvest -> $DEST"
mkdir -p "$DEST"

for item in SKILL.md references scripts; do
  if [ -e "$SRC/$item" ]; then
    rm -rf "$DEST/$item"
    cp -R "$SRC/$item" "$DEST/$item"
    echo "  copied $item"
  fi
done

# Verify
for req in "$DEST/SKILL.md" "$DEST/references" "$DEST/scripts"; do
  [ -e "$req" ] || { echo "ERROR: missing $req after install" >&2; exit 1; }
done

echo ""
echo "Installed successfully."
echo "  - SKILL.md"
echo "  - references/"
echo "  - scripts/ ($(find "$DEST/scripts" -type f | wc -l | tr -d ' ') files)"
echo ""
echo "Next: start CDP Chrome (login must be active) and drive via scripts/cdp.mjs."
echo "  node scripts/cdp.mjs list-targets"
