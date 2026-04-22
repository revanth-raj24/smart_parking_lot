from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class VehicleCreate(BaseModel):
    license_plate: str = Field(..., description="Vehicle registration number (case-insensitive)", examples=["KA01AB1234"])
    vehicle_type: str = Field("car", description="Type of vehicle: `car`, `bike`, or `truck`", examples=["car"])

    model_config = {
        "json_schema_extra": {"example": {"license_plate": "KA01AB1234", "vehicle_type": "car"}}
    }


class VehicleOut(BaseModel):
    id: int
    license_plate: str
    vehicle_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
