"""Add QR scan event KPI indexes

Revision ID: 0005_add_qr_scan_event_kpi_indexes
Revises: 0004_add_sensor_devices
Create Date: 2026-06-10 00:00:00.000000
"""

from alembic import op


revision = "0005_add_qr_scan_event_kpi_indexes"
down_revision = "0004_add_sensor_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_qr_scan_events_occurred_session_event",
        "qr_scan_events",
        ["occurred_at", "session_id", "event_type"],
        unique=False,
    )
    op.create_index(
        "ix_qr_scan_events_variant_occurred_session_event",
        "qr_scan_events",
        ["variant_id", "occurred_at", "session_id", "event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_qr_scan_events_variant_occurred_session_event", table_name="qr_scan_events")
    op.drop_index("ix_qr_scan_events_occurred_session_event", table_name="qr_scan_events")
