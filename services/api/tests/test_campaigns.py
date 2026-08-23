"""Campaign tests."""

from __future__ import annotations

from avd_api.models import Membership, Organization, Product, Project, User


def _seed_product(db_session, subject: str, org_name: str, project_name: str, sku: str):
    org = Organization(name=org_name)
    user = User(subject=subject, email=f"{subject}@example.com")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    project = Project(organization_id=org.id, name=project_name)
    db_session.add(project)
    db_session.flush()
    product = Product(organization_id=org.id, project_id=project.id, sku=sku, name="Sofa")
    db_session.add(product)
    db_session.commit()
    return org, user, project, product


def test_create_campaign_succeeds(client, auth_headers, db_session) -> None:
    org, user, project, product = _seed_product(
        db_session, "camp-owner-1", "Org A", "Project A", "SKU-1"
    )
    headers = auth_headers("camp-owner-1", org.id)
    res = client.post(
        "/v1/campaigns",
        json={
            "project_id": project.id,
            "product_id": product.id,
            "name": "Summer Sale",
            "recipe": "product_ad",
        },
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Summer Sale"
    assert body["recipe"] == "product_ad"
    assert body["version"] == 1


def test_create_campaign_rejects_invalid_recipe(client, auth_headers, db_session) -> None:
    org, user, project, product = _seed_product(
        db_session, "camp-owner-2", "Org A", "Project A", "SKU-2"
    )
    headers = auth_headers("camp-owner-2", org.id)
    res = client.post(
        "/v1/campaigns",
        json={
            "project_id": project.id,
            "product_id": product.id,
            "name": "Bad",
            "recipe": "not_a_recipe",
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")


def test_create_campaign_cross_org_product_404(client, auth_headers, db_session) -> None:
    org_a, _, project_a, _ = _seed_product(
        db_session, "camp-a-3", "Org A", "Project A", "SKU-3"
    )
    org_b, _, _, product_b = _seed_product(
        db_session, "camp-b-3", "Org B", "Project B", "SKU-4"
    )
    headers = auth_headers("camp-a-3", org_a.id)
    res = client.post(
        "/v1/campaigns",
        json={
            "project_id": project_a.id,
            "product_id": product_b.id,
            "name": "Cross",
            "recipe": "product_ad",
        },
        headers=headers,
    )
    assert res.status_code == 404


def test_update_campaign_with_if_match(client, auth_headers, db_session) -> None:
    org, user, project, product = _seed_product(
        db_session, "camp-owner-4", "Org A", "Project A", "SKU-5"
    )
    headers = auth_headers("camp-owner-4", org.id)
    created = client.post(
        "/v1/campaigns",
        json={
            "project_id": project.id,
            "product_id": product.id,
            "name": "Campaign",
            "recipe": "product_ad",
        },
        headers=headers,
    ).json()
    res = client.patch(
        f"/v1/campaigns/{created['id']}",
        json={"name": "Renamed"},
        headers={**headers, "If-Match": "1"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Renamed"
    assert res.json()["version"] == 2


def test_update_campaign_requires_if_match(client, auth_headers, db_session) -> None:
    org, user, project, product = _seed_product(
        db_session, "camp-owner-5", "Org A", "Project A", "SKU-6"
    )
    headers = auth_headers("camp-owner-5", org.id)
    created = client.post(
        "/v1/campaigns",
        json={
            "project_id": project.id,
            "product_id": product.id,
            "name": "Campaign",
            "recipe": "product_ad",
        },
        headers=headers,
    ).json()
    res = client.patch(
        f"/v1/campaigns/{created['id']}",
        json={"name": "NoMatch"},
        headers=headers,
    )
    assert res.status_code == 412


def test_update_campaign_version_conflict(client, auth_headers, db_session) -> None:
    org, user, project, product = _seed_product(
        db_session, "camp-owner-6", "Org A", "Project A", "SKU-7"
    )
    headers = auth_headers("camp-owner-6", org.id)
    created = client.post(
        "/v1/campaigns",
        json={
            "project_id": project.id,
            "product_id": product.id,
            "name": "Campaign",
            "recipe": "product_ad",
        },
        headers=headers,
    ).json()
    res = client.patch(
        f"/v1/campaigns/{created['id']}",
        json={"name": "Stale"},
        headers={**headers, "If-Match": "99"},
    )
    assert res.status_code == 409
