"""Add durable QR token table

Revision ID: 0003_add_qr_tokens
Revises: 0002_add_qr_scan_events
Create Date: 2026-06-09 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_add_qr_tokens"
down_revision = "0002_add_qr_scan_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qr_tokens",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("token_prefix", sa.String(), nullable=False),
        sa.Column("batch_code", sa.String(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("scan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qr_tokens_id", "qr_tokens", ["id"], unique=False)
    op.create_index("ix_qr_tokens_token_hash", "qr_tokens", ["token_hash"], unique=True)
    op.create_index("ix_qr_tokens_product_id", "qr_tokens", ["product_id"], unique=False)
    op.create_index("ix_qr_tokens_expires_at", "qr_tokens", ["expires_at"], unique=False)
    op.create_index("ix_qr_tokens_revoked_at", "qr_tokens", ["revoked_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_qr_tokens_revoked_at", table_name="qr_tokens")
    op.drop_index("ix_qr_tokens_expires_at", table_name="qr_tokens")
    op.drop_index("ix_qr_tokens_product_id", table_name="qr_tokens")
    op.drop_index("ix_qr_tokens_token_hash", table_name="qr_tokens")
    op.drop_index("ix_qr_tokens_id", table_name="qr_tokens")
    op.drop_table("qr_tokens")
