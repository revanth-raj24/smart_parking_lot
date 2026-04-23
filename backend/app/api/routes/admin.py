import uuid
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
import httpx

from app.db.database import get_db
from app.core.deps import get_current_admin
from app.core.config import settings
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import Wallet
from app.models.parking_slot import ParkingSlot, SlotStatus
from app.models.parking_session import ParkingSession, SessionStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.schemas.user import UserOut, AdminUserUpdate, AdminUserDetail
from app.schemas.vehicle import VehicleOut
from app.schemas.parking import (
    SlotOut, OverrideSlotRequest, GateCommand,
    AdminSessionOut, OccupiedSlotOut,
)
from app.schemas.wallet import AdminTransactionOut, AdminTransactionListOut

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


@router.get("/users/{user_id}/detail", response_model=AdminUserDetail)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    vehicles = db.query(Vehicle).filter(Vehicle.user_id == user_id).all()
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()

    total_sessions = active_sessions_count = 0
    if vehicles:
        vid_list = [v.id for v in vehicles]
        total_sessions = (
            db.query(func.count(ParkingSession.id))
            .filter(ParkingSession.vehicle_id.in_(vid_list))
            .scalar() or 0
        )
        active_sessions_count = (
            db.query(func.count(ParkingSession.id))
            .filter(ParkingSession.vehicle_id.in_(vid_list), ParkingSession.status == SessionStatus.ACTIVE)
            .scalar() or 0
        )

    return AdminUserDetail(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
        vehicles=[VehicleOut.model_validate(v) for v in vehicles],
        wallet_balance=float(wallet.balance) if wallet else None,
        total_sessions=total_sessions,
        active_sessions=active_sessions_count,
    )


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


