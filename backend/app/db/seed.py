"""
Run with: python -m app.db.seed
Seeds: default admin account + 11 parking slots

Credentials are read from environment variables:
  ADMIN_SEED_EMAIL    (default: admin@smartpark.com)
  ADMIN_SEED_PASSWORD (default: admin123 — change before production)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.database import SessionLocal, engine, Base
from app.models import User, ParkingSlot, Wallet
from app.core.security import hash_password
from datetime import datetime, timezone

_ADMIN_EMAIL    = os.environ.get("ADMIN_SEED_EMAIL",    "admin@smartpark.com")
_ADMIN_PASSWORD = os.environ.get("ADMIN_SEED_PASSWORD", "admin123")


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # --- Admin account ---
        existing_admin = db.query(User).filter(User.email == _ADMIN_EMAIL).first()
        if not existing_admin:
            admin = User(
                name="Admin",
                email=_ADMIN_EMAIL,
                hashed_password=hash_password(_ADMIN_PASSWORD),
                phone="9999999999",
                is_active=True,
                is_admin=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            db.flush()

            admin_wallet = Wallet(
                user_id=admin.id,
                balance=0.0,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(admin_wallet)
            print(f"[SEED] Admin account created: {_ADMIN_EMAIL}")
            print("[SEED] Set ADMIN_SEED_PASSWORD env var to configure the password before production.")
        else:
            print("[SEED] Admin account already exists — skipping")

        # --- 11 parking slots ---
        slot_count = db.query(ParkingSlot).count()
        if slot_count == 0:
            slots = [
                ParkingSlot(
                    slot_number=f"P{i}",
                    status="available",
                    floor="G",
                    updated_at=datetime.now(timezone.utc),
                )
                for i in range(1, 12)
            ]
            db.add_all(slots)
            print("[SEED] 11 parking slots created: P1–P11")
        else:
            print(f"[SEED] {slot_count} parking slots already exist — skipping")

        db.commit()
        print("[SEED] Done.")

    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
