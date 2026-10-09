"""Device tokens (guests) and login sessions (registered). Only sha256 hashes are stored."""
import sqlite3


def add_device(conn: sqlite3.Connection, token_hash: str, user_id: str, now_iso: str) -> None:
    conn.execute("INSERT INTO device_tokens (token_hash, user_id, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
                 (token_hash, user_id, now_iso, now_iso))


def get_device(conn: sqlite3.Connection, token_hash: str) -> dict | None:
    row = conn.execute("SELECT * FROM device_tokens WHERE token_hash = ?", (token_hash,)).fetchone()
    return dict(row) if row else None


def delete_devices_for_user(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM device_tokens WHERE user_id = ?", (user_id,))


def add_session(conn: sqlite3.Connection, token_hash: str, user_id: str, now_iso: str,
                expires_iso: str, absolute_iso: str) -> None:
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at, absolute_expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (token_hash, user_id, now_iso, now_iso, expires_iso, absolute_iso),
    )


def get_session(conn: sqlite3.Connection, token_hash: str) -> dict | None:
    row = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
    return dict(row) if row else None


def slide_session(conn: sqlite3.Connection, token_hash: str, now_iso: str, expires_iso: str) -> None:
    conn.execute("UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE token_hash = ?",
                 (now_iso, expires_iso, token_hash))


def revoke_session(conn: sqlite3.Connection, token_hash: str, now_iso: str) -> None:
    conn.execute("UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                 (now_iso, token_hash))


def revoke_all_for_user(conn: sqlite3.Connection, user_id: str, now_iso: str) -> None:
    conn.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                 (now_iso, user_id))
