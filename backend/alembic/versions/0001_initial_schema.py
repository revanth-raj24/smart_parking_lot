"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_admin", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("license_plate", sa.String(20), unique=True, nullable=False),
        sa.Column("vehicle_type", sa.String(50), default="car"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_vehicles_license_plate", "vehicles", ["license_plate"])

    op.create_table(
        "parking_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slot_number", sa.String(10), unique=True, nullable=False),
        sa.Column("status", sa.String(20), default="available", nullable=False),
        sa.Column("floor", sa.String(10), default="G"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "parking_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("slot_id", sa.Integer(), sa.ForeignKey("parking_slots.id"), nullable=True),
        sa.Column("license_plate_raw", sa.String(20), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Float(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), default="active", nullable=False),
        sa.Column("entry_image_path", sa.String(255), nullable=True),
        sa.Column("exit_image_path", sa.String(255), nullable=True),
        sa.Column("deny_reason", sa.Text(), nullable=True),
    )

    op.create_table(
        "wallet",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("balance", sa.Float(), default=0.0, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("parking_sessions.id"), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), default="success", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("wallet")
    op.drop_table("parking_sessions")
    op.drop_table("parking_slots")
    op.drop_table("vehicles")
    op.drop_table("users")
