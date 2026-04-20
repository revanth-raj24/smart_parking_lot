from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SlotOut(BaseModel):
    id: int
    slot_number: str
    status: str
    floor: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookSlotRequest(BaseModel):
    slot_id: int
    license_plate: str


class BookSlotResponse(BaseModel):
    status: str
    message: str
    slot: Optional[SlotOut] = None


class ParkingSessionOut(BaseModel):
    id: int
    license_plate_raw: str
    slot_id: Optional[int]
    entry_time: datetime
    exit_time: Optional[datetime]
    duration_minutes: Optional[float]
    cost: Optional[float]
    status: str
    entry_image_path: Optional[str]
    exit_image_path: Optional[str]

    model_config = {"from_attributes": True}


class ESP32EventResponse(BaseModel):
    status: str          # "ALLOW" | "DENY"
    message: str
    license_plate: Optional[str] = None
    session_id: Optional[int] = None
    cost: Optional[float] = None
    wallet_balance: Optional[float] = None


class OverrideSlotRequest(BaseModel):
    slot_id: int
    status: str          # available | occupied | reserved | maintenance


class GateCommand(BaseModel):
    gate: str            # "entry" | "exit"
    action: str          # "open" | "close"
