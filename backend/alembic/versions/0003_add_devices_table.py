"""Add devices table for dynamic IoT device registration

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-23

Replaces the in-memory _registry dict in iot.py.
Devices register on boot; backend discovers their current DHCP IP from this table.
No static IPs are needed anywhere.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(50), unique=True, nullable=False),
        sa.Column("current_ip", sa.String(45), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("firmware_version", sa.String(50), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="offline"),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_devices_device_id", "devices", ["device_id"])
    op.create_index("ix_devices_device_type", "devices", ["device_type"])


def downgrade() -> None:
    op.drop_index("ix_devices_device_type", table_name="devices")
    op.drop_index("ix_devices_device_id", table_name="devices")
    op.drop_table("devices")
