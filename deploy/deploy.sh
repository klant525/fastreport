#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fastreport}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICE_NAME="${SERVICE_NAME:-fastreport}"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Missing APP_DIR: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

$PYTHON_BIN -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

sudo cp deploy/fastreport.service "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

echo "FastReport deployed. Check status with:"
echo "sudo systemctl status ${SERVICE_NAME}"
