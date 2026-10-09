"""TC-27.10: attempts on a locked practice level are refused; passing level 1 unlocks level 2."""
from backend.tests.helpers.practice import DESCRIPTIONS, LABELS, WORDS, att

TABLES = ("attempts", "review_state", "card_progress")


def test_locked_level_returns_409_and_writes_nothing(guest, db):  # TC-27.10
    r = guest.post("/api/attempts", json=att(DESCRIPTIONS[0], item_type="sentence", transcript="hi"))
    assert r.status_code == 409 and r.json()["error"] == "level_locked"
    for table in TABLES:
        assert db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    assert db.execute("SELECT COALESCE(SUM(had_write), 0) FROM usage_sessions").fetchone()[0] == 0


def test_passing_level_one_unlocks_level_two(guest):
    for item, word in zip(LABELS, WORDS):
        last = guest.post("/api/attempts", json=att(item, transcript=word)).json()
    assert last["unlocked_levels"] == [1, 2]
    r = guest.post("/api/attempts", json=att(DESCRIPTIONS[0], item_type="sentence", transcript="hello"))
    assert r.status_code == 201
