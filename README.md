# Smart Parking System

An automated parking management system with IoT-based license plate recognition, real-time slot tracking, and wallet-based billing.

Vehicles are identified at entry and exit by ESP32-CAM modules. A vision LLM reads the license plate via OCR, and the backend manages slot assignment, session tracking, and fee deduction — no manual intervention needed.

---

## Features

- **Automated entry/exit** — IR sensor triggers camera; gate opens only for registered vehicles
- **Vision-based OCR** — License plate extraction via OpenRouter (Gemini Flash Lite) with retry logic
- **Real-time slot grid** — Live availability dashboard for both users and admins
- **Wallet billing** — Prepaid balance; fee auto-deducted on exit; denied if balance is insufficient
- **Admin dashboard** — Session control, user management, slot overrides, image captures, analytics
- **Hardware simulation** — Admin can upload images to test the full OCR → gate flow without real hardware
- **JWT authentication** — Role-based (user / admin) with origin-guard middleware
- **Rate limiting** — 200 req/min per IP via SlowAPI

---

## Architecture

```
┌─────────────────┐        HTTP POST (image)       ┌──────────────────────┐
│  Entry ESP32-CAM│ ──────────────────────────────► │                      │
│  (IR + Servo)   │ ◄────── ALLOW / DENY ────────── │   FastAPI Backend    │
└─────────────────┘                                  │   (Python + MySQL)   │
                                                     │                      │
┌─────────────────┐        HTTP POST (image)         │  • OCR via OpenRouter│
│  Exit ESP32-CAM │ ──────────────────────────────► │  • JWT auth          │
│  (IR + Servo)   │ ◄────── ALLOW / DENY ────────── │  • Wallet billing    │
└─────────────────┘                                  └──────────┬───────────┘
                                                                │  REST API
                              ┌─────────────────────┐          │
                              │   React User App    │ ─────────┤
                              │   (Vite, port 5173) │          │
                              └─────────────────────┘          │
                              ┌─────────────────────┐          │
                              │  React Admin App    │ ─────────┘
                              │  (Vite, port 5174)  │
                              └─────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2, Alembic, PyMySQL |
| Auth | JWT (python-jose), bcrypt |
| OCR | OpenRouter API (`google/gemini-2.5-flash-lite`) via openai SDK |
| Image processing | Pillow |
| Frontend (user) | React 18, Vite, Tailwind CSS, Axios |
| Frontend (admin) | React 18, Vite, Tailwind CSS, Axios |
| Hardware | ESP32-CAM (AI-Thinker), SG90 Servo, IR sensor |
| Production | Nginx, PM2, MySQL 8, Ubuntu VPS |

---

## Project Structure

```
smart-parking/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/routes/       # auth, parking, wallet, admin, esp32
│   │   ├── core/             # config, JWT, deps
│   │   ├── db/               # database, seed
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # OCR, billing, parking logic
│   ├── alembic/              # DB migrations
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # User-facing React app (port 5173)
│   └── .env.example
├── admin-app/                # Admin React app (port 5174)
│   └── .env.example
├── arduino_code/
│   ├── entry_gate/           # ESP32-CAM entry gate firmware
│   └── exit_gate/            # ESP32-CAM exit gate firmware
├── deployment/
│   ├── deploy.sh             # One-command VPS setup
│   └── nginx.conf            # Nginx reverse-proxy config
├── ecosystem.config.js       # PM2 process config
└── README.md
```

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20 LTS
- MySQL 8
- Arduino IDE (for firmware flashing)

### 1. Clone the repo

```bash
git clone https://github.com/your-username/smart-parking.git
cd smart-parking
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, OPENROUTER_API_KEY

alembic upgrade head
python -m app.db.seed             # Creates admin account + 11 slots

