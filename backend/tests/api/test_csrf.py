"""TC-18.7 missing token, TC-18.9 foreign Origin, TC-18.12 no Origin/Referer."""


def test_missing_token_rejected(guest):  # TC-18.7
    r = guest.client.post("/api/session/heartbeat", headers={"Origin": guest.origin})
    assert r.status_code == 403 and r.json()["error"] == "csrf_failed"


def test_wrong_token_rejected(guest):
    r = guest.client.post("/api/session/heartbeat", headers={"Origin": guest.origin, "X-CSRF-Token": "x" * 43})
    assert r.status_code == 403


def test_foreign_origin_rejected(guest):  # TC-18.9
    r = guest.post("/api/session/heartbeat", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"] == "csrf_failed"
    r = guest.client.post("/api/session/bootstrap", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_no_origin_no_referer_rejected_but_referer_fallback_works(guest):  # TC-18.12
    token = {"X-CSRF-Token": guest.csrf_token}
    assert guest.client.post("/api/session/heartbeat", headers=token).status_code == 403
    ok = guest.client.post("/api/session/heartbeat", headers={**token, "Referer": guest.origin + "/page"})
    assert ok.status_code == 200
    bad = guest.client.post("/api/session/heartbeat", headers={**token, "Referer": "https://evil.example/"})
    assert bad.status_code == 403


def test_bootstrap_without_origin_is_allowed_and_get_needs_no_token(client, guest):
    assert client.post("/api/session/bootstrap").status_code == 200
    assert guest.get("/api/me", csrf=False).status_code == 200
