"""SQL for the idempotent seed. Every statement is an upsert keyed by a stable id."""
import json
import sqlite3


def upsert_system_user(conn: sqlite3.Connection, user_id: str, nickname: str, now: str) -> None:
    conn.execute(
        "INSERT INTO users (id, kind, nickname, role, created_at, last_seen_at) "
        "VALUES (?, 'system', ?, 'system', ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET nickname = excluded.nickname",
        (user_id, nickname, now, now),
    )


def upsert_image(conn: sqlite3.Connection, image_id: str, sha256: str, storage_path: str,
                 width: int, height: int, now: str) -> None:
    conn.execute(
        "INSERT INTO image_assets (id, source_sha256, clean_sha256, storage_path, width, height, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET source_sha256 = excluded.source_sha256, "
        "clean_sha256 = excluded.clean_sha256, storage_path = excluded.storage_path, "
        "width = excluded.width, height = excluded.height",
        (image_id, sha256, sha256, storage_path, width, height, now),
    )


def upsert_content(conn: sqlite3.Connection, content_id: str, image_id: str, seed_key: str,
                   topic: str, cefr: str, now: str) -> None:
    conn.execute(
        "INSERT INTO card_contents (id, image_asset_id, seed_key, status, model, prompt_version, "
        "ai_calls, topic, topic_tags, cefr_level, safety, moderation_status, created_at) "
        "VALUES (?, ?, ?, 'ready', 'seed', 'seed', 0, ?, ?, ?, ?, 'approved', ?) "
        "ON CONFLICT(id) DO UPDATE SET image_asset_id = excluded.image_asset_id, "
        "seed_key = excluded.seed_key, topic = excluded.topic, topic_tags = excluded.topic_tags, "
        "cefr_level = excluded.cefr_level, "
        "status = 'ready', moderation_status = 'approved'",
        (content_id, image_id, seed_key, topic, json.dumps([topic], ensure_ascii=False), cefr,
         json.dumps({"faces": False, "personal_info": False, "unsuitable": False}), now),
    )


def upsert_label(conn: sqlite3.Connection, label_id: str, content_id: str, position: int,
                 word: str, ipa: str, vi_meaning: str, accepted: list[str],
                 x: float, y: float, box: tuple[float, float, float, float] | None, cefr: str,
                 audio_file: str) -> None:
    if box is None:
        half = 0.1
        box = (max(0.0, x - half), max(0.0, y - half), min(1.0, x + half), min(1.0, y + half))
    conn.execute(
        "INSERT INTO card_labels (id, content_id, position, word, ipa, vi_meaning, accepted_answers, "
        "cefr_level, confidence, x, y, box_x1, box_y1, box_x2, box_y2, audio_file) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET position = excluded.position, word = excluded.word, "
        "ipa = excluded.ipa, vi_meaning = excluded.vi_meaning, "
        "accepted_answers = excluded.accepted_answers, cefr_level = excluded.cefr_level, x = excluded.x, y = excluded.y, "
        "box_x1 = excluded.box_x1, box_y1 = excluded.box_y1, box_x2 = excluded.box_x2, "
        "box_y2 = excluded.box_y2, audio_file = excluded.audio_file",
        (label_id, content_id, position, word, ipa, vi_meaning,
         json.dumps(accepted, ensure_ascii=False), cefr, x, y, *box, audio_file),
    )


def upsert_sentence(conn: sqlite3.Connection, sentence_id: str, content_id: str, kind: str,
                    position: int, en: str, vi: str, audio_file: str) -> None:
    conn.execute(
        "INSERT INTO card_sentences (id, content_id, kind, position, en, vi, audio_file) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET kind = excluded.kind, position = excluded.position, "
        "en = excluded.en, vi = excluded.vi, audio_file = excluded.audio_file",
        (sentence_id, content_id, kind, position, en, vi, audio_file),
    )


def upsert_card(conn: sqlite3.Connection, card_id: str, owner_id: str, content_id: str,
                title: str, now: str) -> None:
    conn.execute(
        "INSERT INTO cards (id, owner_id, content_id, title, visibility, published_at, created_at) "
        "VALUES (?, ?, ?, ?, 'public', ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET title = excluded.title, visibility = 'public'",
        (card_id, owner_id, content_id, title, now, now),
    )
