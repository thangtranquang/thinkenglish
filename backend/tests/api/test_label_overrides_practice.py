"""Practice and Reflex honour the card owner's label edits (rename / delete), found by the slice 8 e2e."""
import uuid

from backend.app.services import practice as practice_service
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import ready_content


def _attempt(card_id, label_id, transcript):
    return {"client_attempt_id": str(uuid.uuid4()), "card_id": card_id, "item_type": "label",
            "item_id": label_id, "mode": "shadow", "transcript": transcript}


def test_renamed_label_is_scored_against_the_new_word_and_deleted_label_is_gone(reg):
    c = ready_content(reg, jpeg_bytes(201))
    keep, drop = c["labels"][0], c["labels"][1]
    card = reg.post("/api/cards", json={"content_id": c["content_id"], "label_overrides": [
        {"id": keep["id"], "word": "sparkling teapot", "x": 0.4, "y": 0.4}]}).json()
    ok = reg.post("/api/attempts", json=_attempt(card["id"], keep["id"], "sparkling teapot"))
    assert ok.status_code == 201 and ok.json()["accuracy"] == 100
    old = reg.post("/api/attempts", json=_attempt(card["id"], keep["id"], keep["word"]))
    assert old.json()["accuracy"] < 100  # the original AI word no longer counts
    gone = reg.post("/api/attempts", json=_attempt(card["id"], drop["id"], drop["word"]))
    assert gone.status_code == 404


def test_reflex_rounds_use_renamed_words_and_skip_deleted_labels(reg, db):
    c = ready_content(reg, jpeg_bytes(202))
    keep, drop = c["labels"][0], c["labels"][1]
    card = reg.post("/api/cards", json={"content_id": c["content_id"], "label_overrides": [
        {"id": keep["id"], "word": "sparkling teapot", "x": 0.4, "y": 0.4}]}).json()
    rounds = [{"card_id": card["id"], "item_id": lab["id"], "word": lab["word"], "ipa": "/x/", "audio_file": "a.mp3"}
              for lab in c["labels"]]
    out = {r["item_id"]: r for r in practice_service._apply_overrides(db, rounds)}
    assert out[keep["id"]]["word"] == "sparkling teapot"
    assert out[keep["id"]]["ipa"] is None and out[keep["id"]]["audio_file"] is None
    assert drop["id"] not in out


def test_deleted_labels_do_not_block_the_level_two_unlock(reg):
    c = ready_content(reg, jpeg_bytes(203))
    kept = c["labels"][:2]
    card = reg.post("/api/cards", json={"content_id": c["content_id"], "label_overrides": [
        {"id": lab["id"], "word": lab["word"], "x": 0.3, "y": 0.3} for lab in kept]}).json()
    last = None
    for lab in kept:
        last = reg.post("/api/attempts", json=_attempt(card["id"], lab["id"], lab["word"])).json()
    assert last["unlocked_levels"] == [1, 2]
