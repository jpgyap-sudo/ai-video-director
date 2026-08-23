"""FastAPI application entrypoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from avd_api.antivirus import AntivirusScanner, NoopAntivirusScanner
from avd_api.auth import Principal, TestIdentityProvider, get_principal, set_jwks_override
from avd_api.authorization import (
    require_org_principal,
    require_organization,
    require_project_in_organization,
)
from avd_api.config import get_settings
from avd_api.db import get_db
from avd_api.media import ALLOWED_CONTENT_TYPES, SNIFF_HEAD_SIZE, sniff_content_type
from avd_api.models import (
    Membership,
    Organization,
    Product,
    ProductAsset,
    Project,
    ReferenceMedia,
    ReferenceRightsAttestation,
    User,
    uuid7,
)
from avd_api.problems import problem_response, register_problem_handlers
from avd_api.storage import ObjectStorage, build_storage

settings = get_settings()

# Maximum accepted asset size (100 MiB), enforced against the actual object.
MAX_ASSET_BYTES = 100 * 1024 * 1024

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
_antivirus: AntivirusScanner | None = None


def get_storage() -> ObjectStorage:
    """FastAPI dependency exposing the configured object-storage backend.

    Constructed lazily on first call so importing the app (e.g. to export the
    OpenAPI schema) never touches S3 or performs a network round-trip.
    """
    global _storage
    if _storage is None:
        _storage = build_storage(settings)
    return _storage


def get_antivirus() -> AntivirusScanner:
    """FastAPI dependency exposing the antivirus scanner (no-op in Phase 1)."""
    global _antivirus
    if _antivirus is None:
        _antivirus = NoopAntivirusScanner()
    return _antivirus


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
        422: problem_response(422),
    },
)
def get_project(
    project_id: str,
    organization_id: str = Depends(require_org_principal),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
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
    organization_id: str = Depends(require_org_principal),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
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


class CreateProductRequest(BaseModel):
    project_id: str = Field(min_length=1)
    sku: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)


@app.post(
    "/v1/products",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: problem_response(401),
        403: problem_response(403),
        404: problem_response(404),
        422: problem_response(422),
    },
)
def create_product(
    body: CreateProductRequest,
    organization_id: str = Depends(require_org_principal),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    # The project must belong to the resolved organization.
    project = require_project_in_organization(
        principal, db, body.project_id, organization_id
    )
    product = Product(
        organization_id=organization_id,
        project_id=project.id,
        sku=body.sku,
        name=body.name,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {
        "id": product.id,
        "organization_id": product.organization_id,
        "project_id": product.project_id,
        "sku": product.sku,
        "name": product.name,
        "version": product.version,
    }


class CreateUploadIntentRequest(BaseModel):
    product_id: str = Field(min_length=1)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0, le=100 * 1024 * 1024)


@app.post(
    "/v1/assets/upload-intents",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: problem_response(401),
        403: problem_response(403),
        404: problem_response(404),
        422: problem_response(422),
    },
)
def create_upload_intent(
    body: CreateUploadIntentRequest,
    organization_id: str = Depends(require_org_principal),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
) -> dict[str, str]:
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported content type: {body.content_type}",
        )
    product = db.get(Product, body.product_id)
    if product is None or product.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    asset_id = uuid7()
    object_key = f"org/{organization_id}/products/{product.id}/assets/{asset_id}"
    upload_url = storage.presigned_upload_url(object_key, body.content_type)
    asset = ProductAsset(
        id=asset_id,
        organization_id=organization_id,
        product_id=product.id,
        object_key=object_key,
        content_type=body.content_type,
        checksum="",  # set on complete
        size_bytes=body.size_bytes,
        status="QUARANTINED",
    )
    db.add(asset)
    db.commit()
    return {
        "asset_id": asset.id,
        "upload_url": upload_url,
        "object_key": object_key,
    }


class CompleteAssetRequest(BaseModel):
    checksum: str = Field(min_length=1, max_length=128)


@app.post(
    "/v1/assets/{asset_id}/complete",
    status_code=status.HTTP_200_OK,
    responses={
        401: problem_response(401),
        403: problem_response(403),
        404: problem_response(404),
        409: problem_response(409),
        422: problem_response(422),
    },
)
def complete_asset(
    asset_id: str,
    body: CompleteAssetRequest,
    organization_id: str = Depends(require_org_principal),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    antivirus: AntivirusScanner = Depends(get_antivirus),
) -> dict[str, str | int]:
    asset = db.get(ProductAsset, asset_id)
    if asset is None or asset.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    # Idempotent: an already-validated asset returns its record unchanged.
    if asset.status == "VALIDATED":
        return {
            "id": asset.id,
            "status": asset.status,
            "checksum": asset.checksum,
            "size_bytes": asset.size_bytes,
        }
    if not storage.exists(asset.object_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Object not uploaded yet",
        )
    # Enforce the size limit against the actual object, not the client's claim.
    actual_size = storage.size(asset.object_key)
    if actual_size > MAX_ASSET_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Object exceeds the maximum allowed size",
        )
    # Sniff from a ranged read of the leading bytes only.
    head = storage.read_head(asset.object_key, SNIFF_HEAD_SIZE)
    sniffed = sniff_content_type(head)
    if sniffed is None or sniffed != asset.content_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Object content does not match declared content type",
        )
    # Malware scan before promoting to the private original.
    antivirus.scan(asset.object_key)
    # Streaming checksum; never loads the whole object into memory.
    actual_checksum = storage.checksum_sha256(asset.object_key)
    if actual_checksum != body.checksum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Checksum mismatch",
        )
    asset.checksum = actual_checksum
    asset.size_bytes = actual_size
    asset.status = "VALIDATED"
    db.commit()
    db.refresh(asset)
    return {
        "id": asset.id,
        "status": asset.status,
        "checksum": asset.checksum,
        "size_bytes": asset.size_bytes,
    }


class CreateReferenceRequest(BaseModel):
    project_id: str = Field(min_length=1)
    object_key: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=255)
    ownership: str = Field(min_length=1, max_length=50)
    license_type: str = Field(min_length=1, max_length=50)
    source: str | None = Field(default=None, max_length=255)
    permitted_channels: str | None = Field(default=None, max_length=1024)
    permitted_territories: str | None = Field(default=None, max_length=1024)
    expiry: datetime | None = None
    reviewer_notes: str | None = Field(default=None, max_length=2048)


@app.post(
    "/v1/references",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: problem_response(401),
        403: problem_response(403),
        404: problem_response(404),
        422: problem_response(422),
    },
)
def create_reference(
    body: CreateReferenceRequest,
    organization_id: str = Depends(require_org_principal),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    require_project_in_organization(principal, db, body.project_id, organization_id)
    ref = ReferenceMedia(
        organization_id=organization_id,
        project_id=body.project_id,
        object_key=body.object_key,
        content_type=body.content_type,
        ownership=body.ownership,
        license_type=body.license_type,
        source=body.source,
        permitted_channels=body.permitted_channels,
        permitted_territories=body.permitted_territories,
        expiry=body.expiry,
        reviewer_notes=body.reviewer_notes,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return {
        "id": ref.id,
        "organization_id": ref.organization_id,
        "project_id": ref.project_id,
        "ownership": ref.ownership,
        "license_type": ref.license_type,
    }


class CreateAttestationRequest(BaseModel):
    claimed_ownership: str = Field(min_length=1, max_length=50)
    claimed_license_type: str = Field(min_length=1, max_length=50)
    claimed_expiry: datetime | None = None


@app.post(
    "/v1/references/{reference_id}/attestations",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: problem_response(401),
        403: problem_response(403),
        404: problem_response(404),
        422: problem_response(422),
    },
)
def create_attestation(
    reference_id: str,
    body: CreateAttestationRequest,
    organization_id: str = Depends(require_org_principal),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ref = db.get(ReferenceMedia, reference_id)
    if ref is None or ref.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference not found",
        )
    attestation = ReferenceRightsAttestation(
        organization_id=organization_id,
        reference_id=ref.id,
        attested_by_subject=principal.subject,
        claimed_ownership=body.claimed_ownership,
        claimed_license_type=body.claimed_license_type,
        claimed_expiry=body.claimed_expiry,
    )
    db.add(attestation)
    db.commit()
    db.refresh(attestation)
    return {
        "id": attestation.id,
        "reference_id": attestation.reference_id,
        "attested_by_subject": attestation.attested_by_subject,
        "claimed_ownership": attestation.claimed_ownership,
        "claimed_license_type": attestation.claimed_license_type,
    }
