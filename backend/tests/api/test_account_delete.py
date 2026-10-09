"""TC-17.1, 17.4, 17.15: account deletion cascades, keeps shared content, leaves no personal data."""
from backend.tests.conftest import register_payload
from backend.tests.helpers.practice import att, insert_card, insert_claim, insert_content

USER_TABLES = {"device_tokens": "user_id", "sessions": "user_id", "usage_sessions": "user_id",
               "cards": "owner_id", "card_saves": "user_id", "card_progress": "user_id",
               "reflex_sessions": "user_id", "attempts": "user_id", "review_state": "user_id",
               "upload_claims": "user_id"}


def _delete(api, password):
    return api.delete("/api/me", json={"password": password})


def _count(db, table, col, value):
    return db.execute("SELECT COUNT(*) FROM " + table + " WHERE " + col + " = ?", (value,)).fetchone()[0]


def test_delete_with_correct_password(reg, db, settings):  # TC-17.1
    reg.post("/api/attempts", json=att())
    c = insert_content(db, settings.data_dir)
    insert_card(db, reg.user_id, c["content_id"])
    insert_claim(db, reg.user_id, c["content_id"], "2026-01-15T07:00:00.000Z")
    bad = _delete(reg, "wrong-password-1")
    assert bad.status_code == 403 and bad.json()["error"] == "invalid_credentials"
    r = _delete(reg, reg.password)
    assert r.status_code == 204
    assert "re_session" in r.headers.get("set-cookie", "")
    assert _count(db, "users", "id", reg.user_id) == 0
    for table, col in USER_TABLES.items():
        assert _count(db, table, col, reg.user_id) == 0
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert _count(db, "card_contents", "id", c["content_id"]) == 0
    assert _count(db, "image_assets", "id", c["asset_id"]) == 0
    assert not c["path"].exists()


def test_shared_content_survives(reg, new_api, db, settings):  # TC-17.4
    other = new_api()
    c = insert_content(db, settings.data_dir)
    insert_card(db, reg.user_id, c["content_id"])
    b_card = insert_card(db, other.user_id, c["content_id"])
    assert _delete(reg, reg.password).status_code == 204
    assert _count(db, "cards", "id", b_card) == 1
    assert _count(db, "card_contents", "id", c["content_id"]) == 1
    assert _count(db, "image_assets", "id", c["asset_id"]) == 1
    assert c["path"].exists()


def test_wrong_password_is_rate_limited(reg):
    for _ in range(5):
        assert _delete(reg, "wrong-password-1").status_code == 403
    r = _delete(reg, reg.password)
    assert r.status_code == 429 and "retry-after" in r.headers


def test_no_personal_data_remains(new_api, db):  # TC-17.15
    api = new_api()
    payload = register_payload(nickname="Kid_Zed", birth_year=2014, guardian_email="parent@example.org",
                               guardian_consent=True)
    assert api.post("/api/auth/register", json=payload).status_code == 201
    assert _delete(api, payload["password"]).status_code == 204
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    for table in tables:
        for row in db.execute("SELECT * FROM " + table):
            blob = " ".join(str(v) for v in tuple(row)).lower()
            assert "kid_zed" not in blob and "parent@example.org" not in blob
