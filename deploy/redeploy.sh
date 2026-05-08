#!/bin/bash
# Run this every time you want to deploy latest changes from GitHub.
# Run as root: bash redeploy.sh
set -e

DOMAIN="claideco.work"
API_DIR="/var/www/pesobooks-api"
WEB_DIR="/var/www/claideco.work"
REPO_DIR="/tmp/claideco-redeploy"

echo "=== Pulling latest code ==="
rm -rf "$REPO_DIR"
git clone https://github.com/kleyds/claideco.work.git "$REPO_DIR"

echo "=== Updating backend ==="
# Sync backend files but preserve .env
rsync -av --exclude='.env' --exclude='.venv' --exclude='uploads' \
    "$REPO_DIR/backend/" "$API_DIR/"
cd "$API_DIR"
.venv/bin/pip install -r requirements.txt

echo "=== Rebuilding frontend ==="
cd "$REPO_DIR/frontend"
npm install
VITE_API_BASE_URL="https://$DOMAIN/v1" npm run build
rsync -av --delete "$REPO_DIR/frontend/dist/" "$WEB_DIR/"

echo "=== Fix permissions ==="
chown -R www-data:www-data "$API_DIR" "$WEB_DIR"

echo "=== Restart backend ==="
systemctl restart pesobooks
systemctl status pesobooks --no-pager

echo "=== Done! https://$DOMAIN ==="
