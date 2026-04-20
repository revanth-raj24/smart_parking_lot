import httpx
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.deps import get_current_admin
from app.core.config import settings
from app.models.user import User
from app.models.parking_slot import ParkingSlot, SlotStatus
from app.models.parking_session import ParkingSession
from app.models.transaction import Transaction
from app.schemas.user import UserOut, AdminUserUpdate
from app.schemas.parking import (
    SlotOut, ParkingSessionOut, OverrideSlotRequest, GateCommand
)
from app.schemas.wallet import TransactionOut

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_STATUSES = {SlotStatus.AVAILABLE, SlotStatus.OCCUPIED, SlotStatus.RESERVED, SlotStatus.MAINTENANCE}


# ── Users ────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    return db.query(User).offset(skip).limit(limit).all()


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.name is not None:
        user.name = payload.name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.is_active is not None:
        user.is_active = payload.is_active

    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete own admin account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


# ── Parking Sessions ─────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[ParkingSessionOut])
def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    q = db.query(ParkingSession)
    if status:
        q = q.filter(ParkingSession.status == status)
    return q.order_by(ParkingSession.entry_time.desc()).offset(skip).limit(limit).all()


# ── Slot Override ─────────────────────────────────────────────────────────────

@router.post("/override", response_model=SlotOut)
def override_slot(
    payload: OverrideSlotRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    slot = db.query(ParkingSlot).filter(ParkingSlot.id == payload.slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    slot.status = payload.status
    slot.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(slot)
    logger.info(f"[ADMIN] Slot {slot.slot_number} overridden to {payload.status}")
    return slot


# ── Gate Control ──────────────────────────────────────────────────────────────

@router.post("/gate-control")
async def gate_control(
    payload: GateCommand,
    _admin: User = Depends(get_current_admin),
):
    if payload.gate not in ("entry", "exit"):
        raise HTTPException(status_code=400, detail="gate must be 'entry' or 'exit'")
    if payload.action not in ("open", "close"):
        raise HTTPException(status_code=400, detail="action must be 'open' or 'close'")

    cam_url = settings.ENTRY_CAM_URL if payload.gate == "entry" else settings.EXIT_CAM_URL
    esp32_base = cam_url.rsplit("/", 1)[0]
    target = f"{esp32_base}/gate/{payload.action}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(target)
            return {"status": "sent", "gate": payload.gate, "action": payload.action, "esp32_response": resp.status_code}
    except httpx.RequestError as exc:
        logger.warning(f"[ADMIN] Gate control failed: {exc}")
        return {"status": "unreachable", "gate": payload.gate, "action": payload.action, "error": str(exc)}


# ── Transactions ──────────────────────────────────────────────────────────────

@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    return (
        db.query(Transaction)
        .order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    total_slots = db.query(ParkingSlot).count()
    occupied = db.query(ParkingSlot).filter(ParkingSlot.status == SlotStatus.OCCUPIED).count()
    reserved = db.query(ParkingSlot).filter(ParkingSlot.status == SlotStatus.RESERVED).count()
    available = db.query(ParkingSlot).filter(ParkingSlot.status == SlotStatus.AVAILABLE).count()
    total_users = db.query(User).filter(User.is_admin == False).count()  # noqa: E712
    active_sessions = db.query(ParkingSession).filter(ParkingSession.status == "active").count()

    revenue_result = db.query(Transaction).filter(Transaction.transaction_type == "debit").all()
    total_revenue = sum(t.amount for t in revenue_result)

    return {
        "slots": {"total": total_slots, "available": available, "occupied": occupied, "reserved": reserved},
        "users": total_users,
        "active_sessions": active_sessions,
        "total_revenue": round(total_revenue, 2),
    }
