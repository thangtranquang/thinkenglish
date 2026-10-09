"""TC-20.1: upload end to end; an upload never inserts a card."""
import hashlib

from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import upload


def test_upload_end_to_end(reg, db, provider, settings):
    raw = jpeg_bytes(3)
    r = upload(reg, raw)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "processing" and body["dedupe"] == "none" and body["ai_calls"] == 0
    s = reg.get(f"/api/uploads/{body['content_id']}").json()
    assert s["status"] == "ready" and s["ai_calls"] == 1 and 3 <= len(s["labels"]) <= 5
    assert provider.call_count == 1
    asset = db.execute("SELECT * FROM image_assets WHERE first_uploaded_by IS NOT NULL").fetchone()
    assert asset["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert asset["clean_sha256"] and not asset["storage_path"].startswith(("/", "C:"))
    assert db.execute("SELECT COUNT(*) FROM upload_claims").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM cards WHERE owner_id = ?", (reg.user_id,)).fetchone()[0] == 0
    n = db.execute("SELECT COUNT(*) FROM card_sentences WHERE content_id = ?", (body["content_id"],)).fetchone()[0]
    assert n >= 2
    assert reg.get(s["image_url"]).status_code == 200
