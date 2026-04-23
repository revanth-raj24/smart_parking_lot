"""
IoT master routes — Server-as-master / ESP32-as-slave architecture (v4.0).

Flow per event:
  1. ESP32 boots → POST /api/iot/register  (registers device_id + current IP)
  2. IR fires   → ESP32 POSTs /api/iot/trigger  (no image — just "I saw a car")
  3. Server     → returns 202 Accepted immediately
  4. Background → server GETs  http://ESP32_IP/capture  (pulls JPEG from slave)
  5. Background → server runs OCR + parking business logic
  6. Background → server POSTs http://ESP32_IP/gate  {"action": "open"|"close"}
  7. ESP32      → controls servo on /gate command, auto-closes after timeout
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import asyncio
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.vehicle import Vehicle
from app.models.parking_session import ParkingSession, SessionStatus
from app.models.wallet import Wallet
from app.services.ocr import (
    extract_license_plate,
    flip_image_horizontal,
    save_captured_image,
    OCRFailedException,
)
from app.services.parking_service import (
    find_available_slot,
    get_active_session_for_vehicle,
    open_session,
    deny_session,
    close_session,
    InsufficientBalanceError,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Device registry ───────────────────────────────────────────────────────────
# Keyed by device_id ("entry" | "exit").
# Seeded from .env so fixed-IP deployments work without a /register call.
_registry: dict[str, dict] = {}


def _seed_registry() -> None:
    if settings.ENTRY_CAM_IP:
        _registry["entry"] = {
            "ip": settings.ENTRY_CAM_IP,
            "port": settings.ENTRY_CAM_PORT,
            "gate_type": "entry",
            "last_seen": None,
        }
    if settings.EXIT_CAM_IP:
        _registry["exit"] = {
            "ip": settings.EXIT_CAM_IP,
            "port": settings.EXIT_CAM_PORT,
            "gate_type": "exit",
            "last_seen": None,
        }


_seed_registry()


# ── Request / Response schemas ────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    device_id: str        # "entry" | "exit"
    gate_type: str        # "entry" | "exit"
    ip: str               # ESP32's current LAN IP
    port: int = 80        # ESP32 WebServer port


class DeviceTriggerRequest(BaseModel):
    device_id: str
    ip: Optional[str] = None   # latest IP; updates registry if provided


class TriggerAck(BaseModel):
    status: str
    message: str


# ── Master → Slave HTTP helpers ───────────────────────────────────────────────

_CAPTURE_RETRIES = 4
_CAPTURE_RETRY_DELAY_S = 0.5   # seconds between retries


async def _fetch_image(ip: str, port: int) -> bytes:
    """
    Server (master) pulls JPEG from slave's GET /capture.
    Retries to absorb the brief window while ESP32 re-enters handleClient().
    """
    url = f"http://{ip}:{port}/capture"
    last_exc: Exception = RuntimeError("no attempts made")
    async with httpx.AsyncClient(timeout=8.0) as client:
        for attempt in range(1, _CAPTURE_RETRIES + 1):
            try:
                r = await client.get(url)
                if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
                    logger.info(
                        f"[IoT] Image fetched from {ip}:{port} — "
                        f"{len(r.content)} bytes (attempt {attempt})"
                    )
                    return r.content
                last_exc = RuntimeError(f"/capture returned HTTP {r.status_code}")
            except Exception as exc:
                last_exc = exc
                logger.warning(f"[IoT] /capture attempt {attempt}/{_CAPTURE_RETRIES} failed: {exc}")

            if attempt < _CAPTURE_RETRIES:
                await asyncio.sleep(_CAPTURE_RETRY_DELAY_S)

    raise last_exc


async def _command_gate(ip: str, port: int, action: str) -> None:
    """Server (master) commands slave gate: action = 'open' | 'close'."""
    url = f"http://{ip}:{port}/gate"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(url, json={"action": action})
            logger.info(f"[IoT] Gate '{action}' → {ip}:{port} → HTTP {r.status_code}")
    except Exception as exc:
        logger.error(f"[IoT] Gate command '{action}' to {ip}:{port} failed: {exc}")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", summary="ESP32 self-registration on boot")
async def register_device(req: DeviceRegisterRequest):
    """Called by ESP32 on boot. Registers its device_id and current LAN IP."""
    _registry[req.device_id] = {
        "ip": req.ip,
        "port": req.port,
        "gate_type": req.gate_type,
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[IoT] Registered: {req.device_id} @ {req.ip}:{req.port} (type={req.gate_type})")
    return {"status": "registered", "device_id": req.device_id, "ip": req.ip}


@router.get("/devices", summary="List registered IoT devices and their state")
async def list_devices():
    return {"count": len(_registry), "devices": _registry}


@router.post(
    "/trigger",
    response_model=TriggerAck,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Vehicle detected — server takes over from here",
)
async def device_trigger(req: DeviceTriggerRequest, background_tasks: BackgroundTasks):
    """
    Lightweight notification from ESP32 slave — no image payload.
    Responds 202 immediately so ESP32 can return to handleClient()
    before the server calls back for /capture and /gate.
    """
    device = _registry.get(req.device_id)
    if not device and not req.ip:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown device '{req.device_id}' — register first via POST /api/iot/register",
        )

    ip = req.ip or device["ip"]
    port = device["port"] if device else 80
    gate_type = device["gate_type"] if device else req.device_id

    if device:
        if req.ip:
            device["ip"] = req.ip   # keep registry current
        device["last_seen"] = datetime.now(timezone.utc).isoformat()

    logger.info(f"[IoT] Trigger — device={req.device_id}, ip={ip}:{port}, type={gate_type}")

    # Hand off to background — ESP32 gets 202 before we call /capture
    background_tasks.add_task(_process_event, req.device_id, ip, port, gate_type)
    return TriggerAck(status="processing", message="Trigger received — server is orchestrating")


# ── Background: full event pipeline ──────────────────────────────────────────

async def _process_event(device_id: str, ip: str, port: int, gate_type: str) -> None:
    """
    Runs after 202 is sent.  Fully orchestrates the parking event:
    fetch image → OCR → business logic → gate command.
    """
    db = SessionLocal()
    try:
        # 1. Master pulls image from slave
        try:
            image_bytes = await _fetch_image(ip, port)
        except Exception as exc:
            logger.error(f"[IoT] Cannot fetch image from {device_id}: {exc}")
            await _command_gate(ip, port, "close")
            return

        image_bytes = flip_image_horizontal(image_bytes)

        timestamp = datetime.now(timezone.utc)
        filename = (
            f"{gate_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            f"_{uuid.uuid4().hex[:6]}.jpg"
        )
        image_path = f"{settings.CAPTURED_IMAGES_DIR}/{filename}"

        try:
            save_captured_image(image_bytes, filename)
        except Exception as exc:
            logger.warning(f"[IoT] Image save failed (non-fatal): {exc}")

        # 2. OCR
        try:
            plate = await extract_license_plate(image_bytes)
        except OCRFailedException as exc:
            logger.error(f"[IoT] OCR failed for {device_id}: {exc}")
            await _command_gate(ip, port, "close")
            return

        logger.info(f"[IoT] Plate detected: {plate}")

        # 3. Business logic
        if gate_type == "entry":
            allow = _handle_entry(db, plate, timestamp, image_path)
        else:
            allow = _handle_exit(db, plate, timestamp, image_path)

        # 4. Master commands slave gate
        await _command_gate(ip, port, "open" if allow else "close")

    except Exception as exc:
        logger.exception(f"[IoT] Unhandled error in {device_id} event pipeline: {exc}")
        try:
            await _command_gate(ip, port, "close")
        except Exception:
            pass
    finally:
        db.close()


# ── Business logic (sync — called from async background task) ─────────────────

def _handle_entry(db: Session, plate: str, timestamp: datetime, image_path: str) -> bool:
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.license_plate == plate, Vehicle.is_active == True)  # noqa: E712
        .first()
    )
    if not vehicle:
        deny_session(
            db, plate=plate, vehicle_id=None,
            timestamp=timestamp, image_path=image_path,
            reason="Unregistered vehicle",
        )
        db.commit()
        logger.warning(f"[IoT] Entry DENY — unregistered: {plate}")
        return False

    if get_active_session_for_vehicle(db, vehicle.id):
        logger.warning(f"[IoT] Entry DENY — already has active session: {plate}")
        return False

    slot = find_available_slot(db)
    if not slot:
        deny_session(
            db, plate=plate, vehicle_id=vehicle.id,
            timestamp=timestamp, image_path=image_path,
            reason="No available slots",
        )
        db.commit()
        logger.warning(f"[IoT] Entry DENY — lot full: {plate}")
        return False

    session = open_session(
        db, vehicle=vehicle, slot=slot,
        plate=plate, timestamp=timestamp, image_path=image_path,
    )
    db.commit()
    logger.info(f"[IoT] Entry ALLOW — plate={plate}, slot={slot.slot_number}, session={session.id}")
    return True


def _handle_exit(db: Session, plate: str, timestamp: datetime, image_path: str) -> bool:
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.license_plate == plate, Vehicle.is_active == True)  # noqa: E712
        .first()
    )
    if not vehicle:
        db.add(ParkingSession(
            license_plate_raw=plate,
            entry_time=timestamp,
            exit_time=timestamp,
            status=SessionStatus.DENIED,
            exit_image_path=image_path,
            deny_reason="Unregistered vehicle",
        ))
        db.commit()
        logger.warning(f"[IoT] Exit DENY — unregistered: {plate}")
        return False

    session = get_active_session_for_vehicle(db, vehicle.id)
    if not session:
        db.add(ParkingSession(
            vehicle_id=vehicle.id,
            license_plate_raw=plate,
            entry_time=timestamp,
            exit_time=timestamp,
            status=SessionStatus.DENIED,
            exit_image_path=image_path,
            deny_reason="No active session",
        ))
        db.commit()
        logger.warning(f"[IoT] Exit DENY — no active session: {plate}")
        return False

    wallet = db.query(Wallet).filter(Wallet.user_id == vehicle.user_id).first()
    try:
        cost, new_balance = close_session(
            db, session=session, wallet=wallet,
            timestamp=timestamp, image_path=image_path,
        )
        db.commit()
        logger.info(f"[IoT] Exit ALLOW — plate={plate}, cost=₹{cost}, balance=₹{new_balance}")
        return True
    except InsufficientBalanceError as e:
        db.rollback()
        logger.warning(
            f"[IoT] Exit DENY — insufficient balance: {plate} "
            f"(need ₹{e.cost}, have ₹{e.balance})"
        )
        return False
