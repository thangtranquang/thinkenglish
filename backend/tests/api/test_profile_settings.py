"""TC-16.1: /api/me carries streak/XP/level; settings and profile updates."""
from backend.tests.helpers.practice import att


def test_me_has_streak_xp_level_and_no_secrets(reg):  # TC-16.1
    reg.post("/api/attempts", json=att())
    r = reg.get("/api/me")
    assert r.status_code == 200
    user = r.json()["user"]
    assert (user["streak"], user["xp"], user["level"], user["hide_timer"]) == (1, 10, 1, False)
    assert user["level_progress"] == 0.02
    assert r.json()["settings"] == {"hide_timer": False}
    text = r.text.lower()
    assert "password" not in text and "guardian" not in text and "token" not in text


def test_settings_for_any_identity(guest, reg):
    for api in (guest, reg):
        assert api.put("/api/me/settings", json={"hide_timer": True}).json() == {"hide_timer": True}
        assert api.get("/api/me").json()["user"]["hide_timer"] is True
    assert guest.put("/api/me/settings", json={"hide_timer": "yes"}).status_code == 422


def test_patch_profile_registered_only(guest, reg):
    r = reg.patch("/api/me", json={"avatar_key": "owl", "cefr_level": "B1"})
    assert r.status_code == 200 and r.json()["user"]["avatar_key"] == "owl"
    assert r.json()["user"]["cefr_level"] == "B1"
    assert reg.patch("/api/me", json={"cefr_level": "B2"}).status_code == 422
    assert reg.patch("/api/me", json={}).status_code == 422
    assert reg.patch("/api/me", json={"avatar_key": "dragon"}).status_code == 422
    g = guest.patch("/api/me", json={"avatar_key": "owl"})
    assert g.status_code == 403 and g.json()["error"] == "registration_required"
