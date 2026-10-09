"""All SQL for the maintenance sweeps and orphan garbage collection. Parameterized only."""
import sqlite3


def delete_idle_guests(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    return conn.execute("DELETE FROM users WHERE kind = 'guest' AND last_seen_at < ?", (cutoff_iso,)).rowcount


def delete_never_wrote_guests(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    return conn.execute(
        "DELETE FROM users WHERE kind = 'guest' AND created_at < ? "
        "AND NOT EXISTS (SELECT 1 FROM usage_sessions s WHERE s.user_id = users.id AND s.had_write = 1) "
        "AND NOT EXISTS (SELECT 1 FROM attempts a WHERE a.user_id = users.id) "
        "AND NOT EXISTS (SELECT 1 FROM cards c WHERE c.owner_id = users.id) "
        "AND NOT EXISTS (SELECT 1 FROM card_saves v WHERE v.user_id = users.id)", (cutoff_iso,)).rowcount


def fail_stale_processing(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    return conn.execute(
        "UPDATE card_contents SET status = 'failed', error = 'stale' WHERE status = 'processing' "
        "AND (processing_started_at IS NULL OR processing_started_at < ?)", (cutoff_iso,)).rowcount


def delete_stale_claims(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    return conn.execute(
        "DELETE FROM upload_claims WHERE created_at < ? AND NOT EXISTS "
        "(SELECT 1 FROM cards c WHERE c.owner_id = upload_claims.user_id "
        "AND c.content_id = upload_claims.content_id)", (cutoff_iso,)).rowcount


def orphan_contents(conn: sqlite3.Connection, claim_cutoff_iso: str) -> list[dict]:
    """Contents with no card, no claim newer than the cutoff and no seed key."""
    rows = conn.execute(
        "SELECT cc.id AS content_id, ia.id AS asset_id, ia.storage_path FROM card_contents cc "
        "JOIN image_assets ia ON ia.id = cc.image_asset_id WHERE cc.seed_key IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM cards c WHERE c.content_id = cc.id) "
        "AND NOT EXISTS (SELECT 1 FROM upload_claims u WHERE u.content_id = cc.id AND u.created_at >= ?)",
        (claim_cutoff_iso,))
    return [dict(r) for r in rows]


def delete_content_and_asset(conn: sqlite3.Connection, content_id: str, asset_id: str) -> None:
    conn.execute("DELETE FROM card_contents WHERE id = ?", (content_id,))
    conn.execute("DELETE FROM image_assets WHERE id = ?", (asset_id,))


def all_storage_paths(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT storage_path FROM image_assets")]


def delete_old_rate_events(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    return conn.execute("DELETE FROM rate_events WHERE created_at < ?", (cutoff_iso,)).rowcount
