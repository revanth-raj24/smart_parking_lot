# Smart Parking System

An automated parking management system with IoT-based license plate recognition, real-time slot tracking, wallet-based billing, and advance slot pre-booking.

Vehicles are identified at entry and exit by ESP32-CAM modules. The device captures a JPEG, pushes it to the backend, which runs OCR via a vision LLM and responds synchronously with `open` or `close`. No polling — the ESP32 controls its own servo based on the server response.

---

## Features

- **Push-based IoT pipeline** — IR sensor triggers capture; ESP32 POSTs image to backend and receives gate decision in one round-trip
- **Vision-based OCR** — License plate extraction via OpenRouter (Gemini 2.5 Flash Lite) with retry logic
- **Device registry** — ESP32s register their DHCP IP on boot and send heartbeats every 20s; backend marks devices offline after 60s of silence
- **Real-time slot grid** — Live availability dashboard for both users and admins (P1–P11)
- **Pre-booking system** — Reserve any slot for a future date and time window; overlap-aware conflict detection prevents double bookings
- **Wallet billing** — Prepaid balance; ₹60 first hour + ₹30 per additional hour; auto-deducted on exit; denied if balance is insufficient
- **Admin dashboard** — Sessions, user management, slot overrides, captures gallery, transactions, pre-bookings, gate control, hardware simulation, analytics
- **JWT authentication** — Role-based (user / admin) with origin-guard middleware
- **Rate limiting** — 200 req/min per IP via SlowAPI

---

## Architecture

```
┌─────────────────────┐   POST /api/iot/trigger (JPEG)   ┌──────────────────────┐
│  Entry ESP32-CAM    │ ───────────────────────────────►  │                      │
│  (IR + Servo + LED) │ ◄────── {"action":"open|close"} ─ │   FastAPI Backend    │
└─────────────────────┘                                    │   (Python + SQLite)  │
                                                           │   port 6626          │
┌─────────────────────┐   POST /api/iot/trigger (JPEG)    │                      │
│  Exit ESP32-CAM     │ ───────────────────────────────►  │  • OCR via OpenRouter│
│  (IR + Servo + LED) │ ◄────── {"action":"open|close"} ─ │  • JWT auth          │
└─────────────────────┘                                    │  • Wallet billing    │
                                                           │  • Pre-booking       │
                                                           └──────────┬───────────┘
                                                                      │  REST API
                               ┌─────────────────────┐               │
                               │   React User App    │ ──────────────┤
                               │   port 6637         │               │
                               └─────────────────────┘               │
                               ┌─────────────────────┐               │
                               │  React Admin App    │ ──────────────┘
                               │  port 6638          │
                               └─────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2, Alembic, SQLite |
| Auth | JWT (python-jose), bcrypt |
| OCR | OpenRouter API (`google/gemini-2.5-flash-lite`) via openai SDK |
| Image processing | Pillow |
| Frontend (user) | React 18, Vite, Tailwind CSS, Axios |
| Frontend (admin) | React 18, Vite, Tailwind CSS, Axios |
| Hardware | ESP32-CAM (AI-Thinker), SG90 Servo, IR sensor |
| Production | Nginx, PM2, Ubuntu VPS |

---

## Project Structure

```
smart-parking/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/routes/       # auth, parking, wallet, admin, devices, iot, esp32, prebook
│   │   ├── core/             # config, JWT, deps
│   │   ├── db/               # database, seed
│   │   ├── models/           # SQLAlchemy ORM models (incl. PreBooking)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # OCR, billing, parking logic, device service, prebooking service
│   ├── alembic/              # DB migrations (0001–0004)
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # User-facing React app (port 6637)
│   └── .env.example
├── admin-app/                # Admin React app (port 6638)
│   └── .env.example
├── arduino_code/
│   ├── entry_gate/           # ESP32-CAM entry gate firmware (v6.0)
│   └── exit_gate/            # ESP32-CAM exit gate firmware (v6.0)
├── deployment/
│   ├── deploy.sh             # One-command VPS setup
│   └── nginx.conf            # Nginx reverse-proxy config
├── ecosystem.config.js       # PM2 process config
└── README.md
```

---

## API Endpoints

### Auth — `/api/auth`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/register` | Public | Sign up; auto-creates wallet |
| POST | `/login` | Public | Returns JWT |
| GET | `/me` | JWT | Current user profile |
| PATCH | `/me` | JWT | Update name / phone |
| POST | `/vehicles` | JWT | Add license plate |
| GET | `/vehicles` | JWT | List user's vehicles |
| DELETE | `/vehicles/{id}` | JWT | Remove vehicle |

