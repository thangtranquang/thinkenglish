"""Guest-creation rate limit, upload body cap, share text moderation, shared-file GC."""
from dataclasses import replace

from backend.app.maintenance import run_maintenance
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.practice import insert_content
from backend.tests.helpers.uploads import make_card, ready_content


def test_guest_creation_rate_limited_per_ip(new_api, app, clock):
    app.state.settings = replace(app.state.settings, guest_create_per_ip_per_hour=2)
    new_api(), new_api()
    from fastapi.testclient import TestClient
    from backend.tests.conftest import Api
    api = Api(TestClient(app, client=("testclient", 50000)), app.state.settings.app_origin)
    r = api.client.post("/api/session/bootstrap", headers={"Origin": api.origin})
    assert r.status_code == 429 and r.json()["error"] == "rate_limited" and int(r.headers["retry-after"]) >= 1
    # a returning guest (has the cookie) is not counted
    first = new_api(peer=("10.9.9.9", 1))
    assert first.bootstrap().status_code == 200
    assert first.bootstrap().status_code == 200
    clock.advance(seconds=3601)
    assert new_api().user_id


def test_oversized_upload_rejected_before_parsing(reg, settings):
    big = settings.max_upload_bytes + 64 * 1024 + 1
    r = reg.post("/api/uploads", headers={"Content-Length": str(big)}, content=b"x")
    assert r.status_code == 413 and r.json()["error"] == "image_too_large"


def test_share_refused_for_contact_info_in_title(reg):
    card = make_card(reg, jpeg_bytes(31), title="goi 0912 345 678")
    r = reg.post(f"/api/cards/{card['id']}/share")
    assert r.status_code == 422 and r.json()["reason"] == "text" and r.json()["fields"]["message"]


def test_share_refused_for_link_in_label_word(reg):
    c = ready_content(reg, jpeg_bytes(32))
    card = reg.post("/api/cards", json={"content_id": c["content_id"], "label_overrides": [
        {"id": c["labels"][0]["id"], "word": "www.x.com", "x": 0.4, "y": 0.4}]}).json()
    r = reg.post(f"/api/cards/{card['id']}/share")
    assert r.status_code == 422 and r.json()["reason"] == "text"


def test_gc_keeps_file_shared_by_other_asset(reg, db, clock, settings):
    keep = insert_content(db, settings.data_dir)
    gone = insert_content(db, settings.data_dir, created="2020-01-01T00:00:00.000Z")
    shared = db.execute("SELECT storage_path FROM image_assets WHERE id = ?", (keep["asset_id"],)).fetchone()[0]
    db.execute("UPDATE image_assets SET storage_path = ? WHERE id = ?", (shared, gone["asset_id"]))
    db.execute("UPDATE card_contents SET created_at = ? WHERE id = ?", ("2020-01-01T00:00:00.000Z", gone["content_id"]))
    from backend.tests.helpers.practice import insert_card
    insert_card(db, reg.user_id, keep["content_id"])
    run_maintenance(db, clock, settings)
    assert db.execute("SELECT COUNT(*) FROM card_contents WHERE id = ?", (gone["content_id"],)).fetchone()[0] == 0
    assert keep["path"].exists()
