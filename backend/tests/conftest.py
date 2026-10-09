"""Shared fixtures: tmp data dir + DB, fake clock, app and TestClient."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.clock import FakeClock
from backend.app.config import Settings
from backend.app.main import create_app


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "test.db",
        gemini_api_key=None,
    )
    return replace(base, **overrides)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings, clock):
    return create_app(settings, clock=clock)


@pytest.fixture
def client(app):
    with TestClient(app) as c:  # runs the lifespan: migrate + seed
        yield c