### Parking — `/api/parking`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/slots` | Public | All slots with live status |
| POST | `/book-slot` | JWT | Instant slot reservation |
| GET | `/my-sessions` | JWT | Parking history (last 50) |
| GET | `/active-session` | JWT | Current active session |

### Pre-Booking — `/api/prebook`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | JWT | Reserve a slot for a future date/time window |
| GET | `/my` | JWT | List current user's pre-bookings |
| DELETE | `/{id}` | JWT | Cancel a pre-booking |

**Conflict rule:** a new booking is rejected if any active booking for the same slot on the same date satisfies `existing_start < new_end AND existing_end > new_start`.

**Request body for `POST /api/prebook`:**
```json
{
  "slot_id": "P3",
  "date": "2026-05-01",
  "start_time": "10:00",
  "end_time": "12:00"
}
```

### Wallet — `/api/wallet`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/balance` | JWT | Current balance |
| POST | `/add` | JWT | Top-up (INR amount) |
| GET | `/transactions` | JWT | Transaction history (last 100) |

### Devices — `/api/devices`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/register` | Public | ESP32 upserts device_id + IP + type on boot |
| POST | `/heartbeat` | Public | Keepalive every 20s |
| GET | `/` | Admin JWT | List all devices with online/offline status |

### IoT — `/api/iot`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/trigger` | Public | ESP32 sends device_id + JPEG; responds `{"action":"open"\|"close"}` |

### Admin — `/api/admin`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/users` | List all users |
| GET/PATCH/DELETE | `/users/{id}` | View, edit, or delete user |
| GET | `/users/{id}/detail` | Full user detail with sessions and wallet |
| POST | `/users/{id}/wallet/credit` | Manually credit wallet |
| GET | `/sessions` | All sessions (filterable by status / plate) |
| PATCH | `/sessions/{id}/close` | Force-close an active session |
| GET | `/slots/occupied` | Occupied slots with tenant info |
| POST | `/override` | Override a slot's status |
| GET | `/prebookings` | All pre-bookings with user details |
| DELETE | `/prebookings/{id}` | Cancel any pre-booking (admin) |
| GET | `/latest-captures` | Most recent entry/exit images |
| GET | `/captures` | Full captures gallery |
| POST | `/gate-control` | Send open/close to ESP32 |
| GET | `/transactions` | All transactions (paginated, filterable) |
| GET | `/stats` | Slot counts, user count, active sessions, revenue |
| POST | `/simulate-entry` | Upload image to test entry OCR flow |
| POST | `/simulate-exit` | Upload image to test exit OCR flow |

### Health
```
GET /api/health   →  {"status": "ok", "version": "3.0.0"}
```

---

## Billing

| Duration | Cost |
|---|---|
| First hour (or part of) | ₹60 |
| Each additional hour | ₹30 |

Fee is deducted automatically at exit. If wallet balance is insufficient the exit is denied and logged as a `denied` session.

> **Pre-bookings do not deduct the wallet.** Payment is charged only when the vehicle physically parks and exits through the IoT gate.

---

## Pre-Booking Flow

```
User selects slot → switches to "Pre-Book" mode → clicks slot
→ picks date + start time + end time
→ backend checks for overlapping active bookings
→ booking saved (or 409 Conflict returned)
→ "My Bookings" page shows all reservations with cancel option
```

Admin can view and cancel all pre-bookings from the **Pre-Bookings** tab in the admin dashboard.

Pre-bookings are independent of the physical IoT pipeline — a pre-booked slot is not locked in the `parking_slots` table. The IoT entry flow remains unchanged.

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20 LTS
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
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, OPENROUTER_API_KEY

alembic upgrade head            # runs all 4 migrations including prebookings table
python -m app.db.seed           # creates admin account + 11 slots (P1–P11)

uvicorn main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 3. User app

```bash
cd frontend
cp .env.example .env
# Set VITE_API_BASE_URL=http://localhost:8000 in .env
npm install
npm run dev   # http://localhost:5173
```

### 4. Admin app

```bash
cd admin-app
# Create .env with: VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev   # http://localhost:5174
```

Default admin credentials (set via `ADMIN_SEED_EMAIL` / `ADMIN_SEED_PASSWORD` in `backend/.env`):
- Email: `admin@smartpark.com`
- Password: set in `.env` — **change before any deployment**

---

