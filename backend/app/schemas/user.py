from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.schemas.vehicle import VehicleOut


class UserRegister(BaseModel):
    name: str = Field(..., description="Full name", examples=["Revanth Raj"])
    email: EmailStr = Field(..., description="Email address", examples=["user@example.com"])
    password: str = Field(..., min_length=6, description="Password (min 6 characters)", examples=["secret123"])
    phone: Optional[str] = Field(None, description="Mobile number", examples=["+91-9876543210"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Revanth Raj",
                "email": "user@example.com",
                "password": "secret123",
                "phone": "+91-9876543210",
            }
        }
    }


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="Registered email address", examples=["user@example.com"])
    password: str = Field(..., description="Account password", examples=["secret123"])

    model_config = {
        "json_schema_extra": {
            "example": {"email": "user@example.com", "password": "secret123"}
        }
    }


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, description="New display name", examples=["Raj Kumar"])
    phone: Optional[str] = Field(None, description="New phone number", examples=["+91-9000000000"])

    model_config = {
        "json_schema_extra": {"example": {"name": "Raj Kumar", "phone": "+91-9000000000"}}
    }


class AdminUserUpdate(BaseModel):
    name: Optional[str] = Field(None, description="New display name")
    phone: Optional[str] = Field(None, description="New phone number")
    is_active: Optional[bool] = Field(None, description="Set `false` to deactivate the account")

    model_config = {
        "json_schema_extra": {"example": {"name": "Raj Kumar", "phone": "+91-9000000000", "is_active": True}}
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AdminUserDetail(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    vehicles: list[VehicleOut]
    wallet_balance: Optional[float] = None
    total_sessions: int
    active_sessions: int
