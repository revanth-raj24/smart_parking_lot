"""
Run with: python -m app.db.seed
Seeds: default admin account + 11 parking slots
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.database import SessionLocal, engine, Base
from app.models import User, ParkingSlot, Wallet
from app.core.security import hash_password
from datetime import datetime, timezone


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # --- Admin account ---
        existing_admin = db.query(User).filter(User.email == "admin@smartpark.com").first()
        if not existing_admin:
            admin = User(
                name="Admin",
                email="admin@smartpark.com",
                hashed_password=hash_password("admin123"),
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
            print("[SEED] Admin account created: admin@smartpark.com / admin123")
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
