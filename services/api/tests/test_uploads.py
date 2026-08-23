"""Upload intent and asset completion tests."""

from __future__ import annotations

from avd_api.media import sha256_hex, sniff_content_type
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
    return org, user, product


def _upload_png(client, headers, product, object_key, data):
    intent = client.post(
        "/v1/assets/upload-intents",
        json={"product_id": product.id, "content_type": "image/png", "size_bytes": len(data)},
        headers=headers,
    ).json()
    from avd_api.main import get_storage

    get_storage().put(intent["object_key"], data, content_type="image/png")
    return intent


def test_sniff_rejects_wav_and_avi() -> None:
    wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 20
    avi = b"RIFF" + b"\x00" * 4 + b"AVI " + b"\x00" * 20
    assert sniff_content_type(wav) is None
    assert sniff_content_type(avi) is None


def test_sniff_accepts_webp() -> None:
    webp = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 20
    assert sniff_content_type(webp) == "image/webp"


def test_sniff_accepts_mp4_with_0x1c_box() -> None:
    mp4 = b"\x00\x00\x00\x1cftyp" + b"isom" + b"\x00" * 20
    assert sniff_content_type(mp4) == "video/mp4"


def test_sniff_classifies_mov_as_quicktime() -> None:
    mov = b"\x00\x00\x00\x18ftypqt  " + b"\x00" * 20
    assert sniff_content_type(mov) == "video/quicktime"


def test_complete_asset_is_idempotent(client, auth_headers, db_session) -> None:
    org, user, product = _seed_product(db_session, "up-owner-8", "Org A", "Project A", "SKU-8")
    headers = auth_headers("up-owner-8", org.id)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    intent = _upload_png(client, headers, product, None, png)
    first = client.post(
        f"/v1/assets/{intent['asset_id']}/complete",
        json={"checksum": sha256_hex(png)},
        headers=headers,
    )
    assert first.status_code == 200
    second = client.post(
        f"/v1/assets/{intent['asset_id']}/complete",
        json={"checksum": sha256_hex(png)},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json() == first.json()


def test_complete_asset_rejects_oversized_object(client, auth_headers, db_session) -> None:
    org, user, product = _seed_product(db_session, "up-owner-9", "Org A", "Project A", "SKU-9")
    headers = auth_headers("up-owner-9", org.id)
    # Declare a small size but upload an oversized object.
    intent = client.post(
        "/v1/assets/upload-intents",
        json={"product_id": product.id, "content_type": "image/png", "size_bytes": 100},
        headers=headers,
    ).json()
    from avd_api.main import MAX_ASSET_BYTES, get_storage

    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_ASSET_BYTES + 1)
    get_storage().put(intent["object_key"], big, content_type="image/png")
    res = client.post(
        f"/v1/assets/{intent['asset_id']}/complete",
        json={"checksum": sha256_hex(big)},
        headers=headers,
    )
    assert res.status_code == 422


def test_upload_intent_creates_asset(client, auth_headers, db_session) -> None:
    org, user, product = _seed_product(db_session, "up-owner-1", "Org A", "Project A", "SKU-1")
    headers = auth_headers("up-owner-1", org.id)
    res = client.post(
        "/v1/assets/upload-intents",
        json={"product_id": product.id, "content_type": "image/png", "size_bytes": 100},
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["asset_id"]
    assert body["upload_url"]
    assert body["object_key"].startswith(f"org/{org.id}/products/{product.id}/assets/")


def test_upload_intent_rejects_unsupported_type(client, auth_headers, db_session) -> None:
    org, user, product = _seed_product(db_session, "up-owner-2", "Org A", "Project A", "SKU-2")
    headers = auth_headers("up-owner-2", org.id)
    res = client.post(
        "/v1/assets/upload-intents",
        json={
            "product_id": product.id,
            "content_type": "application/x-msdownload",
            "size_bytes": 100,
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")


def test_upload_intent_cross_org_product_404(client, auth_headers, db_session) -> None:
    org_a, _, _ = _seed_product(db_session, "up-a-3", "Org A", "Project A", "SKU-3")
    org_b, _, product_b = _seed_product(db_session, "up-b-3", "Org B", "Project B", "SKU-4")
    headers = auth_headers("up-a-3", org_a.id)
    res = client.post(
        "/v1/assets/upload-intents",
        json={"product_id": product_b.id, "content_type": "image/png", "size_bytes": 100},
        headers=headers,
    )
    assert res.status_code == 404


def test_complete_asset_validates_and_finalizes(client, auth_headers, db_session) -> None:
    org, user, product = _seed_product(db_session, "up-owner-5", "Org A", "Project A", "SKU-5")
    headers = auth_headers("up-owner-5", org.id)
    intent = client.post(
        "/v1/assets/upload-intents",
        json={"product_id": product.id, "content_type": "image/png", "size_bytes": 100},
        headers=headers,
    ).json()
    asset_id = intent["asset_id"]
    # Simulate the client uploading the object to local storage.
    from avd_api.main import get_storage

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    get_storage().put(intent["object_key"], png, content_type="image/png")
    res = client.post(
        f"/v1/assets/{asset_id}/complete",
        json={"checksum": sha256_hex(png)},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "VALIDATED"
    assert body["checksum"] == sha256_hex(png)
    assert body["size_bytes"] == len(png)


def test_complete_asset_rejects_checksum_mismatch(client, auth_headers, db_session) -> None:
    org, user, product = _seed_product(db_session, "up-owner-6", "Org A", "Project A", "SKU-6")
    headers = auth_headers("up-owner-6", org.id)
    intent = client.post(
        "/v1/assets/upload-intents",
        json={"product_id": product.id, "content_type": "image/png", "size_bytes": 100},
        headers=headers,
    ).json()
    from avd_api.main import get_storage

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    get_storage().put(intent["object_key"], png, content_type="image/png")
    res = client.post(
        f"/v1/assets/{intent['asset_id']}/complete",
        json={"checksum": "deadbeef"},
        headers=headers,
    )
    assert res.status_code == 422


def test_complete_asset_rejects_wrong_content(client, auth_headers, db_session) -> None:
    org, user, product = _seed_product(db_session, "up-owner-7", "Org A", "Project A", "SKU-7")
    headers = auth_headers("up-owner-7", org.id)
    intent = client.post(
        "/v1/assets/upload-intents",
        json={"product_id": product.id, "content_type": "image/png", "size_bytes": 100},
        headers=headers,
    ).json()
    from avd_api.main import get_storage

    # Upload a JPEG where PNG was declared.
    jpeg = b"\xff\xd8\xff" + b"\x00" * 100
    get_storage().put(intent["object_key"], jpeg, content_type="image/jpeg")
    res = client.post(
        f"/v1/assets/{intent['asset_id']}/complete",
        json={"checksum": sha256_hex(jpeg)},
        headers=headers,
    )
    assert res.status_code == 422
