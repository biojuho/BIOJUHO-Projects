"""Initial schema — users, products, tracking_events, certificates, sensor_readings

Revision ID: 0001
Revises:
Create Date: 2026-03-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("organization", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("origin", sa.String(), nullable=True),
        sa.Column("harvest_date", sa.DateTime(), nullable=True),
        sa.Column("requires_cold_chain", sa.Boolean(), nullable=True),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("qr_code", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_id", "products", ["id"], unique=False)
    op.create_index("ix_products_name", "products", ["name"], unique=False)
    op.create_index("ix_products_owner_id", "products", ["owner_id"], unique=False)
    op.create_index("ix_products_qr_code", "products", ["qr_code"], unique=True)

    op.create_table(
        "tracking_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("handler_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tracking_events_id", "tracking_events", ["id"], unique=False)
    op.create_index("ix_tracking_events_product_id", "tracking_events", ["product_id"], unique=False)

    op.create_table(
        "certificates",
        sa.Column("cert_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("issued_by", sa.String(), nullable=True),
        sa.Column("issue_date", sa.DateTime(), nullable=True),
        sa.Column("cert_type", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("cert_id"),
    )
    op.create_index("ix_certificates_cert_id", "certificates", ["cert_id"], unique=False)
    op.create_index("ix_certificates_product_id", "certificates", ["product_id"], unique=False)

    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("sensor_id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("battery", sa.Float(), nullable=True),
        sa.Column("zone", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sensor_readings_sensor_id", "sensor_readings", ["sensor_id"], unique=False)
    op.create_index("ix_sensor_readings_timestamp", "sensor_readings", ["timestamp"], unique=False)
    op.create_index("ix_sensor_readings_zone", "sensor_readings", ["zone"], unique=False)
    # Composite index for time-series queries (sensor_id, timestamp)
    op.create_index("ix_sensor_reading_sensor_ts", "sensor_readings", ["sensor_id", "timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sensor_reading_sensor_ts", table_name="sensor_readings")
    op.drop_index("ix_sensor_readings_zone", table_name="sensor_readings")
    op.drop_index("ix_sensor_readings_timestamp", table_name="sensor_readings")
    op.drop_index("ix_sensor_readings_sensor_id", table_name="sensor_readings")
    op.drop_table("sensor_readings")

    op.drop_index("ix_certificates_product_id", table_name="certificates")
    op.drop_index("ix_certificates_cert_id", table_name="certificates")
    op.drop_table("certificates")

    op.drop_index("ix_tracking_events_product_id", table_name="tracking_events")
    op.drop_index("ix_tracking_events_id", table_name="tracking_events")
    op.drop_table("tracking_events")

    op.drop_index("ix_products_qr_code", table_name="products")
    op.drop_index("ix_products_owner_id", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_index("ix_products_id", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
