from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WalletOut(BaseModel):
    id: int
    user_id: int
    balance: float
    updated_at: datetime

    model_config = {"from_attributes": True}


class AddFundsRequest(BaseModel):
    amount: float = Field(..., gt=0, le=10000)


class AddFundsResponse(BaseModel):
    message: str
    new_balance: float
    transaction_id: int


class TransactionOut(BaseModel):
    id: int
    amount: float
    transaction_type: str
    status: str
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminTransactionOut(BaseModel):
    # Core transaction
    id: int
    reference_id: Optional[str] = None
    amount: float
    transaction_type: str       # "credit" | "debit"
    payment_status: str         # "success" | "failed" | "pending"
    description: Optional[str] = None
    created_at: datetime

    # User (joined)
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    # Parking session (joined, null for wallet top-ups)
    session_id: Optional[int] = None
    vehicle_number: Optional[str] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    parking_slot: Optional[str] = None
    entry_image: Optional[str] = None
    exit_image: Optional[str] = None
    session_status: Optional[str] = None


class AdminTransactionListOut(BaseModel):
    total: int
    page: int
    limit: int
    transactions: list[AdminTransactionOut]
