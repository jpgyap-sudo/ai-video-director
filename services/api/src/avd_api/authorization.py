"""Centralized authorization and membership checks.

Every tenant-owned resource must be scoped through these helpers. The
organization ID is always derived from the authenticated principal, never from
browser-supplied input.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from avd_api.auth import Principal, get_principal
from avd_api.db import get_db
from avd_api.models import (
    Membership,
    Organization,
    Project,
    ReferenceMedia,
    ReferenceRightsAttestation,
    User,
)


def resolve_organization_id(principal: Principal, db: Session) -> str:
    """Return the organization the principal acts within.

    The token's `org` claim is an optimization, not the source of truth. When
    the claim is absent, resolve the organization from the principal's
    memberships: a single membership is used directly; multiple memberships
    require explicit selection (not yet supported); none is a 403.
    """
    if principal.organization_id is not None:
        return principal.organization_id
    org_ids = db.scalars(
        select(Membership.organization_id)
        .join(User, User.id == Membership.user_id)
        .where(User.subject == principal.subject)
    ).all()
    if not org_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity has no organization membership",
        )
    if len(org_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Identity belongs to multiple organizations; select one",
        )
    return org_ids[0]


def require_org_principal(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> str:
    """FastAPI dependency: resolve and return the acting organization ID."""
    return resolve_organization_id(principal, db)


def require_organization(
    principal: Principal, db: Session, organization_id: str
) -> Organization:
    """Return the organization if the principal is a member, else 403/404.

    The token's org claim is an optimization. When the claim is present it must
    match the requested organization; when absent, membership is the source of
    truth (the org was already resolved from memberships).
    """
    if principal.organization_id is not None and principal.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    org = db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    # principal.subject is the OIDC sub claim, which lives on users.subject.
    # user_id is a FK to users.id, so we must join through User.
    membership = db.scalar(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.organization_id == organization_id,
            User.subject == principal.subject,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    return org


def require_project_in_organization(
    principal: Principal, db: Session, project_id: str, organization_id: str
) -> Project:
    """Return a project only if it belongs to the principal's organization."""
    require_organization(principal, db, organization_id)
    project = db.get(Project, project_id)
    if project is None or project.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def require_cleared_references(
    principal: Principal, db: Session, project_id: str, organization_id: str
) -> list[ReferenceMedia]:
    """Return the project's references only if their rights are cleared.

    A reference is cleared when it has at least one rights attestation, its
    license metadata has not drifted from the latest attestation, and its
    license has not expired. Expired, unattested, or drifted references block
    submission.

    Expiry is checked against UTC now at submission time only; a job that was
    valid at submission is not retroactively killed if it expires mid-run.
    """
    require_project_in_organization(principal, db, project_id, organization_id)
    references = list(
        db.scalars(
            select(ReferenceMedia).where(
                ReferenceMedia.organization_id == organization_id,
                ReferenceMedia.project_id == project_id,
            )
        ).all()
    )
    if not references:
        return references
    ref_ids = [ref.id for ref in references]
    # Single IN query for all attestations (avoids N+1), tenant-scoped.
    attestations = db.scalars(
        select(ReferenceRightsAttestation).where(
            ReferenceRightsAttestation.organization_id == organization_id,
            ReferenceRightsAttestation.reference_id.in_(ref_ids),
        )
    ).all()
    latest_by_ref: dict[str, ReferenceRightsAttestation] = {}
    for att in attestations:
        current = latest_by_ref.get(att.reference_id)
        if current is None or att.attested_at > current.attested_at:
            latest_by_ref[att.reference_id] = att

    now = datetime.now(UTC)
    for ref in references:
        attested = latest_by_ref.get(ref.id)
        if attested is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Reference {ref.id} has no rights attestation",
            )
        # Normalize both expiries to aware UTC before comparing: SQLite returns
        # the reference expiry as aware but the attestation snapshot as naive.
        ref_expiry = _as_utc(ref.expiry)
        claimed_expiry = _as_utc(attested.claimed_expiry)
        # Drift detection: if the current license metadata no longer matches
        # the latest attestation snapshot, the license changed without
        # re-attestation. Treat it as unattested and block.
        if (
            ref.ownership != attested.claimed_ownership
            or ref.license_type != attested.claimed_license_type
            or ref_expiry != claimed_expiry
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Reference {ref.id} license metadata drifted since attestation",
            )
        # Expiry: clear against the stricter of the two (they match after the
        # drift check, but guard against a naive/aware mismatch).
        if ref_expiry is not None and ref_expiry <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Reference {ref.id} rights have expired",
            )
    return references


def _as_utc(value: datetime | None) -> datetime | None:
    """Return the datetime normalized to aware UTC (SQLite returns naive)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
