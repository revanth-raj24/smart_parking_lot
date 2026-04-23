"""
Device registration and heartbeat routes — /api/devices/*

Called by ESP32 firmware:
  POST /api/devices/register   — on every boot (upserts IP + status)
  POST /api/devices/heartbeat  — every 15–30 s (keeps device marked online)
  GET  /api/devices/           — admin/debug: list all devices + live status
"""
import ipaddress
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.device_service import get_all_devices, touch_heartbeat, upsert_device

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    device_id: str
    current_ip: str
    device_type: str           # entry_cam | exit_cam
    port: int = 80
    firmware_version: Optional[str] = None

    @field_validator("current_ip")
    @classmethod
    def _chk_ip(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValueError(f"Invalid IP address: {v!r}")
        return v

    @field_validator("device_type")
    @classmethod
    def _chk_type(cls, v: str) -> str:
        if v not in ("entry_cam", "exit_cam"):
            raise ValueError("device_type must be 'entry_cam' or 'exit_cam'")
        return v


class HeartbeatRequest(BaseModel):
    device_id: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_200_OK, summary="ESP32 self-registration on boot")
def register_device(req: DeviceRegisterRequest, db: Session = Depends(get_db)):
    """
    Called by ESP32 on every boot after WiFi connects.

    Upsert behaviour:
      - device_id already in DB  → update current_ip, port, last_seen, status=online
      - device_id not in DB      → insert new record

    This is the ONLY way the backend learns a device's current IP.
    No static IP configuration is required or used.
    """
    device = upsert_device(
        db,
        device_id=req.device_id,
        current_ip=req.current_ip,
        device_type=req.device_type,
        port=req.port,
        firmware_version=req.firmware_version,
    )
    logger.info(f"[Devices] Register: {device.device_id!r} @ {device.current_ip}:{device.port}")
    return {
        "status": "registered",
        "device_id": device.device_id,
        "current_ip": device.current_ip,
    }


@router.post("/heartbeat", status_code=status.HTTP_200_OK, summary="ESP32 keepalive heartbeat")
def heartbeat(req: HeartbeatRequest, db: Session = Depends(get_db)):
    """
    Called by ESP32 every 15–30 seconds to signal it is alive.
    Updates last_seen and keeps status=online.

    Device is marked offline by the background watcher in main.py
    if no heartbeat is received within 60 seconds.
    """
    try:
        device = touch_heartbeat(db, req.device_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"status": "ok", "device_id": device.device_id, "last_seen": device.last_seen}


@router.get("/", summary="List all registered IoT devices")
def list_devices(db: Session = Depends(get_db)):
    """Returns all devices with live online/offline status derived from last_seen."""
    devices = get_all_devices(db)
    return {"count": len(devices), "devices": devices}
