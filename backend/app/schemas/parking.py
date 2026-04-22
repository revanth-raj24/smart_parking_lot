from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SlotOut(BaseModel):
    id: int
    slot_number: str = Field(..., description="Human-readable slot identifier, e.g. `A1`")
    status: str = Field(..., description="Current status: `available`, `occupied`, `reserved`, or `maintenance`")
    floor: str = Field(..., description="Floor label, e.g. `G` (ground), `1`, `2`")
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookSlotRequest(BaseModel):
    slot_id: int = Field(..., description="ID of the slot to reserve (from `GET /api/parking/slots`)", examples=[3])
    license_plate: str = Field(..., description="Your vehicle's registration number (case-insensitive)", examples=["KA01AB1234"])

    model_config = {
        "json_schema_extra": {"example": {"slot_id": 3, "license_plate": "KA01AB1234"}}
    }


class BookSlotResponse(BaseModel):
    status: str = Field(..., description="`SUCCESS` or `FAIL`")
    message: str
    slot: Optional[SlotOut] = None


class ParkingSessionOut(BaseModel):
    id: int
    license_plate_raw: str = Field(..., description="License plate as read by OCR or entered manually")
    slot_id: Optional[int] = Field(None, description="Assigned slot ID")
    entry_time: datetime
    exit_time: Optional[datetime] = None
    duration_minutes: Optional[float] = Field(None, description="Total parked duration in minutes")
    cost: Optional[float] = Field(None, description="Fee charged in INR (₹)")
    status: str = Field(..., description="Session status: `active`, `completed`, or `denied`")
    entry_image_path: Optional[str] = Field(None, description="Relative path to the entry gate capture")
    exit_image_path: Optional[str] = Field(None, description="Relative path to the exit gate capture")

    model_config = {"from_attributes": True}


class ESP32EventResponse(BaseModel):
    status: str = Field(..., description="`ALLOW` — gate opens; `DENY` — gate stays closed")
    message: str = Field(..., description="Human-readable explanation sent back to the ESP32")
    license_plate: Optional[str] = Field(None, description="License plate extracted by OCR")
    session_id: Optional[int] = Field(None, description="Created/closed session ID (ALLOW only)")
    cost: Optional[float] = Field(None, description="Fee deducted in INR (exit ALLOW only)")
    wallet_balance: Optional[float] = Field(None, description="Remaining wallet balance after deduction")


class OverrideSlotRequest(BaseModel):
    slot_id: int = Field(..., description="ID of the slot to override")
    status: str = Field(..., description="Target status: `available`, `occupied`, `reserved`, or `maintenance`")

    model_config = {
        "json_schema_extra": {"example": {"slot_id": 2, "status": "maintenance"}}
    }


class GateCommand(BaseModel):
    gate: str = Field(..., description="Which gate: `entry` or `exit`")
    action: str = Field(..., description="Command: `open` or `close`")

    model_config = {
        "json_schema_extra": {"example": {"gate": "entry", "action": "open"}}
    }


class AdminSessionOut(BaseModel):
    id: int
    vehicle_id: Optional[int] = None
    license_plate_raw: str
    slot_id: Optional[int] = None
    slot_number: Optional[str] = None
    entry_time: datetime
    exit_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    cost: Optional[float] = None
    status: str
    entry_image_path: Optional[str] = None
    exit_image_path: Optional[str] = None
    deny_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class OccupiedSlotOut(BaseModel):
    slot_id: int
    slot_number: str
    floor: str
    session_id: int
    entry_time: datetime
    license_plate: str
    vehicle_type: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
