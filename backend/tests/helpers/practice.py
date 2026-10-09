"""Seed ids, attempt payloads and raw-SQL fixtures for the slice 7 tests (no slice 6 imports)."""
import uuid

from backend.app.seed import seed_id

CARD = seed_id("c1", "card")
LABELS = [seed_id("c1", "label", i) for i in range(3)]
DESCRIPTIONS = [seed_id("c1", "sentence", "description", i) for i in range(2)]
STORY = seed_id("c1", "sentence", "story", 0)
WORDS = ["coffee cup", "motorcycle", "pedestrian"]


def att(item_id=LABELS[0], transcript="a red cup", **over) -> dict:
    body = {"client_attempt_id": str(uuid.uuid4()), "card_id": CARD, "item_type": "label",
            "item_id": item_id, "mode": "shadow", "transcript": transcript}
    body.update(over)
    return body


def insert_content(db, data_dir, *, seed_key=None, status="ready", created="2026-01-01T00:00:00.000Z",
                   with_file=True) -> dict:
    """image_assets + card_contents + a real file under data_dir. Returns ids/paths."""
    sha = uuid.uuid4().hex + uuid.uuid4().hex
    rel = f"images/{sha[:2]}/{sha[2:4]}/{sha}.jpg"
    if with_file:
        path = data_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jpeg")
    aid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    db.execute("INSERT INTO image_assets (id, source_sha256, clean_sha256, storage_path, created_at) "
               "VALUES (?, ?, ?, ?, ?)", (aid, sha, sha, rel, created))
    db.execute("INSERT INTO card_contents (id, image_asset_id, seed_key, status, moderation_status, created_at) "
               "VALUES (?, ?, ?, ?, 'pending', ?)", (cid, aid, seed_key, status, created))
    return {"asset_id": aid, "content_id": cid, "path": data_dir / rel, "sha": sha}


def insert_card(db, owner_id, content_id, title="mine", created="2026-01-01T00:00:00.000Z") -> str:
    card_id = str(uuid.uuid4())
    db.execute("INSERT INTO cards (id, owner_id, content_id, title, created_at) VALUES (?, ?, ?, ?, ?)",
               (card_id, owner_id, content_id, title, created))
    return card_id


def insert_claim(db, user_id, content_id, created) -> None:
    db.execute("INSERT INTO upload_claims (user_id, content_id, created_at) VALUES (?, ?, ?)",
               (user_id, content_id, created))
