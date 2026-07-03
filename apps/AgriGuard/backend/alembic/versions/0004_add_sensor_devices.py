"""Add IoT sensor device registry

Revision ID: 0004_add_sensor_devices
Revises: 0003_add_qr_tokens
Create Date: 2026-06-09 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_add_sensor_devices"
down_revision = "0003_add_qr_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sensor_devices",
        sa.Column("sensor_id", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("zone", sa.String(), nullable=True),
        sa.Column("expected_interval_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("registered_at", sa.DateTime(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_battery", sa.Float(), nullable=True),
        sa.Column("last_status", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("sensor_id"),
    )
    op.create_index("ix_sensor_devices_zone", "sensor_devices", ["zone"], unique=False)
    op.create_index("ix_sensor_devices_is_active", "sensor_devices", ["is_active"], unique=False)
    op.create_index("ix_sensor_devices_last_seen_at", "sensor_devices", ["last_seen_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sensor_devices_last_seen_at", table_name="sensor_devices")
    op.drop_index("ix_sensor_devices_is_active", table_name="sensor_devices")
    op.drop_index("ix_sensor_devices_zone", table_name="sensor_devices")
    op.drop_table("sensor_devices")
