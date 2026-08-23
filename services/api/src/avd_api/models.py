"""SQLAlchemy models for Phase 0 tenant-owned resources."""

from __future__ import annotations

import enum
import os
import time
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from avd_api.db import Base


class Recipe(str, enum.Enum):
    """Closed set of generation recipes (plan §4 line 293)."""

    PRODUCT_AD = "product_ad"
    PRODUCT_SWAP = "product_swap"


def uuid7() -> str:
    """Generate a UUIDv7 (time-ordered, sortable) as a string.

    UUIDv7 encodes a 48-bit Unix timestamp in the high bits, so values sort
    chronologically and support cursor pagination. This is required by the
    plan's §7 conventions (UUIDv7 identifiers + cursor pagination).
    """
    timestamp_ms = int(time.time() * 1000)
    rand_b = os.urandom(10)
    # 48-bit timestamp
    time_bytes = timestamp_ms.to_bytes(6, "big")
    # version 7 in the high nibble of byte 6
    rand_b = bytearray(rand_b)
    rand_b[0] = (rand_b[0] & 0x0F) | 0x70
    # variant 10xx in the high bits of byte 8
    rand_b[2] = (rand_b[2] & 0x3F) | 0x80
    raw = time_bytes + bytes(rand_b)
    return str(uuid.UUID(bytes=raw))


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list[Membership]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list[Membership]] = relationship(back_populates="user")


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # SKU is the natural business key, unique within an organization.
        UniqueConstraint("organization_id", "sku", name="uq_products_org_sku"),
    )


class ProductAsset(Base):
    __tablename__ = "product_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="QUARANTINED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReferenceMedia(Base):
    """External video/style image the customer claims authorization for.

    Named `reference_media` (not `references`) because `references` is a
    PostgreSQL reserved word. Carries the license metadata; the attestation
    of that license is a separate, immutable record.
    """

    __tablename__ = "reference_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    # License metadata (plan §4 line 303).
    ownership: Mapped[str] = mapped_column(String(50), nullable=False, default="OWNED")
    license_type: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE")
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permitted_channels: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    permitted_territories: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReferenceRightsAttestation(Base):
    """Immutable record of who attested a reference's rights and when.

    The audit trail is the point of the rights ledger: an attestation is never
    edited, only appended. The reference's reviewer notes may change; the
    attestation captures what was claimed at the moment of attestation.
    """

    __tablename__ = "reference_rights_attestations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reference_id: Mapped[str] = mapped_column(
        ForeignKey("reference_media.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attested_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    attested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Snapshot of the license metadata claimed at attestation time.
    claimed_ownership: Mapped[str] = mapped_column(String(50), nullable=False)
    claimed_license_type: Mapped[str] = mapped_column(String(50), nullable=False)
    claimed_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Campaign(Base):
    """A creative brief for a generation run.

    Versioned (optimistic concurrency, plan §4 line 173): every mutable
    creative object is versioned rather than overwritten. The recipe is a
    closed enum so the Runway adapter can dispatch on it without re-validating.
    """

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipe: Mapped[str] = mapped_column(String(50), nullable=False)
    brief: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
