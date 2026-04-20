import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.vehicle import Vehicle
from app.models.parking_slot import ParkingSlot, SlotStatus
from app.models.parking_session import ParkingSession, SessionStatus
from app.models.wallet import Wallet
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.schemas.parking import ESP32EventResponse
from app.services.ocr import extract_license_plate, save_captured_image, OCRFailedException
from app.services.billing import calculate_parking_cost

logger = logging.getLogger(__name__)
router = APIRouter()


def _first_available_slot(db: Session) -> ParkingSlot | None:
    return (
        db.query(ParkingSlot)
        .filter(ParkingSlot.status == SlotStatus.AVAILABLE)
        .order_by(ParkingSlot.slot_number)
        .first()
    )


@router.post("/entry-event", response_model=ESP32EventResponse)
async def entry_event(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image_bytes = await image.read()
    timestamp = datetime.now(timezone.utc)
    filename = f"entry_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"

    image_path = save_captured_image(image_bytes, filename)
    logger.info(f"[ENTRY] Image saved: {image_path}")

    # OCR
    try:
        plate = extract_license_plate(image_bytes)
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
    vehicle = db.query(Vehicle).filter(Vehicle.license_plate == plate, Vehicle.is_active == True).first()
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
            message=f"Vehicle {plate} is not registered. Please register at the kiosk.",
        )

    # Check for existing active session
    existing_session = db.query(ParkingSession).filter(
        ParkingSession.vehicle_id == vehicle.id,
        ParkingSession.status == SessionStatus.ACTIVE,
    ).first()
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

    # Assign slot and create session
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
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image_bytes = await image.read()
    timestamp = datetime.now(timezone.utc)
    filename = f"exit_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"

    image_path = save_captured_image(image_bytes, filename)
    logger.info(f"[EXIT] Image saved: {image_path}")

    # OCR
    try:
        plate = extract_license_plate(image_bytes)
    except OCRFailedException as exc:
        logger.error(f"[EXIT] OCR failed: {exc}")
        return ESP32EventResponse(status="DENY", message="OCR failed — please use manual exit")

    logger.info(f"[EXIT] Plate: {plate}")

    # Find active session
    vehicle = db.query(Vehicle).filter(Vehicle.license_plate == plate, Vehicle.is_active == True).first()
    if not vehicle:
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            message=f"Vehicle {plate} not found in system",
        )

    session = db.query(ParkingSession).filter(
        ParkingSession.vehicle_id == vehicle.id,
        ParkingSession.status == SessionStatus.ACTIVE,
    ).first()
    if not session:
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
    if not wallet or wallet.balance < cost:
        current_balance = wallet.balance if wallet else 0.0
        return ESP32EventResponse(
            status="DENY",
            license_plate=plate,
            cost=cost,
            wallet_balance=current_balance,
            message=f"Insufficient balance. Required: ₹{cost:.2f}, Available: ₹{current_balance:.2f}",
        )

    # Deduct and close session
    wallet.balance = round(wallet.balance - cost, 2)
    wallet.updated_at = timestamp

    session.exit_time = timestamp
    session.duration_minutes = duration_minutes
    session.cost = cost
    session.status = SessionStatus.COMPLETED
    session.exit_image_path = image_path

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

    logger.info(f"[EXIT] ALLOW — plate={plate}, cost=₹{cost}, balance=₹{wallet.balance}")
    return ESP32EventResponse(
        status="ALLOW",
        license_plate=plate,
        session_id=session.id,
        cost=cost,
        wallet_balance=wallet.balance,
        message=f"₹{cost:.2f} deducted. Remaining balance: ₹{wallet.balance:.2f}. Safe drive!",
    )
