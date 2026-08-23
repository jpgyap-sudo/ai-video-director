"""Object-storage abstraction.

Production uses S3/MinIO. A local filesystem backend is allowed only in tests
and local development, never as the default in production.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import boto3  # type: ignore[import-untyped]
from botocore.client import Config  # type: ignore[import-untyped]

from avd_api.config import Settings


class ObjectStorage(ABC):
    """Minimal object-storage contract used across the codebase."""

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str | None = None) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def size(self, key: str) -> int:
        """Return the object size in bytes without reading its body."""

    @abstractmethod
    def read_head(self, key: str, n: int) -> bytes:
        """Return the first n bytes of the object without reading the rest."""

    @abstractmethod
    def checksum_sha256(self, key: str) -> str:
        """Stream the object and return its SHA-256 hex digest."""

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def presigned_url(self, key: str, expires_in: int = 3600) -> str: ...

    @abstractmethod
    def presigned_upload_url(self, key: str, content_type: str, expires_in: int = 3600) -> str:
        """Return a URL the client can PUT the object to directly."""

    @abstractmethod
    def check(self) -> None:
        """Cheap liveness probe; raises if the backend is unreachable."""


class S3Storage(ObjectStorage):
    def __init__(self, settings: Settings) -> None:
        if not settings.s3_endpoint_url:
            raise ValueError("S3_ENDPOINT_URL is required for S3 storage")
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": (
                        "path" if settings.s3_force_path_style else "virtual"
                    )
                },
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        kwargs = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        self._client.put_object(**kwargs)

    def get(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return bytes(resp["Body"].read())

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def size(self, key: str) -> int:
        resp = self._client.head_object(Bucket=self._bucket, Key=key)
        return int(resp["ContentLength"])

    def read_head(self, key: str, n: int) -> bytes:
        resp = self._client.get_object(
            Bucket=self._bucket, Key=key, Range=f"bytes=0-{n - 1}"
        )
        return bytes(resp["Body"].read())

    def checksum_sha256(self, key: str) -> str:
        import hashlib

        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        digest = hashlib.sha256()
        for chunk in resp["Body"].iter_chunks(chunk_size=1024 * 1024):
            digest.update(chunk)
        return digest.hexdigest()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        )

    def presigned_upload_url(self, key: str, content_type: str, expires_in: int = 3600) -> str:
        return str(
            self._client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
        )

    def check(self) -> None:
        self._client.head_bucket(Bucket=self._bucket)


class LocalStorage(ObjectStorage):
    """Filesystem backend for tests and local development only."""

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        root = self._root.resolve()
        if not path.is_relative_to(root):
            raise ValueError("object key escapes storage root")
        return path

    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def size(self, key: str) -> int:
        return self._path(key).stat().st_size

    def read_head(self, key: str, n: int) -> bytes:
        with self._path(key).open("rb") as f:
            return f.read(n)

    def checksum_sha256(self, key: str) -> str:
        import hashlib

        digest = hashlib.sha256()
        with self._path(key).open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return f"local://{key}"

    def presigned_upload_url(self, key: str, content_type: str, expires_in: int = 3600) -> str:
        return f"local://{key}?upload=1"

    def check(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)


def build_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_storage_root)
    return S3Storage(settings)
