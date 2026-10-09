"""Shared fixtures: tmp data dir + DB, fake clock, mock provider, app, TestClient and identities.

Identity fixtures (all return an ``Api`` = a TestClient with its own cookie jar, i.e. one browser):
- ``guest``   bootstrapped guest. ``guest.post/put/patch/delete/get(url, **kw)`` add ``Origin`` and
              ``X-CSRF-Token`` automatically (pass ``csrf=False`` / ``origin=False`` to omit);
              ``guest.client`` is the plain TestClient (no helpers) for CSRF tests; ``guest.user_id``.
- ``reg``     registered user (nickname ``Minh_An``, password ``reg.password``), session cookie set.
- ``gated``   guest that had one write session, then 31 min idle; bootstrap returned ``second_visit``.
- ``new_api`` factory ``new_api(bootstrap=True, peer=None)`` for extra browsers/devices on the same app.
- ``db``      sqlite connection to the test DB (same pragmas as the app) for assertions.
- ``write_session(user_id)`` marks the user's latest usage session as having a write.
"""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.ai.mock import MockProvider
from backend.app.clock import FakeClock
from backend.app.config import Settings
from backend.app.db import connect
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
    return make_settings(tmp_path, scrypt_n=2**10)  # fast hashing; real params are tested in unit tests


@pytest.fixture
def provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def app(settings, clock, provider):
    return create_app(settings, clock=clock, provider=provider)


@pytest.fixture
def client(app):
    with TestClient(app) as c:  # runs the lifespan: migrate + seed
        yield c


class Api:
    """One browser: a TestClient plus CSRF/Origin helpers."""

    def __init__(self, client: TestClient, origin: str) -> None:
        self.client, self.origin, self.csrf_token, self.user_id = client, origin, None, None

    def bootstrap(self):
        r = self.client.post("/api/session/bootstrap", headers={"Origin": self.origin})
        assert r.status_code == 200, r.text
        self.csrf_token, self.user_id = r.json()["csrf_token"], r.json()["user"]["id"]
        return r

    def _call(self, method: str, url: str, csrf: bool = True, origin: bool = True, **kw):
        headers = dict(kw.pop("headers", None) or {})
        if origin:
            headers.setdefault("Origin", self.origin)
        if csrf and self.csrf_token:
            headers.setdefault("X-CSRF-Token", self.csrf_token)
        return self.client.request(method, url, headers=headers, **kw)

    def get(self, url, **kw):
        return self._call("GET", url, **kw)

    def post(self, url, **kw):
        return self._call("POST", url, **kw)

    def put(self, url, **kw):
        return self._call("PUT", url, **kw)

    def patch(self, url, **kw):
        return self._call("PATCH", url, **kw)

    def delete(self, url, **kw):
        return self._call("DELETE", url, **kw)


@pytest.fixture
def new_api(client, app, settings):
    def make(bootstrap: bool = True, peer: tuple[str, int] | None = None) -> Api:
        api = Api(TestClient(app, client=peer or ("testclient", 50000)), settings.app_origin)
        if bootstrap:
            api.bootstrap()
        return api
    return make


@pytest.fixture
def guest(client, settings) -> Api:
    api = Api(client, settings.app_origin)
    api.bootstrap()
    return api


@pytest.fixture
def db(settings, client):
    conn = connect(settings.db_path)
    yield conn
    conn.close()


@pytest.fixture
def write_session(db):
    def mark(user_id: str) -> None:
        db.execute("UPDATE usage_sessions SET had_write = 1 WHERE id = "
                   "(SELECT id FROM usage_sessions WHERE user_id = ? ORDER BY last_activity_at DESC LIMIT 1)",
                   (user_id,))
    return mark


REG_NICKNAME, REG_PASSWORD = "Minh_An", "correct-horse-9"


def register_payload(**over) -> dict:
    data = {"nickname": REG_NICKNAME, "password": REG_PASSWORD, "birth_year": 2000, "avatar_key": "fox",
            "cefr_level": "A2"}
    data.update(over)
    return data


@pytest.fixture
def reg(new_api) -> Api:
    api = new_api()
    r = api.post("/api/auth/register", json=register_payload())
    assert r.status_code == 201, r.text
    api.password, api.nickname = REG_PASSWORD, REG_NICKNAME
    return api


@pytest.fixture
def gated(guest, clock, write_session) -> Api:
    write_session(guest.user_id)
    clock.advance(minutes=31)
    r = guest.bootstrap()
    assert r.json()["gate"] == {"reason": "second_visit", "mandatory": True}
    return guest
