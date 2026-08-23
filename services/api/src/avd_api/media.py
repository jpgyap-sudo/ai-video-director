"""Media upload validation: magic-byte sniffing and checksums.

Filename and browser MIME are never trusted alone; the first bytes of the
object are inspected to determine the real type.
"""

from __future__ import annotations

import hashlib

# Magic-byte signatures -> canonical content types.
_MAGIC: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF", b"WEBP"],
    "video/mp4": [b"\x00\x00\x00\x18ftyp", b"\x00\x00\x00\x20ftyp"],
    "video/webm": [b"\x1a\x45\xdf\xa3"],
    "video/quicktime": [b"\x00\x00\x00\x14ftypqt", b"\x00\x00\x00\x18ftypqt"],
}

# Content types we accept for product assets.
ALLOWED_CONTENT_TYPES = frozenset(_MAGIC.keys())


def sniff_content_type(data: bytes) -> str | None:
    """Return the canonical MIME type matching the leading bytes, or None."""
    for content_type, signatures in _MAGIC.items():
        for sig in signatures:
            if data.startswith(sig):
                return content_type
    return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
