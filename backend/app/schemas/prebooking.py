from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PreBookingCreate(BaseModel):
    slot_id: str = Field(..., description="Slot number e.g. P3", examples=["P3"])
    date: str = Field(..., description="Booking date YYYY-MM-DD", examples=["2026-04-25"])
    start_time: str = Field(..., description="Start time HH:MM", examples=["10:00"])
    end_time: str = Field(..., description="End time HH:MM", examples=["12:00"])

    model_config = {
        "json_schema_extra": {
            "example": {"slot_id": "P3", "date": "2026-04-25", "start_time": "10:00", "end_time": "12:00"}
        }
    }


class PreBookingOut(BaseModel):
    id: int
    user_id: int
    slot_id: str
    booking_date: str
    start_time: str
    end_time: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminPreBookingOut(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    slot_id: str
    booking_date: str
    start_time: str
    end_time: str
    status: str
    created_at: datetime
