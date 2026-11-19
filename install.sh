#!/usr/bin/env bash
# Installs Bangla AI IME for the current user and registers it with IBus.
#   Code + venv: ~/.local/lib/bangla-ai-ime
#   Settings:    ~/.config/bangla-ai-ime/config.json
#   Learned words: ~/.local/share/bangla-ai-ime/user_dict.json
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/lib/bangla-ai-ime"
BIN_LINK="$HOME/.local/bin/bangla-ai-ime"
COMPONENT_FILE="/usr/share/ibus/component/bangla-ai.xml"

echo "==> System packages (sudo password lagbe)"
sudo apt-get install -y python3-venv python3-gi gir1.2-ibus-1.0 gir1.2-secret-1

echo "==> Python venv: $APP_DIR/venv"
mkdir -p "$APP_DIR"
python3 -m venv --system-site-packages "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade -r "$SRC_DIR/requirements.txt"

echo "==> Code copy: $APP_DIR/bangla_ai"
rm -rf "$APP_DIR/bangla_ai"
cp -r "$SRC_DIR/bangla_ai" "$APP_DIR/bangla_ai"

cat > "$APP_DIR/bangla-ai-ime" <<EOF
#!/bin/sh
export PYTHONPATH="$APP_DIR"
exec "$APP_DIR/venv/bin/python" -m bangla_ai "\$@"
EOF
chmod 755 "$APP_DIR/bangla-ai-ime"
mkdir -p "$(dirname "$BIN_LINK")"
ln -sf "$APP_DIR/bangla-ai-ime" "$BIN_LINK"

echo "==> IBus component: $COMPONENT_FILE"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sed "s|@EXEC@|$APP_DIR/bangla-ai-ime --ibus|" "$SRC_DIR/data/bangla-ai.xml.in" > "$tmp"
sudo install -m 644 "$tmp" "$COMPONENT_FILE"

echo "==> IBus restart"
ibus restart || echo "ibus restart kaj koreni; ekbar logout/login korun."

cat <<'EOF'

Install shesh. Ekhon:
  1. API key set korun:   bangla-ai-ime --set-key
  2. Settings -> Keyboard -> Input Sources -> "+" -> Bangla -> "Bangla AI (Phonetic + Claude)"
  3. Super+Space diye English <-> Bangla AI switch korun.
EOF
