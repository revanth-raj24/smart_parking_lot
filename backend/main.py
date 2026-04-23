import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.api.routes import auth, parking, wallet, admin, esp32, iot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter — IoT devices physically can't trigger faster than ~5 s/event
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

_DESCRIPTION = """
## Smart Parking System API

Automated parking management with **IoT-based license plate recognition**, real-time slot tracking, and wallet billing.

### How it works

1. **Register** an account and add your vehicle's license plate (`POST /api/auth/register`, `POST /api/auth/vehicles`).
2. **Top up** your wallet (`POST /api/wallet/add`).
3. **Drive in** — the entry-gate camera reads your plate via OCR and opens the gate automatically.
4. **Drive out** — the exit-gate camera bills your wallet and opens the gate.

### Authentication

Protected endpoints require a **Bearer JWT token**.
Get one via `POST /api/auth/login`, then click **Authorize** and paste it.

```
Authorization: Bearer <token>
```

### Rate limiting

All endpoints are capped at **200 requests / minute** per IP.

### IoT endpoints

`/api/iot/*` — canonical prefix for ESP32 firmware v2+.
`/api/esp32/*` — legacy prefix kept for already-flashed v1 hardware.
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
        "name": "iot",
        "description": (
            "**Master-Slave IoT (v4+)** — Server is master, ESP32 is slave. "
            "`POST /register` — ESP32 registers its IP on boot. "
            "`POST /trigger` — ESP32 notifies vehicle detected (no image); server fetches image, "
            "runs OCR, then commands the gate via `POST http://ESP32_IP/gate`. "
            "No user auth required."
        ),
    },
    {
        "name": "iot-legacy",
        "description": (
            "**Legacy push-mode (v3 firmware)** — ESP32 posts JPEG directly to server. "
            "Kept for hardware that has not been reflashed to v4 slave firmware."
        ),
    },
    {
        "name": "health",
        "description": "Service liveness check.",
    },
]

app = FastAPI(
    title="Smart Parking API",
    version="2.0.0",
    description=_DESCRIPTION,
    contact={"name": "Smart Parking Team", "email": "revanthrajrrp@gmail.com"},
    openapi_tags=_OPENAPI_TAGS,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    swagger_ui_parameters={
        "docExpansion": "list",
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "filter": True,
        "tryItOutEnabled": True,
        "syntaxHighlight.theme": "monokai",
    },
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Explicit allow-list — no wildcard.
# IoT devices (ESP32) don't send Origin headers, so CORS doesn't affect them.
_ALLOWED_ORIGINS = [
    settings.USER_APP_ORIGIN,                                           # http://localhost:5173
    settings.ADMIN_APP_ORIGIN,                                          # http://localhost:5174
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
# Defence-in-depth: block /api/admin requests arriving from the user-app
# origin. A stolen admin JWT in a user-app context cannot reach admin APIs.
@app.middleware("http")
async def admin_origin_guard(request: Request, call_next):
    if request.url.path.startswith("/api/admin"):
        origin = request.headers.get("origin", "")
        if origin and origin.rstrip("/") == settings.USER_APP_ORIGIN.rstrip("/"):
            logger.warning(f"[SECURITY] Admin endpoint blocked from user-app origin: {request.url.path}")
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

# IoT master-slave routes (v4+ firmware — server as master, ESP32 as slave)
app.include_router(iot.router,   prefix="/api/iot",   tags=["iot"])

# Legacy push-mode routes — v3 firmware that POSTs images directly
app.include_router(esp32.router, prefix="/api/esp32", tags=["iot-legacy"])


@app.get("/api/health", tags=["health"], summary="Health check")
def health():
    """Returns `ok` when the service is up."""
    return {"status": "ok", "version": "2.0.0"}
