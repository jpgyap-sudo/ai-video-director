"""reference_media + reference_rights_attestations

Revision ID: 0004_references
Revises: 0003_asset_status
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_references"
down_revision: str | None = "0003_asset_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_media",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("ownership", sa.String(length=50), nullable=False),
        sa.Column("license_type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("permitted_channels", sa.String(length=1024), nullable=True),
        sa.Column("permitted_territories", sa.String(length=1024), nullable=True),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_notes", sa.String(length=2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reference_media_organization_id"),
        "reference_media",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reference_media_project_id"), "reference_media", ["project_id"], unique=False
    )
    op.create_table(
        "reference_rights_attestations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("reference_id", sa.String(length=36), nullable=False),
        sa.Column("attested_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "attested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claimed_ownership", sa.String(length=50), nullable=False),
        sa.Column("claimed_license_type", sa.String(length=50), nullable=False),
        sa.Column("claimed_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reference_id"], ["reference_media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reference_rights_attestations_organization_id"),
        "reference_rights_attestations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reference_rights_attestations_reference_id"),
        "reference_rights_attestations",
        ["reference_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reference_rights_attestations_reference_id"),
        table_name="reference_rights_attestations",
    )
    op.drop_index(
        op.f("ix_reference_rights_attestations_organization_id"),
        table_name="reference_rights_attestations",
    )
    op.drop_table("reference_rights_attestations")
    op.drop_index(op.f("ix_reference_media_project_id"), table_name="reference_media")
    op.drop_index(op.f("ix_reference_media_organization_id"), table_name="reference_media")
    op.drop_table("reference_media")
