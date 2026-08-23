"""Shared test fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the package is importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("STORAGE_BACKEND", "local")
# CI sets DATABASE_URL to Postgres; local runs default to SQLite.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from avd_api.config import Settings, get_settings  # noqa: E402
from avd_api.db import Base, SessionLocal, engine  # noqa: E402
from avd_api.main import _identity_provider, app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    Path("test.db").unlink(missing_ok=True)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def identity_provider():
    return _identity_provider


@pytest.fixture
def auth_headers(identity_provider):
    def _make(subject: str, organization_id: str | None = None) -> dict[str, str]:
        token = identity_provider.issue_token(subject, organization_id)
        return {"Authorization": f"Bearer {token}"}

    return _make
