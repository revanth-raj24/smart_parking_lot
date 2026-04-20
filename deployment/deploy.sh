#!/bin/bash
# VPS Deployment Script — run as root or sudo user
# Usage: bash deploy.sh

set -e
APP_DIR="/var/www/smart-parking"

echo "=== SmartPark VPS Deployment ==="

# 1. System packages
apt update && apt install -y python3 python3-pip python3-venv nodejs npm nginx mysql-server

# 2. Clone / copy code (assumes code is already in APP_DIR)
# git clone https://github.com/yourrepo/smart-parking $APP_DIR

# 3. Backend setup
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy .env
[ ! -f .env ] && cp .env.example .env && echo "Edit $APP_DIR/backend/.env before continuing" && exit 1

# Run migrations
alembic upgrade head

# Seed database
python -m app.db.seed

# 4. Frontend build
cd "$APP_DIR/frontend"
[ ! -f .env ] && cp .env.example .env
npm install
npm run build

# 5. Nginx config
cp "$APP_DIR/deployment/nginx.conf" /etc/nginx/sites-available/smart-parking
ln -sf /etc/nginx/sites-available/smart-parking /etc/nginx/sites-enabled/smart-parking
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 6. Systemd service
cp "$APP_DIR/deployment/smartparking.service" /etc/systemd/system/smartparking.service
systemctl daemon-reload
systemctl enable smartparking
systemctl restart smartparking

echo ""
echo "=== Deployment complete ==="
echo "Backend status: $(systemctl is-active smartparking)"
echo "Nginx status:   $(systemctl is-active nginx)"
echo ""
echo "Next steps:"
echo "  1. Edit $APP_DIR/backend/.env with real DB credentials + Gemini API key"
echo "  2. Edit $APP_DIR/frontend/.env with ESP32 camera IPs"
echo "  3. Update nginx.conf server_name with your domain/IP"
echo "  4. (Optional) certbot --nginx -d your-domain.com  (for HTTPS)"
