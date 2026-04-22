"""
Parking business logic — isolated from HTTP layer.
Routes call these functions; they never touch Request/Response objects.
"""
import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.parking_slot import ParkingSlot, SlotStatus
from app.models.parking_session import ParkingSession, SessionStatus
from app.models.vehicle import Vehicle
from app.models.wallet import Wallet
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.services.billing import calculate_parking_cost

logger = logging.getLogger(__name__)


def find_available_slot(db: Session) -> ParkingSlot | None:
    """Return the lowest-numbered available slot, or None if the lot is full."""
    return (
        db.query(ParkingSlot)
        .filter(ParkingSlot.status == SlotStatus.AVAILABLE)
        .order_by(ParkingSlot.slot_number)
        .first()
    )


def get_active_session_for_vehicle(db: Session, vehicle_id: int) -> ParkingSession | None:
    return (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_id == vehicle_id,
            ParkingSession.status == SessionStatus.ACTIVE,
        )
        .first()
    )


def open_session(
    db: Session,
    *,
    vehicle: Vehicle,
    slot: ParkingSlot,
    plate: str,
    timestamp: datetime,
    image_path: str,
) -> ParkingSession:
    """Mark slot OCCUPIED, create an ACTIVE session, flush (no commit)."""
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
    db.flush()  # assign session.id without committing
    logger.info(f"[ParkingService] Session opened — plate={plate}, slot={slot.slot_number}")
    return session


def deny_session(
    db: Session,
    *,
    plate: str,
    vehicle_id: int | None,
    timestamp: datetime,
    image_path: str,
    reason: str,
) -> ParkingSession:
    """Record a DENIED session (no slot assigned)."""
    session = ParkingSession(
        vehicle_id=vehicle_id,
        license_plate_raw=plate,
        entry_time=timestamp,
        status=SessionStatus.DENIED,
        entry_image_path=image_path,
        deny_reason=reason,
    )
    db.add(session)
    db.flush()
    return session


class InsufficientBalanceError(Exception):
    def __init__(self, cost: float, balance: float):
        self.cost = cost
        self.balance = balance
        super().__init__(f"Insufficient balance: need ₹{cost}, have ₹{balance}")


def close_session(
    db: Session,
    *,
    session: ParkingSession,
    wallet: Wallet,
    timestamp: datetime,
    image_path: str,
) -> tuple[float, float]:
    """
    Bill the user, close the session, free the slot.

    Returns (cost, new_balance).
    Raises InsufficientBalanceError if wallet is too low.
    Caller is responsible for committing.
    """
    cost, duration_minutes = calculate_parking_cost(session.entry_time, timestamp)
    current_balance = float(wallet.balance)

    if current_balance < cost:
        raise InsufficientBalanceError(cost, current_balance)

    # Deduct wallet
    wallet.balance = round(current_balance - cost, 2)
    wallet.updated_at = timestamp

    # Close session
    session.exit_time = timestamp
    session.duration_minutes = duration_minutes
    session.cost = cost
    session.status = SessionStatus.COMPLETED
    session.exit_image_path = image_path

    # Free slot
    if session.slot_id:
        slot = db.query(ParkingSlot).filter(ParkingSlot.id == session.slot_id).first()
        if slot:
            slot.status = SlotStatus.AVAILABLE
            slot.updated_at = timestamp

    # Transaction record
    txn = Transaction(
        user_id=wallet.user_id,
        session_id=session.id,
        amount=cost,
        transaction_type=TransactionType.DEBIT,
        status=TransactionStatus.SUCCESS,
        description=f"Parking fee — {duration_minutes:.0f} mins",
        reference_id=f"PARK-{uuid.uuid4().hex[:10].upper()}",
        created_at=timestamp,
    )
    db.add(txn)

    new_balance = float(wallet.balance)
    logger.info(
        f"[ParkingService] Session closed — plate={session.license_plate_raw}, "
        f"cost=₹{cost}, balance=₹{new_balance}"
    )
    return cost, new_balance
