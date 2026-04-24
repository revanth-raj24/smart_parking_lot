import re
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.parking_slot import ParkingSlot
from app.schemas.prebooking import PreBookingCreate, PreBookingOut
from app.services.prebooking_service import (
    check_conflict,
    create_booking,
    get_user_bookings,
    cancel_booking,
)

router = APIRouter()

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate(slot_id: str, date: str, start_time: str, end_time: str, db: Session) -> None:
    if not _DATE_RE.match(date):
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")
    try:
        booking_date = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date")
    if booking_date < date_type.today():
        raise HTTPException(status_code=400, detail="Booking date cannot be in the past")
    if not _TIME_RE.match(start_time) or not _TIME_RE.match(end_time):
        raise HTTPException(status_code=422, detail="Time must be HH:MM format")
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")
    slot = db.query(ParkingSlot).filter(ParkingSlot.slot_number == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} not found")


@router.post("", response_model=PreBookingOut, status_code=201, summary="Pre-book a parking slot")
def create_pre_booking(
    payload: PreBookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slot_id = payload.slot_id.upper().strip()
    _validate(slot_id, payload.date, payload.start_time, payload.end_time, db)

    if check_conflict(db, slot_id, payload.date, payload.start_time, payload.end_time):
        raise HTTPException(status_code=409, detail="Slot already booked for selected time")

    return create_booking(
        db,
        user_id=current_user.id,
        slot_id=slot_id,
        booking_date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )


@router.get("/my", response_model=list[PreBookingOut], summary="Get my pre-bookings")
def my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_bookings(db, current_user.id)


@router.delete("/{booking_id}", status_code=200, summary="Cancel a pre-booking")
def cancel_pre_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = cancel_booking(db, booking_id, current_user.id)
    if not booking:
        raise HTTPException(
            status_code=404, detail="Booking not found or already cancelled"
        )
    return {"status": "cancelled", "id": booking_id}
