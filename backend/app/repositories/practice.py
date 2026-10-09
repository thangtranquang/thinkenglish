"""All SQL for attempts, review_state, card_progress and reflex_sessions. Parameterized only."""
import json
import sqlite3


def _one(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


# --- lookups ---------------------------------------------------------------------------------

def card_for_view(conn: sqlite3.Connection, card_id: str) -> dict | None:
    return _one(conn.execute(
        "SELECT c.id, c.owner_id, c.content_id, c.visibility, c.label_overrides, cc.moderation_status, "
        "u.kind AS owner_kind FROM cards c JOIN card_contents cc ON cc.id = c.content_id "
        "JOIN users u ON u.id = c.owner_id WHERE c.id = ?", (card_id,)).fetchone())


def card_overrides(conn: sqlite3.Connection, card_ids: list[str]) -> dict[str, str | None]:
    """card_id -> label_overrides JSON (None when the card keeps the AI labels as they are)."""
    out: dict[str, str | None] = {}
    for card_id in set(card_ids):
        row = conn.execute("SELECT label_overrides FROM cards WHERE id = ?", (card_id,)).fetchone()
        out[card_id] = row[0] if row else None
    return out


def label_item(conn: sqlite3.Connection, content_id: str, item_id: str) -> dict | None:
    return _one(conn.execute(
        "SELECT word, accepted_answers FROM card_labels WHERE id = ? AND content_id = ?",
        (item_id, content_id)).fetchone())


def sentence_item(conn: sqlite3.Connection, content_id: str, item_id: str, kind: str) -> dict | None:
    return _one(conn.execute(
        "SELECT en FROM card_sentences WHERE id = ? AND content_id = ? AND kind = ?",
        (item_id, content_id, kind)).fetchone())


def level_item_ids(conn: sqlite3.Connection, content_id: str, item_type: str) -> list[str]:
    if item_type == "label":
        rows = conn.execute("SELECT id FROM card_labels WHERE content_id = ? ORDER BY position, id",
                            (content_id,))
    else:
        kind = "description" if item_type == "sentence" else "story"
        rows = conn.execute("SELECT id FROM card_sentences WHERE content_id = ? AND kind = ? "
                            "ORDER BY position, id", (content_id, kind))
    return [r[0] for r in rows]


# --- attempts --------------------------------------------------------------------------------

def get_attempt(conn: sqlite3.Connection, user_id: str, client_attempt_id: str) -> dict | None:
    return _one(conn.execute("SELECT * FROM attempts WHERE user_id = ? AND client_attempt_id = ?",
                             (user_id, client_attempt_id)).fetchone())


def insert_attempt(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        "INSERT INTO attempts (id, client_attempt_id, user_id, card_id, item_type, item_id, mode, "
        "reflex_level, reflex_session_id, transcript, accuracy, pronunciation, reflex_ms, reflex_score, "
        "xp, created_at) VALUES (:id, :client_attempt_id, :user_id, :card_id, :item_type, :item_id, :mode, "
        ":reflex_level, :reflex_session_id, :transcript, :accuracy, :pronunciation, :reflex_ms, "
        ":reflex_score, :xp, :created_at)", row)


def practice_scores(conn: sqlite3.Connection, user_id: str, card_id: str, item_type: str) -> dict[str, int]:
    """Latest practice (non-reflex) score per item, oldest first so later attempts win."""
    latest: dict[str, int] = {}
    for item_id, score in conn.execute(
            "SELECT item_id, COALESCE(reflex_score, accuracy, 0) FROM attempts "
            "WHERE user_id = ? AND card_id = ? AND item_type = ? AND mode != 'reflex' ORDER BY rowid",
            (user_id, card_id, item_type)):
        latest[item_id] = score
    return latest


# --- review_state ----------------------------------------------------------------------------

def get_review(conn: sqlite3.Connection, user_id: str, item_type: str, item_id: str) -> dict | None:
    return _one(conn.execute("SELECT * FROM review_state WHERE user_id = ? AND item_type = ? AND item_id = ?",
                             (user_id, item_type, item_id)).fetchone())


def upsert_review(conn: sqlite3.Connection, user_id: str, item_type: str, item_id: str, card_id: str,
                  ease: float, interval_days: int, reps: int, lapses: int, due_at: str, now_iso: str) -> None:
    conn.execute(
        "INSERT INTO review_state (user_id, item_type, item_id, card_id, ease, interval_days, reps, lapses, "
        "due_at, last_reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET ease = excluded.ease, "
        "interval_days = excluded.interval_days, reps = excluded.reps, lapses = excluded.lapses, "
        "due_at = excluded.due_at, last_reviewed_at = excluded.last_reviewed_at",
        (user_id, item_type, item_id, card_id, ease, interval_days, reps, lapses, due_at, now_iso))


# --- card_progress ---------------------------------------------------------------------------

def get_progress(conn: sqlite3.Connection, user_id: str, card_id: str, level: int) -> dict | None:
    return _one(conn.execute("SELECT * FROM card_progress WHERE user_id = ? AND card_id = ? AND level = ?",
                             (user_id, card_id, level)).fetchone())


def upsert_progress(conn: sqlite3.Connection, user_id: str, card_id: str, level: int, best_score: int,
                    unlocked: int, now_iso: str) -> None:
    conn.execute(
        "INSERT INTO card_progress (user_id, card_id, level, best_score, unlocked, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, card_id, level) DO UPDATE SET "
        "best_score = MAX(card_progress.best_score, excluded.best_score), "
        "unlocked = MAX(card_progress.unlocked, excluded.unlocked), updated_at = excluded.updated_at",
        (user_id, card_id, level, best_score, unlocked, now_iso))


def unlocked_levels(conn: sqlite3.Connection, user_id: str, card_id: str) -> list[int]:
    rows = conn.execute("SELECT level FROM card_progress WHERE user_id = ? AND card_id = ? AND unlocked = 1",
                        (user_id, card_id))
    return sorted({1, *(r[0] for r in rows)})


# --- profile stats ---------------------------------------------------------------------------

def user_xp(conn: sqlite3.Connection, user_id: str) -> int:
    return conn.execute("SELECT COALESCE(SUM(xp), 0) FROM attempts WHERE user_id = ?", (user_id,)).fetchone()[0]


def attempt_times(conn: sqlite3.Connection, user_id: str) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT created_at FROM attempts WHERE user_id = ?", (user_id,))]


def card_scores(conn: sqlite3.Connection, user_id: str,
                card_ids: list[str] | None = None) -> dict[str, list[int]]:
    """Per card: combined scores, oldest first (optionally only for the given cards)."""
    wanted = None if card_ids is None else set(card_ids)
    out: dict[str, list[int]] = {}
    for card_id, score in conn.execute(
            "SELECT card_id, COALESCE(reflex_score, accuracy, 0) FROM attempts WHERE user_id = ? ORDER BY rowid",
            (user_id,)):
        if wanted is None or card_id in wanted:
            out.setdefault(card_id, []).append(score)
    return out


# --- reflex ----------------------------------------------------------------------------------

def due_label_items(conn: sqlite3.Connection, user_id: str, now_iso: str, limit: int) -> list[dict]:
    rows = conn.execute(
        "SELECT r.card_id, l.id AS item_id, l.word, l.ipa, l.audio_file FROM review_state r "
        "JOIN cards c ON c.id = r.card_id JOIN card_labels l ON l.id = r.item_id AND l.content_id = c.content_id "
        "WHERE r.user_id = ? AND r.item_type = 'label' AND r.due_at <= ? AND "
        "(c.owner_id = ? OR c.owner_id IN (SELECT id FROM users WHERE kind = 'system') "
        "OR c.id IN (SELECT card_id FROM card_saves WHERE user_id = ?)) "
        "ORDER BY r.due_at, l.id LIMIT ?", (user_id, now_iso, user_id, user_id, limit))
    return [dict(r) for r in rows]


def new_label_items(conn: sqlite3.Connection, user_id: str, limit: int) -> list[dict]:
    rows = conn.execute(
        "SELECT c.id AS card_id, l.id AS item_id, l.word, l.ipa, l.audio_file FROM cards c "
        "JOIN card_labels l ON l.content_id = c.content_id "
        "WHERE (c.owner_id = ? OR c.owner_id IN (SELECT id FROM users WHERE kind = 'system') "
        "OR c.id IN (SELECT card_id FROM card_saves WHERE user_id = ?)) "
        "AND NOT EXISTS (SELECT 1 FROM review_state r WHERE r.user_id = ? AND r.item_type = 'label' "
        "AND r.item_id = l.id) ORDER BY c.id, l.position LIMIT ?", (user_id, user_id, user_id, limit))
    return [dict(r) for r in rows]


def insert_session(conn: sqlite3.Connection, session_id: str, user_id: str, level: int, rounds: list[dict],
                   now_iso: str) -> None:
    conn.execute("INSERT INTO reflex_sessions (id, user_id, level, rounds, started_at) VALUES (?, ?, ?, ?, ?)",
                 (session_id, user_id, level, json.dumps(rounds, ensure_ascii=False), now_iso))


def get_session(conn: sqlite3.Connection, session_id: str) -> dict | None:
    return _one(conn.execute("SELECT * FROM reflex_sessions WHERE id = ?", (session_id,)).fetchone())


def session_summary(conn: sqlite3.Connection, session_id: str) -> tuple[int, float]:
    """(answered rounds, mean reflex_score) over the attempts linked to the session."""
    n, mean = conn.execute("SELECT COUNT(*), COALESCE(AVG(COALESCE(reflex_score, 0)), 0) FROM attempts "
                           "WHERE reflex_session_id = ?", (session_id,)).fetchone()
    return n, float(mean)


def complete_session(conn: sqlite3.Connection, session_id: str, score: int, now_iso: str) -> None:
    conn.execute("UPDATE reflex_sessions SET completed_at = ?, score = ? WHERE id = ?", (now_iso, score, session_id))
