import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.routes import auth, parking, wallet, admin, esp32

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title="Smart Parking API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.CAPTURED_IMAGES_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.CAPTURED_IMAGES_DIR), name="images")

app.include_router(auth.router,    prefix="/api/auth",    tags=["auth"])
app.include_router(parking.router, prefix="/api/parking", tags=["parking"])
app.include_router(wallet.router,  prefix="/api/wallet",  tags=["wallet"])
app.include_router(esp32.router,   prefix="/api/esp32",   tags=["esp32"])
app.include_router(admin.router,   prefix="/api/admin",   tags=["admin"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
