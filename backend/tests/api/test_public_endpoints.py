"""TC-39.1 health, TC-39.2 config (no secrets), TC-36.1 audio served."""
from dataclasses import replace

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_is_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers["cache-control"] == "no-store"


def test_config_has_limits_and_no_secrets(settings, clock):
    settings = replace(settings, gemini_api_key="super-secret-key-123")
    with TestClient(create_app(settings, clock=clock)) as c:
        r = c.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["cefr_levels"] == ["A1", "A2", "B1"]
    assert body["avatars"] and all(isinstance(a, str) for a in body["avatars"])
    assert body["guest_free_sessions"] == settings.guest_free_sessions
    assert body["max_upload_bytes"] == settings.max_upload_bytes
    assert body["max_pixels"] == settings.max_pixels
    assert body["birth_year_min"] < body["birth_year_max"] == 2026 - 10
    text = r.text.lower()
    for forbidden in ("super-secret-key-123", "api_key", "salt", "secret", "scrypt"):
        assert forbidden not in text


def test_audio_is_served_statically(client):
    r = client.get("/audio/cup-b88678d.mp3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert "etag" in r.headers or "cache-control" in r.headers
    assert len(r.content) > 1000
