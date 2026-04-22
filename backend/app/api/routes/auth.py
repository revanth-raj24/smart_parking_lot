from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.schemas.user import UserRegister, UserLogin, UserOut, TokenResponse, UserUpdate
from app.schemas.vehicle import VehicleCreate, VehicleOut
from app.models.vehicle import Vehicle
from datetime import datetime, timezone

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    wallet = Wallet(user_id=user.id, balance=0.0, updated_at=datetime.now(timezone.utc))
    db.add(wallet)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": "user"})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    role = "admin" if user.is_admin else "user"
    token = create_access_token({"sub": str(user.id), "role": role})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.name is not None:
        current_user.name = payload.name
    if payload.phone is not None:
        current_user.phone = payload.phone
    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def add_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plate = payload.license_plate.upper().strip()
    if db.query(Vehicle).filter(Vehicle.license_plate == plate).first():
        raise HTTPException(status_code=400, detail="License plate already registered")

    vehicle = Vehicle(
        user_id=current_user.id,
        license_plate=plate,
        vehicle_type=payload.vehicle_type,
        created_at=datetime.now(timezone.utc),
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id, Vehicle.user_id == current_user.id
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(vehicle)
    db.commit()
