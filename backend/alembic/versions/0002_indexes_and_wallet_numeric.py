"""Add missing indexes and fix wallet balance precision

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-21

Changes:
  - parking_sessions: composite index (vehicle_id, status) + index on status alone
  - parking_slots: index on status
  - transactions: index on user_id
  - wallet.balance: FLOAT → DECIMAL(10,2) for exact financial arithmetic
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # parking_sessions — composite index used by every entry/exit lookup
    op.create_index(
        "ix_parking_sessions_vehicle_status",
        "parking_sessions",
        ["vehicle_id", "status"],
    )
    op.create_index("ix_parking_sessions_status", "parking_sessions", ["status"])

    # parking_slots — status is filtered on every entry event
    op.create_index("ix_parking_slots_status", "parking_slots", ["status"])

    # transactions — filtered by user_id for history views
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])

    # wallet.balance: FLOAT → DECIMAL(10,2)
    # MySQL safely converts existing float values to DECIMAL during ALTER.
    op.alter_column(
        "wallet",
        "balance",
        existing_type=sa.Float(),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "wallet",
        "balance",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Float(),
        existing_nullable=False,
    )
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_index("ix_parking_slots_status", table_name="parking_slots")
    op.drop_index("ix_parking_sessions_status", table_name="parking_sessions")
    op.drop_index("ix_parking_sessions_vehicle_status", table_name="parking_sessions")
