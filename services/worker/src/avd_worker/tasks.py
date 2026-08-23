"""Celery tasks for the AI Video Director worker."""

from __future__ import annotations

from avd_worker.celery_app import celery_app


@celery_app.task(name="avd.health")
def health() -> dict[str, str]:
    """Health task used to verify the worker can execute work."""
    return {"status": "ok", "worker": "avd_worker"}
