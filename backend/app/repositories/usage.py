"""Usage sessions (the second-visit gate) and rate_events (sliding-window limits)."""
import sqlite3


def latest(conn: sqlite3.Connection, user_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM usage_sessions WHERE user_id = ? ORDER BY last_activity_at DESC, started_at DESC LIMIT 1",
        (user_id,)).fetchone()
    return dict(row) if row else None


def insert(conn: sqlite3.Connection, usage_id: str, user_id: str, now_iso: str) -> None:
    conn.execute(
        "INSERT INTO usage_sessions (id, user_id, started_at, last_activity_at, had_write) VALUES (?, ?, ?, ?, 0)",
        (usage_id, user_id, now_iso, now_iso))


def set_activity(conn: sqlite3.Connection, usage_id: str, now_iso: str) -> None:
    conn.execute("UPDATE usage_sessions SET last_activity_at = ? WHERE id = ?", (now_iso, usage_id))


def set_had_write(conn: sqlite3.Connection, usage_id: str) -> None:
    conn.execute("UPDATE usage_sessions SET had_write = 1 WHERE id = ?", (usage_id,))


def count_write_sessions(conn: sqlite3.Connection, user_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM usage_sessions WHERE user_id = ? AND had_write = 1",
                        (user_id,)).fetchone()[0]


def add_rate_event(conn: sqlite3.Connection, bucket: str, key_hash: str, now_iso: str) -> None:
    conn.execute("INSERT INTO rate_events (bucket, key_hash, created_at) VALUES (?, ?, ?)",
                 (bucket, key_hash, now_iso))


def rate_events_since(conn: sqlite3.Connection, bucket: str, key_hash: str, since_iso: str) -> list[str]:
    rows = conn.execute(
        "SELECT created_at FROM rate_events WHERE bucket = ? AND key_hash = ? AND created_at > ?",
        (bucket, key_hash, since_iso)).fetchall()
    return [r[0] for r in rows]
