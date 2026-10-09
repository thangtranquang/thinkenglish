"""TC-28.1, 28.6, 28.14: attempts are scored on the server and update SM-2 state atomically."""
from backend.tests.helpers.practice import CARD, LABELS, att


def test_valid_attempt_end_to_end(guest, db):  # TC-28.1
    r = guest.post("/api/attempts", json=att())
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["accuracy"], body["score"], body["q"], body["xp"]) == (100, 100, 5, 10)
    assert body["unlocked_levels"] == [1]
    row = db.execute("SELECT COUNT(*), SUM(xp) FROM attempts WHERE user_id = ?", (guest.user_id,)).fetchone()
    assert tuple(row) == (1, 10)
    rs = db.execute("SELECT reps, interval_days FROM review_state WHERE user_id = ?", (guest.user_id,)).fetchone()
    assert tuple(rs) == (1, 1)
    prog = db.execute("SELECT level, best_score, unlocked FROM card_progress WHERE user_id = ? AND card_id = ? "
                      "ORDER BY level", (guest.user_id, CARD)).fetchall()
    assert [tuple(p) for p in prog] == [(1, 33, 1)]  # level score = mean over 3 labels, 2 unattempted
    had = db.execute("SELECT MAX(had_write) FROM usage_sessions WHERE user_id = ?", (guest.user_id,)).fetchone()[0]
    assert had == 1


def test_sm2_intervals_for_good_answers(guest, db):  # TC-28.6
    seen = []
    for _ in range(3):
        assert guest.post("/api/attempts", json=att()).status_code == 201
        seen.append(tuple(db.execute("SELECT reps, interval_days, ease FROM review_state WHERE user_id = ?",
                                     (guest.user_id,)).fetchone()))
    assert [s[0] for s in seen] == [1, 2, 3]
    assert [s[1] for s in seen] == [1, 6, 17]  # round(6 * 2.8)
    assert abs(seen[2][2] - 2.8) < 1e-9


def test_client_supplied_accuracy_rejected(guest, db):  # TC-28.14
    for extra in ({"accuracy": 100}, {"score": 100}, {"surprise": 1}):
        assert guest.post("/api/attempts", json=att(**extra)).status_code == 422
    assert guest.post("/api/attempts", json=att(client_attempt_id="not-a-uuid")).status_code == 422
    assert guest.post("/api/attempts", json=att(transcript="x" * 501)).status_code == 422
    assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0


def test_wrong_word_and_foreign_item(guest, db):
    r = guest.post("/api/attempts", json=att(LABELS[1], transcript="dog"))
    assert r.json()["accuracy"] < 100 and r.json()["xp"] == 2
    assert guest.post("/api/attempts", json=att("nope")).status_code == 404
