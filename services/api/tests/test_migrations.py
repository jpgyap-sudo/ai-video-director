"""Migration up/down test against an ephemeral database.

In CI this runs against the Postgres service container; locally it falls back
to SQLite.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_config(tmp_path) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    url = os.getenv("MIGRATION_TEST_DATABASE_URL")
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    else:
        # Local runs use a dedicated SQLite file so the migration test never
        # collides with the shared test database created by conftest.
        db_path = tmp_path / "migration_test.db"
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_migration_up_and_down(alembic_config) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
