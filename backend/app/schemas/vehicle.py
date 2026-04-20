from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class VehicleCreate(BaseModel):
    license_plate: str
    vehicle_type: str = "car"


class VehicleOut(BaseModel):
    id: int
    license_plate: str
    vehicle_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
