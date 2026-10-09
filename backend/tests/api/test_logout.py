"""TC-15.1 logout revokes only this session; idempotent; logout-all registered only."""


def test_logout_revokes_session(reg, new_api, db):  # TC-15.1
    other = new_api()
    other.post("/api/auth/login", json={"nickname": reg.nickname, "password": reg.password})
    r = reg.post("/api/auth/logout")
    assert r.status_code == 204
    cookies = r.headers.get_list("set-cookie")
    assert any(c.startswith("re_session=") and "Max-Age=0" in c for c in cookies)
    assert not any(c.startswith(("re_device=", "re_csrf=")) for c in cookies)
    assert db.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ? AND revoked_at IS NOT NULL",
                      (reg.user_id,)).fetchone()[0] == 1
    assert other.get("/api/me").json()["is_guest"] is False  # other device unaffected
    assert reg.client.cookies.get("re_session") is None
    assert reg.client.cookies.get("re_csrf") == reg.csrf_token


def test_logout_is_idempotent_and_works_for_guest(reg, guest):
    assert reg.post("/api/auth/logout").status_code == 204
    assert reg.post("/api/auth/logout").status_code == 204
    assert guest.post("/api/auth/logout").status_code == 204
    assert guest.get("/api/me").json()["is_guest"] is True


def test_logout_all(reg, new_api, db, guest):
    other = new_api()
    other.post("/api/auth/login", json={"nickname": reg.nickname, "password": reg.password})
    assert reg.post("/api/auth/logout-all").status_code == 204
    assert db.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ? AND revoked_at IS NULL",
                      (reg.user_id,)).fetchone()[0] == 0
    assert other.get("/api/me").status_code == 401
    r = guest.post("/api/auth/logout-all")
    assert r.status_code == 403 and r.json() == {"error": "registration_required", "reason": "account"}
