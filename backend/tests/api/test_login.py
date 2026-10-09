"""TC-11.1 login, TC-11.7 unknown vs wrong password indistinguishable."""


def _card_id(db):
    return db.execute("SELECT id FROM cards LIMIT 1").fetchone()[0]


def test_login_success_replaces_empty_guest(reg, new_api, db):  # TC-11.1
    reg_id = reg.user_id
    other = new_api()  # fresh empty guest on a new device
    guest_id = other.user_id
    r = other.post("/api/auth/login", json={"nickname": "minh_an", "password": reg.password})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["id"] == reg_id and body["is_guest"] is False
    assert "hash" not in r.text and "token" not in r.text
    assert db.execute("SELECT COUNT(*) FROM users WHERE id = ?", (guest_id,)).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM device_tokens WHERE user_id = ?", (guest_id,)).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (reg_id,)).fetchone()[0] == 2
    cookies = r.headers.get_list("set-cookie")
    assert any(c.startswith("re_session=") and "HttpOnly" in c for c in cookies)
    assert any(c.startswith("re_device=") and "Max-Age=0" in c for c in cookies)
    assert other.get("/api/me").json()["user"]["id"] == reg_id


def test_unknown_and_wrong_password_are_identical(reg, new_api):  # TC-11.7
    a = new_api()
    wrong = a.post("/api/auth/login", json={"nickname": reg.nickname, "password": "wrong-password"})
    unknown = a.post("/api/auth/login", json={"nickname": "nobody_here", "password": "wrong-password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.content == unknown.content
    drop = {"date"}
    h = lambda r: {k: v for k, v in r.headers.items() if k not in drop}  # noqa: E731
    assert h(wrong) == h(unknown)


def test_login_requires_csrf_and_strict_body(reg, new_api):
    a = new_api()
    r = a.client.post("/api/auth/login", headers={"Origin": a.origin},
                      json={"nickname": reg.nickname, "password": reg.password})
    assert r.status_code == 403
    r = a.post("/api/auth/login", json={"nickname": reg.nickname, "password": reg.password, "extra": 1})
    assert r.status_code == 422
