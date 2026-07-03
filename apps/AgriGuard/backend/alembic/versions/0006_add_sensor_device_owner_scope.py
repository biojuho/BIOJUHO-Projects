"""Add owner scope to sensor devices

Revision ID: 0006_add_sensor_device_owner_scope
Revises: 0005_add_qr_scan_event_kpi_indexes
Create Date: 2026-06-10 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_add_sensor_device_owner_scope"
down_revision = "0005_add_qr_scan_event_kpi_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sensor_devices", sa.Column("owner_id", sa.String(), nullable=True))
    op.create_index("ix_sensor_devices_owner_id", "sensor_devices", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sensor_devices_owner_id", table_name="sensor_devices")
    op.drop_column("sensor_devices", "owner_id")
