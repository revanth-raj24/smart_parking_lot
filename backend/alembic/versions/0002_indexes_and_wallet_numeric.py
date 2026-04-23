"""Add missing indexes and fix wallet balance precision

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-21

Changes:
  - parking_sessions: composite index (vehicle_id, status) + index on status alone
  - parking_slots: index on status
  - transactions: index on user_id
  - wallet.balance: FLOAT → DECIMAL(10,2)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    # ---------------------------
    # parking_sessions indexes
    # ---------------------------
    existing_indexes = {i["name"] for i in inspector.get_indexes("parking_sessions")}

    if "ix_parking_sessions_vehicle_status" not in existing_indexes:
        op.create_index(
            "ix_parking_sessions_vehicle_status",
            "parking_sessions",
            ["vehicle_id", "status"],
        )

    if "ix_parking_sessions_status" not in existing_indexes:
        op.create_index(
            "ix_parking_sessions_status",
            "parking_sessions",
            ["status"],
        )

    # ---------------------------
    # parking_slots index
    # ---------------------------
    existing_indexes = {i["name"] for i in inspector.get_indexes("parking_slots")}

    if "ix_parking_slots_status" not in existing_indexes:
        op.create_index(
            "ix_parking_slots_status",
            "parking_slots",
            ["status"],
        )

    # ---------------------------
    # transactions index
    # ---------------------------
    existing_indexes = {i["name"] for i in inspector.get_indexes("transactions")}

    if "ix_transactions_user_id" not in existing_indexes:
        op.create_index(
            "ix_transactions_user_id",
            "transactions",
            ["user_id"],
        )

    # ---------------------------
    # wallet.balance fix (SQLite-safe)
    # ---------------------------
    with op.batch_alter_table("wallet") as batch_op:
        batch_op.alter_column(
            "balance",
            existing_type=sa.Float(),
            type_=sa.Numeric(10, 2),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Reverse wallet change (SQLite-safe)
    with op.batch_alter_table("wallet") as batch_op:
        batch_op.alter_column(
            "balance",
            existing_type=sa.Numeric(10, 2),
            type_=sa.Float(),
            existing_nullable=False,
        )

    # Drop indexes safely
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_index("ix_parking_slots_status", table_name="parking_slots")
    op.drop_index("ix_parking_sessions_status", table_name="parking_sessions")
    op.drop_index("ix_parking_sessions_vehicle_status", table_name="parking_sessions")