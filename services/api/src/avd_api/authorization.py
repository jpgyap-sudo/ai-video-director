"""Centralized authorization and membership checks.

Every tenant-owned resource must be scoped through these helpers. The
organization ID is always derived from the authenticated principal, never from
browser-supplied input.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from avd_api.auth import Principal
from avd_api.models import Membership, Organization, Project, User


def require_organization(
    principal: Principal, db: Session, organization_id: str
) -> Organization:
    """Return the organization if the principal is a member, else 403/404."""
    if principal.organization_id != organization_id:
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
