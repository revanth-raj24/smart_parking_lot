"""
IoT routes — Push-based architecture (v6.0).

Flow per event:
  1. ESP32 boots → POST /api/devices/register  (upserts device_id + current DHCP IP)
  2. ESP32 sends heartbeat every 20 s → POST /api/devices/heartbeat
  3. IR fires   → ESP32 captures JPEG → POST /api/iot/trigger (multipart: device_id + image)
  4. Server     → runs OCR + parking business logic synchronously
  5. Server     → responds 200 {"action": "open"|"close"}
  6. ESP32      → reads action, controls servo locally, auto-closes after timeout

No server-initiated callbacks — eliminates NAT traversal issues when ESP32 is on LAN.
"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.device import Device
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
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response schema ───────────────────────────────────────────────────────────

class TriggerAck(BaseModel):
    status: str
    action: str   # "open" | "close" — ESP32 reads this to control the servo
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/trigger",
    response_model=TriggerAck,
    status_code=status.HTTP_200_OK,
    summary="Vehicle detected — ESP32 pushes image, server returns gate action",
)
async def device_trigger(
    device_id: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    ESP32 pushes JPEG captured at IR-trigger time as multipart/form-data.
    Server runs OCR + business logic synchronously and returns {"action":"open"|"close"}.
    ESP32 reads the action and controls its own servo — no server-initiated callbacks needed.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Unknown device '{device_id}' — "
                "device must call POST /api/devices/register on boot first"
            ),
        )

    gate_type = device.device_type
    device.last_seen = datetime.now(timezone.utc)
    device.status = "online"
    db.commit()

    logger.info(f"[IoT] Trigger — device={device_id}, type={gate_type}")

    image_bytes = await image.read()
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

    try:
        plate = await extract_license_plate(image_bytes)
    except OCRFailedException as exc:
        logger.error(f"[IoT] OCR failed for {device_id}: {exc}")
        return TriggerAck(status="error", action="close", message="OCR failed")

    logger.info(f"[IoT] Plate detected: {plate}")

    if "entry" in gate_type:
        allow = _handle_entry(db, plate, timestamp, image_path)
    else:
        allow = _handle_exit(db, plate, timestamp, image_path)

    action = "open" if allow else "close"
    return TriggerAck(status="allow" if allow else "deny", action=action, message=plate)


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
    logger.info(
        f"[IoT] Entry ALLOW — plate={plate}, slot={slot.slot_number}, session={session.id}"
    )
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
        logger.info(
            f"[IoT] Exit ALLOW — plate={plate}, cost=₹{cost}, balance=₹{new_balance}"
        )
        return True
    except InsufficientBalanceError as e:
        db.rollback()
        logger.warning(
            f"[IoT] Exit DENY — insufficient balance: {plate} "
            f"(need ₹{e.cost}, have ₹{e.balance})"
        )
        return False
