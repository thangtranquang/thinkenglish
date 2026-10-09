"""TC-39.11 no secrets in responses, TC-18.22 security headers, plus card mastery from attempts."""
import uuid

from backend.tests.conftest import register_payload
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.practice import CARD, LABELS, att
from backend.tests.helpers.uploads import make_card

GUARDIAN = "parent.secret@example.com"


class Recorder:
    """Wraps an Api and keeps the text of every response it returned."""

    def __init__(self, api):
        self.api, self.texts = api, []

    def __getattr__(self, name):
        fn = getattr(self.api, name)
        if name not in ("get", "post", "put", "patch", "delete"):
            return fn

        def call(*a, **kw):
            r = fn(*a, **kw)
            self.texts.append(f"{r.status_code} {a[0]} {r.text}")
            return r
        return call


def test_no_secrets_in_any_response(new_api, db):  # TC-39.11
    api = new_api(bootstrap=False)
    rec = Recorder(api)
    rec.bootstrap()
    rec.post("/api/attempts", json=att())
    r = rec.post("/api/auth/register", json=register_payload(
        nickname="Be_Nho", birth_year=2013, guardian_email=GUARDIAN, guardian_consent=True))
    assert r.status_code == 201, r.text
    card = make_card(api, jpeg_bytes(77))
    for url in ("/api/me", "/api/cards?scope=mine", "/api/cards?scope=explore", f"/api/cards/{card['id']}",
                f"/api/cards/{CARD}", "/api/topics", "/api/config"):
        assert rec.get(url).status_code == 200
    s = rec.post("/api/reflex/sessions", json={"level": 1})
    assert s.status_code == 201
    rec.post(f"/api/reflex/sessions/{s.json()['session_id']}/complete")
    rec.post(f"/api/cards/{card['id']}/share")
    rec.post("/api/session/bootstrap")
    rec.post("/api/auth/logout")
    blob = "\n".join(rec.texts)

    secrets = {GUARDIAN, "raw_response", "password_hash", "token_hash", "guardian_email", "scrypt"}
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (api.user_id,)).fetchone()
    if row and row[0]:
        secrets.add(row[0])
    for cookie in api.client.cookies.jar:
        if "csrf" not in cookie.name.lower() and len(cookie.value) > 16:
            secrets.add(cookie.value)
    for secret in secrets:
        assert secret not in blob, f"{secret[:12]!r} leaked in a response"


def test_security_headers_on_every_response(client):  # TC-18.22
    for path in ("/", "/api/health", "/api/nope"):
        r = client.get(path)
        assert "default-src 'self'" in r.headers["content-security-policy"], path
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"], path
        assert r.headers["x-content-type-options"] == "nosniff", path
        assert r.headers["referrer-policy"] == "same-origin", path
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_card_mastery_is_mean_of_last_five_scores(guest):
    detail = guest.get(f"/api/cards/{CARD}").json()
    assert detail["mastery"] is None and detail["unlocked_levels"] == [1]
    listing = guest.get("/api/cards?scope=explore").json()["items"]
    assert all(c["mastery"] is None for c in listing)
    for transcript in ("wrong", "wrong", "coffee cup", "coffee cup", "coffee cup", "coffee cup", "coffee cup"):
        r = guest.post("/api/attempts", json=att(item_id=LABELS[0], transcript=transcript,
                                                 client_attempt_id=str(uuid.uuid4())))
        assert r.status_code == 201
    assert guest.get(f"/api/cards/{CARD}").json()["mastery"] == 100  # last 5 are all 100
    item = next(c for c in guest.get("/api/cards?scope=explore").json()["items"] if c["id"] == CARD)
    assert item["mastery"] == 100
    other = next(c for c in guest.get("/api/cards?scope=explore").json()["items"] if c["id"] != CARD)
    assert other["mastery"] is None
