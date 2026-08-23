"""campaigns

Revision ID: 0005_campaigns
Revises: 0004_references
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_campaigns"
down_revision: str | None = "0004_references"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("recipe", sa.String(length=50), nullable=False),
        sa.Column("brief", sa.String(length=4096), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_campaigns_organization_id"), "campaigns", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_campaigns_project_id"), "campaigns", ["project_id"], unique=False)
    op.create_index(op.f("ix_campaigns_product_id"), "campaigns", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_campaigns_product_id"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_project_id"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_organization_id"), table_name="campaigns")
    op.drop_table("campaigns")
