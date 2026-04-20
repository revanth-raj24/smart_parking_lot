from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class SessionStatus:
    ACTIVE = "active"
    COMPLETED = "completed"
    DENIED = "denied"


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicles.id"), nullable=True)
    slot_id: Mapped[int] = mapped_column(Integer, ForeignKey("parking_slots.id"), nullable=True)
    license_plate_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[float] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.ACTIVE, nullable=False)
    entry_image_path: Mapped[str] = mapped_column(String(255), nullable=True)
    exit_image_path: Mapped[str] = mapped_column(String(255), nullable=True)
    deny_reason: Mapped[str] = mapped_column(Text, nullable=True)

    vehicle = relationship("Vehicle", back_populates="parking_sessions")
    slot = relationship("ParkingSlot", back_populates="sessions")
    transaction = relationship("Transaction", back_populates="session", uselist=False)
