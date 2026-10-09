"""TC-7.1 conversion in place, TC-7.5 guardian consent, TC-7.11 nickname taken."""
from backend.tests.conftest import REG_NICKNAME, register_payload


def test_register_converts_guest_in_place(guest, db, write_session):  # TC-7.1
    guest_id = guest.user_id
    write_session(guest_id)
    db.execute("INSERT INTO card_progress (user_id, card_id, level, best_score, unlocked, updated_at) "
               "SELECT ?, id, 1, 80, 1, '2026-01-15T08:00:00.000000Z' FROM cards LIMIT 1", (guest_id,))
    r = guest.post("/api/auth/register", json=register_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["id"] == guest_id and body["user"]["kind"] == "registered"
    assert body["user"]["nickname"] == REG_NICKNAME and body["is_guest"] is False and body["gate"] is None
    assert "password" not in r.text and "hash" not in r.text and "guardian" not in r.text
    u = db.execute("SELECT * FROM users WHERE id = ?", (guest_id,)).fetchone()
    assert u["kind"] == "registered" and u["nickname_ci"] == "minh_an" and u["registered_at"]
    assert u["password_hash"] and '"n"' in u["password_params"] and u["gate_required_at"] is None
    assert db.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (guest_id,)).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM device_tokens WHERE user_id = ?", (guest_id,)).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM card_progress WHERE user_id = ?", (guest_id,)).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM usage_sessions WHERE user_id = ?", (guest_id,)).fetchone()[0] == 1
    cookies = r.headers.get_list("set-cookie")
    sess = next(c for c in cookies if c.startswith("re_session="))
    assert "HttpOnly" in sess and f"Max-Age={90 * 86400}" in sess
    assert any(c.startswith("re_device=") and "Max-Age=0" in c for c in cookies)
    me = guest.get("/api/me").json()
    assert me["user"]["id"] == guest_id and me["is_guest"] is False


def test_register_clears_gate(gated):
    assert gated.post("/api/auth/register", json=register_payload()).status_code == 201
    assert gated.get("/api/me").json()["gate"] is None


def test_under_16_requires_and_stores_guardian_consent(guest, db):  # TC-7.5
    year = 2026 - 12
    r = guest.post("/api/auth/register", json=register_payload(birth_year=year))
    assert r.status_code == 422 and r.json()["error"] == "guardian_email"
    r = guest.post("/api/auth/register", json=register_payload(
        birth_year=year, guardian_email="parent@example.com", guardian_consent=True))
    assert r.status_code == 201
    u = db.execute("SELECT guardian_email, guardian_consent_at FROM users WHERE id = ?", (guest.user_id,)).fetchone()
    assert u["guardian_email"] == "parent@example.com" and u["guardian_consent_at"]
    assert "parent@example.com" not in r.text
    assert "parent@example.com" not in guest.get("/api/me").text


def test_nickname_taken(reg, new_api, db):  # TC-7.11
    other = new_api()
    r = other.post("/api/auth/register", json=register_payload(nickname="minh_AN"))
    assert r.status_code == 409 and r.json()["error"] == "nickname_taken"
    assert other.get("/api/me").json()["is_guest"] is True
    assert db.execute("SELECT kind FROM users WHERE id = ?", (other.user_id,)).fetchone()[0] == "guest"


def test_already_registered_and_validation(reg, guest):
    r = reg.post("/api/auth/register", json=register_payload(nickname="Other_1"))
    assert r.status_code == 409 and r.json()["error"] == "already_registered"
    for bad, code in ((dict(nickname="ab"), "nickname_invalid"), (dict(password="short"), "password_length"),
                      (dict(birth_year=2020), "too_young"), (dict(nickname="admin"), "nickname_reserved")):
        r = guest.post("/api/auth/register", json=register_payload(**bad))
        assert r.status_code == 422 and r.json()["error"] == code, (bad, r.text)
    assert guest.post("/api/auth/register", json={**register_payload(), "role": "admin"}).status_code == 422
    assert guest.post("/api/auth/register", json=register_payload(avatar_key="dragon")).status_code == 422
