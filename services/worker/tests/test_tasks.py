"""Worker tests."""

from avd_worker.tasks import health


def test_health_task() -> None:
    result = health()
    assert result == {"status": "ok", "worker": "avd_worker"}
