"""TC-14.6 expired or revoked sessions become a new guest and reveal nothing."""


def test_idle_expiry_becomes_new_guest(reg, clock):  # TC-14.6
    old_id = reg.user_id
    clock.advance(days=91)
    body = reg.bootstrap().json()
    assert body["is_guest"] is True and body["user"]["id"] != old_id and body["user"]["nickname"] is None
    assert "Minh_An" not in str(body)
    assert reg.client.cookies.get("re_device")
    assert reg.get("/api/me").json()["user"]["id"] == body["user"]["id"]


def test_sliding_window_then_absolute_limit(reg, clock):  # TC-14.6 / DT-13
    old_id = reg.user_id
    for _ in range(4):  # activity every 80 days keeps sliding the idle window
        clock.advance(days=80)
        assert reg.get("/api/me").json()["user"]["id"] == old_id
    clock.advance(days=80)  # day 400: beyond the 365-day absolute limit despite recent activity
    body = reg.bootstrap().json()
    assert body["is_guest"] is True and body["user"]["id"] != old_id


def test_revoked_session_is_a_new_guest(reg, db):
    old_id = reg.user_id
    db.execute("UPDATE sessions SET revoked_at = '2026-01-15T08:00:00.000000Z' WHERE user_id = ?", (old_id,))
    body = reg.bootstrap().json()
    assert body["is_guest"] is True and body["user"]["id"] != old_id
