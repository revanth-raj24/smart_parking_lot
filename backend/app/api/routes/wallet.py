import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.schemas.wallet import WalletOut, AddFundsRequest, AddFundsResponse, TransactionOut
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

router = APIRouter()


def _get_wallet(user_id: int, db: Session) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.get("/balance", response_model=WalletOut)
def get_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_wallet(current_user.id, db)


@router.post("/add", response_model=AddFundsResponse)
def add_funds(
    payload: AddFundsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = _get_wallet(current_user.id, db)
    wallet.balance = (wallet.balance + Decimal(str(payload.amount))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    wallet.updated_at = datetime.now(timezone.utc)

    txn = Transaction(
        user_id=current_user.id,
        amount=payload.amount,
        transaction_type=TransactionType.CREDIT,
        status=TransactionStatus.SUCCESS,
        description=f"Wallet top-up of ₹{payload.amount:.2f}",
        reference_id=f"TOPUP-{uuid.uuid4().hex[:10].upper()}",
        created_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    return AddFundsResponse(
        message=f"₹{payload.amount:.2f} added to wallet",
        new_balance=wallet.balance,
        transaction_id=txn.id,
    )


@router.get("/transactions", response_model=list[TransactionOut])
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .limit(100)
        .all()
    )
