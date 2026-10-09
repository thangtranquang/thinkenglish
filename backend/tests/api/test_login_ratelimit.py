"""TC-13.1 five failures lock the nickname; IP and register buckets; window slides."""
from backend.tests.conftest import register_payload


def _bad(api, nick="minh_an"):
    return api.post("/api/auth/login", json={"nickname": nick, "password": "wrong-password-1"})


def test_five_failures_lock_nickname(reg, new_api, clock, db):  # TC-13.1
    a = new_api()
    assert [_bad(a).status_code for _ in range(5)] == [401] * 5
    r = a.post("/api/auth/login", json={"nickname": reg.nickname, "password": reg.password})
    assert r.status_code == 429
    assert r.headers["retry-after"].isdigit() and 1 <= int(r.headers["retry-after"]) <= 900
    assert "giây" in r.json()["fields"]["message"]
    # keys are hashed, never the raw nickname
    assert all("minh" not in row[0] for row in db.execute("SELECT key_hash FROM rate_events"))
    # 429s are not counted
    assert db.execute("SELECT COUNT(*) FROM rate_events WHERE bucket = 'login_nick'").fetchone()[0] == 5
    clock.advance(seconds=901)
    assert a.post("/api/auth/login", json={"nickname": reg.nickname, "password": reg.password}).status_code == 200


def test_ip_bucket_limits_across_nicknames(new_api, settings):
    a = new_api()
    for i in range(settings.login_fail_per_ip):
        assert _bad(a, f"user_{i}").status_code == 401
    assert _bad(a, "someone_else").status_code == 429


def test_other_ip_is_independent(reg, new_api):
    a, b = new_api(peer=("10.0.0.1", 1)), new_api(peer=("10.0.0.2", 1))
    for _ in range(5):
        _bad(a)
    assert _bad(a).status_code == 429
    assert _bad(b).status_code == 429  # the nickname bucket is shared across IPs


def test_register_limit_per_ip(new_api, settings):
    a = new_api()
    for _ in range(settings.register_per_ip):
        assert a.post("/api/auth/register", json=register_payload(nickname="ab")).status_code == 422
    r = a.post("/api/auth/register", json=register_payload())
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
