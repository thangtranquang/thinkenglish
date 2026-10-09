"""TC-1.1 bootstrap creates a guest; TC-1.12 forged device cookie ignored."""
import hashlib
import re


def test_bootstrap_creates_guest(client, db, settings):  # TC-1.1
    r = client.post("/api/session/bootstrap", headers={"Origin": settings.app_origin})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["kind"] == "guest" and body["user"]["nickname"] is None
    assert body["user"]["cefr_level"] == "A1" and body["is_guest"] is True and body["gate"] is None
    assert body["csrf_token"] and "config" in body and "guardian_email" not in r.text
    assert r.headers["cache-control"] == "no-store"
    device = client.cookies.get("re_device")
    row = db.execute("SELECT token_hash FROM device_tokens").fetchone()
    assert row["token_hash"] == hashlib.sha256(device.encode()).hexdigest()
    assert db.execute("SELECT COUNT(*) FROM usage_sessions WHERE had_write = 0").fetchone()[0] == 1
    cookies = r.headers.get_list("set-cookie")
    dev = next(c for c in cookies if c.startswith("re_device="))
    csrf = next(c for c in cookies if c.startswith("re_csrf="))
    assert "HttpOnly" in dev and "samesite=lax" in dev.lower() and "Path=/" in dev
    assert re.search(r"Max-Age=\d+", dev) and "HttpOnly" not in csrf and "samesite=lax" in csrf.lower()


def test_bootstrap_is_idempotent_and_csrf_stable(client, db):
    first = client.post("/api/session/bootstrap").json()
    second = client.post("/api/session/bootstrap").json()
    assert first["user"]["id"] == second["user"]["id"] and first["csrf_token"] == second["csrf_token"]
    assert db.execute("SELECT COUNT(*) FROM users WHERE kind = 'guest'").fetchone()[0] == 1


def test_forged_device_cookie_is_ignored(client, db):  # TC-1.12
    for forged in ("garbage", "a" * 64):
        client.cookies.clear()
        client.cookies.set("re_device", forged, domain="testserver.local", path="/")
        r = client.post("/api/session/bootstrap")
        assert r.status_code == 200 and r.json()["is_guest"] is True
        assert client.cookies.get("re_device", domain="testserver.local") != forged
    assert db.execute("SELECT COUNT(*) FROM users WHERE kind = 'guest'").fetchone()[0] == 2
