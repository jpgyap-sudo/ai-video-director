"""UUIDv7 generation tests."""

from __future__ import annotations

import time
import uuid

from avd_api.models import uuid7


def test_uuid7_is_valid_uuid() -> None:
    value = uuid7()
    parsed = uuid.UUID(value)
    assert parsed.version == 7
    assert parsed.variant == uuid.RFC_4122


def test_uuid7_is_time_ordered() -> None:
    first = uuid.UUID(uuid7())
    time.sleep(0.002)  # ensure a distinct millisecond timestamp
    second = uuid.UUID(uuid7())
    assert first < second


def test_uuid7_is_unique() -> None:
    values = {uuid7() for _ in range(1000)}
    assert len(values) == 1000
