#!/bin/bash
# SmartPark VPS Deployment Script — PM2 + Nginx + SQLite
# Usage: sudo bash deploy.sh
# Run from: /var/www/smart-parking/deployment/
set -e

APP_DIR="/var/www/smart-parking"
LOG_DIR="/var/log/smartpark"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   SmartPark VPS Deployment (PM2 mode)    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
echo "[1/7] Installing system packages..."
apt update -qq
apt install -y curl git nginx python3 python3-pip python3-venv build-essential

# ── 2. Node.js 20 LTS via NodeSource ─────────────────────────────────────────
echo "[2/7] Installing Node.js 20 LTS..."
if ! node --version 2>/dev/null | grep -q "v20"; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
fi
echo "Node: $(node --version)  npm: $(npm --version)"

# ── 3. PM2 ───────────────────────────────────────────────────────────────────
echo "[3/7] Installing PM2..."
npm install -g pm2

# ── 4. Backend ─────────────────────────────────────────────────────────────────────
echo "[4/7] Setting up FastAPI backend..."
cd "$APP_DIR/backend"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  ✗ backend/.env was created from .env.example."
    echo "    STOP HERE — edit $APP_DIR/backend/.env with real values then re-run."
    echo ""
    exit 1
fi

# Create captured images directory
mkdir -p "$(grep CAPTURED_IMAGES_DIR .env | cut -d= -f2 | tr -d ' ')"
mkdir -p "$LOG_DIR"
chown -R www-data:www-data "$LOG_DIR"

# Run migrations
alembic upgrade head
echo "  ✓ Migrations applied"

# Seed database (idempotent)
python -m app.db.seed
echo "  ✓ Database seeded"

deactivate

# ── 5. Frontend (User App) ───────────────────────────────────────────────────────────
echo "[5/7] Building user frontend..."
cd "$APP_DIR/frontend"
[ ! -f .env ] && cp .env.example .env
npm ci --prefer-offline
npm run build
echo "  ✓ User app built → dist/"

# ── 6. Admin App ──────────────────────────────────────────────────────────────────────
echo "[6/7] Building admin frontend..."
cd "$APP_DIR/admin-app"
[ ! -f .env ] && cp .env.example .env
npm ci --prefer-offline
npm run build
echo "  ✓ Admin app built → dist/"

# ── 7. Nginx ───────────────────────────────────────────────────────────────────────
echo "[7/7] Configuring Nginx..."
cp "$APP_DIR/deployment/nginx.conf" /etc/nginx/sites-available/smart-parking
ln -sf /etc/nginx/sites-available/smart-parking /etc/nginx/sites-enabled/smart-parking
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

# ── PM2 startup ───────────────────────────────────────────────────────────────
echo ""
echo "Starting backend with PM2..."
cd "$APP_DIR"
pm2 start ecosystem.config.js --env production
pm2 save
pm2 startup systemd -u root --hp /root | tail -1 | bash

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          Deployment Complete!            ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  PM2 status:    pm2 status"
echo "  API logs:      pm2 logs smartpark-api"
echo "  Nginx status:  systemctl status nginx"
echo "  Health check:  curl http://localhost:8000/api/health"
echo ""
echo "  Next steps:"
echo "  1. Update nginx.conf: replace yourdomain.com with your real domain/IP"
echo "  2. Update backend/.env: real DB password, SECRET_KEY, OPENROUTER_API_KEY"
echo "  3. Update USER_APP_ORIGIN and ADMIN_APP_ORIGIN in backend/.env"
echo "  4. For HTTPS: certbot --nginx -d yourdomain.com -d admin.yourdomain.com"
echo ""
