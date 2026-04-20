from datetime import datetime
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
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
