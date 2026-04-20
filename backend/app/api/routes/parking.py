from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.parking_slot import ParkingSlot, SlotStatus
from app.models.parking_session import ParkingSession, SessionStatus
from app.models.vehicle import Vehicle
from app.schemas.parking import SlotOut, BookSlotRequest, BookSlotResponse, ParkingSessionOut
from datetime import datetime, timezone

router = APIRouter()


@router.get("/slots", response_model=list[SlotOut])
def get_slots(db: Session = Depends(get_db)):
    return db.query(ParkingSlot).order_by(ParkingSlot.slot_number).all()


@router.post("/book-slot", response_model=BookSlotResponse)
def book_slot(
    payload: BookSlotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == payload.slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.status != SlotStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail=f"Slot {slot.slot_number} is not available")

    plate = payload.license_plate.upper().strip()
    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == plate,
        Vehicle.user_id == current_user.id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=400, detail="License plate not registered to your account")

    active = db.query(ParkingSession).filter(
        ParkingSession.vehicle_id == vehicle.id,
        ParkingSession.status == SessionStatus.ACTIVE,
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="Vehicle already has an active parking session")

    slot.status = SlotStatus.RESERVED
    slot.updated_at = datetime.now(timezone.utc)

    session = ParkingSession(
        vehicle_id=vehicle.id,
        slot_id=slot.id,
        license_plate_raw=plate,
        entry_time=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    db.commit()
    db.refresh(slot)

    return BookSlotResponse(
        status="SUCCESS",
        message=f"Slot {slot.slot_number} reserved",
        slot=SlotOut.model_validate(slot),
    )


@router.get("/my-sessions", response_model=list[ParkingSessionOut])
def my_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicles = db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()
    vehicle_ids = [v.id for v in vehicles]
    return (
        db.query(ParkingSession)
        .filter(ParkingSession.vehicle_id.in_(vehicle_ids))
        .order_by(ParkingSession.entry_time.desc())
        .limit(50)
        .all()
    )


@router.get("/active-session", response_model=ParkingSessionOut | None)
def active_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicles = db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()
    vehicle_ids = [v.id for v in vehicles]
    return (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_id.in_(vehicle_ids),
            ParkingSession.status == SessionStatus.ACTIVE,
        )
        .first()
    )
