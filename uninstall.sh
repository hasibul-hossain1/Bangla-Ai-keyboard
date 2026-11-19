#!/usr/bin/env bash
# Removes Bangla AI IME. Settings and learned words are kept unless you delete them.
set -euo pipefail

APP_DIR="$HOME/.local/lib/bangla-ai-ime"
BIN_LINK="$HOME/.local/bin/bangla-ai-ime"
COMPONENT_FILE="/usr/share/ibus/component/bangla-ai.xml"

if [ -x "$APP_DIR/bangla-ai-ime" ]; then
    read -r -p "Saved API key o muche felbo? [y/N] " answer || answer=""
    if [ "${answer,,}" = "y" ]; then
        "$APP_DIR/bangla-ai-ime" --clear-key || true
    fi
fi

sudo rm -f "$COMPONENT_FILE"
rm -rf "$APP_DIR"
rm -f "$BIN_LINK"
ibus restart || true

cat <<'EOF'
Uninstall shesh. Ei folder gulo rakha holo (chaile nije delete korun):
  ~/.config/bangla-ai-ime        (settings)
  ~/.local/share/bangla-ai-ime   (shekha word)
  ~/.cache/bangla-ai-ime         (log)
EOF
