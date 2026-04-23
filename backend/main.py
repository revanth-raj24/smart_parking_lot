import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.db.database import SessionLocal
from app.api.routes import auth, parking, wallet, admin, esp32, iot
from app.api.routes import devices
from app.services.device_service import mark_stale_devices_offline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Background: mark devices offline when heartbeat times out ─────────────────

async def _offline_watcher() -> None:
    """Runs every 30 s; marks any device whose last_seen > 60 s ago as offline."""
    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            count = mark_stale_devices_offline(db)
            if count:
                logger.info(f"[OfflineWatcher] Marked {count} device(s) offline")
        except Exception as exc:
            logger.error(f"[OfflineWatcher] Error: {exc}")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_offline_watcher())
    logger.info("[Startup] Device offline watcher started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("[Shutdown] Device offline watcher stopped")


# ── Rate limiter ──────────────────────────────────────────────────────────────
# IoT devices physically can't trigger faster than ~5 s/event
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

_DESCRIPTION = """
## Smart Parking System API

Automated parking management with **IoT-based license plate recognition**,
real-time slot tracking, and wallet billing.

### How it works

1. **Register** an account and add your vehicle's license plate.
2. **Top up** your wallet (`POST /api/wallet/add`).
3. **Drive in** — the entry-gate camera reads your plate via OCR and opens the gate automatically.
4. **Drive out** — the exit-gate camera bills your wallet and opens the gate.

### Authentication

Protected endpoints require a **Bearer JWT token**.
Get one via `POST /api/auth/login`, then click **Authorize** and paste it.

### IoT Device Management

ESP32 devices register themselves on boot via `POST /api/devices/register`.
The backend discovers their current DHCP IP from the `devices` table — no static IPs needed.
"""

_OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "User registration, login, profile updates, and vehicle management.",
    },
    {
        "name": "parking",
        "description": "Parking slot availability, manual slot booking, and session history.",
    },
    {
        "name": "wallet",
        "description": "Wallet balance, INR top-ups, and transaction history.",
    },
    {
        "name": "admin",
        "description": (
            "**Admin only** — requires an admin JWT. "
            "User management, session control, slot overrides, analytics, "
            "image captures, gate control, and hardware simulation."
        ),
    },
    {
        "name": "devices",
        "description": (
            "**IoT device registry** — called by ESP32 firmware. "
            "`POST /register` — upserts device_id + current DHCP IP on boot. "
            "`POST /heartbeat` — keepalive every 15–30 s. "
            "Device is marked offline automatically after 60 s of silence."
        ),
    },
    {
        "name": "iot",
        "description": (
            "**Master-Slave IoT (v5+)** — Server is master, ESP32 is slave. "
            "`POST /trigger` — ESP32 notifies vehicle detected; server fetches image, "
            "runs OCR, then commands the gate. Device IP is resolved from DB — never from config."
        ),
    },
    {
        "name": "iot-legacy",
        "description": (
            "**Legacy push-mode (v3 firmware)** — ESP32 posts JPEG directly to server. "
            "Kept for hardware that has not been reflashed to v5 slave firmware."
        ),
    },
    {
        "name": "health",
        "description": "Service liveness check.",
    },
]

app = FastAPI(
    title="Smart Parking API",
    description=_DESCRIPTION,
    openapi_tags=_OPENAPI_TAGS,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Custom validation error handler ───────────────────────────────────────────
# Prevents UnicodeDecodeError when multipart request validation fails with binary data
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", "Validation error"),
                    "type": err.get("type", "value_error"),
                }
                for err in exc.errors()
            ]
        },
    )

# ── CORS ──────────────────────────────────────────────────────────────────────
_ALLOWED_ORIGINS = [
    settings.USER_APP_ORIGIN,
    settings.ADMIN_APP_ORIGIN,
    settings.USER_APP_ORIGIN.replace("localhost", "127.0.0.1"),
    settings.ADMIN_APP_ORIGIN.replace("localhost", "127.0.0.1"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Admin origin guard ────────────────────────────────────────────────────────
@app.middleware("http")
async def admin_origin_guard(request: Request, call_next):
    if request.url.path.startswith("/api/admin"):
        origin = request.headers.get("origin", "")
        if origin and origin.rstrip("/") == settings.USER_APP_ORIGIN.rstrip("/"):
            logger.warning(
                f"[SECURITY] Admin endpoint blocked from user-app origin: {request.url.path}"
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Admin API is not accessible from the user portal."},
            )
    return await call_next(request)


# ── Static files ──────────────────────────────────────────────────────────────
os.makedirs(settings.CAPTURED_IMAGES_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.CAPTURED_IMAGES_DIR), name="images")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,    prefix="/api/auth",    tags=["auth"])
app.include_router(parking.router, prefix="/api/parking", tags=["parking"])
app.include_router(wallet.router,  prefix="/api/wallet",  tags=["wallet"])
app.include_router(admin.router,   prefix="/api/admin",   tags=["admin"])

# IoT device registry (register on boot, heartbeat every 20 s)
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])

# IoT master-slave event pipeline (trigger → fetch image → OCR → gate)
app.include_router(iot.router,   prefix="/api/iot",   tags=["iot"])

# Legacy push-mode routes — v3 firmware that POSTs images directly
app.include_router(esp32.router, prefix="/api/esp32", tags=["iot-legacy"])


@app.get("/api/health", tags=["health"], summary="Health check")
def health():
    return {"status": "ok", "version": "3.0.0"}
