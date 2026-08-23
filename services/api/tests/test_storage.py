"""Object-storage adapter tests."""

from __future__ import annotations

import pytest

from avd_api.config import Settings
from avd_api.storage import LocalStorage, build_storage


@pytest.fixture
def local_storage(tmp_path) -> LocalStorage:
    return LocalStorage(str(tmp_path / "storage"))


def test_put_get_roundtrip(local_storage) -> None:
    local_storage.put("org/1/a.txt", b"hello", content_type="text/plain")
    assert local_storage.get("org/1/a.txt") == b"hello"
    assert local_storage.exists("org/1/a.txt")


def test_delete(local_storage) -> None:
    local_storage.put("org/1/a.txt", b"x")
    local_storage.delete("org/1/a.txt")
    assert not local_storage.exists("org/1/a.txt")


def test_presigned_url(local_storage) -> None:
    assert local_storage.presigned_url("org/1/a.txt") == "local://org/1/a.txt"


def test_path_traversal_rejected(local_storage) -> None:
    with pytest.raises(ValueError):
        local_storage.put("../escape.txt", b"x")


def test_build_storage_local(tmp_path) -> None:
    settings = Settings(storage_backend="local", local_storage_root=str(tmp_path / "s"))
    storage = build_storage(settings)
    assert isinstance(storage, LocalStorage)
