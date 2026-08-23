"""Antivirus hook interface.

The media lifecycle (plan §4) places a malware scan between validation and
the private original. Phase 1 ships a no-op interface so the pipeline has a
defined seam to plug a real scanner into later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AntivirusScanner(ABC):
    """Scans an uploaded object for malware before it is promoted."""

    @abstractmethod
    def scan(self, object_key: str) -> None:
        """Raise if the object is malicious; otherwise return."""


class NoopAntivirusScanner(AntivirusScanner):
    """No-op scanner used until a real scanner is integrated."""

    def scan(self, object_key: str) -> None:
        return None
