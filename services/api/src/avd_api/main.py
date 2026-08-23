"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from avd_api.auth import Principal, TestIdentityProvider, get_principal, set_jwks_override
from avd_api.authorization import (
    require_org_principal,
    require_organization,
    require_project_in_organization,
)
from avd_api.config import get_settings
from avd_api.db import get_db
from avd_api.models import Membership, Organization, Project, User
from avd_api.problems import problem_response, register_problem_handlers
from avd_api.storage import ObjectStorage, build_storage

settings = get_settings()

app = FastAPI(
    title="AI Video Director API",
    version="0.1.0",
    openapi_url="/openapi.json",
)

register_problem_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_identity_provider = TestIdentityProvider(settings)
# Only the local/test identity provider is used outside production. In
# production the verifier must fetch the real issuer's JWKS from AUTH_JWKS_URL.
if settings.environment != "production":
    set_jwks_override(_identity_provider.jwks)

_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    """FastAPI dependency exposing the configured object-storage backend.

    Constructed lazily on first call so importing the app (e.g. to export the
    OpenAPI schema) never touches S3 or performs a network round-trip.
    """
    global _storage
    if _storage is None:
        _storage = build_storage(settings)
    return _storage


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    try:
        storage.check()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage backend unreachable",
        ) from exc
    return {"status": "ready"}


@app.get("/.well-known/jwks.json")
def jwks() -> dict[str, object]:
    return _identity_provider.jwks


@app.get(
    "/v1/projects/{project_id}",
    responses={
        401: problem_response(401),
        403: problem_response(403),
        404: problem_response(404),
    },
)
def get_project(
    project_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    organization_id = require_org_principal(principal, db)
    project = require_project_in_organization(
        principal, db, project_id, organization_id
    )
    return {"id": project.id, "name": project.name, "organization_id": project.organization_id}


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@app.post(
    "/v1/projects",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: problem_response(401),
        403: problem_response(403),
        409: problem_response(409),
        422: problem_response(422),
    },
)
def create_project(
    body: CreateProjectRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    organization_id = require_org_principal(principal, db)
    # Verify the principal is a member of the resolved organization before
    # creating a project inside it.
    require_organization(principal, db, organization_id)
    project = Project(organization_id=organization_id, name=body.name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "organization_id": project.organization_id}


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@app.post(
    "/v1/organizations",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: problem_response(401),
        409: problem_response(409),
        422: problem_response(422),
    },
)
def create_organization(
    body: CreateOrganizationRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Bootstrap path: create an organization and make the caller a member.

    The caller must not already belong to an organization (by claim or by
    membership), or the request is rejected (an identity belongs to one org at
    a time in Phase 1).
    """
    existing = db.scalar(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(User.subject == principal.subject)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Identity already belongs to an organization",
        )
    org = Organization(name=body.name)
    db.add(org)
    db.flush()
    user = db.scalar(select(User).where(User.subject == principal.subject))
    if user is None:
        user = User(subject=principal.subject, email=principal.email)
        db.add(user)
        db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(org)
    return {"id": org.id, "name": org.name}
