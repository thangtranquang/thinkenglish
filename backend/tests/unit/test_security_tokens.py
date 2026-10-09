"""TC-1.17 tokens hashed at rest, TC-7.4 scrypt, TC-14.16 session arithmetic (DT-13)."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from backend.app import security

T0 = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)


def test_tokens_are_256_bit_unique_and_hashed():  # TC-1.17
    tokens = [security.new_token() for _ in range(1000)]
    assert len(set(tokens)) == 1000
    assert all(len(t) >= 43 and all(c.isalnum() or c in "-_" for c in t) for t in tokens)
    t = tokens[0]
    assert security.hash_token(t) == hashlib.sha256(t.encode()).hexdigest()
    assert t not in security.hash_token(t)


def test_scrypt_per_user_salt_and_params():  # TC-7.4
    h1, p1 = security.hash_password("hunter2hunter2", 2**14)
    h2, p2 = security.hash_password("hunter2hunter2", 2**14)
    assert h1 != h2
    assert len(bytes.fromhex(h1.split("$")[0])) == 16
    params = json.loads(p1)
    assert params["n"] >= 16384 and params["r"] == 8 and params["p"] == 1
    assert security.verify_password("hunter2hunter2", h1, p1)
    assert not security.verify_password("hunter2hunter3", h1, p1)
    assert not security.verify_password("x", "garbage", p1)
    assert security.dummy_verify("hunter2hunter2", 2**10) is False


def test_session_arithmetic():  # TC-14.16
    exp, ab = security.session_expiry(T0)
    for idle, expired in ((89, False), (90, True), (91, True)):
        assert security.session_expired(T0 + timedelta(days=idle), exp, ab) is expired
    for age, expired in ((364, False), (365, True), (366, True)):
        now = T0 + timedelta(days=age)  # idle window kept open so only the absolute limit can expire it
        assert security.session_expired(now, now + timedelta(days=1), ab) is expired
    assert security.slide_expiry(T0 + timedelta(days=80), ab) == T0 + timedelta(days=170)
    assert security.slide_expiry(T0 + timedelta(days=300), ab) == ab


def test_origin_rules():
    ok = security.origin_ok
    assert ok("http://localhost:8000", None, "http://localhost:8000", False)
    assert not ok("https://evil.example", None, "http://localhost:8000", False)
    assert ok(None, "http://localhost:8000/page", "http://localhost:8000", False)
    assert not ok(None, None, "http://localhost:8000", False)
    assert ok(None, None, "http://localhost:8000", True)
