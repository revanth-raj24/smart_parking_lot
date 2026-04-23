from sqlalchemy import Column, Integer, String, DateTime
from app.db.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    current_ip = Column(String(45), nullable=False)
    port = Column(Integer, nullable=False, default=80)
    device_type = Column(String(20), nullable=False, index=True)  # entry_cam | exit_cam
    firmware_version = Column(String(50), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(10), nullable=False, default="offline")  # online | offline
    registered_at = Column(DateTime(timezone=True), nullable=False)
