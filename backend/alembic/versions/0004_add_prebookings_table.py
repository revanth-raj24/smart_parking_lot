"""Add prebookings table for slot pre-reservation

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prebookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("slot_id", sa.String(10), nullable=False),
        sa.Column("booking_date", sa.String(10), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("end_time", sa.String(5), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prebookings_user_id", "prebookings", ["user_id"])
    op.create_index("ix_prebookings_slot_id",  "prebookings", ["slot_id"])
    op.create_index("ix_prebookings_status",   "prebookings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_prebookings_status",  table_name="prebookings")
    op.drop_index("ix_prebookings_slot_id", table_name="prebookings")
    op.drop_index("ix_prebookings_user_id", table_name="prebookings")
    op.drop_table("prebookings")
