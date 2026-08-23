"""Authentication contract.

Phase 0 defines the contract: OIDC-compatible identity with issuer/audience/JWKS
validation, plus a deterministic local/test identity provider. No UI is built yet.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient

from avd_api.config import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    """Authenticated identity derived from a verified token."""

    subject: str
    email: str | None
    organization_id: str | None
    claims: dict[str, Any]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _generate_rsa_keypair() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def _build_jwks(public_pem: bytes) -> dict[str, Any]:
    public_key = serialization.load_pem_public_key(public_pem)
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise TypeError("expected RSA public key")
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-identity",
                "n": _b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
            }
        ]
    }


class TokenVerifier:
    """Validates issuer, audience, and signature against a JWKS source.

    The JWKS may be supplied directly (tests/test) or fetched from a URL
    (production OIDC issuer). The URL client is cached so it is not rebuilt
    (and does not re-fetch keys) on every request.
    """

    def __init__(self, settings: Settings, jwks: dict[str, Any] | None = None) -> None:
        self._settings = settings
        self._jwks = jwks
        self._client = None if jwks is not None else _get_jwks_client(settings)

    def verify(self, token: str) -> dict[str, Any]:
        if self._jwks is not None:
            signing_key = self._select_key(self._jwks, token)
        else:
            assert self._client is not None
            signing_key = self._client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[self._settings.auth_algorithm],
            audience=self._settings.auth_audience,
            issuer=self._settings.auth_issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        return dict(claims)

    @staticmethod
    def _select_key(jwks: dict[str, Any], token: str) -> jwt.PyJWK:
        """Select the JWK matching the token's `kid` header.

        Falls back to the sole key when the token carries no `kid` (common for
        locally issued tokens) and there is exactly one key.
        """
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        keys = jwks.get("keys", [])
        if kid:
            for key in keys:
                if key.get("kid") == kid:
                    return jwt.PyJWK(key)
            raise jwt.InvalidKeyError(f"No JWKS key matches kid={kid!r}")
        if len(keys) == 1:
            return jwt.PyJWK(keys[0])
        raise jwt.InvalidKeyError("Token has no kid and JWKS has multiple keys")


class TestIdentityProvider:
    """Deterministic local/test identity provider.

    Issues RS256-signed tokens using a fixed key pair so tests and local
    development can exercise the full verification path without an external IdP.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._private_pem, self._public_pem = _generate_rsa_keypair()
        self._jwks = _build_jwks(self._public_pem)

    @property
    def jwks(self) -> dict[str, Any]:
        return self._jwks

    def issue_token(self, subject: str, organization_id: str | None = None) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": self._settings.auth_issuer,
            "aud": self._settings.auth_audience,
            "sub": subject,
            "iat": now,
            "exp": now + 3600,
        }
        if organization_id:
            claims["org"] = organization_id
        return jwt.encode(
            claims,
            self._private_pem,
            algorithm=self._settings.auth_algorithm,
            headers={"kid": "test-identity"},
        )


def get_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Principal:
    """Extract and verify the bearer token into a Principal."""
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.removeprefix("Bearer ").strip()
    verifier = TokenVerifier(settings, jwks=_get_jwks())
    try:
        claims = verifier.verify(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc
    return Principal(
        subject=claims["sub"],
        email=claims.get("email"),
        organization_id=claims.get("org"),
        claims=claims,
    )


_jwks_override: dict[str, Any] | None = None
_jwks_client: PyJWKClient | None = None


def set_jwks_override(jwks: dict[str, Any] | None) -> None:
    """Allow the app to inject the local identity provider's keys."""
    global _jwks_override
    _jwks_override = jwks


def _get_jwks() -> dict[str, Any] | None:
    return _jwks_override


def _get_jwks_client(settings: Settings) -> PyJWKClient:
    """Return a cached PyJWKClient for the configured JWKS URL.

    PyJWKClient already caches fetched keys internally; caching the client
    itself avoids rebuilding it (and re-fetching) on every request.
    """
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.auth_jwks_url)
    return _jwks_client
