"""Product and version tests."""

from __future__ import annotations

from avd_api.models import Membership, Organization, Product, Project, User


def _seed_tenant(db_session, subject: str, org_name: str, project_name: str):
    org = Organization(name=org_name)
    user = User(subject=subject, email=f"{subject}@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    project = Project(organization_id=org.id, name=project_name)
    db_session.add(project)
    db_session.commit()
    return org, user, project


def test_create_product_succeeds_for_member(client, auth_headers, db_session) -> None:
    org, user, project = _seed_tenant(db_session, "prod-owner-1", "Org A", "Project A")
    headers = auth_headers("prod-owner-1", org.id)
    res = client.post(
        "/v1/products",
        json={"project_id": project.id, "sku": "SKU-1", "name": "Sofa"},
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["organization_id"] == org.id
    assert body["project_id"] == project.id
    assert body["sku"] == "SKU-1"
    assert body["name"] == "Sofa"
    assert body["version"] == 1


def test_create_product_requires_membership(client, auth_headers, db_session) -> None:
    org, user, project = _seed_tenant(db_session, "prod-owner-2", "Org A", "Project A")
    headers = auth_headers("prod-intruder-2", org.id)
    res = client.post(
        "/v1/products",
        json={"project_id": project.id, "sku": "SKU-1", "name": "Sofa"},
        headers=headers,
    )
    assert res.status_code == 403
    assert res.headers["content-type"].startswith("application/problem+json")


def test_create_product_cross_org_project_404(client, auth_headers, db_session) -> None:
    org_a, _, _ = _seed_tenant(db_session, "user-a-3", "Org A", "Project A")
    org_b, _, project_b = _seed_tenant(db_session, "user-b-3", "Org B", "Project B")
    # user-a is a member of Org A; creating a product in Org B's project 404s.
    headers = auth_headers("user-a-3", org_a.id)
    res = client.post(
        "/v1/products",
        json={"project_id": project_b.id, "sku": "SKU-1", "name": "Sofa"},
        headers=headers,
    )
    assert res.status_code == 404


def test_project_has_version_field(db_session) -> None:
    org, user, project = _seed_tenant(db_session, "ver-owner-4", "Org A", "Project A")
    assert project.version == 1


def test_product_has_version_field(db_session) -> None:
    org, user, project = _seed_tenant(db_session, "ver-owner-5", "Org A", "Project A")
    product = Product(
        organization_id=org.id, project_id=project.id, sku="SKU-1", name="Sofa"
    )
    db_session.add(product)
    db_session.commit()
    assert product.version == 1
