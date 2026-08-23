"""Media upload validation: magic-byte sniffing and checksums.

Filename and browser MIME are never trusted alone; the leading bytes of the
object are inspected to determine the real type. Sniffing reads only the first
few bytes, never the whole object.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

# Number of leading bytes needed to identify any supported type.
SNIFF_HEAD_SIZE = 16


def _is_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _is_mp4(data: bytes) -> bool:
    # ISO BMFF: a top-level box whose type is "ftyp". The box size (bytes 0-3)
    # varies (0x18, 0x1C, 0x20, ...), so match the type field, not a fixed size.
    return data[4:8] == b"ftyp"


def _is_quicktime(data: bytes) -> bool:
    # MOV is also ISO BMFF but carries the "qt  " brand in the ftyp box.
    return data[4:8] == b"ftyp" and data[8:12] == b"qt  "


# Ordered sniffers: more specific types must be checked before generic ones.
_SNIFFERS: list[tuple[str, Callable[[bytes], bool]]] = [
    ("image/jpeg", lambda d: d.startswith(b"\xff\xd8\xff")),
    ("image/png", lambda d: d.startswith(b"\x89PNG\r\n\x1a\n")),
    ("image/webp", _is_webp),
    ("video/quicktime", _is_quicktime),
    ("video/mp4", _is_mp4),
    ("video/webm", lambda d: d.startswith(b"\x1a\x45\xdf\xa3")),
]

# Content types we accept for product assets.
ALLOWED_CONTENT_TYPES = frozenset(t for t, _ in _SNIFFERS)


def sniff_content_type(data: bytes) -> str | None:
    """Return the canonical MIME type matching the leading bytes, or None."""
    for content_type, sniffer in _SNIFFERS:
        if sniffer(data):
            return content_type
    return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