@router.post("/users/{user_id}/wallet/credit")
def admin_credit_wallet(
    user_id: int,
    amount: float = Body(..., embed=True, gt=0, le=50000),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found for this user")

    now = datetime.now(timezone.utc)
    wallet.balance = round(float(wallet.balance) + amount, 2)
    wallet.updated_at = now

    txn = Transaction(
        user_id=user_id,
        amount=amount,
        transaction_type=TransactionType.CREDIT,
        status=TransactionStatus.SUCCESS,
        description="Admin manual credit",
        reference_id=f"ADM-{uuid.uuid4().hex[:10].upper()}",
        created_at=now,
    )
    db.add(txn)
    db.commit()
    logger.info(f"[ADMIN] Credited ₹{amount} to user {user_id}. Balance: {wallet.balance}")
    return {"new_balance": float(wallet.balance), "credited": amount}


# ── Parking Sessions ─────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[AdminSessionOut])
def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    status: str | None = Query(None),
    plate: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    q = db.query(ParkingSession).options(joinedload(ParkingSession.slot))
    if status:
        q = q.filter(ParkingSession.status == status)
    if plate:
        q = q.filter(ParkingSession.license_plate_raw.ilike(f"%{plate}%"))
    sessions = q.order_by(ParkingSession.entry_time.desc()).offset(skip).limit(limit).all()
    return [
        AdminSessionOut(
            id=s.id,
            vehicle_id=s.vehicle_id,
            license_plate_raw=s.license_plate_raw,
            slot_id=s.slot_id,
            slot_number=s.slot.slot_number if s.slot else None,
            entry_time=s.entry_time,
            exit_time=s.exit_time,
            duration_minutes=s.duration_minutes,
            cost=s.cost,
            status=s.status,
            entry_image_path=s.entry_image_path,
            exit_image_path=s.exit_image_path,
            deny_reason=s.deny_reason,
        )
        for s in sessions
    ]


@router.patch("/sessions/{session_id}/close")
def force_close_session(
    session_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    session = db.query(ParkingSession).filter(ParkingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Only active sessions can be force-closed")

    now = datetime.now(timezone.utc)
    entry = session.entry_time
    if entry.tzinfo is None:
        entry = entry.replace(tzinfo=timezone.utc)
    duration_min = round((now - entry).total_seconds() / 60, 1)

    session.exit_time = now
    session.duration_minutes = duration_min
    session.cost = 0.0
    session.status = SessionStatus.COMPLETED

    if session.slot_id:
        slot = db.query(ParkingSlot).filter(ParkingSlot.id == session.slot_id).first()
        if slot:
            slot.status = SlotStatus.AVAILABLE
            slot.updated_at = now

    db.commit()
    logger.info(f"[ADMIN] Force-closed session {session_id}, duration {duration_min}m")
    return {"status": "closed", "session_id": session_id, "duration_minutes": duration_min}


# ── Slots ─────────────────────────────────────────────────────────────────────

@router.get("/slots/occupied", response_model=list[OccupiedSlotOut])
def get_occupied_slots(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
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
        result.append(OccupiedSlotOut(
            slot_id=s.slot_id or 0,
            slot_number=slot.slot_number if slot else "?",
            floor=slot.floor if slot else "G",
            session_id=s.id,
            entry_time=s.entry_time,
            license_plate=s.license_plate_raw,
            vehicle_type=vehicle.vehicle_type if vehicle else "unknown",
            user_id=user.id if user else None,
            user_name=user.name if user else None,
            user_email=user.email if user else None,
            user_phone=user.phone if user else None,
        ))
    return result


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


# ── Latest Captures ───────────────────────────────────────────────────────────

@router.get("/latest-captures")
def latest_captures(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    latest_entry = (
        db.query(ParkingSession)
        .filter(ParkingSession.entry_image_path.isnot(None))
        .order_by(ParkingSession.entry_time.desc())
        .first()
    )
    latest_exit = (
        db.query(ParkingSession)
        .filter(ParkingSession.exit_image_path.isnot(None))
        .order_by(ParkingSession.exit_time.desc())
        .first()
    )

    def _fname(path: str | None) -> str | None:
        return path.split("/")[-1] if path else None

    return {
        "entry_image": _fname(latest_entry.entry_image_path) if latest_entry else None,
        "entry_time": latest_entry.entry_time if latest_entry else None,
        "entry_plate": latest_entry.license_plate_raw if latest_entry else None,
        "exit_image": _fname(latest_exit.exit_image_path) if latest_exit else None,
        "exit_time": latest_exit.exit_time if latest_exit else None,
        "exit_plate": latest_exit.license_plate_raw if latest_exit else None,
    }


# ── All Captures ──────────────────────────────────────────────────────────────

@router.get("/captures")
def all_captures(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Return every entry and exit image ever captured, newest first."""
    def _fname(p: str | None) -> str | None:
        return p.split("/")[-1] if p else None

    captures = []

    for s in (
        db.query(ParkingSession)
        .filter(ParkingSession.entry_image_path.isnot(None))
        .order_by(ParkingSession.entry_time.desc())
        .limit(limit)
        .all()
    ):
        captures.append({
            "session_id": s.id,
            "type": "entry",
            "image": _fname(s.entry_image_path),
            "timestamp": s.entry_time,
            "plate": s.license_plate_raw,
        })

    for s in (
        db.query(ParkingSession)
        .filter(ParkingSession.exit_image_path.isnot(None))
        .order_by(ParkingSession.exit_time.desc())
        .limit(limit)
        .all()
    ):
        captures.append({
            "session_id": s.id,
            "type": "exit",
            "image": _fname(s.exit_image_path),
            "timestamp": s.exit_time,
            "plate": s.license_plate_raw,
        })

    captures.sort(key=lambda x: x["timestamp"] or datetime.min, reverse=True)
    return captures[:limit]


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

@router.get("/transactions", response_model=AdminTransactionListOut)
def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="Filter by payment status: success | failed | pending"),
    txn_type: str | None = Query(None, description="Filter by type: credit | debit"),
    vehicle: str | None = Query(None, description="Search by vehicle plate (partial match)"),
    date_from: str | None = Query(None, description="Start date ISO format: YYYY-MM-DD"),
    date_to: str | None = Query(None, description="End date ISO format: YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    filters = []

    if status:
        filters.append(Transaction.status == status)
    if txn_type:
        filters.append(Transaction.transaction_type == txn_type)
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            filters.append(Transaction.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
            filters.append(Transaction.created_at < dt)
        except ValueError:
            pass
    if vehicle:
        matching_ids = (
            db.query(ParkingSession.id)
            .filter(ParkingSession.license_plate_raw.ilike(f"%{vehicle}%"))
            .subquery()
        )
        filters.append(Transaction.session_id.in_(matching_ids))

    total: int = (
        db.query(func.count(Transaction.id))
        .filter(*filters)
        .scalar() or 0
    )

    offset = (page - 1) * limit
    txns = (
        db.query(Transaction)
        .filter(*filters)
        .options(
            joinedload(Transaction.user),
            joinedload(Transaction.session).joinedload(ParkingSession.slot),
        )
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    def _fname(path: str | None) -> str | None:
        return path.split("/")[-1] if path else None

    result: list[AdminTransactionOut] = []
    for t in txns:
        s = t.session
        result.append(AdminTransactionOut(
            id=t.id,
            reference_id=t.reference_id,
            amount=t.amount,
            transaction_type=t.transaction_type,
            payment_status=t.status,
            description=t.description,
            created_at=t.created_at,
            user_id=t.user_id,
            user_name=t.user.name if t.user else None,
            user_email=t.user.email if t.user else None,
            session_id=t.session_id,
            vehicle_number=s.license_plate_raw if s else None,
            entry_time=s.entry_time if s else None,
            exit_time=s.exit_time if s else None,
            duration_minutes=s.duration_minutes if s else None,
            parking_slot=s.slot.slot_number if s and s.slot else None,
            entry_image=_fname(s.entry_image_path) if s else None,
            exit_image=_fname(s.exit_image_path) if s else None,
            session_status=s.status if s else None,
        ))

    return AdminTransactionListOut(total=total, page=page, limit=limit, transactions=result)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    slot_counts: dict[str, int] = {}
    for status_val, count in db.query(ParkingSlot.status, func.count()).group_by(ParkingSlot.status).all():
        slot_counts[status_val] = count

    total_users = db.query(func.count(User.id)).filter(User.is_admin == False).scalar() or 0  # noqa: E712
    active_sessions = db.query(func.count(ParkingSession.id)).filter(ParkingSession.status == "active").scalar() or 0
    total_revenue = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.transaction_type == TransactionType.DEBIT)
        .scalar()
    ) or 0.0

    return {
        "slots": {
            "total": sum(slot_counts.values()),
            "available": slot_counts.get(SlotStatus.AVAILABLE, 0),
            "occupied": slot_counts.get(SlotStatus.OCCUPIED, 0),
            "reserved": slot_counts.get(SlotStatus.RESERVED, 0),
        },
        "users": total_users,
        "active_sessions": active_sessions,
        "total_revenue": round(float(total_revenue), 2),
    }


# ── Hardware Simulation ───────────────────────────────────────────────────────

async def _forward_to_esp32_endpoint(request: Request, image_bytes: bytes, filename: str, path: str) -> dict:
    base = str(request.base_url).rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base}/{path}",
            files={"image": (filename, image_bytes, "image/jpeg")},
        )
        resp.raise_for_status()
        return resp.json()


@router.post("/simulate-entry")
async def simulate_entry(
    request: Request,
    image: UploadFile = File(...),
    _admin: User = Depends(get_current_admin),
):
    image_bytes = await image.read()
    filename = image.filename or "simulate_entry.jpg"
    logger.info(f"[SIM] Entry simulation — {len(image_bytes)} bytes")
    return await _forward_to_esp32_endpoint(request, image_bytes, filename, "api/esp32/entry-event")


@router.post("/simulate-exit")
async def simulate_exit(
    request: Request,
    image: UploadFile = File(...),
    _admin: User = Depends(get_current_admin),
):
    image_bytes = await image.read()
    filename = image.filename or "simulate_exit.jpg"
    logger.info(f"[SIM] Exit simulation — {len(image_bytes)} bytes")
    return await _forward_to_esp32_endpoint(request, image_bytes, filename, "api/esp32/exit-event")
