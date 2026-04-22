"""
Slot management business logic.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.parking_slot import ParkingSlot, SlotStatus
from app.models.parking_session import ParkingSession, SessionStatus
from app.models.user import User
from app.models.vehicle import Vehicle

logger = logging.getLogger(__name__)


def get_all_slots(db: Session) -> list[ParkingSlot]:
    return db.query(ParkingSlot).order_by(ParkingSlot.slot_number).all()


def set_slot_status(db: Session, slot_id: int, status: str) -> ParkingSlot:
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    if slot is None:
        raise ValueError(f"Slot {slot_id} not found")
    if status not in {SlotStatus.AVAILABLE, SlotStatus.OCCUPIED, SlotStatus.RESERVED, SlotStatus.MAINTENANCE}:
        raise ValueError(f"Invalid slot status: {status}")
    slot.status = status
    slot.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(slot)
    logger.info(f"[SlotService] Slot {slot.slot_number} → {status}")
    return slot


def get_slot_summary(db: Session) -> dict:
    """Aggregate slot counts in one GROUP BY query."""
    counts: dict[str, int] = {}
    for status_val, count in db.query(ParkingSlot.status, func.count()).group_by(ParkingSlot.status).all():
        counts[status_val] = count
    return {
        "total":       sum(counts.values()),
        "available":   counts.get(SlotStatus.AVAILABLE,    0),
        "occupied":    counts.get(SlotStatus.OCCUPIED,     0),
        "reserved":    counts.get(SlotStatus.RESERVED,     0),
        "maintenance": counts.get(SlotStatus.MAINTENANCE,  0),
    }


def get_occupied_slots_with_users(db: Session) -> list[dict]:
    """
    Returns active sessions enriched with slot, vehicle, and user data.
    Uses 2 queries total (sessions+joins, then users IN-list).
    """
    sessions = (
        db.query(ParkingSession)
        .options(joinedload(ParkingSession.slot), joinedload(ParkingSession.vehicle))
        .filter(ParkingSession.status == SessionStatus.ACTIVE)
        .order_by(ParkingSession.entry_time)
        .all()
    )

    user_ids = {s.vehicle.user_id for s in sessions if s.vehicle}
    users_by_id: dict[int, User] = {}
    if user_ids:
        users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    result = []
    for s in sessions:
        slot = s.slot
        vehicle = s.vehicle
        user = users_by_id.get(vehicle.user_id) if vehicle else None
        result.append({
            "slot_id":     s.slot_id or 0,
            "slot_number": slot.slot_number if slot else "?",
            "floor":       slot.floor if slot else "G",
            "session_id":  s.id,
            "entry_time":  s.entry_time,
            "license_plate": s.license_plate_raw,
            "vehicle_type":  vehicle.vehicle_type if vehicle else "unknown",
            "user_id":    user.id    if user else None,
            "user_name":  user.name  if user else None,
            "user_email": user.email if user else None,
            "user_phone": user.phone if user else None,
        })
    return result
