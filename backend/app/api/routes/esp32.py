import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.vehicle import Vehicle
from app.models.parking_slot import ParkingSlot, SlotStatus
from app.models.parking_session import ParkingSession, SessionStatus
from app.models.wallet import Wallet
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.schemas.parking import ESP32EventResponse
from app.services.ocr import extract_license_plate, flip_image_horizontal, save_captured_image, OCRFailedException
from app.services.billing import calculate_parking_cost

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB hard limit


def _save_image_safe(image_bytes: bytes, filename: str) -> None:
    """Wrapper used as a BackgroundTask — logs errors instead of raising."""
    try:
        save_captured_image(image_bytes, filename)
    except Exception as exc:
        logger.error(f"[IMAGE] Background save failed ({filename}): {exc}")


def _first_available_slot(db: Session) -> ParkingSlot | None:
    return (
        db.query(ParkingSlot)
        .filter(ParkingSlot.status == SlotStatus.AVAILABLE)
        .order_by(ParkingSlot.slot_number)
        .first()
    )


@router.post("/entry-event", response_model=ESP32EventResponse)
async def entry_event(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image_bytes = await image.read()

    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB limit")

    timestamp = datetime.now(timezone.utc)
    filename = f"entry_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
    image_path = f"{settings.CAPTURED_IMAGES_DIR}/{filename}"

    logger.info(f"[ENTRY] Image received: {filename} ({len(image_bytes)} bytes)")

    # Entry-gate camera produces a mirrored image — correct before OCR and save
    image_bytes = flip_image_horizontal(image_bytes)

    # Save corrected image after the response is sent — keeps it off the critical path.
    background_tasks.add_task(_save_image_safe, image_bytes, filename)

    # OCR — async, does not block the event loop
    try:
        plate = await extract_license_plate(image_bytes)
    except OCRFailedException as exc:
        logger.error(f"[ENTRY] OCR failed: {exc}")
        db.add(ParkingSession(
            license_plate_raw="UNKNOWN",
            entry_time=timestamp,
            status=SessionStatus.DENIED,
            entry_image_path=image_path,
            deny_reason=f"OCR failure: {exc}",
        ))
        db.commit()
        return ESP32EventResponse(status="DENY", message="OCR failed — could not read plate")

    logger.info(f"[ENTRY] Plate: {plate}")

    # Vehicle lookup
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.license_plate == plate, Vehicle.is_active == True)  # noqa: E712
        .first()
    )
    if not vehicle:
        db.add(ParkingSession(
            license_plate_raw=plate,
            entry_time=timestamp,
            status=SessionStatus.DENIED,
            entry_image_path=image_path,
            deny_reason="Unregistered vehicle",
        ))
        db.commit()
        logger.warning(f"[ENTRY] Unregistered plate: {plate}")
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            message=f"Vehicle {plate} is not registered in the system.",
        )

    # Prevent double-entry for the same vehicle
    existing_session = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_id == vehicle.id,
            ParkingSession.status == SessionStatus.ACTIVE,
        )
        .first()
    )
    if existing_session:
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            message="Vehicle already has an active parking session",
        )

    # Find available slot
    slot = _first_available_slot(db)
    if not slot:
        db.add(ParkingSession(
            vehicle_id=vehicle.id,
            license_plate_raw=plate,
            entry_time=timestamp,
            status=SessionStatus.DENIED,
            entry_image_path=image_path,
            deny_reason="No available slots",
        ))
        db.commit()
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            message="Parking lot is full",
        )

    # Assign slot and open session
    slot.status = SlotStatus.OCCUPIED
    slot.updated_at = timestamp

    session = ParkingSession(
        vehicle_id=vehicle.id,
        slot_id=slot.id,
        license_plate_raw=plate,
        entry_time=timestamp,
        status=SessionStatus.ACTIVE,
        entry_image_path=image_path,
    )
    db.add(session)
    db.commit()

    logger.info(f"[ENTRY] ALLOW — plate={plate}, slot={slot.slot_number}")
    return ESP32EventResponse(
        status="ALLOW",
        license_plate=plate,
        session_id=session.id,
        message=f"Welcome! Slot {slot.slot_number} assigned.",
    )


