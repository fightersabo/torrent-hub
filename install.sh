#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOWNLOAD_DIR="$PROJECT_DIR/data/downloads"

sudo apt-get update
sudo apt-get install -y transmission-daemon python3-venv python3-pip curl ffmpeg

sudo systemctl stop transmission-daemon || true

if [ -f /etc/transmission-daemon/settings.json ]; then
  sudo cp /etc/transmission-daemon/settings.json /etc/transmission-daemon/settings.json.bak || true
  sudo sed -i "s#\"download-dir\": \".*\"#\"download-dir\": \"$DOWNLOAD_DIR\"#" /etc/transmission-daemon/settings.json
  sudo sed -i 's/"rpc-authentication-required":.*/"rpc-authentication-required": false,/' /etc/transmission-daemon/settings.json
  sudo sed -i 's/"rpc-whitelist-enabled":.*/"rpc-whitelist-enabled": false,/' /etc/transmission-daemon/settings.json
  sudo sed -i 's/"incomplete-dir-enabled":.*/"incomplete-dir-enabled": false,/' /etc/transmission-daemon/settings.json
fi

sudo systemctl start transmission-daemon || true

python3 -m venv "$PROJECT_DIR/.venv"
source "$PROJECT_DIR/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

echo "\nSetup complete!"
echo "1) Activate the virtualenv: source $PROJECT_DIR/.venv/bin/activate"
echo "2) Launch the API/UI: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
echo "Transmission RPC runs on port 9091. Adjust TRANSMISSION_* env vars if needed."
