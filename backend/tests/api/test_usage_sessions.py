"""TC-3.1 idle starts a new usage session; the write flag drives prior sessions."""


def test_new_session_after_idle(guest, clock, db, write_session):  # TC-3.1
    write_session(guest.user_id)
    clock.advance(minutes=31)
    guest.bootstrap()
    rows = db.execute("SELECT had_write FROM usage_sessions WHERE user_id = ? ORDER BY started_at",
                      (guest.user_id,)).fetchall()
    assert [r[0] for r in rows] == [1, 0]
    write_session(guest.user_id)
    assert [r[0] for r in db.execute("SELECT had_write FROM usage_sessions ORDER BY started_at")] == [1, 1]


def test_activity_is_throttled_and_exact_idle_is_same_session(guest, clock, db):
    start = db.execute("SELECT last_activity_at FROM usage_sessions").fetchone()[0]
    clock.advance(seconds=30)
    guest.post("/api/session/heartbeat")  # under 60 s: no write
    assert db.execute("SELECT last_activity_at FROM usage_sessions").fetchone()[0] == start
    clock.advance(seconds=40)
    guest.post("/api/session/heartbeat")  # 70 s: recorded
    assert db.execute("SELECT last_activity_at FROM usage_sessions").fetchone()[0] != start
    clock.advance(seconds=1800)  # idle exactly 1800 s: same session (only strictly greater starts a new one)
    guest.post("/api/session/heartbeat")
    assert db.execute("SELECT COUNT(*) FROM usage_sessions").fetchone()[0] == 1
    clock.advance(seconds=1801)
    guest.post("/api/session/heartbeat")
    assert db.execute("SELECT COUNT(*) FROM usage_sessions").fetchone()[0] == 2
