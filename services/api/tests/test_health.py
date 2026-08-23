"""Health endpoint tests."""

from avd_api.main import get_storage
from avd_api.storage import LocalStorage


def test_health_live(client) -> None:
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_ready(client) -> None:
    res = client.get("/health/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready"}


def test_storage_dependency_is_wired() -> None:
    storage = get_storage()
    assert isinstance(storage, LocalStorage)


def test_storage_check_probe(client) -> None:
    storage = get_storage()
    storage.check()
    res = client.get("/health/ready")
    assert res.status_code == 200
