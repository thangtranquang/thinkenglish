"""TC-24.2, 24.8."""
import uuid

from backend.tests.conftest import register_payload
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import ready_content


def test_save_with_overrides(reg, db):
    c = ready_content(reg, jpeg_bytes(11))
    first = c["labels"][0]
    ovr = [{"id": lab["id"], "word": lab["word"], "x": lab["x"], "y": lab["y"]} for lab in c["labels"][:3]]
    ovr[0].update(word="Renamed", x=0.5, y=0.25)
    r = reg.post("/api/cards", json={"content_id": c["content_id"], "title": "Của tôi", "label_overrides": ovr})
    assert r.status_code == 201, r.text
    card = r.json()
    assert card["visibility"] == "private" and card["title"] == "Của tôi"
    assert card["labels"][0]["word"] == "Renamed" and card["labels"][0]["x"] == 0.5
    assert len(card["labels"]) == 3
    assert db.execute("SELECT label_overrides FROM cards WHERE id = ?", (card["id"],)).fetchone()[0]
    assert db.execute("SELECT word FROM card_labels WHERE id = ?", (first["id"],)).fetchone()[0] == first["word"]
    again = reg.post("/api/cards", json={"content_id": c["content_id"]})
    assert again.status_code == 200 and again.json()["id"] == card["id"]
    assert db.execute("SELECT COUNT(*) FROM cards WHERE owner_id = ?", (reg.user_id,)).fetchone()[0] == 1


def test_invalid_overrides_rejected(reg):
    c = ready_content(reg, jpeg_bytes(12))
    bad = [{"id": str(uuid.uuid4()), "word": "x", "x": 0.1, "y": 0.1}]
    r = reg.post("/api/cards", json={"content_id": c["content_id"], "label_overrides": bad})
    assert r.status_code == 422
    r = reg.post("/api/cards", json={"content_id": c["content_id"], "extra": 1})
    assert r.status_code == 422


def test_idor_on_upload_and_card_creation(reg, new_api):
    c = ready_content(reg, jpeg_bytes(13))
    b = new_api()
    b.post("/api/auth/register", json=register_payload(nickname="Bao_Chau"))
    missing = str(uuid.uuid4())
    got = b.get(f"/api/uploads/{c['content_id']}")
    ref = b.get(f"/api/uploads/{missing}")
    assert got.status_code == 404 and got.content == ref.content
    r = b.post("/api/cards", json={"content_id": c["content_id"]})
    ref2 = b.post("/api/cards", json={"content_id": missing})
    assert r.status_code == 404 and r.content == ref2.content
    assert b.get(f"/api/uploads/{c['content_id']}/image").status_code == 404
