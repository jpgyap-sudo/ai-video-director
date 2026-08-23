"""Configuration validation tests."""

from __future__ import annotations

import pytest

from avd_api.config import Settings


def test_defaults_are_sane() -> None:
    settings = Settings(
        environment="development", storage_backend="s3", _env_file=None
    )
    assert settings.environment == "development"
    assert settings.storage_backend == "s3"
    assert settings.api_cors_origins == ["http://localhost:3000"]


def test_cors_origins_split_from_csv() -> None:
    settings = Settings(api_cors_origins="http://a,http://b")
    assert settings.api_cors_origins == ["http://a", "http://b"]


def test_production_requires_s3_credentials() -> None:
    with pytest.raises(ValueError):
        Settings(
            environment="production",
            s3_access_key=None,
            s3_secret_key=None,
            auth_jwks_url="http://localhost:8000/.well-known/jwks.json",
        ).validate_for_environment()


def test_production_rejects_localhost_jwks() -> None:
    with pytest.raises(ValueError):
        Settings(
            environment="production",
            s3_access_key="k",
            s3_secret_key="s",
            auth_jwks_url="http://localhost:8000/.well-known/jwks.json",
        ).validate_for_environment()


def test_production_forbids_local_storage() -> None:
    with pytest.raises(ValueError):
        Settings(
            environment="production",
            storage_backend="local",
            s3_access_key="k",
            s3_secret_key="s",
            auth_jwks_url="https://issuer.example.com/.well-known/jwks.json",
        ).validate_for_environment()


def test_s3_backend_requires_endpoint() -> None:
    with pytest.raises(ValueError):
        Settings(storage_backend="s3", s3_endpoint_url=None).validate_for_environment()


def test_local_backend_does_not_require_endpoint() -> None:
    settings = Settings(storage_backend="local", s3_endpoint_url=None)
    settings.validate_for_environment()