## Environment Variables

### `backend/.env`

| Variable | Description |
|---|---|
| `DATABASE_URL` | SQLite path, e.g. `sqlite:///./smart_parking.db` |
| `SECRET_KEY` | JWT signing key — `openssl rand -hex 32` |
| `ALGORITHM` | JWT algorithm (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL (default: `1440` = 24 h) |
| `OPENROUTER_API_KEY` | OpenRouter key for Gemini Flash Lite OCR |
| `CAPTURED_IMAGES_DIR` | Directory for saved JPEG captures |
| `ENVIRONMENT` | `development` or `production` |
| `USER_APP_ORIGIN` | CORS origin for user app |
| `ADMIN_APP_ORIGIN` | CORS origin for admin app |
| `ADMIN_SEED_EMAIL` | Admin account email (seeding only) |
| `ADMIN_SEED_PASSWORD` | Admin account password (seeding only) |

### `frontend/.env`

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Backend URL e.g. `http://localhost:8000` (empty = use Vite proxy) |
| `VITE_ENTRY_CAM_URL` | Entry camera MJPEG stream URL |
| `VITE_EXIT_CAM_URL` | Exit camera MJPEG stream URL |

### `admin-app/.env`

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Backend URL e.g. `http://localhost:8000` (empty = use Vite proxy) |
| `VITE_USER_APP_URL` | URL to the user app (shown as a link in admin panel) |

---

## Database Migrations

| Revision | Description |
|---|---|
| `0001` | Initial schema — users, vehicles, parking_slots, parking_sessions, wallet, transactions |
| `0002` | Add indexes; fix wallet balance precision to `Numeric(10,2)` |
| `0003` | Add `devices` table for dynamic IoT device registration |
| `0004` | Add `prebookings` table for advance slot reservation |

Run all migrations:
```bash
cd backend && alembic upgrade head
```

---

## ESP32 Firmware (v6.0)

Edit the User Config section at the top of each `.ino` file before flashing:

```cpp
#define DEVICE_ID        "entry"          // "entry" or "exit"
#define DEVICE_TYPE      "entry_cam"      // "entry_cam" or "exit_cam"
#define WIFI_SSID        "YourNetwork"
#define WIFI_PASSWORD    "YourPassword"
#define SERVER_BASE_URL  "http://<server-ip>:6626"
#define GATE_OPEN_ANGLE  90               // servo angle when open
#define GATE_CLOSE_ANGLE 0                // servo angle when closed
#define GATE_OPEN_MS     5000             // auto-close after 5s
```

**Boot sequence:**
1. Connect to WiFi
2. `POST /api/devices/register` — upsert device_id + current DHCP IP
3. Start local HTTP server on port 80 (for admin gate control)
4. Loop: send heartbeat every 20s, monitor IR sensor

**On IR trigger:**
1. Capture JPEG (352×288 CIF) to PSRAM
2. Flip 180° (AI-Thinker camera is physically inverted)
3. `POST /api/iot/trigger` with device_id + JPEG
4. Parse `{"action":"open"|"close"}` and control servo
5. Auto-close gate after 5s if opened

**Local HTTP endpoints (slave mode):**
- `GET /capture` — Serve latest JPEG frame
- `POST /gate` — Accept `{"action":"open"|"close"}` from admin
- `GET /status` — Device status (IP, gate state, heap, uptime)

**Required libraries (Arduino Library Manager):**
- ArduinoJson by Benoit Blanchon v6.x
- ESP32 board package by Espressif

**Board:** AI-Thinker ESP32-CAM

---

## VPS Deployment

```bash
# On your Ubuntu VPS
sudo bash deployment/deploy.sh
```

The script installs dependencies, builds both React apps, runs migrations, seeds the database, and starts all processes under PM2.

**Before running:**
1. Copy the project to the server
2. Edit `deployment/nginx.conf` — replace placeholder domain/IP
3. Set all real values in `backend/.env`
4. Set `VITE_API_BASE_URL=` (empty) in both frontend `.env` files — Nginx proxies `/api` to the backend
5. Set a strong `ADMIN_SEED_PASSWORD`

**PM2 processes:**

| Process | Port | Command |
|---|---|---|
| `smartpark-api` | 6626 | `uvicorn main:app` |
| `smartpark-frontend` | 6637 | `vite preview` |
| `smartpark-admin` | 6638 | `vite preview` |

**After deployment:**
```bash
pm2 status
curl http://localhost:6626/api/health
```

---

## License

MIT
