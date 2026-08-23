"""RFC 9457 problem-details and org bootstrap tests."""

from __future__ import annotations

from avd_api.models import Membership, Organization, User


def test_http_exception_returns_problem_json(client, auth_headers) -> None:
    headers = auth_headers("user-1", "org-1")
    res = client.get("/v1/projects/does-not-exist", headers=headers)
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["type"] == "urn:avd:problem:not-found"
    assert body["title"] == "Not found"
    assert body["status"] == 404
    assert "detail" in body


def test_validation_error_returns_problem_json(client, auth_headers, db_session) -> None:
    org = Organization(name="Org A")
    user = User(subject="val-user", email="val-user@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db_session.commit()
    headers = auth_headers("val-user", org.id)
    # Empty name fails min_length validation.
    res = client.post("/v1/projects", json={"name": ""}, headers=headers)
    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["type"] == "urn:avd:problem:validation-error"
    assert body["status"] == 422
    assert "errors" in body
    assert body["errors"][0]["loc"] == ["body", "name"]


def test_create_organization_bootstraps_membership(client, auth_headers, db_session) -> None:
    headers = auth_headers("bootstrap-user", None)
    res = client.post("/v1/organizations", json={"name": "Acme"}, headers=headers)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Acme"
    org_id = body["id"]
    # The caller is now a member and can create a project.
    member_headers = auth_headers("bootstrap-user", org_id)
    proj = client.post("/v1/projects", json={"name": "Campaign 1"}, headers=member_headers)
    assert proj.status_code == 201
    assert proj.json()["organization_id"] == org_id


def test_create_organization_rejects_existing_org_claim(client, auth_headers, db_session) -> None:
    org = Organization(name="Org A")
    user = User(subject="conflict-user", email="conflict-user@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db_session.commit()
    headers = auth_headers("conflict-user", org.id)
    res = client.post("/v1/organizations", json={"name": "Another"}, headers=headers)
    assert res.status_code == 409
    assert res.headers["content-type"].startswith("application/problem+json")


def test_create_project_requires_membership(client, auth_headers, db_session) -> None:
    org = Organization(name="Org A")
    user = User(subject="proj-owner", email="proj-owner@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db_session.commit()
    # A non-member with the same org claim is rejected.
    headers = auth_headers("proj-intruder", org.id)
    res = client.post("/v1/projects", json={"name": "Sneaky"}, headers=headers)
    assert res.status_code == 403
    assert res.headers["content-type"].startswith("application/problem+json")


def test_org_resolved_from_membership_when_token_has_no_claim(
    client, auth_headers, db_session
) -> None:
    # A real OIDC token carries no org claim. The org must be resolved from
    # the principal's single membership.
    org = Organization(name="Org A")
    user = User(subject="no-claim-user", email="no-claim-user@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db_session.commit()
    headers = auth_headers("no-claim-user", None)  # no org claim
    res = client.post("/v1/projects", json={"name": "Resolved"}, headers=headers)
    assert res.status_code == 201
    assert res.json()["organization_id"] == org.id


def test_org_resolution_requires_membership(client, auth_headers, db_session) -> None:
    # No membership at all -> 403.
    headers = auth_headers("no-membership-user", None)
    res = client.post("/v1/projects", json={"name": "Nope"}, headers=headers)
    assert res.status_code == 403
    assert res.headers["content-type"].startswith("application/problem+json")
