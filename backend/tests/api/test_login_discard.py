"""TC-12.1 login with discard_guest deletes the guest and its progress; flag required when progress exists."""


def _give_progress(db, user_id):
    db.execute("INSERT INTO card_saves (user_id, card_id, saved_at) "
               "SELECT ?, id, '2026-01-15T08:00:00.000000Z' FROM cards LIMIT 1", (user_id,))
    db.execute("INSERT INTO card_progress (user_id, card_id, level, best_score, unlocked, updated_at) "
               "SELECT ?, id, 1, 80, 1, '2026-01-15T08:00:00.000000Z' FROM cards LIMIT 1", (user_id,))


def test_progress_requires_discard_flag(reg, new_api, db):
    other = new_api()
    _give_progress(db, other.user_id)
    creds = {"nickname": reg.nickname, "password": reg.password}
    r = other.post("/api/auth/login", json=creds)
    assert r.status_code == 409 and r.json()["error"] == "guest_has_progress"
    assert db.execute("SELECT COUNT(*) FROM users WHERE id = ?", (other.user_id,)).fetchone()[0] == 1
    assert other.get("/api/me").json()["is_guest"] is True  # still the guest


def test_discard_guest_deletes_everything(reg, new_api, db):  # TC-12.1
    other = new_api()
    guest_id = other.user_id
    _give_progress(db, guest_id)
    r = other.post("/api/auth/login", json={"nickname": reg.nickname, "password": reg.password,
                                            "discard_guest": True})
    assert r.status_code == 200 and r.json()["user"]["id"] == reg.user_id
    for table in ("users", "device_tokens", "card_saves", "card_progress", "usage_sessions"):
        col = "id" if table == "users" else "user_id"
        assert db.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (guest_id,)).fetchone()[0] == 0, table  # noqa: S608
    assert any(c.startswith("re_device=") and "Max-Age=0" in c for c in r.headers.get_list("set-cookie"))
    assert other.get("/api/me").json()["user"]["id"] == reg.user_id


def test_wrong_password_does_not_discard(reg, new_api, db):
    other = new_api()
    _give_progress(db, other.user_id)
    r = other.post("/api/auth/login", json={"nickname": reg.nickname, "password": "nope-nope-1",
                                            "discard_guest": True})
    assert r.status_code == 401
    assert db.execute("SELECT COUNT(*) FROM users WHERE id = ?", (other.user_id,)).fetchone()[0] == 1


def test_login_clears_old_session_of_same_browser(reg, db):
    first = db.execute("SELECT token_hash FROM sessions WHERE user_id = ?", (reg.user_id,)).fetchone()[0]
    r = reg.post("/api/auth/login", json={"nickname": reg.nickname, "password": reg.password})
    assert r.status_code == 200
    assert db.execute("SELECT revoked_at FROM sessions WHERE token_hash = ?", (first,)).fetchone()[0] is not None