@router.post("/exit-event", response_model=ESP32EventResponse)
async def exit_event(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image_bytes = await image.read()

    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB limit")

    timestamp = datetime.now(timezone.utc)
    filename = f"exit_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
    image_path = f"{settings.CAPTURED_IMAGES_DIR}/{filename}"

    logger.info(f"[EXIT] Image received: {filename} ({len(image_bytes)} bytes)")

    # Exit-gate camera produces a mirrored image — correct before OCR and save
    image_bytes = flip_image_horizontal(image_bytes)

    background_tasks.add_task(_save_image_safe, image_bytes, filename)

    def _deny_exit(plate: str, reason: str, **extra):
        """Create a DENIED session record so every exit capture has a DB row."""
        db.add(ParkingSession(
            license_plate_raw=plate,
            entry_time=timestamp,
            exit_time=timestamp,
            status=SessionStatus.DENIED,
            exit_image_path=image_path,
            deny_reason=reason,
            **extra,
        ))
        db.commit()

    # OCR
    try:
        plate = await extract_license_plate(image_bytes)
    except OCRFailedException as exc:
        logger.error(f"[EXIT] OCR failed: {exc}")
        _deny_exit("UNKNOWN", f"OCR failure: {exc}")
        return ESP32EventResponse(status="DENY", message="OCR failed — please use manual exit")

    logger.info(f"[EXIT] Plate: {plate}")

    # Vehicle and session lookup
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.license_plate == plate, Vehicle.is_active == True)  # noqa: E712
        .first()
    )
    if not vehicle:
        _deny_exit(plate, "Unregistered vehicle")
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            message=f"Vehicle {plate} not found in system",
        )

    session = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_id == vehicle.id,
            ParkingSession.status == SessionStatus.ACTIVE,
        )
        .first()
    )
    if not session:
        _deny_exit(plate, "No active session found", vehicle_id=vehicle.id)
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            message="No active parking session found for this vehicle",
        )

    # Billing
    cost, duration_minutes = calculate_parking_cost(session.entry_time, timestamp)
    logger.info(f"[EXIT] duration={duration_minutes:.1f}m cost=₹{cost}")

    # Wallet check
    wallet = db.query(Wallet).filter(Wallet.user_id == vehicle.user_id).first()
    current_balance = float(wallet.balance) if wallet else 0.0
    if not wallet or current_balance < cost:
        _deny_exit(plate, f"Insufficient balance (need ₹{cost:.2f}, have ₹{current_balance:.2f})", vehicle_id=vehicle.id)
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            cost=cost,
            wallet_balance=current_balance,
            message=f"Insufficient balance. Required: ₹{cost:.2f}, Available: ₹{current_balance:.2f}",
        )

    # Deduct balance
    wallet.balance = round(current_balance - cost, 2)
    wallet.updated_at = timestamp

    # Close session
    session.exit_time = timestamp
    session.duration_minutes = duration_minutes
    session.cost = cost
    session.status = SessionStatus.COMPLETED
    session.exit_image_path = image_path

    # Free the slot — initialized to None so the Transaction description is always safe
    slot = None
    if session.slot_id:
        slot = db.query(ParkingSlot).filter(ParkingSlot.id == session.slot_id).first()
        if slot:
            slot.status = SlotStatus.AVAILABLE
            slot.updated_at = timestamp

    txn = Transaction(
        user_id=vehicle.user_id,
        session_id=session.id,
        amount=cost,
        transaction_type=TransactionType.DEBIT,
        status=TransactionStatus.SUCCESS,
        description=f"Parking fee — {duration_minutes:.0f} mins, slot {slot.slot_number if slot else 'N/A'}",
        reference_id=f"PARK-{uuid.uuid4().hex[:10].upper()}",
        created_at=timestamp,
    )
    db.add(txn)
    db.commit()

    new_balance = float(wallet.balance)
    logger.info(f"[EXIT] ALLOW — plate={plate}, cost=₹{cost}, balance=₹{new_balance}")
    return ESP32EventResponse(
        status="ALLOW",
        license_plate=plate,
        session_id=session.id,
        cost=cost,
        wallet_balance=new_balance,
        message=f"₹{cost:.2f} deducted. Remaining balance: ₹{new_balance:.2f}. Safe drive!",
    )
