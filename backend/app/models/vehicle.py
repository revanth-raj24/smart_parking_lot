from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    license_plate: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), default="car")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    owner = relationship("User", back_populates="vehicles")
    parking_sessions = relationship("ParkingSession", back_populates="vehicle")
