"""Add QR scan events table

Revision ID: 0002_add_qr_scan_events
Revises: 0001_initial_schema
Create Date: 2026-03-27 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_add_qr_scan_events"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qr_scan_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("qr_value", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("recovery_method", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="qr_reader"),
        sa.Column("variant_id", sa.String(), nullable=False, server_default="qr_page_v1"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qr_scan_events_id", "qr_scan_events", ["id"], unique=False)
    op.create_index("ix_qr_scan_events_session_id", "qr_scan_events", ["session_id"], unique=False)
    op.create_index("ix_qr_scan_events_event_type", "qr_scan_events", ["event_type"], unique=False)
    op.create_index("ix_qr_scan_events_occurred_at", "qr_scan_events", ["occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_qr_scan_events_occurred_at", table_name="qr_scan_events")
    op.drop_index("ix_qr_scan_events_event_type", table_name="qr_scan_events")
    op.drop_index("ix_qr_scan_events_session_id", table_name="qr_scan_events")
    op.drop_index("ix_qr_scan_events_id", table_name="qr_scan_events")
    op.drop_table("qr_scan_events")
