"""TC-28.20 / TC-46.1: replaying a client_attempt_id returns the original with 200."""
from backend.tests.helpers.practice import att


def test_replay_returns_original(guest, db):  # TC-28.20
    body = att()
    first = guest.post("/api/attempts", json=body)
    again = guest.post("/api/attempts", json=att(client_attempt_id=body["client_attempt_id"], transcript="dog"))
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json() == again.json()
    assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 1
    assert db.execute("SELECT reps FROM review_state").fetchone()[0] == 1
    assert db.execute("SELECT SUM(xp) FROM attempts").fetchone()[0] == 10
