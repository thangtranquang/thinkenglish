"""TC-23.4: hard cap of 6 provider calls per image (1 automatic retry per run)."""
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import upload


def _boom(n, data):
    raise RuntimeError("provider down")


def test_cap_of_six_calls(reg, provider, db):
    provider.script = _boom
    data = jpeg_bytes(7)
    for calls in (2, 4, 6):
        r = upload(reg, data)
        assert r.status_code == 202
        s = reg.get(f"/api/uploads/{r.json()['content_id']}").json()
        assert s["status"] == "failed" and s["ai_calls"] == calls
    assert s["retryable"] is False
    r = upload(reg, data)
    assert r.status_code == 409 and r.json()["error"] == "analysis_unavailable"
    assert provider.call_count == 6
    assert db.execute("SELECT ai_calls FROM card_contents WHERE seed_key IS NULL").fetchone()[0] == 6


def test_automatic_retry_succeeds_on_second_call(reg, provider):
    def first_fails(n, data):
        if n == 1:
            raise RuntimeError("blip")
        return None
    provider.script = first_fails
    r = upload(reg, jpeg_bytes(8))
    s = reg.get(f"/api/uploads/{r.json()['content_id']}").json()
    assert s["status"] == "ready" and s["ai_calls"] == 2


def test_stale_processing_reported_failed(reg, db, clock, settings):
    cid = upload(reg, jpeg_bytes(2)).json()["content_id"]
    db.execute("UPDATE card_contents SET status='processing', processing_started_at=? WHERE id=?",
               (clock.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), cid))
    clock.advance(seconds=settings.processing_stale_seconds + 5)
    assert reg.get(f"/api/uploads/{cid}").json()["status"] == "failed"
