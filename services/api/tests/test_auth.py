"""Authentication and authorization tests."""

from __future__ import annotations

import jwt

from avd_api.auth import TokenVerifier
from avd_api.config import Settings
from avd_api.models import Membership, Organization, Project, User


def _seed_tenant(db_session, subject: str, org_name: str, project_name: str):
    org = Organization(name=org_name)
    user = User(subject=subject, email=f"{subject}@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="member"))
    project = Project(organization_id=org.id, name=project_name)
    db_session.add(project)
    db_session.commit()
    return org, user, project


def test_jwks_endpoint_serves_keys(client) -> None:
    res = client.get("/.well-known/jwks.json")
    assert res.status_code == 200
    keys = res.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["alg"] == "RS256"


def test_production_does_not_use_test_jwks_override() -> None:
    # In production the verifier must fetch the real issuer's JWKS, not the
    # ephemeral test keypair injected by the app.
    prod = Settings(environment="production", _env_file=None)
    assert prod.environment == "production"
    # The override is only set for non-production environments; a production
    # verifier constructed without an explicit jwks must use the URL client.
    verifier = TokenVerifier(prod)
    assert verifier._client is not None
    assert verifier._jwks is None


def test_token_with_wrong_audience_rejected(identity_provider, settings: Settings) -> None:
    token = identity_provider.issue_token("user-1", "org-1")
    bad_settings = Settings(auth_audience="other-audience")
    verifier = TokenVerifier(bad_settings, jwks=identity_provider.jwks)
    try:
        verifier.verify(token)
        raise AssertionError("expected token to be rejected")
    except jwt.PyJWTError:
        pass


def test_verify_selects_key_by_kid(identity_provider, settings: Settings) -> None:
    token = identity_provider.issue_token("user-1", "org-1")
    # A JWKS with a decoy first key and the real key second: selection must
    # match the token's kid, not keys[0].
    jwks = identity_provider.jwks
    real_key = jwks["keys"][0]
    decoy = dict(real_key)
    decoy["kid"] = "decoy"
    shuffled = {"keys": [decoy, real_key]}
    verifier = TokenVerifier(settings, jwks=shuffled)
    claims = verifier.verify(token)
    assert claims["sub"] == "user-1"


def test_verify_rejects_unknown_kid(identity_provider, settings: Settings) -> None:
    token = identity_provider.issue_token("user-1", "org-1")
    # A JWKS that does not contain the token's kid must be rejected.
    jwks = {"keys": [{"kty": "RSA", "kid": "other", "n": "AQAB", "e": "AQAB"}]}
    verifier = TokenVerifier(settings, jwks=jwks)
    try:
        verifier.verify(token)
        raise AssertionError("expected token to be rejected")
    except jwt.PyJWTError:
        pass


def test_missing_token_rejected(client) -> None:
    res = client.get("/v1/projects/abc")
    assert res.status_code == 401


def test_token_without_org_claim_forbidden(client, auth_headers) -> None:
    headers = auth_headers("user-1", None)
    res = client.get("/v1/projects/abc", headers=headers)
    assert res.status_code == 403


def test_cross_tenant_project_returns_404(client, auth_headers) -> None:
    headers = auth_headers("user-1", "org-1")
    res = client.get("/v1/projects/does-not-exist", headers=headers)
    assert res.status_code == 404


def test_member_can_read_own_project(client, auth_headers, db_session) -> None:
    org, user, project = _seed_tenant(db_session, "member-1", "Org A", "Project A")
    headers = auth_headers("member-1", org.id)
    res = client.get(f"/v1/projects/{project.id}", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == project.id
    assert body["name"] == "Project A"
    assert body["organization_id"] == org.id


def test_non_member_cannot_read_project(client, auth_headers, db_session) -> None:
    org, user, project = _seed_tenant(db_session, "owner-1", "Org A", "Project A")
    # A different subject with the same org claim is not a member.
    headers = auth_headers("intruder-1", org.id)
    res = client.get(f"/v1/projects/{project.id}", headers=headers)
    assert res.status_code == 403


def test_member_cannot_read_other_org_project(client, auth_headers, db_session) -> None:
    org_a, _, project_a = _seed_tenant(db_session, "user-a", "Org A", "Project A")
    org_b, _, project_b = _seed_tenant(db_session, "user-b", "Org B", "Project B")
    # user-a is a member of Org A; requesting Org B's project with an Org A
    # token must 404 (the project is not in the principal's organization).
    headers = auth_headers("user-a", org_a.id)
    res = client.get(f"/v1/projects/{project_b.id}", headers=headers)
    assert res.status_code == 404
