"""All SQL for ``users``. Parameterized only."""
import sqlite3


def _one(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def insert_guest(conn: sqlite3.Connection, user_id: str, now_iso: str) -> None:
    conn.execute(
        "INSERT INTO users (id, kind, cefr_level, created_at, last_seen_at) VALUES (?, 'guest', 'A1', ?, ?)",
        (user_id, now_iso, now_iso),
    )


def get(conn: sqlite3.Connection, user_id: str) -> dict | None:
    return _one(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def get_registered_by_nickname_ci(conn: sqlite3.Connection, nickname_ci: str) -> dict | None:
    return _one(conn.execute(
        "SELECT * FROM users WHERE kind = 'registered' AND nickname_ci = ?", (nickname_ci,)).fetchone())


def set_last_seen(conn: sqlite3.Connection, user_id: str, now_iso: str) -> None:
    conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now_iso, user_id))


def set_gate(conn: sqlite3.Connection, user_id: str, gate_required_at: str | None) -> None:
    conn.execute("UPDATE users SET gate_required_at = ? WHERE id = ?", (gate_required_at, user_id))


def convert_to_registered(conn: sqlite3.Connection, user_id: str, *, nickname: str, password_hash: str,
                          password_params: str, avatar_key: str, birth_year: int, cefr_level: str,
                          guardian_email: str | None, guardian_consent_at: str | None, now_iso: str) -> None:
    conn.execute(
        "UPDATE users SET kind = 'registered', nickname = ?, nickname_ci = ?, password_hash = ?, "
        "password_params = ?, avatar_key = ?, birth_year = ?, cefr_level = ?, guardian_email = ?, "
        "guardian_consent_at = ?, gate_required_at = NULL, registered_at = ?, last_seen_at = ? WHERE id = ?",
        (nickname, nickname.lower(), password_hash, password_params, avatar_key, birth_year, cefr_level,
         guardian_email, guardian_consent_at, now_iso, now_iso, user_id),
    )


_PROGRESS_QUERIES = (
    "SELECT 1 FROM attempts WHERE user_id = ? LIMIT 1",
    "SELECT 1 FROM card_saves WHERE user_id = ? LIMIT 1",
    "SELECT 1 FROM card_progress WHERE user_id = ? LIMIT 1",
    "SELECT 1 FROM reflex_sessions WHERE user_id = ? LIMIT 1",
    "SELECT 1 FROM review_state WHERE user_id = ? LIMIT 1",
    "SELECT 1 FROM cards WHERE owner_id = ? LIMIT 1",
)


def has_progress(conn: sqlite3.Connection, user_id: str) -> bool:
    """True when the user owns any learning data worth keeping (attempts, saves, cards, ...)."""
    return any(conn.execute(q, (user_id,)).fetchone() for q in _PROGRESS_QUERIES)


def delete(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def set_hide_timer(conn: sqlite3.Connection, user_id: str, hide_timer: bool) -> None:
    conn.execute("UPDATE users SET hide_timer = ? WHERE id = ?", (1 if hide_timer else 0, user_id))


def update_profile(conn: sqlite3.Connection, user_id: str, avatar_key: str | None, cefr_level: str | None) -> None:
    conn.execute("UPDATE users SET avatar_key = COALESCE(?, avatar_key), cefr_level = COALESCE(?, cefr_level) "
                 "WHERE id = ?", (avatar_key, cefr_level, user_id))


def set_reflex_level_unlocked(conn: sqlite3.Connection, user_id: str, level: int) -> None:
    conn.execute("UPDATE users SET reflex_level_unlocked = ? WHERE id = ?", (level, user_id))
