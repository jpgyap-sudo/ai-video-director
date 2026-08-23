"""Application configuration and environment validation."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Environment = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    database_url: str = "postgresql+psycopg://avd:avd@localhost:5432/avd"

    redis_url: str = "redis://localhost:6379/0"

    storage_backend: Literal["s3", "local"] = "s3"
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "avd-assets"
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True
    local_storage_root: str = "data/storage"

    auth_issuer: str = "http://localhost:8000/auth"
    auth_audience: str = "ai-video-director"
    auth_jwks_url: str = "http://localhost:8000/.well-known/jwks.json"
    auth_algorithm: str = "RS256"

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def validate_for_environment(self) -> None:
        """Raise if required configuration is missing for the active environment."""
        if self.environment == "production":
            if self.storage_backend == "local":
                raise ValueError("STORAGE_BACKEND=local is not allowed in production")
            if not self.s3_access_key or not self.s3_secret_key:
                raise ValueError("S3 credentials are required in production")
            if self.auth_jwks_url.startswith("http://localhost"):
                raise ValueError("AUTH_JWKS_URL must point to a real issuer in production")
        if self.storage_backend == "s3" and not self.s3_endpoint_url:
            raise ValueError("S3_ENDPOINT_URL is required when STORAGE_BACKEND=s3")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_for_environment()
    return settings