uvicorn main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/api/docs`

### 3. User app

```bash
cd frontend
cp .env.example .env
npm install
npm run dev                       # http://localhost:5173
```

### 4. Admin app

```bash
cd admin-app
npm install
npm run dev                       # http://localhost:5174
```

Default admin credentials (set via `ADMIN_SEED_EMAIL` / `ADMIN_SEED_PASSWORD` in `backend/.env`):
- Email: `admin@smartpark.com`
- Password: `admin123` — **change this before any deployment**

---

## Environment Variables

### `backend/.env`

| Variable | Description |
|---|---|
| `DATABASE_URL` | MySQL connection string |
| `SECRET_KEY` | JWT signing key — generate with `openssl rand -hex 32` |
| `ALGORITHM` | JWT algorithm (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL (default: `1440` = 24 h) |
| `OPENROUTER_API_KEY` | OpenRouter API key for OCR |
| `ENTRY_CAM_URL` | ESP32 entry-gate IP, e.g. `http://192.168.1.34/capture` |
| `EXIT_CAM_URL` | ESP32 exit-gate IP, e.g. `http://192.168.1.39/capture` |
| `CAPTURED_IMAGES_DIR` | Directory for saved JPEG captures |
| `ENVIRONMENT` | `development` or `production` |
| `USER_APP_ORIGIN` | CORS origin for user app |
| `ADMIN_APP_ORIGIN` | CORS origin for admin app |
| `ADMIN_SEED_EMAIL` | Admin account email (seeding only) |
| `ADMIN_SEED_PASSWORD` | Admin account password (seeding only) |

### `frontend/.env`

| Variable | Description |
|---|---|
| `VITE_ADMIN_APP_URL` | URL to the admin app (shown as a link) |

---

## ESP32 Firmware

Edit the User Config section at the top of each `.ino` file before flashing:

```cpp
// entry_gate/entry_gate.ino  (and exit_gate/exit_gate.ino)
#define WIFI_SSID      "YourNetworkName"
#define WIFI_PASSWORD  "YourNetworkPassword"
#define BACKEND_URL    "http://<server-ip>:8000/api/esp32/entry-event"
```

Open in Arduino IDE, select board **AI-Thinker ESP32-CAM**, and upload.

Required libraries (Arduino Library Manager):
- ArduinoJson by Benoit Blanchon v6.x
- ESP32 board package by Espressif

---

## VPS Deployment

```bash
# On your Ubuntu VPS — run as root from /var/www/smart-parking/
sudo bash deployment/deploy.sh
```

The script installs dependencies, sets up MySQL, builds both React apps, runs migrations, seeds the database, and starts the backend under PM2 with Nginx as the reverse proxy.

**Before running:**
1. Copy your project to `/var/www/smart-parking/`
2. Edit `deployment/nginx.conf` — replace `yourdomain.com` with your domain or IP
3. Set all real values in `backend/.env`
4. Set `ADMIN_SEED_PASSWORD` to a strong password

**After deployment:**
```bash
pm2 status                                  # check backend process
curl http://localhost:8000/api/health       # verify API is up
# For HTTPS:
certbot --nginx -d yourdomain.com -d admin.yourdomain.com
```

---

## API Documentation

Interactive Swagger UI: `http://localhost:8000/api/docs`  
ReDoc: `http://localhost:8000/api/redoc`

### Endpoint groups

| Tag | Prefix | Auth |
|---|---|---|
| `auth` | `/api/auth` | Public / JWT |
| `parking` | `/api/parking` | JWT |
| `wallet` | `/api/wallet` | JWT |
| `admin` | `/api/admin` | Admin JWT |
| `iot` | `/api/iot` | None (hardware) |

---

## Screenshots

> _Add screenshots here_

| User Dashboard | Admin Panel | Entry Gate |
|---|---|---|
| ![user-dashboard](docs/screenshots/user-dashboard.png) | ![admin-panel](docs/screenshots/admin-panel.png) | ![entry-gate](docs/screenshots/entry-gate.jpg) |

---

## License

MIT
