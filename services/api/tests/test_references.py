"""Reference rights guard tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from avd_api.auth import Principal
from avd_api.authorization import require_cleared_references
from avd_api.models import (
    Membership,
    Organization,
    Project,
    ReferenceMedia,
    ReferenceRightsAttestation,
    User,
)


def _seed_project(db_session, subject: str, org_name: str, project_name: str):
    org = Organization(name=org_name)
    user = User(subject=subject, email=f"{subject}@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    project = Project(organization_id=org.id, name=project_name)
    db_session.add(project)
    db_session.commit()
    return org, user, project


def _principal(subject: str, org_id: str) -> Principal:
    return Principal(subject=subject, email=None, organization_id=org_id, claims={})


def _add_reference(db_session, org, project, expiry=None):
    ref = ReferenceMedia(
        organization_id=org.id,
        project_id=project.id,
        object_key=f"org/{org.id}/refs/{project.id}/1",
        content_type="video/mp4",
        ownership="LICENSED",
        license_type="COMMERCIAL",
        expiry=expiry,
    )
    db_session.add(ref)
    db_session.commit()
    return ref


def test_cleared_reference_passes(db_session) -> None:
    org, user, project = _seed_project(db_session, "ref-owner-1", "Org A", "Project A")
    expiry = datetime.now(UTC) + timedelta(days=30)
    ref = _add_reference(db_session, org, project, expiry=expiry)
    db_session.add(
        ReferenceRightsAttestation(
            organization_id=org.id,
            reference_id=ref.id,
            attested_by_subject="ref-owner-1",
            claimed_ownership="LICENSED",
            claimed_license_type="COMMERCIAL",
            claimed_expiry=expiry,
        )
    )
    db_session.commit()
    result = require_cleared_references(
        _principal("ref-owner-1", org.id), db_session, project.id, org.id
    )
    assert len(result) == 1


def test_expired_reference_blocks(db_session) -> None:
    org, user, project = _seed_project(db_session, "ref-owner-2", "Ref A", "Project A")
    expiry = datetime.now(UTC) - timedelta(days=1)
    ref = _add_reference(db_session, org, project, expiry=expiry)
    db_session.add(
        ReferenceRightsAttestation(
            organization_id=org.id,
            reference_id=ref.id,
            attested_by_subject="ref-owner-2",
            claimed_ownership="LICENSED",
            claimed_license_type="COMMERCIAL",
            claimed_expiry=expiry,
        )
    )
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        require_cleared_references(
            _principal("ref-owner-2", org.id), db_session, project.id, org.id
        )
    assert exc.value.status_code == 409
    assert "expired" in exc.value.detail


def test_unattested_reference_blocks(db_session) -> None:
    org, user, project = _seed_project(db_session, "ref-owner-3", "Ref A", "Project A")
    _add_reference(
        db_session, org, project, expiry=datetime.now(UTC) + timedelta(days=30)
    )
    with pytest.raises(HTTPException) as exc:
        require_cleared_references(
            _principal("ref-owner-3", org.id), db_session, project.id, org.id
        )
    assert exc.value.status_code == 409
    assert "no rights attestation" in exc.value.detail


def test_no_references_passes(db_session) -> None:
    org, user, project = _seed_project(db_session, "ref-owner-4", "Ref A", "Project A")
    result = require_cleared_references(
        _principal("ref-owner-4", org.id), db_session, project.id, org.id
    )
    assert result == []


def test_drifted_license_blocks(db_session) -> None:
    org, user, project = _seed_project(db_session, "ref-owner-5", "Ref A", "Project A")
    ref = _add_reference(
        db_session, org, project, expiry=datetime.now(UTC) + timedelta(days=30)
    )
    db_session.add(
        ReferenceRightsAttestation(
            organization_id=org.id,
            reference_id=ref.id,
            attested_by_subject="ref-owner-5",
            claimed_ownership="LICENSED",
            claimed_license_type="COMMERCIAL",
            claimed_expiry=datetime.now(UTC) + timedelta(days=30),
        )
    )
    db_session.commit()
    # Drift: change the license type after attestation without re-attesting.
    ref.license_type = "EDITORIAL"
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        require_cleared_references(
            _principal("ref-owner-5", org.id), db_session, project.id, org.id
        )
    assert exc.value.status_code == 409
    assert "drifted" in exc.value.detail


def test_create_reference_endpoint(client, auth_headers, db_session) -> None:
    org, user, project = _seed_project(db_session, "ref-api-1", "Ref A", "Project A")
    headers = auth_headers("ref-api-1", org.id)
    res = client.post(
        "/v1/references",
        json={
            "project_id": project.id,
            "object_key": f"org/{org.id}/refs/1",
            "content_type": "video/mp4",
            "ownership": "LICENSED",
            "license_type": "COMMERCIAL",
        },
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["ownership"] == "LICENSED"
    assert body["license_type"] == "COMMERCIAL"


def test_create_attestation_endpoint(client, auth_headers, db_session) -> None:
    org, user, project = _seed_project(db_session, "ref-api-2", "Ref A", "Project A")
    headers = auth_headers("ref-api-2", org.id)
    ref = client.post(
        "/v1/references",
        json={
            "project_id": project.id,
            "object_key": f"org/{org.id}/refs/2",
            "content_type": "video/mp4",
            "ownership": "LICENSED",
            "license_type": "COMMERCIAL",
        },
        headers=headers,
    ).json()
    res = client.post(
        f"/v1/references/{ref['id']}/attestations",
        json={"claimed_ownership": "LICENSED", "claimed_license_type": "COMMERCIAL"},
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["attested_by_subject"] == "ref-api-2"
    assert body["claimed_ownership"] == "LICENSED"
