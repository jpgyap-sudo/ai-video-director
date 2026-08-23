"""product_assets status + size_bytes

Revision ID: 0003_asset_status
Revises: 0002_products
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_asset_status"
down_revision: str | None = "0002_products"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_assets",
        sa.Column("size_bytes", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "product_assets",
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="QUARANTINED",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("product_assets", "status")
    op.drop_column("product_assets", "size_bytes")
