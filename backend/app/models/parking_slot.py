from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class SlotStatus:
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slot_number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    # Indexed: queried on every entry event to find the first available slot
    status: Mapped[str] = mapped_column(String(20), default=SlotStatus.AVAILABLE, nullable=False, index=True)
    floor: Mapped[str] = mapped_column(String(10), default="G")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sessions = relationship("ParkingSession", back_populates="slot")
