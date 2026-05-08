#!/bin/bash
# Full VPS setup script for claideco.work on Ubuntu 24.04
# Run as root: bash setup.sh
set -e

DOMAIN="claideco.work"
API_DIR="/var/www/pesobooks-api"
WEB_DIR="/var/www/claideco.work"
UPLOAD_DIR="/var/www/pesobooks-uploads"
REPO="https://github.com/kleyds/claideco.work.git"

echo "=== [1/9] System update ==="
apt update && apt upgrade -y

echo "=== [2/9] Install dependencies ==="
apt install -y \
    git curl nginx certbot python3-certbot-nginx \
    python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    tesseract-ocr \
    nodejs npm

echo "=== [3/9] Set up PostgreSQL ==="
PG_PASSWORD=$(openssl rand -base64 16)
sudo -u postgres psql <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pesobooks') THEN
        CREATE ROLE pesobooks WITH LOGIN PASSWORD '$PG_PASSWORD';
    END IF;
END
\$\$;
CREATE DATABASE pesobooks OWNER pesobooks;
SQL
echo "Postgres password: $PG_PASSWORD  <-- SAVE THIS"

echo "=== [4/9] Clone repository ==="
if [ -d "$API_DIR" ]; then
    cd "$API_DIR" && git pull
else
    git clone "$REPO" /tmp/claideco-repo
    mkdir -p "$API_DIR"
    cp -r /tmp/claideco-repo/backend/. "$API_DIR/"
fi

echo "=== [5/9] Backend Python setup ==="
cd "$API_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f "$API_DIR/.env" ]; then
    SECRET_KEY=$(openssl rand -hex 32)
    API_KEY=$(openssl rand -hex 16)
    cat > "$API_DIR/.env" <<ENV
APP_ENV=production
SECRET_KEY=$SECRET_KEY
API_KEY=$API_KEY
DATABASE_URL=postgresql+psycopg2://pesobooks:$PG_PASSWORD@localhost:5432/pesobooks
UPLOAD_DIR=$UPLOAD_DIR
MAX_FILE_SIZE_MB=20
MAX_FILES_PER_UPLOAD=50
CORS_ORIGINS=https://$DOMAIN,https://www.$DOMAIN
FRONTEND_BASE_URL=https://$DOMAIN

# Fill these in after setup:
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=you@gmail.com
SMTP_USE_TLS=true
ENV
    echo ".env created at $API_DIR/.env — edit it to add OPENAI_API_KEY and SMTP settings"
fi

echo "=== [6/9] Build frontend ==="
cd /tmp/claideco-repo/frontend
npm install
VITE_API_BASE_URL="https://$DOMAIN/v1" npm run build
mkdir -p "$WEB_DIR"
cp -r dist/. "$WEB_DIR/"

echo "=== [7/9] Set permissions ==="
mkdir -p "$UPLOAD_DIR"
chown -R www-data:www-data "$API_DIR" "$WEB_DIR" "$UPLOAD_DIR"
chmod -R 755 "$WEB_DIR"
chmod 600 "$API_DIR/.env"

echo "=== [8/9] Nginx + systemd ==="
cp /tmp/claideco-repo/deploy/nginx.conf /etc/nginx/sites-available/$DOMAIN
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
rm -f /etc/nginx/sites-enabled/default

cp /tmp/claideco-repo/deploy/pesobooks.service /etc/systemd/system/pesobooks.service
systemd-analyze verify /etc/systemd/system/pesobooks.service 2>/dev/null || true
systemctl daemon-reload
systemctl enable pesobooks
systemctl start pesobooks

echo "=== [9/9] SSL certificate (Let's Encrypt) ==="
# Temporarily serve HTTP for certbot challenge
sed -i 's/return 301/#return 301/' /etc/nginx/sites-available/$DOMAIN
cat > /etc/nginx/sites-available/${DOMAIN}-temp <<NGINX
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    root $WEB_DIR;
}
NGINX
ln -sf /etc/nginx/sites-available/${DOMAIN}-temp /etc/nginx/sites-enabled/${DOMAIN}-temp
nginx -t && systemctl reload nginx

certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

rm /etc/nginx/sites-enabled/${DOMAIN}-temp
rm /etc/nginx/sites-available/${DOMAIN}-temp
sed -i 's/#return 301/return 301/' /etc/nginx/sites-available/$DOMAIN

nginx -t && systemctl reload nginx

echo ""
echo "=============================="
echo " Setup complete!"
echo "=============================="
echo " Site:    https://$DOMAIN"
echo " API:     https://$DOMAIN/v1/docs"
echo " DB pass: $PG_PASSWORD"
echo ""
echo " Next steps:"
echo "  1. Edit $API_DIR/.env — add OPENAI_API_KEY and SMTP settings"
echo "  2. systemctl restart pesobooks"
echo "  3. Visit https://$DOMAIN"
echo "=============================="
