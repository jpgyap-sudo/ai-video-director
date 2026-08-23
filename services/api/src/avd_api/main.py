"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from avd_api.auth import Principal, TestIdentityProvider, get_principal, set_jwks_override
from avd_api.authorization import require_project_in_organization
from avd_api.config import get_settings
from avd_api.db import get_db
from avd_api.storage import ObjectStorage, build_storage

settings = get_settings()

app = FastAPI(
    title="AI Video Director API",
    version="0.1.0",
    openapi_url="/openapi.json",
)

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


@app.get("/v1/projects/{project_id}")
def get_project(
    project_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if principal.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token has no organization claim",
        )
    project = require_project_in_organization(
        principal, db, project_id, principal.organization_id
    )
    return {"id": project.id, "name": project.name, "organization_id": project.organization_id}
