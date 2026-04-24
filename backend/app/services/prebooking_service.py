from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.prebooking import PreBooking
from app.models.user import User


def check_conflict(
    db: Session,
    slot_id: str,
    booking_date: str,
    start_time: str,
    end_time: str,
    exclude_id: int | None = None,
) -> bool:
    """Return True if the requested window overlaps any existing active booking.

    Overlap formula: new_start < existing_end AND new_end > existing_start
    Stored times are "HH:MM" strings; lexicographic comparison == chronological for same-day times.
    """
    q = db.query(PreBooking).filter(
        PreBooking.slot_id == slot_id,
        PreBooking.booking_date == booking_date,
        PreBooking.status == "active",
        PreBooking.start_time < end_time,   # existing start before new end
        PreBooking.end_time > start_time,   # existing end after new start
    )
    if exclude_id is not None:
        q = q.filter(PreBooking.id != exclude_id)
    return db.query(q.exists()).scalar()


def create_booking(
    db: Session,
    user_id: int,
    slot_id: str,
    booking_date: str,
    start_time: str,
    end_time: str,
) -> PreBooking:
    booking = PreBooking(
        user_id=user_id,
        slot_id=slot_id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def get_user_bookings(db: Session, user_id: int) -> list[PreBooking]:
    return (
        db.query(PreBooking)
        .filter(PreBooking.user_id == user_id)
        .order_by(PreBooking.booking_date.desc(), PreBooking.start_time.desc())
        .all()
    )


def get_all_bookings(db: Session) -> list[dict]:
    rows = (
        db.query(PreBooking, User.name, User.email)
        .join(User, PreBooking.user_id == User.id, isouter=True)
        .order_by(PreBooking.booking_date, PreBooking.start_time)
        .all()
    )
    return [
        {
            "id": b.id,
            "user_id": b.user_id,
            "user_name": name,
            "user_email": email,
            "slot_id": b.slot_id,
            "booking_date": b.booking_date,
            "start_time": b.start_time,
            "end_time": b.end_time,
            "status": b.status,
            "created_at": b.created_at,
        }
        for b, name, email in rows
    ]


def cancel_booking(db: Session, booking_id: int, user_id: int) -> PreBooking | None:
    booking = db.query(PreBooking).filter(
        PreBooking.id == booking_id,
        PreBooking.user_id == user_id,
        PreBooking.status == "active",
    ).first()
    if booking:
        booking.status = "cancelled"
        db.commit()
        db.refresh(booking)
    return booking


def admin_cancel_booking(db: Session, booking_id: int) -> PreBooking | None:
    booking = db.query(PreBooking).filter(
        PreBooking.id == booking_id,
        PreBooking.status == "active",
    ).first()
    if booking:
        booking.status = "cancelled"
        db.commit()
        db.refresh(booking)
    return booking
