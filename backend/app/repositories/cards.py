"""SQL for cards, saves, listing and visibility. All queries are parameterized.

Visibility mirrors ``policy.can_view``: system-owned, own, or (public AND approved).
"""
from __future__ import annotations

import sqlite3

_BASE = (
    "FROM cards c JOIN card_contents cc ON cc.id = c.content_id "
    "JOIN image_assets ia ON ia.id = cc.image_asset_id JOIN users u ON u.id = c.owner_id "
)
_SELECT = (
    "SELECT c.id, c.owner_id, c.content_id, c.title, c.visibility, c.label_overrides, c.created_at, "
    "cc.topic, cc.cefr_level, cc.safety, cc.moderation_status, ia.storage_path, "
    "u.nickname AS owner_nickname, u.kind AS owner_kind, "
    "EXISTS (SELECT 1 FROM card_saves s WHERE s.card_id = c.id AND s.user_id = :me) AS saved "
)
_VISIBLE = (
    "(u.kind = 'system' OR c.owner_id = :me OR (c.visibility = 'public' AND cc.moderation_status = 'approved'))"
)
_EXPLORE = "(u.kind = 'system' OR (c.visibility = 'public' AND cc.moderation_status = 'approved'))"
_SCOPE = {
    "explore": _EXPLORE,
    "mine": "c.owner_id = :me",
    "saved": "EXISTS (SELECT 1 FROM card_saves s2 WHERE s2.card_id = c.id AND s2.user_id = :me) AND " + _VISIBLE,
    "due": ("EXISTS (SELECT 1 FROM review_state rs WHERE rs.card_id = c.id AND rs.user_id = :me "
            "AND rs.due_at <= :now) AND " + _VISIBLE),
}
_GET_SQL = _SELECT + _BASE + "WHERE c.id = :id"
_FILTERS = (
    " AND (:topic IS NULL OR lower(cc.topic) = lower(:topic))"
    " AND (:cefr IS NULL OR cc.cefr_level = :cefr)"
    " AND (:q IS NULL OR lower(c.title) LIKE :q ESCAPE '\\' OR EXISTS ("
    "SELECT 1 FROM card_labels l WHERE l.content_id = c.content_id AND lower(l.word) LIKE :q ESCAPE '\\'))"
    " ORDER BY c.created_at DESC, c.id DESC LIMIT :lim OFFSET :off"
)
_LIST_SQL = {k: _SELECT + _BASE + "WHERE " + v + _FILTERS for k, v in _SCOPE.items()}
_TOPICS_SQL = (
    "SELECT cc.topic AS name, COUNT(*) AS count " + _BASE + "WHERE cc.topic IS NOT NULL AND " + _EXPLORE
    + " GROUP BY cc.topic ORDER BY count DESC, cc.topic"
)
_LIKE_ESC = {"\\": "\\\\", "%": "\\%", "_": "\\_"}


def get_card(conn: sqlite3.Connection, card_id: str, viewer_id: str) -> dict | None:
    row = conn.execute(_GET_SQL, {"me": viewer_id, "id": card_id}).fetchone()
    return dict(row) if row else None


def find_by_owner_content(conn: sqlite3.Connection, owner_id: str, content_id: str) -> str | None:
    row = conn.execute("SELECT id FROM cards WHERE owner_id = ? AND content_id = ?",
                       (owner_id, content_id)).fetchone()
    return row["id"] if row else None


def insert_card(conn: sqlite3.Connection, card_id: str, owner_id: str, content_id: str, title: str,
                overrides_json: str | None, now: str) -> bool:
    """False when the (owner, content) card already exists (idempotent create)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO cards (id, owner_id, content_id, title, visibility, label_overrides, created_at) "
        "VALUES (?, ?, ?, ?, 'private', ?, ?)", (card_id, owner_id, content_id, title, overrides_json, now))
    return cur.rowcount == 1


def list_cards(conn: sqlite3.Connection, viewer_id: str, scope: str, topic: str | None, cefr: str | None,
               q: str | None, offset: int, limit: int, now_iso: str) -> list[dict]:
    """Up to ``limit`` rows (callers ask for limit+1 to learn ``has_more``)."""
    like = None
    if q:
        like = "%" + "".join(_LIKE_ESC.get(ch, ch) for ch in q.lower()) + "%"
    params = {"me": viewer_id, "now": now_iso, "topic": topic, "cefr": cefr, "off": offset, "lim": limit,
              "q": like}
    sql = _LIST_SQL[scope]
    return [dict(r) for r in conn.execute(sql, params)]


def topic_counts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(_TOPICS_SQL)
    return [dict(r) for r in rows]


def add_save(conn: sqlite3.Connection, user_id: str, card_id: str, now: str) -> None:
    conn.execute("INSERT OR IGNORE INTO card_saves (user_id, card_id, saved_at) VALUES (?, ?, ?)",
                 (user_id, card_id, now))


def remove_save(conn: sqlite3.Connection, user_id: str, card_id: str) -> None:
    conn.execute("DELETE FROM card_saves WHERE user_id = ? AND card_id = ?", (user_id, card_id))


def remove_other_saves(conn: sqlite3.Connection, card_id: str, owner_id: str) -> None:
    conn.execute("DELETE FROM card_saves WHERE card_id = ? AND user_id != ?", (card_id, owner_id))


def set_visibility(conn: sqlite3.Connection, card_id: str, visibility: str, published_at: str | None) -> None:
    conn.execute("UPDATE cards SET visibility = ?, published_at = ? WHERE id = ?",
                 (visibility, published_at, card_id))


def delete_card(conn: sqlite3.Connection, card_id: str) -> None:
    conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
