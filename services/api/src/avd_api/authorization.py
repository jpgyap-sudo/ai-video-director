"""Centralized authorization and membership checks.

Every tenant-owned resource must be scoped through these helpers. The
organization ID is always derived from the authenticated principal, never from
browser-supplied input.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from avd_api.auth import Principal, get_principal
from avd_api.db import get_db
from avd_api.models import Membership, Organization, Project, User


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
