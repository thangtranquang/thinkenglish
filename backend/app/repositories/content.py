"""SQL for image assets, card contents, labels, sentences and upload claims."""
from __future__ import annotations

import json
import sqlite3


def _one(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def asset_by_source(conn: sqlite3.Connection, source_sha: str) -> dict | None:
    return _one(conn.execute("SELECT * FROM image_assets WHERE source_sha256 = ?", (source_sha,)).fetchone())


def insert_asset(conn: sqlite3.Connection, asset_id: str, source_sha: str, clean_sha: str, storage_path: str,
                 width: int, height: int, user_id: str, now: str) -> None:
    conn.execute(
        "INSERT INTO image_assets (id, source_sha256, clean_sha256, storage_path, width, height, "
        "first_uploaded_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, source_sha, clean_sha, storage_path, width, height, user_id, now))


def insert_content(conn: sqlite3.Connection, content_id: str, asset_id: str, now: str) -> None:
    conn.execute(
        "INSERT INTO card_contents (id, image_asset_id, status, ai_calls, processing_started_at, created_at) "
        "VALUES (?, ?, 'processing', 0, ?, ?)", (content_id, asset_id, now, now))


def content_by_asset(conn: sqlite3.Connection, asset_id: str) -> dict | None:
    return _one(conn.execute("SELECT * FROM card_contents WHERE image_asset_id = ?", (asset_id,)).fetchone())


def get_content(conn: sqlite3.Connection, content_id: str) -> dict | None:
    return _one(conn.execute(
        "SELECT cc.*, ia.storage_path FROM card_contents cc JOIN image_assets ia ON ia.id = cc.image_asset_id "
        "WHERE cc.id = ?", (content_id,)).fetchone())


def restart_processing(conn: sqlite3.Connection, content_id: str, now: str) -> None:
    conn.execute("UPDATE card_contents SET status = 'processing', processing_started_at = ?, error = NULL "
                 "WHERE id = ?", (now, content_id))


def bump_ai_calls(conn: sqlite3.Connection, content_id: str) -> None:
    conn.execute("UPDATE card_contents SET ai_calls = ai_calls + 1 WHERE id = ?", (content_id,))


def mark_failed(conn: sqlite3.Connection, content_id: str, error: str) -> None:
    conn.execute("UPDATE card_contents SET status = 'failed', error = ? WHERE id = ? AND status != 'ready'",
                 (error, content_id))


def expire_if_stale(conn: sqlite3.Connection, content_id: str, cutoff: str) -> None:
    conn.execute("UPDATE card_contents SET status = 'failed', error = 'stale' "
                 "WHERE id = ? AND status = 'processing' AND processing_started_at < ?", (content_id, cutoff))


def save_result(conn: sqlite3.Connection, content_id: str, *, model: str, topic: str, topic_tags: list[str],
                cefr_level: str, safety: dict, moderation_status: str) -> None:
    conn.execute(
        "UPDATE card_contents SET status = 'ready', error = NULL, model = ?, topic = ?, topic_tags = ?, "
        "cefr_level = ?, safety = ?, moderation_status = ? WHERE id = ?",
        (model, topic, json.dumps(topic_tags, ensure_ascii=False), cefr_level,
         json.dumps(safety), moderation_status, content_id))


def clear_children(conn: sqlite3.Connection, content_id: str) -> None:
    conn.execute("DELETE FROM card_labels WHERE content_id = ?", (content_id,))
    conn.execute("DELETE FROM card_sentences WHERE content_id = ?", (content_id,))


def insert_label(conn: sqlite3.Connection, label_id: str, content_id: str, position: int, word: str,
                 ipa: str, vi: str, accepted: list[str], cefr: str, confidence: float, x: float, y: float,
                 audio_file: str | None) -> None:
    conn.execute(
        "INSERT INTO card_labels (id, content_id, position, word, ipa, vi_meaning, accepted_answers, "
        "cefr_level, confidence, x, y, audio_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (label_id, content_id, position, word, ipa, vi, json.dumps(accepted, ensure_ascii=False),
         cefr, confidence, x, y, audio_file))


def insert_sentence(conn: sqlite3.Connection, sentence_id: str, content_id: str, kind: str, position: int,
                    en: str, vi: str, audio_file: str | None) -> None:
    conn.execute("INSERT INTO card_sentences (id, content_id, kind, position, en, vi, audio_file) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)", (sentence_id, content_id, kind, position, en, vi, audio_file))


def labels_for(conn: sqlite3.Connection, content_ids: list[str]) -> dict[str, list[dict]]:
    """Labels grouped by content id in position order (one query; ids passed as a JSON parameter)."""
    out: dict[str, list[dict]] = {cid: [] for cid in content_ids}
    rows = conn.execute(
        "SELECT * FROM card_labels WHERE content_id IN (SELECT value FROM json_each(?)) "
        "ORDER BY content_id, position", (json.dumps(content_ids),)).fetchall()
    for row in rows:
        out[row["content_id"]].append(dict(row))
    return out


def sentences_for(conn: sqlite3.Connection, content_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM card_sentences WHERE content_id = ? "
                        "ORDER BY CASE kind WHEN 'description' THEN 0 ELSE 1 END, position", (content_id,))
    return [dict(r) for r in rows]


def claim_exists(conn: sqlite3.Connection, user_id: str, content_id: str) -> bool:
    return conn.execute("SELECT 1 FROM upload_claims WHERE user_id = ? AND content_id = ?",
                        (user_id, content_id)).fetchone() is not None


def insert_claim(conn: sqlite3.Connection, user_id: str, content_id: str, now: str) -> None:
    conn.execute("INSERT OR IGNORE INTO upload_claims (user_id, content_id, created_at) VALUES (?, ?, ?)",
                 (user_id, content_id, now))
