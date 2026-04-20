from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class TransactionType:
    DEBIT = "debit"
    CREDIT = "credit"


class TransactionStatus:
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("parking_sessions.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=TransactionStatus.SUCCESS, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="transactions")
    session = relationship("ParkingSession", back_populates="transaction")
