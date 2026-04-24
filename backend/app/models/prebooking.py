from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class PreBooking(Base):
    __tablename__ = "prebookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # slot_id stores slot_number text (e.g. "P3") — not FK to avoid coupling with slot lifecycle
    slot_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    booking_date: Mapped[str] = mapped_column(String(10), nullable=False)   # "YYYY-MM-DD"
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)      # "HH:MM"
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)        # "HH:MM"
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", backref="prebookings")
